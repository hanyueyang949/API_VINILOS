import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

import main
from config.config_variables import CORS_ORIGINS
from database.database import create_db_engine, get_db
from models.vinilo import Vinilo


class APITest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.engine = create_db_engine(f"sqlite:///{Path(self.directory.name) / 'api.db'}")
        self.sessions = sessionmaker(bind=self.engine)
        self.rollbacks = []

        def override_db():
            with self.sessions() as db:
                original_rollback = db.rollback

                def rollback():
                    self.rollbacks.append(True)
                    original_rollback()

                db.rollback = rollback
                try:
                    yield db
                except Exception:
                    db.rollback()
                    raise

        main.app.app.dependency_overrides[get_db] = override_db
        self.engine_patch = patch.object(main, "engine", self.engine)
        self.engine_patch.start()
        self.client = TestClient(main.app, raise_server_exceptions=False)
        self.client.__enter__()
        self.origin = CORS_ORIGINS[0]

    def tearDown(self):
        self.client.__exit__(None, None, None)
        main.app.app.dependency_overrides.clear()
        self.engine_patch.stop()
        self.engine.dispose()
        self.directory.cleanup()

    def seed(self):
        artista = self.client.post("/artistas", json={"nombre": "Artista"})
        genero = self.client.post("/generos", json={"tipo": "Rock"})
        self.assertEqual(artista.status_code, 201)
        self.assertEqual(genero.status_code, 201)
        return {
            "titulo": "Disco", "año": 2000, "precio": "12.50",
            "artista_id": artista.json()["id_artista"],
            "genero_id": genero.json()["id_genero"],
        }

    def detail(self, vinilo):
        artista = self.client.get(f"/artistas/{vinilo['artista_id']}").json()
        genero = self.client.get(f"/generos/{vinilo['genero_id']}").json()
        return dict(
            vinilo,
            artista={"id_artista": artista["id_artista"], "nombre": artista["nombre"]},
            genero={"id_genero": genero["id_genero"], "tipo": genero["tipo"]},
        )

    def test_crud_with_cors(self):
        payload = self.seed()
        headers = {"Origin": self.origin}
        created = self.client.post("/vinilos", json=payload, headers=headers)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.headers["access-control-allow-origin"], self.origin)
        item_id = created.json()["id_vinilo"]
        self.assertEqual(created.json()["año"], 2000)
        for resource in ("artistas", "generos", "vinilos"):
            self.assertEqual(self.client.get(f"/{resource}").status_code, 200)
            self.assertEqual(self.client.get(f"/{resource}/1").status_code, 200)
        payload["titulo"] = "Editado"
        response = self.client.put(f"/vinilos/{item_id}", json=payload, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["titulo"], "Editado")
        self.assertEqual(response.headers["access-control-allow-origin"], self.origin)
        for resource, key in (("artistas", "nombre"), ("generos", "tipo")):
            response = self.client.put(f"/{resource}/1", json={key: "Editado"}, headers=headers)
            self.assertEqual(response.status_code, 200)
        for resource in ("vinilos", "artistas", "generos"):
            response = self.client.delete(f"/{resource}/1", headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["access-control-allow-origin"], self.origin)

    def test_preflight_for_all_crud_methods(self):
        for method in ("GET", "POST", "PUT", "DELETE"):
            with self.subTest(method=method):
                response = self.client.options("/vinilos/1", headers={
                    "Origin": self.origin,
                    "Access-Control-Request-Method": method,
                    "Access-Control-Request-Headers": "content-type",
                })
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["access-control-allow-origin"], self.origin)
                self.assertIn(method, response.headers["access-control-allow-methods"])

    def test_vinilo_update_can_change_artist_and_genre(self):
        payload = self.seed()
        created = self.client.post("/vinilos", json=payload).json()
        artista = self.client.post("/artistas", json={"nombre": "Otro artista"}).json()
        genero = self.client.post("/generos", json={"tipo": "Jazz"}).json()
        payload.update(artista_id=artista["id_artista"], genero_id=genero["id_genero"])
        response = self.client.put(f"/vinilos/{created['id_vinilo']}", json=payload)
        self.assertEqual(response.status_code, 200)
        expected = dict(payload, id_vinilo=created["id_vinilo"], descripcion=None)
        self.assertEqual(response.json(), expected)
        self.assertEqual(self.client.get(f"/vinilos/{created['id_vinilo']}").json(), self.detail(expected))
        self.assertEqual(self.client.get("/vinilos").json(), [expected])
        for resource in ("artistas", "generos"):
            self.assertEqual(self.client.delete(f"/{resource}/1").status_code, 200)

    def test_put_resets_omitted_optional_fields(self):
        payload = self.seed()
        self.client.post("/vinilos", json=payload)
        response = self.client.put("/vinilos/1", json={"titulo": "Conservado", "artista_id": 1, "genero_id": 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "id_vinilo": 1, "titulo": "Conservado", "año": None, "precio": None,
            "descripcion": None, "artista_id": 1, "genero_id": 1,
        })
        response = self.client.put("/artistas/1", json={"nombre": "Conservado"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["descripcion"])

    def test_create_and_update_validation_reject_invalid_payloads(self):
        payload = self.seed()
        self.client.post("/vinilos", json=payload)
        cases = [
            ("artistas", {"nombre": "x" * 101}),
            ("artistas", {"descripcion": "x" * 501}),
            ("artistas", {"nombre": 42}),
            ("generos", {"tipo": "x" * 101}),
            ("generos", {"tipo": []}),
        ]
        for invalid in (
            {"titulo": "x" * 151}, {"precio": "1.001"},
            {"precio": "100000000"}, {"artista_id": None},
            {"genero_id": 0}, {"artista_id": True}, {"genero_id": "1"},
            {"año": "2000"}, {"id_vinilo": 99}, {"artista": {"id_artista": 1}},
        ):
            cases.append(("vinilos", dict(payload, **invalid)))
        cases.append(("vinilos", {"titulo": "Sin relaciones"}))
        for resource, data in cases:
            for method, url in (("POST", f"/{resource}"), ("PUT", f"/{resource}/1")):
                with self.subTest(method=method, resource=resource, data=data):
                    response = self.client.request(method, url, json=data)
                    self.assertEqual(response.status_code, 422)
                    self.assertEqual(response.json()["detail"], "Datos de entrada no válidos.")
                    self.assertTrue(response.json()["errors"])
        for resource in ("artistas", "generos", "vinilos"):
            self.assertEqual(len(self.client.get(f"/{resource}").json()), 1)
        self.assertEqual(self.client.get("/vinilos/1").json()["titulo"], "Disco")

    def test_openapi_distinguishes_create_update_and_read(self):
        document = self.client.get("/openapi.json").json()
        for resource, entity in (("artistas", "Artista"), ("generos", "Genero"), ("vinilos", "Vinilo")):
            for method, path, suffix in (
                ("post", f"/{resource}", "Create"),
                ("put", f"/{resource}/{{item_id}}", "Update"),
            ):
                body = document["paths"][path][method]["requestBody"]
                self.assertEqual(
                    body["content"]["application/json"]["schema"]["$ref"],
                    f"#/components/schemas/{entity}{suffix}",
                )
            response = document["paths"][f"/{resource}/{{item_id}}"]["get"]["responses"]["200"]
            self.assertEqual(
                response["content"]["application/json"]["schema"]["$ref"],
                f"#/components/schemas/{entity}{'Read' if entity == 'Genero' else 'Detail'}",
            )

    def test_unconfigured_origin_is_not_allowed(self):
        response = self.client.options("/vinilos", headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "DELETE",
        })
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_client_errors_include_cors_headers(self):
        self.seed()
        for method, path, payload, status in (
            ("POST", "/artistas", {"nombre": "Artista"}, 400),
            ("GET", "/vinilos/9999", None, 404),
            ("POST", "/vinilos", {}, 422),
        ):
            with self.subTest(status=status):
                response = self.client.request(
                    method, path, json=payload, headers={"Origin": self.origin}
                )
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.headers["access-control-allow-origin"], self.origin)

    def test_not_found_and_validation(self):
        for resource in ("artistas", "generos", "vinilos"):
            self.assertEqual(self.client.get(f"/{resource}/9999").status_code, 404)
            self.assertEqual(self.client.delete(f"/{resource}/9999").status_code, 404)
            self.assertEqual(self.client.get(f"/{resource}/invalid").status_code, 422)
        for payload in ({}, {"artista_id": None, "genero_id": 1}):
            self.assertEqual(self.client.post("/vinilos", json=payload).status_code, 422)
        response = self.client.post("/artistas", json={"nombre": "x" * 101, "password": "secret"})
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("secret", response.text)

    def test_integrity_errors_rollback_and_preserve_data(self):
        payload = self.seed()
        self.assertEqual(self.client.post("/vinilos", json=payload).status_code, 201)
        self.assertEqual(self.client.post("/vinilos", json=payload).status_code, 400)
        for resource, data in (("artistas", {"nombre": "Artista"}), ("generos", {"tipo": "Rock"})):
            self.assertEqual(self.client.post(f"/{resource}", json=data).status_code, 400)
            self.assertEqual(self.client.delete(f"/{resource}/1").status_code, 400)
        payload["artista_id"] = 9999
        response = self.client.put("/vinilos/1", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("sqlite", response.text.lower())
        self.assertEqual(self.client.get("/vinilos/1").json()["artista_id"], 1)
        self.assertTrue(self.rollbacks)

    def test_write_failure_returns_safe_500_with_cors_and_rollback(self):
        payload = self.seed()
        self.client.post("/vinilos", json=payload)
        with patch("sqlalchemy.orm.Session.commit", side_effect=SQLAlchemyError("secret credentials SQL")):
            for method, url, data in (
                ("POST", "/artistas", {"nombre": "Fallido"}),
                ("PUT", "/vinilos/1", dict(payload, titulo="Fallido")),
                ("DELETE", "/vinilos/1", None),
            ):
                response = self.client.request(method, url, json=data, headers={"Origin": self.origin})
                self.assertEqual(response.status_code, 500)
                self.assertNotIn("secret", response.text)
                self.assertEqual(response.headers["access-control-allow-origin"], self.origin)
        self.assertGreaterEqual(len(self.rollbacks), 3)
        self.assertEqual(len(self.client.get("/artistas").json()), 1)
        self.assertEqual(self.client.get("/vinilos/1").json()["titulo"], "Disco")

    def test_unexpected_error_returns_safe_500_with_cors(self):
        with patch("controllers.artista_controller.list_items", side_effect=RuntimeError("secret internal details")):
            response = self.client.get("/artistas", headers={"Origin": self.origin})
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("secret", response.text)
        self.assertEqual(response.headers["access-control-allow-origin"], self.origin)

    def test_artist_create_list_and_empty_detail(self):
        self.assertEqual(self.client.get("/artistas").json(), [])
        response = self.client.post("/artistas", json={
            "nombre": "Artista de prueba", "descripcion": "Biografía de prueba",
        })
        self.assertEqual(response.status_code, 201)
        artista = response.json()
        self.assertEqual(artista["nombre"], "Artista de prueba")
        self.assertEqual(artista["descripcion"], "Biografía de prueba")
        self.assertEqual(self.client.get("/artistas").json(), [artista])
        detail = self.client.get(f"/artistas/{artista['id_artista']}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json(), dict(artista, vinilos=[]))

    def test_artist_detail_contains_only_its_associated_vinilos(self):
        payload = self.seed()
        first = self.client.post("/vinilos", json=payload).json()
        second = self.client.post("/vinilos", json=dict(payload, titulo="Segundo")).json()
        other_artist = self.client.post("/artistas", json={"nombre": "Otro"}).json()
        self.client.post("/vinilos", json=dict(payload, artista_id=other_artist["id_artista"]))
        response = self.client.get("/artistas/1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["nombre"], "Artista")
        self.assertCountEqual(response.json()["vinilos"], [first, second])
        for vinilo in response.json()["vinilos"]:
            self.assertNotIn("artista", vinilo)
            self.assertNotIn("genero", vinilo)
            self.assertEqual(vinilo["artista_id"], 1)

    def test_artist_duplicate_invalid_input_and_missing_id(self):
        original = {"nombre": "Nombre único", "descripcion": "Original"}
        self.assertEqual(self.client.post("/artistas", json=original).status_code, 201)
        duplicate = self.client.post("/artistas", json=original)
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate.json(), {
            "detail": "No se pudo guardar: hay datos duplicados o referencias no válidas.",
        })
        for payload in (
            {"nombre": "x" * 101}, {"descripcion": "x" * 501},
            {"nombre": 123}, {"descripcion": []}, {"id_artista": 99},
        ):
            with self.subTest(payload=payload):
                response = self.client.post("/artistas", json=payload)
                self.assertEqual(response.status_code, 422)
        self.assertEqual(len(self.client.get("/artistas").json()), 1)
        response = self.client.get("/artistas/9999")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Recurso no encontrado."})

    def test_docs_exposes_artist_creation_and_detail(self):
        self.assertEqual(self.client.get("/docs").status_code, 200)
        document = self.client.get("/openapi.json").json()
        self.assertIn("201", document["paths"]["/artistas"]["post"]["responses"])
        schemas = document["components"]["schemas"]
        detail = schemas["ArtistaDetail"]
        self.assertEqual(detail["properties"]["vinilos"]["type"], "array")
        self.assertEqual(
            detail["properties"]["vinilos"]["items"]["$ref"],
            "#/components/schemas/ViniloRead",
        )

    def test_artist_update_keeps_vinilos_and_exposes_current_data(self):
        payload = self.seed()
        first = self.client.post("/vinilos", json=payload).json()
        second = self.client.post("/vinilos", json=dict(payload, titulo="Segundo")).json()
        updated = {"nombre": "Artista editado", "descripcion": "Nueva biografía"}
        response = self.client.put("/artistas/1", json=updated)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), dict(updated, id_artista=1))
        detail = self.client.get("/artistas/1").json()
        self.assertEqual(detail["nombre"], updated["nombre"])
        self.assertEqual(detail["descripcion"], updated["descripcion"])
        self.assertCountEqual(detail["vinilos"], [first, second])
        self.assertEqual(self.client.get("/artistas").json(), [response.json()])
        for vinilo in (first, second):
            current = self.client.get(f"/vinilos/{vinilo['id_vinilo']}").json()
            self.assertEqual(current, self.detail(vinilo))
            artist = self.client.get(f"/artistas/{current['artista_id']}").json()
            self.assertEqual(artist["nombre"], updated["nombre"])
            self.assertEqual(artist["descripcion"], updated["descripcion"])
            with self.sessions() as db:
                stored = db.get(Vinilo, vinilo["id_vinilo"])
                self.assertEqual(stored.artista_id, 1)
                self.assertEqual(stored.artista.nombre, updated["nombre"])
                self.assertEqual(stored.artista.descripcion, updated["descripcion"])
        # Guardar sin cambiar el nombre no se considera un duplicado.
        self.assertEqual(self.client.put("/artistas/1", json=updated).status_code, 200)

    def test_artist_delete_without_vinilos_and_repeated_delete(self):
        artista = self.client.post("/artistas", json={"nombre": "Sin vinilos"}).json()
        url = f"/artistas/{artista['id_artista']}"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"detail": "Recurso eliminado correctamente."})
        self.assertEqual(self.client.get("/artistas").json(), [])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)

    def test_artist_delete_with_vinilos_is_blocked_until_unlinked(self):
        payload = self.seed()
        vinilo = self.client.post("/vinilos", json=payload).json()
        response = self.client.delete("/artistas/1")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {
            "detail": "No se puede eliminar el recurso porque tiene vinilos asociados.",
        })
        self.assertEqual(self.client.get("/artistas/1").json()["vinilos"], [vinilo])
        self.assertEqual(self.client.get(f"/vinilos/{vinilo['id_vinilo']}").json(), self.detail(vinilo))
        self.assertTrue(self.rollbacks)
        self.assertEqual(self.client.delete(f"/vinilos/{vinilo['id_vinilo']}").status_code, 200)
        self.assertEqual(self.client.delete("/artistas/1").status_code, 200)
        self.assertEqual(self.client.get("/generos/1").status_code, 200)

    def test_artist_update_duplicate_rolls_back_all_changes(self):
        payload = self.seed()
        self.client.post("/vinilos", json=payload)
        other = self.client.post("/artistas", json={"nombre": "Reservado"}).json()
        before = self.client.get("/artistas/1").json()
        response = self.client.put("/artistas/1", json={
            "nombre": "Reservado", "descripcion": "No debe guardarse",
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {
            "detail": "No se pudo guardar: hay datos duplicados o referencias no válidas.",
        })
        self.assertTrue(self.rollbacks)
        self.assertEqual(self.client.get("/artistas/1").json(), before)
        self.assertEqual(self.client.get(f"/artistas/{other['id_artista']}").json()["nombre"], "Reservado")
        response = self.client.put("/artistas/1", json={"nombre": "Disponible", "descripcion": "Válida"})
        self.assertEqual(response.status_code, 200)

    def test_artist_update_and_delete_missing_id(self):
        for method, payload in (("PUT", {"nombre": "No existe"}), ("DELETE", None)):
            response = self.client.request(method, "/artistas/9999", json=payload)
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json(), {"detail": "Recurso no encontrado."})

    def test_artist_write_failures_rollback_and_preserve_original(self):
        original = {"nombre": "Original", "descripcion": "Se conserva"}
        self.client.post("/artistas", json=original)
        with patch("sqlalchemy.orm.Session.commit", side_effect=SQLAlchemyError("secret SQL")):
            for method, payload in (
                ("PUT", {"nombre": "Fallido", "descripcion": "No guardar"}),
                ("DELETE", None),
            ):
                response = self.client.request(method, "/artistas/1", json=payload)
                self.assertEqual(response.status_code, 500)
                self.assertNotIn("secret", response.text)
        self.assertGreaterEqual(len(self.rollbacks), 2)
        self.assertEqual(self.client.get("/artistas/1").json(), dict(original, id_artista=1, vinilos=[]))

    def test_genero_create_list_detail_update_and_delete(self):
        self.assertEqual(self.client.get("/generos").json(), [])
        created = self.client.post("/generos", json={"tipo": "Rock"})
        self.assertEqual(created.status_code, 201)
        genero = created.json()
        self.assertEqual(genero["tipo"], "Rock")
        url = f"/generos/{genero['id_genero']}"
        self.assertEqual(self.client.get("/generos").json(), [genero])
        self.assertEqual(self.client.get(url).json(), genero)
        updated = self.client.put(url, json={"tipo": "Jazz"})
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json(), dict(genero, tipo="Jazz"))
        self.assertEqual(self.client.get(url).json(), updated.json())
        # Mantener el propio tipo no es un duplicado.
        self.assertEqual(self.client.put(url, json={"tipo": "Jazz"}).status_code, 200)
        deleted = self.client.delete(url)
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.json(), {"detail": "Recurso eliminado correctamente."})
        self.assertEqual(self.client.get("/generos").json(), [])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)

    def test_genero_duplicate_create_and_rename_rollback(self):
        rock = self.client.post("/generos", json={"tipo": "Rock"}).json()
        jazz = self.client.post("/generos", json={"tipo": "Jazz"}).json()
        for method, url in (("POST", "/generos"), ("PUT", f"/generos/{jazz['id_genero']}")):
            response = self.client.request(method, url, json={"tipo": "Rock"})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json(), {
                "detail": "No se pudo guardar: hay datos duplicados o referencias no válidas.",
            })
        self.assertTrue(self.rollbacks)
        self.assertEqual(self.client.get("/generos").json(), [rock, jazz])
        self.assertEqual(self.client.put(f"/generos/{jazz['id_genero']}", json={"tipo": "Blues"}).status_code, 200)

    def test_genero_rename_preserves_vinilo_associations(self):
        payload = self.seed()
        first = self.client.post("/vinilos", json=payload).json()
        second = self.client.post("/vinilos", json=dict(payload, titulo="Segundo")).json()
        response = self.client.put("/generos/1", json={"tipo": "Rock alternativo"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id_genero": 1, "tipo": "Rock alternativo"})
        for vinilo in (first, second):
            current = self.client.get(f"/vinilos/{vinilo['id_vinilo']}").json()
            self.assertEqual(current, self.detail(vinilo))
            self.assertEqual(self.client.get(f"/generos/{current['genero_id']}").json()["tipo"], "Rock alternativo")
            with self.sessions() as db:
                stored = db.get(Vinilo, vinilo["id_vinilo"])
                self.assertEqual(stored.genero_id, 1)
                self.assertEqual(stored.genero.tipo, "Rock alternativo")

    def test_genero_delete_is_blocked_until_all_vinilos_are_removed(self):
        payload = self.seed()
        vinilo = self.client.post("/vinilos", json=payload).json()
        response = self.client.delete("/generos/1")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {
            "detail": "No se puede eliminar el recurso porque tiene vinilos asociados.",
        })
        self.assertTrue(self.rollbacks)
        self.assertEqual(self.client.get("/generos/1").json(), {"id_genero": 1, "tipo": "Rock"})
        self.assertEqual(self.client.get(f"/vinilos/{vinilo['id_vinilo']}").json(), self.detail(vinilo))
        self.assertEqual(self.client.delete(f"/vinilos/{vinilo['id_vinilo']}").status_code, 200)
        self.assertEqual(self.client.delete("/generos/1").status_code, 200)
        self.assertEqual(self.client.get("/artistas/1").status_code, 200)

    def test_genero_invalid_input_and_missing_ids(self):
        self.client.post("/generos", json={"tipo": "Rock"})
        for payload in (
            {"tipo": "x" * 101}, {"tipo": 123}, {"tipo": []},
            {"id_genero": 99}, {"unknown": "value"},
        ):
            for method, url in (("POST", "/generos"), ("PUT", "/generos/1")):
                with self.subTest(method=method, payload=payload):
                    response = self.client.request(method, url, json=payload)
                    self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.get("/generos/1").json()["tipo"], "Rock")
        for method, payload in (("GET", None), ("PUT", {"tipo": "Jazz"}), ("DELETE", None)):
            response = self.client.request(method, "/generos/9999", json=payload)
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json(), {"detail": "Recurso no encontrado."})
            for item_id in ("invalid", "0", "-1"):
                self.assertEqual(self.client.request(method, f"/generos/{item_id}", json=payload).status_code, 422)

    def test_genero_write_failures_rollback_and_hide_internal_details(self):
        self.client.post("/generos", json={"tipo": "Rock"})
        with patch("sqlalchemy.orm.Session.commit", side_effect=SQLAlchemyError("secret SQL")):
            for method, url, payload in (
                ("POST", "/generos", {"tipo": "Jazz"}),
                ("PUT", "/generos/1", {"tipo": "Jazz"}),
                ("DELETE", "/generos/1", None),
            ):
                response = self.client.request(method, url, json=payload)
                self.assertEqual(response.status_code, 500)
                self.assertNotIn("secret", response.text)
        self.assertGreaterEqual(len(self.rollbacks), 3)
        self.assertEqual(self.client.get("/generos").json(), [{"id_genero": 1, "tipo": "Rock"}])

    def test_docs_exposes_all_genero_operations(self):
        self.assertEqual(self.client.get("/docs").status_code, 200)
        paths = self.client.get("/openapi.json").json()["paths"]
        self.assertTrue({"get", "post"}.issubset(paths["/generos"]))
        self.assertTrue({"get", "put", "delete"}.issubset(paths["/generos/{item_id}"]))
        self.assertIn("201", paths["/generos"]["post"]["responses"])

    def test_vinilo_creation_saves_all_fields_and_relationships(self):
        payload = dict(self.seed(), descripcion="Edición de prueba")
        response = self.client.post("/vinilos", json=payload)
        self.assertEqual(response.status_code, 201)
        created = response.json()
        self.assertEqual(created, dict(payload, id_vinilo=created["id_vinilo"]))
        self.assertEqual(self.client.get("/vinilos").json(), [created])
        self.assertEqual(self.client.get(f"/vinilos/{created['id_vinilo']}").json(), self.detail(created))
        self.assertEqual(self.client.get("/artistas/1").json()["vinilos"], [created])
        self.assertEqual(self.client.get(f"/generos/{created['genero_id']}").json()["tipo"], "Rock")
        with self.sessions() as db:
            stored = db.get(Vinilo, created["id_vinilo"])
            self.assertEqual(stored.titulo, payload["titulo"])
            self.assertEqual(stored.anio, payload["año"])
            self.assertEqual(stored.precio, Decimal(payload["precio"]))
            self.assertEqual(stored.descripcion, payload["descripcion"])
            self.assertEqual(stored.artista_id, payload["artista_id"])
            self.assertEqual(stored.genero_id, payload["genero_id"])
            self.assertEqual(stored.artista.nombre, "Artista")
            self.assertEqual(stored.genero.tipo, "Rock")

    def test_vinilo_creation_rejects_each_nonexistent_relation(self):
        payload = self.seed()
        for invalid in (
            {"artista_id": 9999}, {"genero_id": 9999},
            {"artista_id": 9999, "genero_id": 9999},
        ):
            with self.subTest(invalid=invalid):
                response = self.client.post("/vinilos", json=dict(payload, **invalid))
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json(), {
                    "detail": "No se pudo guardar: hay datos duplicados o referencias no válidas.",
                })
                self.assertEqual(self.client.get("/vinilos").json(), [])
                self.assertEqual(self.client.get("/artistas/1").json()["vinilos"], [])
        self.assertTrue(self.rollbacks)
        self.assertEqual(len(self.client.get("/artistas").json()), 1)
        self.assertEqual(len(self.client.get("/generos").json()), 1)
        self.assertEqual(self.client.post("/vinilos", json=payload).status_code, 201)

    def test_vinilo_creation_duplicate_key_is_title_and_artist_not_genre(self):
        payload = self.seed()
        created = self.client.post("/vinilos", json=payload).json()
        other_genre = self.client.post("/generos", json={"tipo": "Jazz"}).json()
        for data in (payload, dict(payload, genero_id=other_genre["id_genero"])):
            response = self.client.post("/vinilos", json=data)
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/vinilos").json(), [created])
        other_artist = self.client.post("/artistas", json={"nombre": "Otro artista"}).json()
        # Mismo título, artista distinto: permitido.
        self.assertEqual(self.client.post(
            "/vinilos", json=dict(payload, artista_id=other_artist["id_artista"])
        ).status_code, 201)
        # Mismo artista, título distinto: permitido.
        self.assertEqual(self.client.post(
            "/vinilos", json=dict(payload, titulo="Otro título")
        ).status_code, 201)
        self.assertEqual(len(self.client.get("/vinilos").json()), 3)

    def test_vinilo_creation_requires_both_foreign_keys(self):
        payload = self.seed()
        for field in ("artista_id", "genero_id"):
            missing = dict(payload)
            del missing[field]
            for data in (missing, dict(payload, **{field: None})):
                with self.subTest(field=field, data=data):
                    response = self.client.post("/vinilos", json=data)
                    self.assertEqual(response.status_code, 422)
                    self.assertIn(["body", field], [error["loc"] for error in response.json()["errors"]])
        self.assertEqual(self.client.get("/vinilos").json(), [])

    def test_vinilo_creation_accepts_python_year_alias_and_returns_contract_alias(self):
        payload = self.seed()
        payload["anio"] = payload.pop("año")
        response = self.client.post("/vinilos", json=payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["año"], payload["anio"])
        self.assertNotIn("anio", response.json())

    def test_vinilo_catalog_and_filters_return_empty_lists_without_matches(self):
        for url in ("/vinilos", "/vinilos?genero_id=9999"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), [])
        self.seed()
        response = self.client.get("/vinilos?genero_id=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_vinilo_catalog_and_genre_filter_preserve_contract_and_order(self):
        payload = self.seed()
        jazz = self.client.post("/generos", json={"tipo": "Jazz"}).json()
        empty_genre = self.client.post("/generos", json={"tipo": "Sin discos"}).json()
        first = self.client.post("/vinilos", json=payload).json()
        second = self.client.post("/vinilos", json=dict(
            payload, titulo="Jazz", genero_id=jazz["id_genero"]
        )).json()
        third = self.client.post("/vinilos", json=dict(payload, titulo="Otro rock")).json()
        self.assertEqual(self.client.get("/vinilos").json(), [first, second, third])
        self.assertEqual(self.client.get("/vinilos?genero_id=1").json(), [first, third])
        self.assertEqual(self.client.get(f"/vinilos?genero_id={jazz['id_genero']}").json(), [second])
        for genero_id in (empty_genre["id_genero"], 9999):
            response = self.client.get("/vinilos", params={"genero_id": genero_id})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), [])
        for item in (first, second, third):
            response = self.client.get(f"/vinilos/{item['id_vinilo']}")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), self.detail(item))
            self.assertEqual(set(item), {
                "id_vinilo", "titulo", "año", "precio", "descripcion",
                "artista_id", "genero_id",
            })
            self.assertEqual(self.client.get(f"/artistas/{item['artista_id']}").status_code, 200)
            self.assertEqual(self.client.get(f"/generos/{item['genero_id']}").status_code, 200)

    def test_vinilo_invalid_genre_filter_returns_validation_error(self):
        for value in ("", "invalid", "0", "-1", "1.5", "1.0", "true", "null", "1 OR 1=1"):
            with self.subTest(value=value):
                response = self.client.get("/vinilos", params={"genero_id": value})
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["detail"], "Datos de entrada no válidos.")
                self.assertIn(
                    ["query", "genero_id"],
                    [error["loc"] for error in response.json()["errors"]],
                )

    def test_vinilo_detail_nonexistent_and_invalid_ids(self):
        response = self.client.get("/vinilos/9999")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Recurso no encontrado."})
        for item_id in ("invalid", "0", "-1", "1.5"):
            self.assertEqual(self.client.get(f"/vinilos/{item_id}").status_code, 422)

    def test_openapi_exposes_optional_genre_filter(self):
        document = self.client.get("/openapi.json").json()
        parameters = document["paths"]["/vinilos"]["get"]["parameters"]
        genero = next(item for item in parameters if item["name"] == "genero_id")
        self.assertEqual(genero["in"], "query")
        self.assertFalse(genero["required"])
        self.assertIn({"type": "integer", "exclusiveMinimum": 0}, genero["schema"]["anyOf"])

    def test_vinilo_update_all_fields_and_relationships_is_visible_in_queries(self):
        original = self.client.post("/vinilos", json=self.seed()).json()
        artista = self.client.post("/artistas", json={"nombre": "Nuevo artista"}).json()
        genero = self.client.post("/generos", json={"tipo": "Nuevo género"}).json()
        data = {
            "titulo": "Nuevo título", "año": 2026, "precio": "25.75",
            "descripcion": "Nueva descripción",
            "artista_id": artista["id_artista"], "genero_id": genero["id_genero"],
        }
        url = f"/vinilos/{original['id_vinilo']}"
        response = self.client.put(url, json=data)
        self.assertEqual(response.status_code, 200)
        expected = dict(data, id_vinilo=original["id_vinilo"])
        self.assertEqual(response.json(), expected)
        self.assertEqual(self.client.get(url).json(), self.detail(expected))
        self.assertEqual(self.client.get("/vinilos").json(), [expected])
        self.assertEqual(self.client.get("/vinilos?genero_id=1").json(), [])
        self.assertEqual(self.client.get(f"/vinilos?genero_id={genero['id_genero']}").json(), [expected])
        self.assertEqual(self.client.get("/artistas/1").json()["vinilos"], [])
        self.assertEqual(self.client.get(f"/artistas/{artista['id_artista']}").json()["vinilos"], [expected])
        with self.sessions() as db:
            stored = db.get(Vinilo, original["id_vinilo"])
            self.assertEqual(stored.artista.nombre, "Nuevo artista")
            self.assertEqual(stored.genero.tipo, "Nuevo género")
            self.assertEqual(stored.precio, Decimal("25.75"))
        # Actualizar con la misma clave única propia está permitido.
        self.assertEqual(self.client.put(url, json=data).status_code, 200)

    def test_vinilo_update_nonexistent_relations_rolls_back_all_fields(self):
        payload = self.seed()
        original = self.client.post("/vinilos", json=payload).json()
        url = f"/vinilos/{original['id_vinilo']}"
        for invalid in (
            {"artista_id": 9999}, {"genero_id": 9999},
            {"artista_id": 9999, "genero_id": 9999},
        ):
            with self.subTest(invalid=invalid):
                data = dict(payload, titulo="No guardar", descripcion="No guardar", precio="99.99")
                data.update(invalid)
                response = self.client.put(url, json=data)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json(), {
                    "detail": "No se pudo guardar: hay datos duplicados o referencias no válidas.",
                })
                self.assertEqual(self.client.get(url).json(), self.detail(original))
                self.assertEqual(self.client.get("/vinilos").json(), [original])
                self.assertEqual(self.client.get("/artistas/1").json()["vinilos"], [original])
        self.assertTrue(self.rollbacks)

    def test_vinilo_update_duplicate_title_artist_rolls_back_even_with_new_genre(self):
        payload = self.seed()
        first = self.client.post("/vinilos", json=payload).json()
        second_payload = dict(payload, titulo="Segundo")
        second = self.client.post("/vinilos", json=second_payload).json()
        artista = self.client.post("/artistas", json={"nombre": "Otro artista"}).json()
        third_payload = dict(payload, artista_id=artista["id_artista"])
        third = self.client.post("/vinilos", json=third_payload).json()
        genero = self.client.post("/generos", json={"tipo": "Otro género"}).json()
        for original, changes in (
            (second, dict(payload)),  # Conflicto al cambiar solo el título.
            (third, dict(payload)),  # Conflicto al cambiar solo el artista.
            (second, dict(payload, genero_id=genero["id_genero"])),
        ):
            changes["descripcion"] = "No guardar"
            response = self.client.put(f"/vinilos/{original['id_vinilo']}", json=changes)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(self.client.get(f"/vinilos/{original['id_vinilo']}").json(), self.detail(original))
        self.assertEqual(self.client.get("/vinilos").json(), [first, second, third])
        self.assertTrue(self.rollbacks)

    def test_vinilo_delete_removes_from_all_queries_but_preserves_parents(self):
        payload = self.seed()
        created = self.client.post("/vinilos", json=payload).json()
        artista = self.client.get("/artistas/1").json()
        genero = self.client.get("/generos/1").json()
        url = f"/vinilos/{created['id_vinilo']}"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"detail": "Recurso eliminado correctamente."})
        for query in ("/vinilos", "/vinilos?genero_id=1"):
            self.assertEqual(self.client.get(query).json(), [])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Recurso no encontrado."})
        self.assertEqual(self.client.get("/artistas/1").json(), dict(artista, vinilos=[]))
        self.assertEqual(self.client.get("/generos/1").json(), genero)
        with self.sessions() as db:
            self.assertIsNone(db.get(Vinilo, created["id_vinilo"]))

    def test_vinilo_update_and_delete_nonexistent_id(self):
        payload = self.seed()
        for method, data in (("PUT", payload), ("DELETE", None)):
            response = self.client.request(method, "/vinilos/9999", json=data)
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json(), {"detail": "Recurso no encontrado."})
        self.assertEqual(self.client.get("/vinilos").json(), [])

    def test_vinilo_delete_keeps_other_vinilos_and_repeated_delete_returns_404(self):
        payload = self.seed()
        first = self.client.post("/vinilos", json=payload).json()
        second = self.client.post("/vinilos", json=dict(payload, titulo="Segundo")).json()
        url = f"/vinilos/{first['id_vinilo']}"
        self.assertEqual(self.client.delete(url).status_code, 200)
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertEqual(self.client.get("/vinilos").json(), [second])
        self.assertEqual(self.client.get("/vinilos?genero_id=1").json(), [second])
        self.assertEqual(self.client.get("/artistas/1").json()["vinilos"], [second])
        self.assertEqual(self.client.get("/generos/1").status_code, 200)

    def test_required_text_validation_in_post_and_put_preserves_data(self):
        payload = self.seed()
        created = self.client.post("/vinilos", json=payload).json()
        for resource, field, valid in (
            ("artistas", "nombre", {"nombre": "Artista"}),
            ("generos", "tipo", {"tipo": "Rock"}),
            ("vinilos", "titulo", payload),
        ):
            before = self.client.get(f"/{resource}/1").json()
            for value in (None, "", "   ", "\t\n"):
                for method, path in (("POST", f"/{resource}"), ("PUT", f"/{resource}/1")):
                    with self.subTest(resource=resource, value=value, method=method):
                        response = self.client.request(method, path, json=dict(valid, **{field: value}))
                        self.assertEqual(response.status_code, 422)
                        self.assertIn(["body", field], [error["loc"] for error in response.json()["errors"]])
            missing = dict(valid)
            del missing[field]
            for method, path in (("POST", f"/{resource}"), ("PUT", f"/{resource}/1")):
                self.assertEqual(self.client.request(method, path, json=missing).status_code, 422)
            self.assertEqual(self.client.get(f"/{resource}/1").json(), before)
            self.assertEqual(len(self.client.get(f"/{resource}").json()), 1)
        self.assertEqual(self.client.get("/vinilos").json(), [created])

    def test_price_optional_zero_and_negative_in_post_and_put(self):
        payload = self.seed()
        original = self.client.post("/vinilos", json=payload).json()
        for price in ("-0.01", -1):
            for method, path in (("POST", "/vinilos"), ("PUT", "/vinilos/1")):
                response = self.client.request(method, path, json=dict(payload, precio=price))
                self.assertEqual(response.status_code, 422)
                self.assertIn(["body", "precio"], [error["loc"] for error in response.json()["errors"]])
        self.assertEqual(self.client.get("/vinilos").json(), [original])
        for index, price in enumerate((None, "0", 0)):
            data = dict(payload, titulo=f"Precio válido {index}", precio=price)
            for method, path in (("POST", "/vinilos"), ("PUT", "/vinilos/1")):
                if method == "PUT":
                    # Evitar colisión con el título recién creado.
                    data["titulo"] += " editado"
                response = self.client.request(method, path, json=data)
                self.assertEqual(response.status_code, 201 if method == "POST" else 200)
                self.assertEqual(response.json()["precio"], None if price is None else "0.00")
        data = dict(payload, titulo="Sin precio")
        del data["precio"]
        self.assertEqual(self.client.post("/vinilos", json=data).status_code, 201)
        data["titulo"] = "Sin precio editado"
        response = self.client.put("/vinilos/1", json=data)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["precio"])

    def test_vinilo_detail_shows_related_names_and_keeps_catalog_flat(self):
        created = self.client.post("/vinilos", json=self.seed()).json()
        expected = dict(created,
            artista={"id_artista": 1, "nombre": "Artista"},
            genero={"id_genero": 1, "tipo": "Rock"},
        )
        self.assertEqual(self.client.get("/vinilos/1").json(), expected)
        self.assertEqual(self.client.get("/vinilos").json(), [created])
        self.assertEqual(self.client.get("/vinilos?genero_id=1").json(), [created])
        self.client.put("/artistas/1", json={"nombre": "Artista renombrado"})
        self.client.put("/generos/1", json={"tipo": "Género renombrado"})
        expected["artista"]["nombre"] = "Artista renombrado"
        expected["genero"]["tipo"] = "Género renombrado"
        self.assertEqual(self.client.get("/vinilos/1").json(), expected)

    def test_refresh_failure_precedes_commit_and_rolls_back_every_entity(self):
        payload = self.seed()
        self.client.post("/vinilos", json=payload)
        for resource, data in (
            ("artistas", {"nombre": "Nuevo nombre", "descripcion": "No guardar"}),
            ("generos", {"tipo": "Nuevo tipo"}),
            ("vinilos", dict(payload, titulo="Nuevo título", precio="99.99")),
        ):
            before = self.client.get(f"/{resource}").json()
            detail = self.client.get(f"/{resource}/1").json()
            for method, path in (("POST", f"/{resource}"), ("PUT", f"/{resource}/1")):
                with self.subTest(resource=resource, method=method):
                    with patch("sqlalchemy.orm.Session.refresh", side_effect=SQLAlchemyError("secret refresh")):
                        with patch("sqlalchemy.orm.Session.commit") as commit:
                            response = self.client.request(method, path, json=data)
                            self.assertEqual(response.status_code, 500)
                            self.assertNotIn("secret", response.text)
                            commit.assert_not_called()
                    self.assertEqual(self.client.get(f"/{resource}").json(), before)
                    self.assertEqual(self.client.get(f"/{resource}/1").json(), detail)

    def test_response_validation_failure_rolls_back_before_commit(self):
        from schemas.artista import ArtistaRead

        try:
            ArtistaRead.model_validate({})
        except ValidationError as exc:
            validation_error = exc
        with patch.object(ArtistaRead, "model_validate", side_effect=validation_error):
            with patch("sqlalchemy.orm.Session.commit") as commit:
                response = self.client.post("/artistas", json={"nombre": "No guardar"})
                self.assertEqual(response.status_code, 500)
                commit.assert_not_called()
        self.assertEqual(self.client.get("/artistas").json(), [])
