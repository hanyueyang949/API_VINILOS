# API_VINILOS

## Inicio

```sh
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

SQLAlchemy crea las tablas al iniciar FastAPI. La base SQLite `vinilos.db`
se guarda en la raíz del proyecto, independientemente del directorio de ejecución,
y conserva los datos al reiniciar. `create_all` no migra tablas existentes.

## Modelos y relaciones

Fuente del esquema y las reglas de negocio: [DER](1233333.png).

- `artista`: `id_artista` (PK, entero), `nombre` (VARCHAR(100), único),
  `descripcion` (VARCHAR(500)).
- `genero`: `id_genero` (PK, entero), `tipo` (VARCHAR(100), único).
- `vinilo`: `id_vinilo` (PK, entero), `titulo` (VARCHAR(150)), `año` (entero,
  atributo Python `anio`), `precio` (DECIMAL(10,2)), `descripcion` (TEXT),
  `artista_id` y `genero_id` (FK obligatorias).

Cada vinilo pertenece a un único artista y a un único género existentes.
Cada artista y género puede tener cero o muchos vinilos.
La combinación `(titulo, artista_id)` es única: ni `titulo` ni `artista_id`
son únicos individualmente, y `UNIQUE*` no es una columna adicional.
Los campos distintos de PK y FK
permiten NULL, tal como están definidos en los modelos. En SQLite, UNIQUE permite
múltiples valores NULL; VARCHAR y DECIMAL indican tipos, pero no imponen por sí
solos longitud máxima o precisión decimal estrictas.

Las claves foráneas se activan en cada conexión SQLite. `ON DELETE RESTRICT`
impide eliminar artistas y géneros vinculados, incluso mediante SQL directo.
Las relaciones no borran vinilos en cascada.

## Cliente web y CORS

- Backend: `http://127.0.0.1:8000` (`uvicorn main:app --reload`).
- Origen local predeterminado del frontend: `http://localhost:5173`.
- El repositorio hermano `frontend_vinilos` solo contiene un README: este puerto
  es una propuesta configurable, no una dirección ya confirmada por el cliente.

Para permitir otros orígenes exactos, configura la variable antes de arrancar:

```sh
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173 uvicorn main:app --reload
```

`localhost` y `127.0.0.1` son orígenes distintos. No incluyas rutas ni barra final.
Se permiten GET, POST, PUT, DELETE y OPTIONS, con Content-Type y Accept.
No se habilitan cookies ni credenciales de navegador. CORS también se aplica a
las respuestas de error, incluidos los errores internos. CORS no es autenticación.

El cliente debe enviar JSON (`Content-Type: application/json`) y utilizar la URL
del backend como base. Por ejemplo, desde la consola del navegador en el frontend:

```js
const api = "http://127.0.0.1:8000";
const created = await fetch(`${api}/artistas`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ nombre: `Prueba CORS ${Date.now()}` }),
});
if (!created.ok) throw new Error((await created.json()).detail);
const artista = await created.json();
const edited = await fetch(`${api}/artistas/${artista.id_artista}`, {
  method: "PUT",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ nombre: `${artista.nombre} editado` }),
});
const deleted = await fetch(`${api}/artistas/${artista.id_artista}`, {
  method: "DELETE",
});
console.log(created.status, edited.status, deleted.status); // 201, 200, 200
```

Pendiente cuando exista el cliente: documentar su comando de inicio, origen real y
URL base de API en su propio repositorio y verificar los formularios en navegador.

## Contrato HTTP

Documentación interactiva en `http://127.0.0.1:8000/docs`.
Las rutas usan los recursos `/artistas`, `/generos` y `/vinilos` (sin barra final):

| Operación | Ruta | Éxito |
| --- | --- | --- |
| Listar | `GET /{recurso}` | 200, lista JSON |
| Consultar | `GET /{recurso}/{id}` | 200, objeto JSON |
| Crear | `POST /{recurso}` | 201, objeto creado |
| Reemplazar | `PUT /{recurso}/{id}` | 200, objeto actualizado |
| Borrar | `DELETE /{recurso}/{id}` | 200, mensaje JSON |

POST y PUT aceptan los campos del DER excepto la clave primaria. PUT reemplaza
todos los campos editables; los opcionales omitidos pasan a NULL (no es PATCH).
En vinilos, `artista_id` y `genero_id` son obligatorios; se admite `año` o `anio`
en la entrada y se devuelve `año`. `precio` se devuelve como cadena decimal para
preservar precisión. Los campos desconocidos se rechazan.

| Error | Código |
| --- | --- |
| Duplicados, FK inexistente o borrado de artista/género vinculado | 400 |
| Recurso inexistente | 404 |
| JSON, tipos, longitudes o campos obligatorios no válidos | 422 |
| Fallo de base de datos no relacionado con integridad o error inesperado | 500 |

Los errores devuelven `{"detail": "mensaje"}`; los 422 incluyen además `errors`
con ubicación y tipo de validación, sin reproducir los valores recibidos.
Los fallos de escritura ejecutan rollback. Las respuestas no exponen SQL,
credenciales, trazas ni excepciones internas. Los IDs deben ser enteros positivos.

## Pruebas

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Las pruebas utilizan bases temporales y verifican claves foráneas, duplicados,
borrados restringidos, relaciones y persistencia al recrear el motor. También
comprueban CRUD HTTP, preflight CORS de edición/borrado, rechazo de orígenes no
permitidos, códigos de error, rollback y respuestas 500 sin detalles internos.
