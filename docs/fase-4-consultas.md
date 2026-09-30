# Fase 4 (posterior): consultas en lenguaje natural

Objetivo: preguntar «¿cuál es el mejor apunte de regresión?» o «apuntes de DOE con más de 4 estrellas».

## Base ya lista
`https://<usuario>.github.io/<repo>/data/puntuaciones.json` contiene todo lo necesario
(curso, título, autor, fecha, promedio, votos, puntaje de ranking y opiniones).

## Diseño propuesto (gratis, sin exponer claves)
La clave de Gemini no puede ir en la página (sería pública), así que la IA corre en Actions:

1. Nuevo formulario de issue «❓ Preguntar» (etiqueta `pregunta`).
2. Workflow `responder-pregunta.yml`: lee `puntuaciones.json`, envía a Gemini la pregunta
   y **una versión compacta** de los datos (sin opiniones largas) con instrucciones de
   responder solo con base en ellos y con enlaces a los apuntes.
3. Comenta la respuesta y cierra el issue (~30 s).

Alternativa más barata que conviene hacer primero: en la página, un buscador que
reconozca patrones simples («regresión», «> 4 estrellas», «DOE») y los traduzca a los
filtros existentes, sin IA. Cubre la mayoría de preguntas reales.
