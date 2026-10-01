import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from comun import cargar_config, cargar_cursos, curso_por_carpeta, leer_formulario, normalizar_texto, slug  # noqa: E402
from validar_apunte import puntuar_curso  # noqa: E402
from votos import extraer_voto, problemas_basicos  # noqa: E402

RUTA = "apuntes/XS-2130-modelos-de-regresion-aplicados/notas.pdf"


def issue(cuerpo, usuario="ana"):
    return {"number": 1, "html_url": "u", "user": {"login": usuario}, "created_at": "2026-01-01T00:00:00Z", "body": cuerpo}


def cuerpo(apunte=RUTA, punt="4 — Muy bueno", just="Muy claro y ordenado, incluye ejemplos resueltos en R de cada tema y buen resumen de supuestos."):
    return f"### Apunte\n\n{apunte}\n\n### Puntuación\n\n{punt}\n\n### Justificación\n\n{just}\n\n### Confirmación\n\n- [X] Leí"


class PruebasCatalogo(unittest.TestCase):
    def test_carpetas_existen_y_son_unicas(self):
        cursos = cargar_cursos()
        raiz = Path(__file__).resolve().parent.parent
        self.assertEqual(len({c["carpeta"] for c in cursos}), len(cursos))
        for c in cursos:
            self.assertTrue((raiz / "apuntes" / c["carpeta"]).is_dir(), c["carpeta"])
            self.assertTrue(c["carpeta"].startswith(c["sigla"] + "-"))

    def test_sin_cursos_excluidos(self):
        nombres = " ".join(normalizar_texto(c["nombre"]) for c in cargar_cursos())
        for excluido in ("precalculo", "optativ", "humanidades", "repertorio", "actividad deportiva", "seminario de realidad"):
            self.assertNotIn(excluido, nombres)

    def test_plantillas_sincronizadas(self):
        raiz = Path(__file__).resolve().parent.parent
        plantilla = (raiz / ".github/ISSUE_TEMPLATE/subir-apunte.yml").read_text(encoding="utf-8")
        for c in cargar_cursos():
            self.assertIn(c["sigla"], plantilla, "Ejecuta scripts/generar_plantillas.py")


class PruebasVotos(unittest.TestCase):
    def setUp(self):
        self.config = cargar_config()
        self.rutas = {RUTA: {"ruta": RUTA, "autor_login": "beto"}}

    def test_formulario(self):
        campos = leer_formulario(cuerpo())
        self.assertEqual(campos["apunte"], RUTA)
        self.assertEqual(campos["puntuacion"], "4 — Muy bueno")

    def test_voto_valido(self):
        v = extraer_voto(issue(cuerpo()))
        self.assertEqual(v["puntuacion"], 4)
        self.assertEqual(problemas_basicos(v, self.rutas, self.config), [])

    def test_justificacion_corta(self):
        v = extraer_voto(issue(cuerpo(just="Me gustó")))
        self.assertTrue(problemas_basicos(v, self.rutas, self.config))

    def test_justificacion_relleno(self):
        v = extraer_voto(issue(cuerpo(just="bueno bueno bueno bueno bueno bueno bueno bueno bueno bueno bueno")))
        self.assertTrue(problemas_basicos(v, self.rutas, self.config))

    def test_apunte_inexistente(self):
        v = extraer_voto(issue(cuerpo(apunte="apuntes/x/y.pdf")))
        self.assertTrue(problemas_basicos(v, self.rutas, self.config))

    def test_autovoto(self):
        v = extraer_voto(issue(cuerpo(), usuario="Beto"))
        self.assertIn("No puede puntuar sus propios apuntes.", problemas_basicos(v, self.rutas, self.config))

    def test_url_pegada(self):
        v = extraer_voto(issue(cuerpo(apunte=f"https://github.com/o/r/blob/main/{RUTA}")))
        self.assertEqual(v["ruta"], RUTA)


class PruebasHeuristica(unittest.TestCase):
    def test_regresion(self):
        curso = curso_por_carpeta("XS-2130-modelos-de-regresion-aplicados")
        texto = normalizar_texto("Apuntes XS-2130 Modelos de Regresión Aplicados. Regresión lineal por mínimos "
                                 "cuadrados, análisis de residuos, multicolinealidad y heterocedasticidad.")
        puntos, _ = puntuar_curso(texto, curso)
        self.assertGreaterEqual(puntos, cargar_config()["validacion"]["umbral_heuristico"])

    def test_texto_ajeno(self):
        curso = curso_por_carpeta("XS-2130-modelos-de-regresion-aplicados")
        puntos, _ = puntuar_curso(normalizar_texto("Receta de gallo pinto con arroz y frijoles."), curso)
        self.assertLess(puntos, cargar_config()["validacion"]["umbral_heuristico"])

    def test_slug(self):
        self.assertEqual(slug("Resumen Parcial 1: Regresión"), "resumen-parcial-1-regresion")


if __name__ == "__main__":
    unittest.main()
