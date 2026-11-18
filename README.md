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

## Pruebas

```sh
python -m unittest discover -s tests -v
```

Las pruebas utilizan bases temporales y verifican claves foráneas, duplicados,
borrados restringidos, relaciones y persistencia al recrear el motor.
