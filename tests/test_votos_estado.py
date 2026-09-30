import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import votos  # noqa: E402

RUTA = "apuntes/XS-2130-modelos-de-regresion-aplicados/notas.pdf"


class GitHubFalso:
    repo = "o/r"

    def __init__(self):
        self.parches, self.cerrados, self.comentarios = [], [], []

    def comentar(self, n, texto, marcador=None):
        self.comentarios.append(texto)

    def poner_etiquetas(self, *a, **k):
        pass

    def patch(self, ruta, datos):
        self.parches.append(datos)

    def cerrar_issue(self, n, motivo="completed"):
        self.cerrados.append(motivo)


def procesar(justificacion, estado):
    cuerpo = (f"### Apunte\n\n{RUTA}\n\n### Puntuación\n\n5 — Excelente\n\n### Justificación\n\n{justificacion}")
    issue = {"number": 17, "state": estado, "title": "Voto: x", "html_url": "u", "created_at": "2026-01-01T00:00:00Z",
             "user": {"login": "ana"}, "labels": [{"name": "voto"}], "body": cuerpo}
    gh = GitHubFalso()
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({"issue": issue}, f)
    with mock.patch.object(votos, "GitHub", return_value=gh), \
         mock.patch.object(votos, "_rutas_existentes", return_value={RUTA: {"ruta": RUTA, "autor_login": "beto"}}), \
         mock.patch.object(votos, "revisar_justificacion_gemini", return_value=None):
        votos.procesar_evento(f.name)
    return gh


class PruebasEstadoIssue(unittest.TestCase):
    def test_rechazado_queda_abierto(self):
        gh = procesar("es prueba", "open")
        self.assertEqual(gh.cerrados, [])
        self.assertIn("todavía no cuenta", gh.comentarios[-1])

    def test_rechazado_cerrado_se_reabre(self):
        gh = procesar("es prueba", "closed")
        self.assertIn({"state": "open"}, gh.parches)

    def test_valido_se_cierra(self):
        gh = procesar("Resume muy bien MCO, supuestos e inferencia, ordenado por temas y con ejemplos claros.", "open")
        self.assertEqual(gh.cerrados, ["completed"])


if __name__ == "__main__":
    unittest.main()
