# Cómo contribuir

## Opción fácil (sin Git)
1. En el ranking o en *Issues → New issue*, elige **📤 Subir un apunte**.
2. Elige el curso, escribe un título y arrastra tu PDF al cuadro «Archivo».
3. Un robot crea el Pull Request por ti y comenta si el contenido corresponde al curso.

Si el robot rechaza el apunte, edita el issue (por ejemplo, para cambiar el curso) y se reintentará solo.

## Opción con Git / interfaz web de GitHub
1. Haz *fork* del repositorio.
2. Agrega tu archivo en la carpeta del curso: `apuntes/<SIGLA-nombre>/<titulo>.pdf`.
   - Nombre en minúsculas, sin tildes ni espacios: `resumen-parcial-1.pdf`, `notas-de-clase-i-2026.pdf`.
     El nombre se muestra como título en el ranking.
   - Formatos: PDF (preferido) o Markdown (`.md`). Máximo 50 MB.
   - En la interfaz web: entra a la carpeta → *Add file → Upload files*.
3. Abre un Pull Request. La validación automática comentará en unos minutos.

## Actualizar o borrar un apunte
Solo **quien subió el apunte** y los **mantenedores del repositorio** pueden modificarlo,
renombrarlo o eliminarlo. Para subir una versión corregida de tu apunte, abre un PR que reemplace
el archivo con el **mismo nombre**: así conserva sus votos. La validación automática rechaza los PR
que cambien apuntes de otras personas.

## Reglas
- Un PR = apuntes: solo se aceptan archivos dentro de `apuntes/<curso>/` (los demás los cambian los mantenedores).
- No renombres ni muevas apuntes ya publicados: sus votos están ligados a la ruta.
- Solo material propio o con permiso; nada de exámenes ni material restringido.

## Puntuar
Usa el botón **Puntuar** del ranking. La justificación es obligatoria y pública:
explica qué tiene de bueno o malo el apunte (claridad, orden, temas, errores, legibilidad…).
Los votos sin razones («porque sí», «no me cae bien») se rechazan. No puedes puntuar tus propios apuntes.
