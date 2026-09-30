import importlib
import io
import json
import os
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import gemini  # noqa: E402

MODELOS = ["gemini-3.8-flash", "gemini-3.8-flash-lite", "gemini-3.7-flash", "gemini-3.7-flash-lite", "gemini-4.0-flash-preview"]
OK = json.dumps({"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}]}).encode()
CUOTA = b'{"error": {"code": 429, "message": "You exceeded your current quota", "status": "RESOURCE_EXHAUSTED"}}'
SATURADO = b'{"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}}'


class Respuesta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


def api_falsa(comportamiento, llamadas):
    """comportamiento: {modelo: 'ok' | 'cuota' | 'saturado' | 'no-existe'}"""
    def urlopen(req, timeout=0):
        url = req.full_url
        llamadas.append(url)
        if url.endswith("pageSize=200"):
            return Respuesta(json.dumps({"models": [{"name": f"models/{m}", "supportedGenerationMethods": ["generateContent"]}
                                                    for m in MODELOS]}).encode())
        modelo = url.split("/models/")[1].split(":")[0]
        estado = comportamiento.get(modelo, "no-existe" if modelo not in MODELOS else "ok")
        if estado == "ok":
            return Respuesta(OK)
        codigo, cuerpo = {"cuota": (429, CUOTA), "saturado": (503, SATURADO), "no-existe": (404, b"not found")}[estado]
        raise urllib.error.HTTPError(url, codigo, estado, {}, io.BytesIO(cuerpo))
    return urlopen


class PruebasGemini(unittest.TestCase):
    def setUp(self):
        importlib.reload(gemini)
        self.esperas = []
        self.llamadas = []
        os.environ["GEMINI_API_KEY"] = "x"
        self.parches = [mock.patch.object(gemini.time, "sleep", self.esperas.append)]
        for p in self.parches:
            p.start()

    def tearDown(self):
        for p in self.parches:
            p.stop()
        os.environ.pop("GEMINI_API_KEY", None)

    def correr(self, comportamiento, modelo="gemini-3.8-flash"):
        with mock.patch.object(gemini.urllib.request, "urlopen", api_falsa(comportamiento, self.llamadas)):
            return gemini.preguntar_json("hola", modelo)

    def test_cuota_agotada_cambia_de_modelo_sin_esperar(self):
        self.assertEqual(self.correr({"gemini-3.8-flash": "cuota"}), {"ok": True})
        self.assertEqual(self.esperas, [])
        self.assertIn("gemini-3.8-flash", gemini._sin_cuota)

    def test_sin_cuota_en_ningun_modelo_se_rinde_al_instante(self):
        todo_sin_cuota = {m: "cuota" for m in MODELOS}
        with self.assertRaisesRegex(RuntimeError, "Cuota gratuita"):
            self.correr(todo_sin_cuota)
        self.assertEqual(self.esperas, [])
        self.assertFalse(gemini.disponible())

    def test_votos_usan_modelo_lite(self):
        # «gemini-flash-lite-latest» no existe en esta API falsa → busca el lite más nuevo.
        self.assertEqual(self.correr({}, "gemini-flash-lite-latest"), {"ok": True})
        self.assertTrue(any("gemini-3.8-flash-lite:" in u for u in self.llamadas))

    def test_saturacion_sigue_reintentando(self):
        self.assertEqual(self.correr({"gemini-3.8-flash": "saturado"}), {"ok": True})
        self.assertEqual(self.esperas, [5, 10])  # tras 2 fallos cambia de modelo


if __name__ == "__main__":
    unittest.main()
