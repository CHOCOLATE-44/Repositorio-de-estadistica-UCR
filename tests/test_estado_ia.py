import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import estado_ia  # noqa: E402
from comun import cargar_config  # noqa: E402


class PruebasEstadoIA(unittest.TestCase):
    def test_suma_en_el_mismo_dia(self):
        t = datetime(2026, 10, 2, 15, 0, tzinfo=timezone.utc)  # 08:00 en el Pacífico
        e = estado_ia.combinar({}, {"m": 3}, set(), t)
        e = estado_ia.combinar(e, {"m": 2, "otro": 1}, {"otro"}, t)
        self.assertEqual(e["consultas"], {"m": 5, "otro": 1})
        self.assertEqual(e["agotados"], ["otro"])

    def test_se_reinicia_a_medianoche_del_pacifico(self):
        antes = datetime(2026, 10, 2, 6, 59, tzinfo=timezone.utc)   # 23:59 PDT del día 1
        despues = datetime(2026, 10, 2, 7, 1, tzinfo=timezone.utc)  # 00:01 PDT del día 2
        e = estado_ia.combinar({}, {"m": 9}, {"m"}, antes)
        self.assertEqual(e["reinicio"], "2026-10-02T07:00:00+00:00")  # 1:00 a. m. en Costa Rica
        e = estado_ia.combinar(e, {}, set(), despues)
        self.assertEqual((e["consultas"], e["agotados"]), ({}, []))

    def test_cuerpo_guarda_los_datos_y_muestra_semaforo(self):
        config = cargar_config()
        modelo = config["validacion"]["gemini_modelo"]
        limite = config["ia"]["limites_diarios"][modelo]
        e = estado_ia.combinar({}, {modelo: limite}, set(), datetime(2026, 10, 2, 15, tzinfo=timezone.utc))
        texto = estado_ia.cuerpo(e, config)
        self.assertIn(f"{limite} de {limite}", texto)
        self.assertIn("🟡", texto)
        self.assertIn("01:00", texto)  # hora de Costa Rica
        self.assertEqual(json.loads(estado_ia.DATOS.search(texto).group(1)), e)

    def test_usos_agrupa_por_modelo(self):
        config = {"validacion": {"gemini_modelo": "a", "gemini_modelo_votos": "a", "gemini_modelo_preguntas": "b"}}
        self.assertEqual(estado_ia.usos(config), [("a", "Validar apuntes y Revisar votos"), ("b", "Responder preguntas")])


if __name__ == "__main__":
    unittest.main()
