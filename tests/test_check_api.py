import unittest

import httpx

from scripts.check_api import Checks


class CheckReportTest(unittest.TestCase):
    def test_report_keeps_immutable_input_and_expected_snapshots(self):
        body = {"nombre": "Original", "vinilos": [{"titulo": "Original"}]}
        data = {"nombre": "Original", "nested": {"value": "Original"}}
        transport = httpx.MockTransport(lambda request: httpx.Response(201, json=body))
        checks = Checks()
        with httpx.Client(transport=transport, base_url="http://test") as client:
            checks.request(client, "Alta", "POST", "/artistas", 201, body, data)
        body["nombre"] = "Editado"
        body["vinilos"][0]["titulo"] = "Editado"
        data["nested"]["value"] = "Editado"
        result = checks.results[0]
        self.assertTrue(result["correcto"])
        self.assertEqual(result["esperado"]["body"], result["obtenido"]["body"])
        self.assertEqual(result["entrada"]["nested"]["value"], "Original")
