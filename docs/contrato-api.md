# Contrato de la API de vinilos

Contrato con las reglas de entrada y la ficha de vinilo confirmadas.
Basado en el [DER](../1233333.png), los esquemas de validación y las rutas actuales.

## Convenciones

- URL base local: `http://127.0.0.1:8000`.
- Rutas en plural, sin barra final y sin prefijo `/api`.
- Cuerpos y respuestas JSON; enviar `Content-Type: application/json`.
- Los IDs son enteros positivos generados por el servidor, no se envían en el cuerpo.
- Las listas son arrays sin envoltorio ni paginación, ordenados por ID ascendente.
  Sin resultados se devuelve `200 []`, no 404.
- POST crea; PUT reemplaza todos los campos editables. Los opcionales omitidos se
  guardan como NULL. No se define PATCH ni edición parcial.
- Las respuestas incluyen los campos opcionales con `null` cuando no tienen valor.
- No se exige autenticación en esta versión. La configuración CORS está en el
  [README](../README.md#cliente-web-y-cors).

## Entradas y validaciones

Los nombres `ArtistaEntrada`, `GeneroEntrada` y `ViniloEntrada` de la tabla de
rutas se refieren a los siguientes cuerpos JSON, iguales para POST y PUT.
No se admiten campos desconocidos, claves primarias ni objetos relacionados en
las entradas.

Los esquemas Pydantic distinguen cada operación aunque POST y PUT compartan las
reglas de los campos (PUT no es parcial):

| Entidad | Creación | Actualización PUT | Respuesta |
| --- | --- | --- | --- |
| Artista | `ArtistaCreate` | `ArtistaUpdate` | `ArtistaRead`; `ArtistaDetail` en consulta por ID |
| Género | `GeneroCreate` | `GeneroUpdate` | `GeneroRead` |
| Vinilo | `ViniloCreate` | `ViniloUpdate` | `ViniloRead`; `ViniloDetail` en consulta por ID |

Los esquemas `Read` se construyen desde los modelos ORM con `from_attributes=True`.
Las claves primarias solo aparecen en las salidas. En Vinilo, tanto Create como
Update exigen `artista_id` y `genero_id` y permiten cambiarlos por otros existentes.
La existencia y la unicidad se comprueban en la base de datos (400), no en Pydantic.

| Cuerpo | Campo | Tipo JSON | Regla |
| --- | --- | --- | --- |
| ArtistaEntrada | `nombre` | string | Obligatorio, no vacío ni solo espacios, máximo 100 caracteres; único |
| ArtistaEntrada | `descripcion` | string o null | Opcional, máximo 500 caracteres |
| GeneroEntrada | `tipo` | string | Obligatorio, no vacío ni solo espacios, máximo 100 caracteres; único |
| ViniloEntrada | `titulo` | string | Obligatorio, no vacío ni solo espacios, máximo 150 caracteres |
| ViniloEntrada | `año` | integer o null | Opcional; también se admite `anio` como alias de entrada |
| ViniloEntrada | `precio` | string decimal, number o null | Opcional, mayor o igual a cero, hasta 10 dígitos totales y 2 decimales |
| ViniloEntrada | `descripcion` | string o null | Opcional, texto sin límite adicional definido |
| ViniloEntrada | `artista_id` | integer | Obligatorio, positivo y debe existir |
| ViniloEntrada | `genero_id` | integer | Obligatorio, positivo y debe existir |

Enviar preferentemente `precio` como cadena decimal para evitar imprecisiones del
cliente. Enviar solo una de las claves `año`/`anio`. La salida siempre usa `año`.
En el cuerpo JSON, año y claves foráneas exigen enteros reales: no se convierten
cadenas, booleanos ni números decimales a enteros; esas entradas producen 422.
Omitir `nombre`, `tipo` o `titulo`, enviarlos nulos, vacíos o con solo espacios
devuelve 422. `precio` admite cero, NULL u omisión; los negativos devuelven 422.
No se limita el rango del año ni se normalizan los espacios, mayúsculas o
minúsculas del texto aceptado. Los límites de longitud se aplican al texto recibido.

La unicidad del vinilo es **compuesta**: `(titulo, artista_id)`.
Dos artistas pueden tener un disco con el mismo título y un artista puede tener
varios discos con títulos distintos. El género no forma parte de esta clave.
Estas son validaciones de entrada de la API: no se modifica el DER ni se migran
registros existentes. Los esquemas de lectura admiten los NULL y precios negativos
históricos que permite la base, para no convertir consultas existentes en errores
500; al editarlos hay que proporcionar los campos obligatorios y un precio válido.

## Tabla de rutas

`id` es un parámetro de ruta entero positivo. `Artista`, `Genero` y `Vinilo`
son los objetos de respuesta definidos en la sección siguiente. Los errores
compartidos y sus cuerpos exactos se detallan al final.

| Método | Ruta | Entradas | Respuesta de éxito | Errores previstos |
| --- | --- | --- | --- | --- |
| POST | `/artistas` | Cuerpo ArtistaEntrada | 201, Artista creado | 400 duplicado; 422; 500 |
| GET | `/artistas` | Ninguna | 200, Artista[] | 500 |
| GET | `/artistas/{id}` | id | 200, ArtistaDetail con `vinilos` | 404; 422; 500 |
| PUT | `/artistas/{id}` | id y ArtistaEntrada | 200, Artista actualizado | 400 duplicado; 404; 422; 500 |
| DELETE | `/artistas/{id}` | id, sin cuerpo | 200, mensaje de eliminación | 400 borrado bloqueado; 404; 422; 500 |
| POST | `/generos` | Cuerpo GeneroEntrada | 201, Genero creado | 400 duplicado; 422; 500 |
| GET | `/generos` | Ninguna | 200, Genero[] | 500 |
| GET | `/generos/{id}` | id | 200, Genero | 404; 422; 500 |
| PUT | `/generos/{id}` | id y GeneroEntrada | 200, Genero actualizado | 400 duplicado; 404; 422; 500 |
| DELETE | `/generos/{id}` | id, sin cuerpo | 200, mensaje de eliminación | 400 borrado bloqueado; 404; 422; 500 |
| POST | `/vinilos` | Cuerpo ViniloEntrada | 201, Vinilo creado | 400 duplicado o FK inexistente; 422; 500 |
| GET | `/vinilos` | Query opcional `genero_id` | 200, Vinilo[] | 422 para filtro inválido; 500 |
| GET | `/vinilos/{id}` | id | 200, ViniloDetail con artista y género | 404; 422; 500 |
| PUT | `/vinilos/{id}` | id y ViniloEntrada | 200, Vinilo actualizado | 400 duplicado o FK inexistente; 404; 422; 500 |
| DELETE | `/vinilos/{id}` | id, sin cuerpo | 200, mensaje de eliminación | 404; 422; 500 |

## Filtro de vinilos por género

Ruta implementada: `GET /vinilos?genero_id=2`.

- Sin `genero_id`: devuelve todos los vinilos.
- Con un entero positivo: devuelve solo los vinilos cuyo `genero_id` coincide,
  en el mismo formato JSON y orden que el listado sin filtro.
- Género existente sin vinilos o género inexistente: `200 []`. El filtro busca
  coincidencias, no consulta un recurso por ID.
- Valor vacío, texto, decimal, cero o negativo: `422`, con ubicación
  `["query", "genero_id"]` en `errors`.

El filtro está implementado en `controllers/vinilo_controller.py` y validado por
el esquema de query `ViniloFilter`. Se declara como parámetro opcional en `/docs`
y `/openapi.json`. El listado usa `ViniloRead` y el detalle `ViniloDetail`.

## Representación JSON y relaciones

Artista (respuesta de crear y editar; cada elemento del listado):

```json
{
  "id_artista": 1,
  "nombre": "Artista de ejemplo",
  "descripcion": null
}
```

La consulta `GET /artistas/{id}` devuelve además `vinilos`, con los mismos objetos
de salida que `/vinilos`. Si no tiene asociados, devuelve una lista vacía:

```json
{
  "id_artista": 1,
  "nombre": "Artista de ejemplo",
  "descripcion": null,
  "vinilos": []
}
```

Si tiene vinilos, por ejemplo:

```json
{
  "id_artista": 1,
  "nombre": "Artista de ejemplo",
  "descripcion": null,
  "vinilos": [
    {
      "id_vinilo": 3,
      "titulo": "Disco de ejemplo",
      "año": 2000,
      "precio": "12.50",
      "descripcion": null,
      "artista_id": 1,
      "genero_id": 2
    }
  ]
}
```

Género:

```json
{
  "id_genero": 2,
  "tipo": "Rock"
}
```

Vinilo en listado, creación y edición (`ViniloRead`):

```json
{
  "id_vinilo": 3,
  "titulo": "Disco de ejemplo",
  "año": 2000,
  "precio": "12.50",
  "descripcion": null,
  "artista_id": 1,
  "genero_id": 2
}
```

La ficha `GET /vinilos/3` conserva todos los campos anteriores y añade las
relaciones actuales (`ViniloDetail`, tarea 13):

```json
{
  "id_vinilo": 3,
  "titulo": "Disco de ejemplo",
  "año": 2000,
  "precio": "12.50",
  "descripcion": null,
  "artista_id": 1,
  "genero_id": 2,
  "artista": {"id_artista": 1, "nombre": "Artista de ejemplo"},
  "genero": {"id_genero": 2, "tipo": "Rock"}
}
```

Los listados (con y sin filtro), POST y PUT mantienen las relaciones por ID sin
anidar objetos. Solo GET por ID añade `artista` y `genero`, sin listas inversas
ni descripciones. La ficha del artista incluye `vinilos` en formato `ViniloRead`;
el listado de artistas, su creación y su edición no incluyen esa lista.

`precio` se devuelve como cadena decimal (o null), no como número flotante.
Los ejemplos suponen que los recursos relacionados existen; los IDs generados
no tienen por qué empezar por estos valores.

## Códigos y mensajes

Crear y editar devuelven el objeto resultante, sin mensaje adicional. Consultar
devuelve el objeto y listar devuelve un array. Eliminar devuelve exactamente:

```json
{"detail": "Recurso eliminado correctamente."}
```

| Situación | HTTP | Valor exacto de `detail` |
| --- | --- | --- |
| Creación correcta | 201 | No hay `detail`: se devuelve el objeto creado |
| Lista, detalle o edición correctos | 200 | No hay `detail`: se devuelven los datos |
| Eliminación correcta | 200 | `Recurso eliminado correctamente.` |
| Datos inválidos, JSON mal formado, ID o filtro de tipo/rango inválido | 422 | `Datos de entrada no válidos.` |
| Recurso solicitado por ID no existe (GET, PUT o DELETE) | 404 | `Recurso no encontrado.` |
| Nombre/tipo duplicado o combinación título-artista duplicada | 400 | `No se pudo guardar: hay datos duplicados o referencias no válidas.` |
| FK positiva pero inexistente al crear o editar vinilo | 400 | `No se pudo guardar: hay datos duplicados o referencias no válidas.` |
| Artista o género con vinilos asociados al borrar | 400 | `No se puede eliminar el recurso porque tiene vinilos asociados.` |
| Fallo interno al guardar | 500 | `No se pudo guardar el recurso. Inténtalo más tarde.` |
| Fallo interno al eliminar | 500 | `No se pudo eliminar el recurso. Inténtalo más tarde.` |
| Otro error interno | 500 | `Error interno del servidor. Inténtalo más tarde.` |

El contrato conserva 400 para conflictos de integridad, no introduce 409.
Una FK ausente o nula es un error de validación 422; una FK con formato válido
pero sin registro asociado es un error de integridad 400.
Un ID inexistente produce 404 cuando la entrada es válida; si la petición también
tiene errores de validación, FastAPI puede devolver primero 422.

Error de validación (ejemplo: falta `genero_id`):

```json
{
  "detail": "Datos de entrada no válidos.",
  "errors": [
    {"loc": ["body", "genero_id"], "type": "missing"}
  ]
}
```

`errors` contiene ubicación (`body`, `path` o `query` y el campo afectado) y tipo
de cada fallo. No reproduce valores recibidos ni contexto interno. Los demás
errores solo contienen `detail`:

```json
{"detail": "Recurso no encontrado."}
```

No hay borrado en cascada de artistas/géneros. Pueden existir sin vinilos y solo
se pueden eliminar si no tienen ninguno. Eliminar un vinilo no elimina su artista
ni su género. Los fallos de escritura hacen rollback; los errores no exponen SQL,
credenciales ni trazas.

### Edición de artistas y conservación de asociaciones

`PUT /artistas/{id}` modifica el registro existente, nunca lo reemplaza por un
artista con otro ID. Actualiza `nombre` y `descripcion` según las reglas de PUT.
Los vinilos mantienen `artista_id`: al resolver esa referencia mediante
`GET /artistas/{id}`, el cliente obtiene los datos actualizados y los mismos
vinilos asociados. La ficha de vinilo muestra el nombre actual en `artista`;
la descripción se consulta en la ficha de artista, sin duplicarla en cada vinilo.

Cambiar el nombre por uno de otro artista devuelve el 400 de duplicados y
revierte todos los cambios; mantener el propio nombre no es un conflicto.
DELETE usa la restricción de la base de datos para bloquear artistas con vinilos,
sin cascadas, también ante escrituras concurrentes. Tras eliminar o reasignar
todos sus vinilos puede borrarse. Repetir un borrado exitoso devuelve 404.

## Comprobación antes de conectar el cliente

La edición y eliminación de vinilos están implementadas en
`controllers/vinilo_controller.py`. PUT guarda los datos y ambas relaciones en
una única operación, sin cambiar `id_vinilo`. Las FK deben existir y la combinación
`(titulo, artista_id)` no puede pertenecer a otro vinilo; el propio registro no
se considera un duplicado. Los conflictos devuelven el 400 de integridad y hacen
rollback completo. Los cambios se reflejan en detalle, catálogo, filtro por
género y fichas de artistas. DELETE elimina solo el vinilo y devuelve el mensaje
200 acordado; el artista y género se conservan. Una consulta posterior al ID o
un nuevo intento de borrarlo devuelve 404. PUT sobre un ID inexistente también
devuelve 404 con una entrada válida.

El alta de vinilos está implementada en `controllers/vinilo_controller.py`.
Guarda título, año, precio, descripción y ambas FK en una operación. Las FK
obligatorias y la clave compuesta `(titulo, artista_id)` están protegidas por la
base de datos: cambiar solo el género no permite repetir un título del mismo
artista. Un alta inválida no crea artistas, géneros ni vinilos parciales. Un alta
válida devuelve 201 y aparece en el listado, el detalle y la ficha de su artista,
con las relaciones por ID descritas en este contrato.

El CRUD de géneros está implementado en `controllers/genero_controller.py`.
Renombrar `tipo` conserva `id_genero` y las FK de sus vinilos; la salida de vinilo
sigue usando `genero_id` y la ficha añade el tipo actual en `genero`. Los duplicados
en POST y PUT devuelven el 400 de integridad; guardar el propio tipo está permitido.
DELETE protege los géneros asociados mediante la FK y devuelve el mensaje de
borrado bloqueado, sin cascadas. Una vez eliminados o reasignados todos sus vinilos,
se puede borrar el género. Estas cinco operaciones están disponibles en `/docs`.

- Revisar con el frontend esta propuesta y confirmar su origen local.
- Verificar con el cliente el filtro `genero_id`, incluidos validación y lista vacía.
- Mantener este contrato, los esquemas y `/openapi.json` alineados. `/docs`
  describe las rutas ejecutables, pero todavía no detalla todos los cuerpos de
  error personalizados.
- Ejecutar `python -m unittest discover -s tests -v` con las dependencias de
  `requirements-dev.txt` instaladas.
