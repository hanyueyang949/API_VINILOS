import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

import main
from config.config_variables import CORS_ORIGINS
from database.database import Base, enable_foreign_keys, get_db


class APITest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.engine = create_engine(
            f"sqlite:///{Path(self.directory.name) / 'api.db'}",
            connect_args={"check_same_thread": False},
        )
        event.listen(self.engine, "connect", enable_foreign_keys)
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
        with patch("routes.routes.list_items", side_effect=RuntimeError("secret internal details")):
            response = self.client.get("/artistas", headers={"Origin": self.origin})
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("secret", response.text)
        self.assertEqual(response.headers["access-control-allow-origin"], self.origin)
