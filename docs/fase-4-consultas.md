# Fase 4: consultas en lenguaje natural

Hay dos niveles, del más barato al más potente.

## 1. Buscador de la página (sin IA, instantáneo)
`sitio/consulta.js` traduce frases a filtros. Ejemplos:

| Escribes | Entiende |
|---|---|
| ¿cuál es el mejor apunte de regresión? | XS-2130 · el mejor (muestra solo el primero y lo anuncia) |
| apuntes de DOE con más de 4 estrellas | XS-3150 · promedio > 4 |
| top 3 de muestreo | XS-3110 · los 3 mejores |
| series de tiempo de este año | XS-0127 · subidos desde el 1 de enero |
| probabilidad con al menos 5 votos | XS-0122 · ≥ 5 votos |
| los más votados de bayes | XS-0128 · ordenado por votos |
| XS2310 | XS-0122 (sigla equivalente del plan anterior) |

Los cursos se reconocen por sigla, nombre, siglas equivalentes y **alias** (`cursos.json → alias`).
Si la gente usa otro apodo para un curso, agrégalo ahí. Lo que no se reconoce se usa como búsqueda de texto.
Pruebas: `node tests/test_consulta.js`.

## 2. «Pregúntale a la IA» (Gemini, ~30 s)
Para preguntas abiertas («¿qué me sirve para repasar ANOVA?»). El enlace aparece bajo el buscador
y abre el formulario **❓ Preguntar** con la pregunta ya escrita. El workflow `responder-pregunta.yml`
recalcula los datos del ranking, se los pasa a Gemini con instrucciones de responder solo con ellos,
comenta la respuesta y cierra el issue. La clave nunca llega a la página (sería pública).
