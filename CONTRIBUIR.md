# Cómo contribuir

## Opción fácil (sin Git)
1. En el ranking o en *Issues → New issue*, elija **📤 Subir un apunte**.
2. Elija el curso, escriba un título y arrastre su PDF al cuadro «Archivo».
3. Un robot crea el Pull Request por usted y revisa si el contenido corresponde al curso.
   Si coincide, el apunte **se publica solo** en unos minutos.

## Si el robot rechaza su apunte
El robot compara su apunte con la **carta al estudiante** del curso. Si lo rechaza por su contenido,
le preguntará qué pasó. Responda con un comentario (en el PR o en su issue) que empiece con:

- **`/contenido-nuevo`** — el tema sí es del curso pero no aparece en la carta (por ejemplo, el profesor
  lo agregó este semestre). Puede explicarlo en el mismo comentario. Un mantenedor lo revisará a mano.
- **`/curso XS-0122`** — se equivocó de curso: escriba la sigla correcta y el robot moverá el apunte
  y lo validará de nuevo.

## Opción con Git / interfaz web de GitHub
1. Haga *fork* del repositorio.
2. Agregue su archivo en la carpeta del curso: `apuntes/<SIGLA-nombre>/<titulo>.pdf`.
   - Nombre en minúsculas, sin tildes ni espacios: `resumen-parcial-1.pdf`, `notas-de-clase-i-2026.pdf`.
     El nombre se muestra como título en el ranking.
   - Formatos: PDF (preferido) o Markdown (`.md`). Máximo 50 MB.
   - En la interfaz web: entre a la carpeta → *Add file → Upload files*.
3. Abra un Pull Request. La validación automática comentará en unos minutos y, si coincide con el curso, lo publicará sola.

## Actualizar o borrar un apunte
Solo **quien subió el apunte** y los **mantenedores del repositorio** pueden modificarlo,
renombrarlo o eliminarlo. Para subir una versión corregida de su apunte, abra un PR que reemplace
el archivo con el **mismo nombre**: así conserva sus votos. La validación automática rechaza los PR
que cambien apuntes de otras personas.

## Reglas
- Un PR = apuntes: solo se aceptan archivos dentro de `apuntes/<curso>/` (los demás los cambian los mantenedores).
- No renombre ni mueva apuntes ya publicados: sus votos están ligados a la ruta.
- Solo material propio o con permiso; nada de exámenes ni material restringido.

## Puntuar
Use el botón **Puntuar** del ranking. La justificación es obligatoria y pública:
explique qué tiene de bueno o malo el apunte (claridad, orden, temas, errores, legibilidad…).
Los votos sin razones («porque sí», «no me cae bien») se rechazan. No puede puntuar sus propios apuntes.
