# Cartas al estudiante (**activa**)

Cuando un curso tiene aquí su carta al estudiante, **todo apunte de ese curso se compara con su
temario antes de aprobarse**.

## Cómo subir una carta
1. En GitHub, entra a esta carpeta `cartas/` → **Add file → Upload files**.
2. Arrastra el PDF de la carta. El nombre solo tiene que **contener la sigla** del curso:
   `XS-2130.pdf`, `carta-xs2130-II-2026.pdf`, `Carta XS-3150.pdf`… (también sirve la sigla del plan anterior).
3. Crea el Pull Request y fusiónalo (solo los mantenedores pueden cambiar esta carpeta).

Se aceptan `.pdf` (con texto seleccionable; si es escaneada, mejor pásala a `.txt`), `.md` o `.txt`.
Si un curso tiene varias versiones (`v2`, `g03`, `(1)`…), **se usan todas juntas**; no hace falta borrar ninguna.

## Cómo se usa
- **Gemini** recibe la sección de *contenidos* de la carta como criterio principal y solo aprueba
  si el apunte trata temas de ese temario (basta con que cubra una parte). El comentario del PR
  indica qué temas de la carta cubre.
- **Sin Gemini** (cuota agotada o sin clave), las reglas simples dividen el temario en temas
  («técnicas de conteo», «distribución de Poisson»…) y exigen que el apunte trate al menos
  `min_temas_carta` de ellos (3 por defecto, en `config.json`).
- Si el apunte encaja claramente mejor en la carta de **otro** curso, se rechaza por carpeta equivocada.
- Curso **sin carta**: se valida con los temas generales de `cursos.json` y el comentario lo avisa.
  Para exigir carta en todos los cursos, pon `"exigir_carta": true` en `config.json`.

Para desactivar la función: `"usar_carta_estudiante": false` en `config.json`.

⚠️ Este repositorio es público: las cartas quedarán visibles para cualquiera.
