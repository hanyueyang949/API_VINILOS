"""Comprobaciones HTTP contra Uvicorn real con SQLite temporal y reporte Markdown."""

import argparse
from copy import deepcopy
import json
import os
import platform
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parent.parent


def serve(database, port):
    # Solo el proceso de prueba se conecta a esta base: no tocar vinilos.db.
    sys.path.insert(0, str(ROOT))
    import uvicorn
    os.environ["DATABASE_URL"] = f"sqlite:///{database}"
    import main
    try:
        uvicorn.run(main.app, host="127.0.0.1", port=port, log_level="warning")
    finally:
        main.engine.dispose()


@contextmanager
def server(database):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    with tempfile.TemporaryFile(mode="w+") as log:
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--serve", "--database", str(database), "--port", str(port)],
            cwd=ROOT, stdout=log, stderr=log,
        )
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=5) as client:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        log.seek(0)
                        raise RuntimeError(f"El servidor no arrancó: {log.read()}")
                    try:
                        if client.get("/openapi.json").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(0.05)
                else:
                    raise RuntimeError("Tiempo de espera de arranque agotado.")
                yield client, process.pid
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


class Checks:
    def __init__(self):
        self.results = []
        self.process_ids = []

    def request(self, client, name, method, path, status, body=None, data=None):
        response = client.request(method, path, json=data)
        try:
            actual = response.json()
        except ValueError:
            actual = response.text
        # Los errores 422 se comparan por detail y conservan los errors obtenidos.
        matches = actual == body
        if status == 422 and isinstance(actual, dict):
            matches = actual.get("detail") == body["detail"] and bool(actual.get("errors"))
        self.results.append({
            "caso": name, "peticion": f"{method} {path}", "entrada": deepcopy(data),
            "esperado": {"status": status, "body": deepcopy(body)},
            "obtenido": {"status": response.status_code, "body": actual},
            "correcto": response.status_code == status and matches,
        })
        return actual

    def run(self, database):
        integrity = {"detail": "No se pudo guardar: hay datos duplicados o referencias no válidas."}
        invalid = {"detail": "Datos de entrada no válidos."}
        missing = {"detail": "Recurso no encontrado."}
        blocked = {"detail": "No se puede eliminar el recurso porque tiene vinilos asociados."}
        deleted = {"detail": "Recurso eliminado correctamente."}
        artista = {"id_artista": 1, "nombre": "Artista HTTP", "descripcion": "Biografía"}
        other = {"id_artista": 2, "nombre": "Otro artista", "descripcion": None}
        rock = {"id_genero": 1, "tipo": "Rock HTTP"}
        jazz = {"id_genero": 2, "tipo": "Jazz HTTP"}
        data = {
            "titulo": "Disco HTTP", "año": 2000, "precio": "12.50",
            "descripcion": "Prueba HTTP", "artista_id": 1, "genero_id": 1,
        }
        first = dict(data, id_vinilo=1)
        def detail(vinilo):
            artist = {1: artista, 2: other}[vinilo["artista_id"]]
            genre = {1: rock, 2: jazz}[vinilo["genero_id"]]
            return dict(vinilo,
                artista={"id_artista": artist["id_artista"], "nombre": artist["nombre"]},
                genero={"id_genero": genre["id_genero"], "tipo": genre["tipo"]},
            )
        second_data = dict(data, titulo="Segundo disco")
        second = dict(second_data, id_vinilo=2)
        with server(database) as (client, first_pid):
            self.process_ids.append(first_pid)
            q = lambda *args, **kwargs: self.request(client, *args, **kwargs)
            for resource in ("artistas", "generos", "vinilos"):
                q(f"Catálogo vacío de {resource}", "GET", f"/{resource}", 200, [])
            q("Alta de artista", "POST", "/artistas", 201, artista, {"nombre": artista["nombre"], "descripcion": artista["descripcion"]})
            q("Alta de segundo artista", "POST", "/artistas", 201, other, {"nombre": other["nombre"]})
            for genero in (rock, jazz, {"id_genero": 3, "tipo": "Sin discos"}):
                q("Alta de género", "POST", "/generos", 201, genero, {"tipo": genero["tipo"]})
            q("Nombre duplicado", "POST", "/artistas", 400, integrity, {"nombre": artista["nombre"]})
            q("Tipo duplicado", "POST", "/generos", 400, integrity, {"tipo": rock["tipo"]})
            q("Alta de vinilo con ambas relaciones", "POST", "/vinilos", 201, first, data)
            q("Alta de otro vinilo", "POST", "/vinilos", 201, second, second_data)
            q("Consulta por ID con artista y género", "GET", "/vinilos/1", 200, detail(first))
            q("Listado de artistas", "GET", "/artistas", 200, [artista, other])
            q("Ficha de artista con vinilos", "GET", "/artistas/1", 200, dict(artista, vinilos=[first, second]))
            q("Ficha de artista sin vinilos", "GET", "/artistas/2", 200, dict(other, vinilos=[]))
            q("Género sin vinilos", "GET", "/vinilos?genero_id=3", 200, [])
            q("Filtro con coincidencias", "GET", "/vinilos?genero_id=1", 200, [first, second])
            q("Filtro de género inexistente", "GET", "/vinilos?genero_id=9999", 200, [])
            for value in ("", "abc", "0", "-1", "1.5", "1.0"):
                q("Filtro inválido", "GET", f"/vinilos?genero_id={value}", 422, invalid)
            for resource, bad in (
                ("artistas", {"nombre": "x" * 101}),
                ("generos", {"tipo": 123}),
                ("vinilos", dict(data, precio="1.001")),
                ("vinilos", {"titulo": "Sin relaciones"}),
                ("artistas", {}), ("artistas", {"nombre": None}),
                ("artistas", {"nombre": "   "}), ("artistas", {"nombre": ""}),
                ("generos", {}), ("generos", {"tipo": None}),
                ("generos", {"tipo": "   "}), ("generos", {"tipo": ""}),
                ("vinilos", {"artista_id": 1, "genero_id": 1}),
                ("vinilos", dict(data, titulo=None)),
                ("vinilos", dict(data, titulo="   ")),
                ("vinilos", dict(data, titulo="")),
                ("vinilos", dict(data, precio="-0.01")),
            ):
                for method, url in (("POST", f"/{resource}"), ("PUT", f"/{resource}/1")):
                    q("Entrada inválida", method, url, 422, invalid, bad)
            for resource, payload in (("artistas", {"nombre": "X"}), ("generos", {"tipo": "X"}), ("vinilos", data)):
                for method, payload in (("GET", None), ("PUT", payload), ("DELETE", None)):
                    q("ID inexistente", method, f"/{resource}/9999", 404, missing, payload)
            for field in ("artista_id", "genero_id"):
                for method, url in (("POST", "/vinilos"), ("PUT", "/vinilos/1")):
                    q("Relación inexistente", method, url, 400, integrity, dict(data, **{field: 9999}))
            q("Vinilo duplicado", "POST", "/vinilos", 400, integrity, dict(data, genero_id=2))
            q("Edición a vinilo duplicado", "PUT", "/vinilos/2", 400, integrity, dict(data, genero_id=2))
            q("Renombrar artista a duplicado", "PUT", "/artistas/1", 400, integrity, {"nombre": other["nombre"]})
            q("Renombrar género a duplicado", "PUT", "/generos/1", 400, integrity, {"tipo": jazz["tipo"]})
            q("Rollback tras errores", "GET", "/vinilos", 200, [first, second])
            artista.update(nombre="Artista editado", descripcion="Biografía editada")
            q("Editar artista", "PUT", "/artistas/1", 200, artista, {"nombre": artista["nombre"], "descripcion": artista["descripcion"]})
            rock["tipo"] = "Rock editado"
            q("Renombrar género", "PUT", "/generos/1", 200, rock, {"tipo": rock["tipo"]})
            q("Asociaciones conservadas", "GET", "/artistas/1", 200, dict(artista, vinilos=[first, second]))
            for resource in ("artistas", "generos"):
                q("Borrado bloqueado", "DELETE", f"/{resource}/1", 400, blocked)
            data.update(titulo="Disco editado", **{"año": 2026}, precio="25.75", descripcion="Edición modificada", artista_id=2, genero_id=2)
            first = dict(data, id_vinilo=1)
            q("Editar todos los datos y relaciones", "PUT", "/vinilos/1", 200, first, data)
            q("Ficha tras editar", "GET", "/vinilos/1", 200, detail(first))
            q("Catálogo tras editar", "GET", "/vinilos", 200, [first, second])
            q("Filtro anterior tras reasignación", "GET", "/vinilos?genero_id=1", 200, [second])
            q("Filtro nuevo tras reasignación", "GET", "/vinilos?genero_id=2", 200, [first])

        # El proceso anterior ha terminado. Arrancar otro con el mismo archivo.
        with server(database) as (client, second_pid):
            self.process_ids.append(second_pid)
            if first_pid == second_pid:
                raise RuntimeError("No se pudo verificar el cambio de proceso.")
            q = lambda *args, **kwargs: self.request(client, *args, **kwargs)
            q("Persistencia: catálogo tras reiniciar Uvicorn", "GET", "/vinilos", 200, [first, second])
            q("Persistencia: artista editado", "GET", "/artistas/1", 200, dict(artista, vinilos=[second]))
            q("Persistencia: género renombrado", "GET", "/generos/1", 200, rock)
            q("Persistencia: nuevas relaciones", "GET", "/artistas/2", 200, dict(other, vinilos=[first]))
            q("Persistencia: filtro", "GET", "/vinilos?genero_id=2", 200, [first])
            q("Persistencia: ficha con relaciones", "GET", "/vinilos/1", 200, detail(first))
            q("FK activas tras reiniciar", "DELETE", "/generos/2", 400, blocked)
            q("Borrar un vinilo", "DELETE", "/vinilos/1", 200, deleted)
            q("Vinilo eliminado no existe", "GET", "/vinilos/1", 404, missing)
            q("Segundo borrado de vinilo", "DELETE", "/vinilos/1", 404, missing)
            q("Borrado no afecta al resto del catálogo", "GET", "/vinilos", 200, [second])
            q("Género conservado", "GET", "/generos/2", 200, jazz)
            q("Artista conservado", "GET", "/artistas/2", 200, dict(other, vinilos=[]))
            q("Borrar artista sin vinilos", "DELETE", "/artistas/2", 200, deleted)
            q("Borrar género sin vinilos", "DELETE", "/generos/2", 200, deleted)
            q("Artista eliminado", "GET", "/artistas/2", 404, missing)
            q("Género eliminado", "GET", "/generos/2", 404, missing)
            q("Otro artista sigue protegido", "DELETE", "/artistas/1", 400, blocked)
            q("Precio cero permitido", "PUT", "/vinilos/2", 200,
              dict(second, precio="0.00"), dict(second_data, precio="0"))
            q("Precio nulo permitido", "PUT", "/vinilos/2", 200,
              dict(second, precio=None), dict(second_data, precio=None))
            without_price = dict(second_data)
            del without_price["precio"]
            q("Precio omitido permitido", "PUT", "/vinilos/2", 200,
              dict(second, precio=None), without_price)

    def report(self, path):
        def compact(value):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("|", "&#124;")

        passed = sum(result["correcto"] for result in self.results)
        lines = [
            "# Registro de comprobación HTTP de la API", "",
            f"Ejecución UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}", "",
            f"Resultado: **{passed}/{len(self.results)} casos correctos**.", "",
            f"Entorno: Python {platform.python_version()}, FastAPI {version('fastapi')}, "
            f"SQLAlchemy {version('SQLAlchemy')}, Uvicorn {version('uvicorn')}, HTTPX {version('httpx')}.", "",
            "Herramienta: `python scripts/check_api.py`. Peticiones HTTP reales con HTTPX a "
            "Uvicorn en puerto local libre; SQLite temporal, sin modificar `vinilos.db`.", "",
            "Persistencia: se detiene el primer proceso, se espera su salida y se arranca otro "
            "contra el mismo archivo SQLite. Se verifican datos, relaciones y FK después del reinicio.", "",
            f"PIDs de los dos procesos verificados: `{self.process_ids}`.", "",
            "En 422 se exige `detail` y una lista `errors` no vacía; los tipos concretos se registran en obtenido. "
            "Los demás cuerpos se comparan completos. Entradas completas y resultados también en el JSON adjunto.", "",
            f"[Registro JSON completo]({path.with_suffix('.json').name}).", "",
            "| # | Caso / petición | Esperado (HTTP y JSON) | Obtenido (HTTP y JSON) | Resultado |",
            "| --- | --- | --- | --- | --- |",
        ]
        for index, result in enumerate(self.results, 1):
            lines.append(
                f"| {index} | {result['caso']} · `{result['peticion']}` | "
                f"`{compact(result['esperado'])}` | `{compact(result['obtenido'])}` | "
                f"{'OK' if result['correcto'] else 'FALLO'} |"
            )
        lines.extend(["", "## Incidencias y recomprobación", ""])
        if passed == len(self.results):
            lines.append("No se detectaron fallos en esta ejecución. El informe utiliza copias "
                         "independientes de entradas y resultados esperados para evitar su alteración "
                         "por ediciones posteriores. Las regresiones de transacción y validación "
                         "se comprueban en la suite automatizada, ejecutada por separado según el README.")
        else:
            lines.append("Hay casos fallidos: revisar las filas FALLO, corregir y repetir el comando; "
                         "no considerar esta ejecución una validación satisfactoria.")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        path.with_suffix(".json").write_text(
            json.dumps(self.results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"{passed}/{len(self.results)} casos correctos. Registro: {path}")
        return passed == len(self.results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=ROOT / "docs/resultados-api.md")
    parser.add_argument("--serve", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--database", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.serve:
        if args.database is None or args.port is None:
            parser.error("El servidor de prueba exige --database y --port.")
        serve(args.database, args.port)
        return
    checks = Checks()
    with tempfile.TemporaryDirectory(prefix="vinilos-http-") as directory:
        checks.run(Path(directory) / "http.db")
    if not checks.report(args.report):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
