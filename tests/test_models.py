import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.database import Base, enable_foreign_keys
from models.artista import Artista
from models.genero import Genero
from models.vinilo import Vinilo


class ModelsTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.url = f"sqlite:///{Path(self.directory.name) / 'test.db'}"
        self.engine = self.make_engine()
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        artista = Artista(nombre="Artista")
        genero = Genero(tipo="Rock")
        self.session.add_all([artista, genero])
        self.session.commit()
        self.artista_id = artista.id_artista
        self.genero_id = genero.id_genero

    def make_engine(self):
        engine = create_engine(self.url)
        event.listen(engine, "connect", enable_foreign_keys)
        return engine

    def tearDown(self):
        self.session.close()
        self.engine.dispose()
        self.directory.cleanup()

    def vinilo(self, **overrides):
        values = dict(
            titulo="Disco", artista_id=self.artista_id, genero_id=self.genero_id
        )
        values.update(overrides)
        return Vinilo(**values)

    def assert_rejected(self, instance):
        self.session.add(instance)
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_foreign_keys_enabled_on_new_connections(self):
        for _ in range(2):
            self.engine.dispose()
            with self.engine.connect() as connection:
                self.assertEqual(connection.scalar(text("PRAGMA foreign_keys")), 1)

    def test_schema_matches_der(self):
        inspector = inspect(self.engine)
        expected = {
            "artista": {
                "id_artista": "INTEGER", "nombre": "VARCHAR(100)",
                "descripcion": "VARCHAR(500)",
            },
            "genero": {"id_genero": "INTEGER", "tipo": "VARCHAR(100)"},
            "vinilo": {
                "id_vinilo": "INTEGER", "titulo": "VARCHAR(150)",
                "año": "INTEGER", "precio": "DECIMAL(10, 2)",
                "descripcion": "TEXT", "artista_id": "INTEGER",
                "genero_id": "INTEGER",
            },
        }
        self.assertEqual(set(inspector.get_table_names()), set(expected))
        for table, columns in expected.items():
            with self.subTest(table=table):
                actual = inspector.get_columns(table)
                self.assertEqual(
                    {column["name"]: str(column["type"]) for column in actual},
                    columns,
                )
                self.assertEqual(
                    inspector.get_pk_constraint(table)["constrained_columns"],
                    [f"id_{table}"],
                )
                for column in actual:
                    required = column["name"] in (
                        f"id_{table}", "artista_id", "genero_id"
                    )
                    self.assertEqual(column["nullable"], not required)
        for table, columns in (
            ("artista", ["nombre"]), ("genero", ["tipo"]),
            ("vinilo", ["titulo", "artista_id"]),
        ):
            self.assertEqual(
                [item["column_names"] for item in inspector.get_unique_constraints(table)],
                [columns],
            )
        foreign_keys = inspector.get_foreign_keys("vinilo")
        self.assertEqual(len(foreign_keys), 2)
        for fk in foreign_keys:
            parent = fk["referred_table"]
            self.assertIn(parent, ("artista", "genero"))
            self.assertEqual(fk["constrained_columns"], [f"{parent}_id"])
            self.assertEqual(fk["referred_columns"], [f"id_{parent}"])
            self.assertEqual(fk["options"]["ondelete"], "RESTRICT")

    def test_artist_and_genre_can_exist_without_vinilos(self):
        artista = self.session.get(Artista, self.artista_id)
        genero = self.session.get(Genero, self.genero_id)
        self.assertEqual(artista.vinilos, [])
        self.assertEqual(genero.vinilos, [])

    def test_artist_and_genre_can_have_multiple_vinilos(self):
        self.session.add_all([self.vinilo(), self.vinilo(titulo="Otro disco")])
        self.session.commit()
        artista = self.session.get(Artista, self.artista_id)
        genero = self.session.get(Genero, self.genero_id)
        self.assertEqual(len(artista.vinilos), 2)
        self.assertEqual(len(genero.vinilos), 2)
        for vinilo in artista.vinilos:
            self.assertIs(vinilo.artista, artista)
            self.assertIs(vinilo.genero, genero)

    def test_updates_cannot_break_foreign_keys_or_uniqueness(self):
        vinilo = self.vinilo()
        other = self.vinilo(titulo="Otro disco")
        self.session.add_all([vinilo, other])
        self.session.commit()
        for field in ("artista_id", "genero_id"):
            for value in (None, 9999):
                with self.subTest(field=field, value=value):
                    setattr(vinilo, field, value)
                    with self.assertRaises(IntegrityError):
                        self.session.commit()
                    self.session.rollback()
        other.titulo = "Disco"
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_vinilo_requires_existing_artista_and_genero(self):
        for field in ("artista_id", "genero_id"):
            for value in (None, 9999):
                with self.subTest(field=field, value=value):
                    self.assert_rejected(self.vinilo(**{field: value}))

    def test_defined_duplicates_are_rejected(self):
        self.assert_rejected(Artista(nombre="Artista"))
        self.assert_rejected(Genero(tipo="Rock"))
        self.session.add(self.vinilo())
        self.session.commit()
        self.assert_rejected(self.vinilo())

    def test_same_title_is_allowed_for_different_artists(self):
        other = Artista(nombre="Otro")
        self.session.add(other)
        self.session.flush()
        self.session.add_all([self.vinilo(), self.vinilo(artista_id=other.id_artista)])
        self.session.commit()

    def test_linked_parents_cannot_be_deleted(self):
        self.session.add(self.vinilo())
        self.session.commit()
        for model, pk in ((Artista, self.artista_id), (Genero, self.genero_id)):
            for loaded in (False, True):
                with self.subTest(model=model.__name__, loaded=loaded):
                    parent = self.session.get(model, pk)
                    if loaded:
                        list(parent.vinilos)
                    self.session.delete(parent)
                    with self.assertRaises(IntegrityError):
                        self.session.commit()
                    self.session.rollback()

    def test_raw_sql_cannot_bypass_foreign_keys_or_delete_restrictions(self):
        self.session.add(self.vinilo())
        self.session.commit()
        statements = (
            "INSERT INTO vinilo (artista_id, genero_id) VALUES (9999, 9999)",
            "DELETE FROM artista",
            "DELETE FROM genero",
        )
        for statement in statements:
            with self.subTest(statement=statement):
                with self.engine.begin() as connection:
                    with self.assertRaises(IntegrityError):
                        connection.execute(text(statement))

    def test_unlinked_parents_can_be_deleted(self):
        self.session.delete(self.session.get(Artista, self.artista_id))
        self.session.delete(self.session.get(Genero, self.genero_id))
        self.session.commit()

    def test_data_and_relationships_survive_engine_restart(self):
        self.session.add(self.vinilo())
        self.session.commit()
        self.session.close()
        self.engine.dispose()
        self.engine = self.make_engine()
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as session:
            vinilo = session.scalars(select(Vinilo)).one()
            self.assertEqual(vinilo.artista.nombre, "Artista")
            self.assertEqual(vinilo.genero.tipo, "Rock")


if __name__ == "__main__":
    unittest.main()
