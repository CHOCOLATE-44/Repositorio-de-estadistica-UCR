import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from validar_apunte import Veredicto, motivo_revision_manual  # noqa: E402

CONFIG = {"publicacion": {"confianza_minima": 0.8, "exigir_carta": True}}


def veredicto(**cambios):
    v = Veredicto("apuntes/XS-2130-modelos-de-regresion-aplicados/notas.pdf", True, "ok")
    v.por_gemini, v.confianza, v.con_carta, v.es_examen, v.nuevo = True, 0.95, True, False, True
    for k, valor in cambios.items():
        setattr(v, k, valor)
    return v


class PruebasListoParaPublicar(unittest.TestCase):
    def test_listo(self):
        self.assertIsNone(motivo_revision_manual([veredicto()], [], CONFIG))

    def test_motivos_para_revisar(self):
        casos = {
            "examen": {"es_examen": True},
            "confianza": {"confianza": 0.6},
            "carta": {"con_carta": False},
            "Gemini": {"por_gemini": False},
            "existente": {"nuevo": False},
        }
        for palabra, cambio in casos.items():
            motivo = motivo_revision_manual([veredicto(**cambio)], [], CONFIG)
            self.assertIn(palabra, motivo, cambio)

    def test_otros_archivos(self):
        self.assertIsNotNone(motivo_revision_manual([veredicto()], ["sitio/app.js"], CONFIG))


if __name__ == "__main__":
    unittest.main()
