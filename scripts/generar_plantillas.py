"""Regenera los formularios de issues a partir de `cursos.json`.
Ejecútalo cada vez que cambies la lista de cursos:  python scripts/generar_plantillas.py"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import RAIZ, cargar_config, cargar_cursos  # noqa: E402

DESTINO = RAIZ / ".github" / "ISSUE_TEMPLATE"


def q(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)  # JSON es YAML válido para cadenas


def main():
    cursos, cfg = cargar_cursos(), cargar_config()
    opciones = "\n".join(f"        - {q(c['sigla'] + ' — ' + c['nombre'])}" for c in cursos)
    (DESTINO / "subir-apunte.yml").write_text(f"""# Generado por scripts/generar_plantillas.py — no editar a mano.
name: 📤 Subir un apunte
description: Sube tu PDF sin usar Git. Un robot crea el Pull Request y valida el contenido.
title: "Apunte: "
labels: ["subir-apunte"]
body:
  - type: markdown
    attributes:
      value: |
        ¡Gracias por compartir! Completa el formulario y **arrastra tu PDF** al cuadro «Archivo».
        Un proceso automático revisará que el contenido corresponda al curso y te avisará aquí.
  - type: dropdown
    id: curso
    attributes:
      label: Curso
      options:
{opciones}
    validations:
      required: true
  - type: input
    id: titulo
    attributes:
      label: Título
      description: Corto y descriptivo. Ej. «Resumen completo parcial 1» o «Notas de clase I-2026».
    validations:
      required: true
  - type: textarea
    id: archivo
    attributes:
      label: Archivo
      description: Arrastra aquí el PDF (máx. {cfg['validacion']['tamano_maximo_mb']} MB). Espera a que termine de subir antes de enviar.
      placeholder: Arrastra tu PDF aquí…
    validations:
      required: true
  - type: textarea
    id: descripcion
    attributes:
      label: Descripción
      description: Opcional. Semestre, temas que cubre…
  - type: checkboxes
    id: confirmacion
    attributes:
      label: Confirmación
      options:
        - label: Este apunte es de mi autoría (o tengo permiso) y acepto que se publique en este repositorio público.
          required: true
        - label: No contiene exámenes o material que el profesor haya pedido no compartir.
          required: true
""", encoding="utf-8")

    (DESTINO / "puntuar-apunte.yml").write_text(f"""# Generado por scripts/generar_plantillas.py — no editar a mano.
name: ⭐ Puntuar un apunte
description: Da de 1 a 5 estrellas a un apunte y explica por qué.
title: "Voto: "
labels: ["voto"]
body:
  - type: markdown
    attributes:
      value: |
        Lo más fácil es usar el botón **«Puntuar»** en la página del ranking: rellena el apunte por ti.
        Cuenta un voto por persona y apunte (si votas de nuevo, vale el más reciente). Tu justificación será pública.
  - type: input
    id: apunte
    attributes:
      label: Apunte
      description: Ruta del archivo en el repositorio (se rellena sola desde la página).
      placeholder: apuntes/XS-2130-modelos-de-regresion-aplicados/mi-apunte.pdf
    validations:
      required: true
  - type: dropdown
    id: puntuacion
    attributes:
      label: Puntuación
      options:
        - "5 — Excelente"
        - "4 — Muy bueno"
        - "3 — Aceptable"
        - "2 — Deficiente"
        - "1 — Malo"
    validations:
      required: true
  - type: textarea
    id: justificacion
    attributes:
      label: Justificación
      description: >-
        Obligatoria. Explica tu puntuación con razones concretas (claridad, orden, temas que cubre,
        errores, ejemplos, legibilidad…). Mínimo {cfg['votos']['min_palabras_justificacion']} palabras.
        Los votos «por gusto» se rechazan.
    validations:
      required: true
  - type: checkboxes
    id: confirmacion
    attributes:
      label: Confirmación
      options:
        - label: Leí o usé este apunte y mi voto es honesto.
          required: true
""", encoding="utf-8")
    (DESTINO / "preguntar.yml").write_text("""# Generado por scripts/generar_plantillas.py — no editar a mano.
name: ❓ Preguntar sobre los apuntes
description: Pregunta en lenguaje natural; la IA responde con base en el ranking.
title: "Pregunta: "
labels: ["pregunta"]
body:
  - type: markdown
    attributes:
      value: |
        Para búsquedas simples («mejor apunte de regresión», «DOE con más de 4 estrellas») usa el buscador
        de la página del ranking: responde al instante. Aquí puedes hacer preguntas más abiertas,
        por ejemplo «¿qué apuntes me sirven para repasar ANOVA antes del parcial?».
        Un robot responderá en este issue en menos de un minuto.
  - type: textarea
    id: pregunta
    attributes:
      label: Pregunta
    validations:
      required: true
""", encoding="utf-8")
    print("Plantillas regeneradas.")


if __name__ == "__main__":
    main()
