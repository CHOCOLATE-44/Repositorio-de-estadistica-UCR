# Cartas al estudiante (validación opcional, **desactivada**)

La validación de apuntes puede usar la carta al estudiante de cada curso para
comparar el apunte con el temario oficial. Está implementada pero apagada.

## Para activarla
1. Guarda aquí la carta de cada curso con su sigla como nombre:
   `cartas/XS-2130.pdf`, `cartas/XS-3150.pdf`, … (también se acepta `.md` o `.txt`).
2. En `config.json` cambia `"usar_carta_estudiante": false` a `true`.

## Qué hace cuando está activa
- **Reglas simples:** extrae los ~40 términos más frecuentes de la carta y suma puntos si
  al menos el 30 % aparece en el apunte.
- **Gemini:** incluye un fragmento de la carta en la consulta como referencia del temario.
- Si falta la carta de algún curso, la validación de ese curso sigue funcionando como
  siempre y el comentario del PR lo indica.

Revisa que la carta pueda publicarse (este repositorio es público).
