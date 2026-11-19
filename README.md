# API_VINILOS

## Inicio

```sh
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

SQLAlchemy crea las tablas al iniciar FastAPI. La base SQLite `vinilos.db`
se guarda en la raíz del proyecto, independientemente del directorio de ejecución,
y conserva los datos al reiniciar. `create_all` no migra tablas existentes.
Para otra base SQLite, configura `DATABASE_URL` antes de arrancar; por ejemplo,
`DATABASE_URL=sqlite:////ruta/absoluta/pruebas.db uvicorn main:app --reload`.
La API y las pruebas usan la misma función `create_db_engine`, incluidas las FK.

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

En POST y PUT, Pydantic exige `nombre` de artista, `tipo` de género y `titulo`
de vinilo. Se rechazan omisión, NULL, cadenas vacías o solo espacios con 422.
`precio` es opcional y admite NULL o cero, pero no negativos. Son reglas de
entrada acordadas: no se modifican las columnas ni los datos históricos del DER.
Los esquemas de lectura conservan compatibilidad con esos registros históricos.

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

La tabla completa de las 15 operaciones, entradas, ejemplos JSON, relaciones,
validaciones y mensajes está en el [contrato de la API](docs/contrato-api.md).
Incluye el filtro implementado `GET /vinilos?genero_id=…`. El documento debe
revisarse con el cliente antes de la integración.

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
Los esquemas `Create`, `Update` y `Read` tienen pruebas de campos obligatorios,
límites, tipos, alias y serialización desde atributos, además de pruebas de API
para edición de las relaciones del vinilo y validación HTTP 422.

Para ejecutar solo las pruebas Pydantic, sin conexión a base de datos:

```sh
python -m unittest discover -s tests -p test_schemas.py -v
```

## Alta y consulta de artistas

El controller `controllers/artista_controller.py` implementa crear, listar y
consultar artistas. Para probarlo desde `/docs`:

1. Arranca `uvicorn main:app --reload` y abre `http://127.0.0.1:8000/docs`.
2. Ejecuta `POST /artistas` con `{"nombre": "Artista de prueba", "descripcion": "Biografía"}`.
   Devuelve 201 y el artista con su ID generado.
3. Ejecuta `GET /artistas`: el artista aparece en la lista (200).
4. Ejecuta `GET /artistas/{item_id}` con ese ID: devuelve sus datos y `vinilos: []`.
   Tras crear vinilos asociados, la ficha los incluye con el formato de `/vinilos`.
5. Repite el nombre para comprobar el duplicado (400), supera 100 caracteres
   en el nombre para comprobar la validación (422), o consulta un ID que no exista (404).

La lista de artistas, su creación y su edición conservan su respuesta simple;
solo el detalle por ID añade la lista de vinilos. La descripción es opcional;
el nombre es obligatorio en altas y ediciones.

## Edición y borrado protegido de artistas

El mismo controller implementa `PUT /artistas/{item_id}` y
`DELETE /artistas/{item_id}`:

- PUT acepta `nombre` y `descripcion` y devuelve 200 con el artista actualizado.
  Es un reemplazo completo: los campos opcionales omitidos pasan a NULL.
  Su ID no cambia y los vinilos conservan `artista_id`. Consulta ese ID en
  `/artistas/{item_id}` para obtener nombre y descripción actuales. La ficha de
  vinilo también muestra el nombre actual en el objeto `artista`.
- Un nombre perteneciente a otro artista devuelve 400 y revierte todos los
  cambios, incluida la descripción. Conservar el propio nombre está permitido.
- DELETE sin vinilos devuelve 200 y `Recurso eliminado correctamente.`.
- DELETE con vinilos devuelve 400 y
  `No se puede eliminar el recurso porque tiene vinilos asociados.`.
  La clave foránea bloquea el borrado sin eliminar ni desvincular vinilos.
- Un ID inexistente devuelve 404 en ambas operaciones; datos inválidos, 422.

En `/docs`, crea dos artistas, prueba cambiar el nombre del primero por el del
segundo y comprueba el 400. Crea un vinilo del primero, edita sus datos y consulta
su ficha para verificar la asociación. El borrado estará bloqueado hasta que
elimines o reasignes todos sus vinilos.

## CRUD de géneros

Las cinco operaciones delegan en `controllers/genero_controller.py` y están
disponibles en `/docs`:

| Método | Ruta | Entrada | Éxito |
| --- | --- | --- | --- |
| POST | `/generos` | `{"tipo": "Rock"}` | 201, género creado con `id_genero` |
| GET | `/generos` | Sin cuerpo | 200, lista ordenada por ID; `[]` si está vacía |
| GET | `/generos/{item_id}` | ID positivo | 200, `{"id_genero": 1, "tipo": "Rock"}` |
| PUT | `/generos/{item_id}` | `{"tipo": "Jazz"}` | 200, género actualizado |
| DELETE | `/generos/{item_id}` | ID positivo, sin cuerpo | 200, mensaje de eliminación |

`tipo` es obligatorio, no vacío ni solo espacios y tiene un máximo de 100
caracteres. PUT es un reemplazo completo. Los tipos duplicados al crear o
renombrar devuelven 400 y hacen rollback;
guardar el propio tipo sin cambios está permitido. Datos inválidos devuelven
422 e IDs inexistentes, 404.

Renombrar conserva el ID y todos los vínculos `genero_id`; el cliente obtiene el
tipo actual consultando ese ID. DELETE solo funciona sin vinilos: con asociaciones
devuelve 400 y `No se puede eliminar el recurso porque tiene vinilos asociados.`,
sin borrar ni desvincular ningún vinilo.

Para comprobarlo en `/docs`, crea Rock y Jazz, lista y consulta sus IDs. Intenta
renombrar Jazz a Rock (400), después a Blues (200). Crea un vinilo asociado y
comprueba que el borrado del género queda bloqueado. Tras eliminar o reasignar
todos sus vinilos, el género podrá borrarse.

## Alta de vinilos con artista y género

`POST /vinilos` delega en `controllers/vinilo_controller.py`. En `/docs`, crea
primero un artista y un género y usa sus IDs reales en este cuerpo de ejemplo:

```json
{
  "titulo": "Disco de ejemplo",
  "año": 2000,
  "precio": "12.50",
  "descripcion": "Edición de prueba",
  "artista_id": 1,
  "genero_id": 1
}
```

Devuelve 201 con los seis campos y `id_vinilo`. Se acepta también `anio` en la
entrada, pero la salida usa `año`. Comprueba el resultado en `GET /vinilos`,
`GET /vinilos/{item_id}` y la ficha del artista. Las relaciones se representan
por `artista_id` y `genero_id`; la ficha del vinilo añade `artista` y `genero`.

- Omitir o enviar NULL en cualquiera de las FK devuelve 422.
- Un artista o género inexistente devuelve 400, sin crear el vinilo ni los padres.
- Repetir `(titulo, artista_id)` devuelve 400, incluso si cambia `genero_id`.
  El mismo título con otro artista está permitido.
- Las restricciones se comprueban en la base de datos; los fallos revierten la
  operación y usan el mensaje de integridad acordado, sin detalles internos.

## Catálogo, ficha y filtro de vinilos

`controllers/vinilo_controller.py` implementa también las consultas:

- `GET /vinilos`: catálogo completo, ordenado por `id_vinilo` ascendente.
- `GET /vinilos?genero_id=1`: solo los vinilos del género seleccionado.
- `GET /vinilos/{item_id}`: ficha por ID, o 404 si el vinilo no existe.

Listado y detalle devuelven los campos del alta, incluidos `artista_id` y
`genero_id`. Solo el detalle añade `artista: {id_artista, nombre}` y
`genero: {id_genero, tipo}` (tarea 13), con los datos actuales de ambos.
El catálogo vacío, un género
sin vinilos o un género inexistente devuelven `200 []`. Un filtro vacío, decimal,
no numérico, cero o negativo devuelve 422, no el catálogo sin filtrar.

En `/docs`, crea vinilos de dos géneros, ejecuta `GET /vinilos` sin `genero_id`
y después indica uno de los IDs en ese parámetro para comprobar el filtro.
Usa el ID de uno de los resultados en la consulta de detalle.

## Edición y eliminación de vinilos

El controller de vinilos completa el CRUD con estas operaciones en `/docs`:

- `PUT /vinilos/{item_id}`: reemplaza título, año, precio, descripción,
  `artista_id` y `genero_id`, y devuelve 200 con el mismo ID. Envía las dos FK
  obligatorias y `titulo`, incluso si no cambian; los campos opcionales omitidos
  pasan a NULL.
- Las FK inexistentes y los conflictos `(titulo, artista_id)` devuelven 400 y
  revierten todos los cambios. Cambiar solo el género no evita un duplicado;
  mantener la clave propia sin cambios está permitido.
- `DELETE /vinilos/{item_id}` devuelve 200 y
  `Recurso eliminado correctamente.`. El vinilo desaparece del catálogo, filtro
  y ficha del artista. Artista, género y otros vinilos se conservan.
- Un ID inexistente devuelve 404 en PUT y DELETE. Tras eliminar el vinilo,
  consultarlo o intentar borrarlo otra vez también devuelve 404.

Para comprobarlo, crea un segundo artista y género y envía sus IDs en PUT junto
con los datos nuevos. Consulta el detalle, el catálogo, ambos filtros de género
y las fichas del artista anterior y nuevo. Después elimina el vinilo y comprueba
que sus padres siguen disponibles. Los errores de validación siguen devolviendo
422 y los fallos internos de escritura, 500 con rollback.

## Registro de comprobación del backend

Resultados HTTP esperados y obtenidos: [registro de pruebas](docs/resultados-api.md)
y [datos completos de peticiones y respuestas](docs/resultados-api.json).

Para repetir la comprobación desde la raíz del repositorio:

```sh
python -m pip install -r requirements-dev.txt
python scripts/check_api.py
python -m unittest discover -s tests -v
```

El script usa HTTPX contra un servidor Uvicorn real en un puerto local libre.
Prepara sus propios artistas, géneros y vinilos en una base SQLite temporal;
no usa ni modifica `vinilos.db`. Detiene el proceso y arranca otro con el mismo
archivo temporal para comprobar persistencia de datos y relaciones, así como
claves foráneas activas después del reinicio. Finalmente elimina solo sus datos
temporales. No requiere arrancar manualmente la API ni el frontend.

El registro contiene altas, consultas, cambios, filtros, borrados, entradas
inválidas, IDs inexistentes, duplicados, FK inexistentes, borrados bloqueados y
rollback. Se comparan códigos HTTP y cuerpos JSON; para 422 se comprueban el
mensaje y la presencia de errores de validación y se registra el cuerpo obtenido.
El comando termina con código 1 si hay discrepancias y marca las filas FALLO;
tras corregirlas, se debe repetir para actualizar la evidencia.

Los resultados actuales se consultan en el registro enlazado y en la salida de
la suite, sin mantener cifras obsoletas en este README.
La suite añade casos de error 500 simulado, rollback, CORS y restricciones desde
SQL directo; el registro HTTP no simula esos fallos internos.

Regresiones añadidas: los informes guardan copias de los datos comparados; cambiar
un diccionario después ya no altera el resultado esperado de peticiones anteriores.
Las escrituras hacen `flush`, `refresh` y validación de salida antes del commit;
un fallo en esas operaciones revierte la escritura. La respuesta de POST/PUT se
prepara en memoria y no necesita consultas ORM posteriores al commit.

El informe se regenera al repetir el script. Para conservar otra ejecución:

```sh
python scripts/check_api.py --report docs/resultados-api-segunda-ejecucion.md
```
