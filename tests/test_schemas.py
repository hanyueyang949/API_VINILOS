import json
import unittest
from decimal import Decimal
from types import SimpleNamespace

from pydantic import ValidationError

from schemas.artista import ArtistaCreate, ArtistaRead, ArtistaUpdate
from schemas.genero import GeneroCreate, GeneroRead, GeneroUpdate
from schemas.vinilo import ViniloCreate, ViniloRead, ViniloUpdate


class SchemasTest(unittest.TestCase):
    def test_text_limits_for_create_and_update(self):
        for schema, field, limit in (
            (ArtistaCreate, "nombre", 100), (ArtistaUpdate, "nombre", 100),
            (ArtistaCreate, "descripcion", 500), (ArtistaUpdate, "descripcion", 500),
            (GeneroCreate, "tipo", 100), (GeneroUpdate, "tipo", 100),
            (ViniloCreate, "titulo", 150), (ViniloUpdate, "titulo", 150),
        ):
            with self.subTest(schema=schema.__name__, field=field):
                if schema in (ViniloCreate, ViniloUpdate):
                    data = {"titulo": "Disco", "artista_id": 1, "genero_id": 2}
                elif schema in (ArtistaCreate, ArtistaUpdate):
                    data = {"nombre": "Artista"}
                else:
                    data = {"tipo": "Rock"}
                self.assertEqual(getattr(schema(**dict(data, **{field: "x" * limit})), field), "x" * limit)
                for invalid in ("x" * (limit + 1), 42, [], {}):
                    with self.assertRaises(ValidationError):
                        schema(**dict(data, **{field: invalid}))

    def test_required_vinilo_foreign_keys(self):
        for schema in (ViniloCreate, ViniloUpdate):
            for field in ("artista_id", "genero_id"):
                with self.subTest(schema=schema.__name__, field=field):
                    values = {"titulo": "Disco", "artista_id": 1, "genero_id": 2}
                    del values[field]
                    with self.assertRaises(ValidationError):
                        schema(**values)
                    for invalid in (None, 0, -1, "1", True, 1.5, 1.0, [], {}):
                        with self.assertRaises(ValidationError):
                            schema(**dict(values, **{field: invalid}))

    def test_optional_fields_follow_der_and_put_replacement(self):
        for schema in (ArtistaCreate, ArtistaUpdate):
            self.assertEqual(schema(nombre="Artista").model_dump(), {"nombre": "Artista", "descripcion": None})
        for schema in (GeneroCreate, GeneroUpdate):
            self.assertEqual(schema(tipo="Rock").model_dump(), {"tipo": "Rock"})
        for schema in (ViniloCreate, ViniloUpdate):
            data = schema(titulo="Disco", artista_id=1, genero_id=2).model_dump()
            self.assertEqual(data, {
                "titulo": "Disco", "anio": None, "precio": None,
                "descripcion": None, "artista_id": 1, "genero_id": 2,
            })

    def test_price_precision_and_year_aliases(self):
        for schema in (ViniloCreate, ViniloUpdate):
            for price in ("99999999.99", "0.01", "0", 12.5, None):
                schema(titulo="Disco", artista_id=1, genero_id=2, precio=price)
            for price in ("-0.01", "-12.50", "100000000.00", "1.001", "NaN", "Infinity", "invalid", True):
                with self.assertRaises(ValidationError):
                    schema(titulo="Disco", artista_id=1, genero_id=2, precio=price)
            for alias in ("año", "anio"):
                value = schema(titulo="Disco", artista_id=1, genero_id=2, **{alias: 2000})
                self.assertEqual(value.anio, 2000)
                self.assertEqual(value.model_dump(by_alias=True)["año"], 2000)
            for year in ("2000", True, 2000.5):
                with self.assertRaises(ValidationError):
                    schema(titulo="Disco", artista_id=1, genero_id=2, anio=year)
            with self.assertRaises(ValidationError):
                schema(titulo="Disco", artista_id=1, genero_id=2, anio=2000, **{"año": 2000})

    def test_inputs_reject_ids_unknown_fields_and_nested_relations(self):
        for schema, pk, values in (
            (ArtistaCreate, "id_artista", {"nombre": "Artista"}), (ArtistaUpdate, "id_artista", {"nombre": "Artista"}),
            (GeneroCreate, "id_genero", {"tipo": "Rock"}), (GeneroUpdate, "id_genero", {"tipo": "Rock"}),
            (ViniloCreate, "id_vinilo", {"titulo": "Disco", "artista_id": 1, "genero_id": 2}),
            (ViniloUpdate, "id_vinilo", {"titulo": "Disco", "artista_id": 1, "genero_id": 2}),
        ):
            for field in (pk, "unknown", "artista", "genero", "vinilos"):
                with self.subTest(schema=schema.__name__, field=field):
                    with self.assertRaises(ValidationError):
                        schema(**dict(values, **{field: 1}))

    def test_required_text_is_not_null_empty_or_whitespace(self):
        for schema, field, values in (
            (ArtistaCreate, "nombre", {}), (ArtistaUpdate, "nombre", {}),
            (GeneroCreate, "tipo", {}), (GeneroUpdate, "tipo", {}),
            (ViniloCreate, "titulo", {"artista_id": 1, "genero_id": 2}),
            (ViniloUpdate, "titulo", {"artista_id": 1, "genero_id": 2}),
        ):
            with self.subTest(schema=schema.__name__):
                with self.assertRaises(ValidationError):
                    schema(**values)
                for value in (None, "", " ", "\t\n", "\u2003"):
                    with self.assertRaises(ValidationError):
                        schema(**dict(values, **{field: value}))

    def test_output_from_attributes_uses_contract_representation(self):
        # Objetos con atributos: la validación de salida no necesita una conexión.
        artista = SimpleNamespace(id_artista=1, nombre="Artista", descripcion=None)
        genero = SimpleNamespace(id_genero=2, tipo="Rock")
        vinilo = SimpleNamespace(
            id_vinilo=3, titulo="Disco", anio=2000, precio=Decimal("12.50"),
            descripcion=None, artista_id=1, genero_id=2, artista=artista, genero=genero,
        )
        self.assertEqual(ArtistaRead.model_validate(artista).model_dump(), {
            "id_artista": 1, "nombre": "Artista", "descripcion": None,
        })
        self.assertEqual(GeneroRead.model_validate(genero).model_dump(), {
            "id_genero": 2, "tipo": "Rock",
        })
        self.assertEqual(json.loads(ViniloRead.model_validate(vinilo).model_dump_json(by_alias=True)), {
            "id_vinilo": 3, "titulo": "Disco", "año": 2000, "precio": "12.50",
            "descripcion": None, "artista_id": 1, "genero_id": 2,
        })

    def test_output_primary_keys_are_required_and_positive(self):
        for schema, pk, values in (
            (ArtistaRead, "id_artista", {}), (GeneroRead, "id_genero", {}),
            (ViniloRead, "id_vinilo", {"artista_id": 1, "genero_id": 2}),
        ):
            with self.assertRaises(ValidationError):
                schema(**values)
            for invalid in (None, 0, -1, "1", True):
                with self.assertRaises(ValidationError):
                    schema(**dict(values, **{pk: invalid}))
