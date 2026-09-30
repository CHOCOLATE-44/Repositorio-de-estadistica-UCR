import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import validar_apunte as va  # noqa: E402
from comun import cargar_config, cargar_cursos, curso_por_sigla, normalizar_texto  # noqa: E402

CARTA_1130 = """Carta al estudiante XS-1130 Principios de Inferencia Estadística
Contenidos
Unidad 1. Teoría de probabilidades: espacio muestral, eventos, probabilidad condicional, teorema de Bayes.
Técnicas de conteo: permutaciones, combinaciones, factorial.
Unidad 2. Distribuciones discretas: binomial, hipergeométrica, Poisson. Distribuciones continuas: normal, t de Student.
Unidad 3. Intervalos de confianza y pruebas de hipótesis.
Evaluación: tres exámenes parciales.
Bibliografía: Walpole."""

CARTA_2130 = """Carta al estudiante XS-2130 Modelos de Regresión Aplicados
Contenidos: regresión lineal simple, mínimos cuadrados, coeficiente de determinación, regresión múltiple,
residuos, heterocedasticidad, multicolinealidad, variables indicadoras, selección de variables.
Evaluación: parciales y proyecto."""

CONTEO = ("Técnicas de conteo. Permutaciones sin repetición: nPr = n!/(n-r)!. Combinaciones: el orden no importa. "
          "Factorial de un número. Ejemplo: de cuántas formas se sientan 10 personas en 5 asientos.")
REGRESION = ("Modelos de regresión aplicados. Regresión lineal simple por mínimos cuadrados, coeficiente de "
             "determinación, análisis de residuos, heterocedasticidad y multicolinealidad en regresión múltiple.")


class PruebasCartas(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        d = Path(self.dir.name)
        (d / "carta-xs1130-II-2026.txt").write_text(CARTA_1130, encoding="utf-8")
        (d / "XS-2130.txt").write_text(CARTA_2130, encoding="utf-8")
        self.config = cargar_config()
        self.config["validacion"].update(usar_carta_estudiante=True, carpeta_cartas=self.dir.name)
        self.cursos = cargar_cursos()
        va._cache_cartas.clear()

    def tearDown(self):
        self.dir.cleanup()
        va._cache_cartas.clear()

    def validar(self, texto, carpeta):
        archivo = Path(self.dir.name) / "apunte.md"
        archivo.write_text(texto, encoding="utf-8")
        return va.validar_archivo(archivo, "apunte.md", carpeta, self.config, self.cursos)

    def test_busca_carta_con_nombre_flexible(self):
        self.assertEqual(va.buscar_carta(curso_por_sigla("XS-1130"), self.config).name, "carta-xs1130-II-2026.txt")
        self.assertIsNone(va.buscar_carta(curso_por_sigla("XS-3150"), self.config))

    def test_temario_sin_evaluacion_ni_bibliografia(self):
        temas = va.temas_de_carta(CARTA_1130)
        self.assertIn("tecnicas de conteo", temas)
        self.assertFalse(any("parciales" in t or "walpole" in t for t in temas))

    def test_temas_encontrados(self):
        encontrados = va.temas_carta_en_apunte(normalizar_texto(CONTEO), CARTA_1130)
        for t in ("tecnicas de conteo", "permutaciones", "combinaciones", "factorial"):
            self.assertIn(t, encontrados)

    def test_apunte_de_su_curso_aprobado(self):
        v = self.validar(CONTEO, "XS-1130-principios-de-inferencia-estadistica")
        self.assertTrue(v.valido, v.motivo)
        self.assertIn("carta al estudiante", v.motivo)

    def test_apunte_de_otro_curso_rechazado(self):
        v = self.validar(REGRESION, "XS-1130-principios-de-inferencia-estadistica")
        self.assertFalse(v.valido)
        v = self.validar(CONTEO, "XS-2130-modelos-de-regresion-aplicados")
        self.assertFalse(v.valido)

    def test_curso_sin_carta_avisa(self):
        v = self.validar(CONTEO, "XS-3150-diseno-de-experimentos")
        self.assertTrue(any("aún no tiene carta" in d for d in v.detalles))


if __name__ == "__main__":
    unittest.main()
