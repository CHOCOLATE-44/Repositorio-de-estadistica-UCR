// Intérprete de consultas en lenguaje natural, sin IA.
// Convierte frases como «el mejor apunte de regresión» o «DOE con más de 4 estrellas»
// en filtros: { curso, min: {valor, estricto}, minVotos, orden, desde, limite, resto, explicacion }.
(function (global) {
  "use strict";

  const norm = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
    .replace(/[¿?¡!,;:"«»()]/g, " ").replace(/\s+/g, " ").trim();
  const escapar = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const palabra = (s) => new RegExp(`(^|\\s)${escapar(s)}(?=\\s|$)`);

  const VACIAS = new Set(("apunte apuntes de del con el la los las lo cual cuales es son que mejor mejores " +
    "dame quiero busco buscar hay para un una unos unas y en curso cursos estrellas estrella me muestra " +
    "mostrar ver top a o por favor mas muy recomendado recomendados recomiendas algun alguno tenga tengan " +
    "tiene tienen sobre votos voto").split(" "));

  function formasSigla(sigla) {
    const [pre, num] = sigla.toLowerCase().split("-");
    return [`${pre}-${num}`, `${pre}${num}`, `${pre} ${num}`, num];
  }

  function buscarCurso(q, cursos) {
    let mejor = null;
    for (const c of cursos) {
      const cands = [norm(c.nombre), ...(c.alias || []).map(norm)];
      for (const s of [c.sigla, ...(c.siglas_equivalentes || [])]) cands.push(...formasSigla(s));
      for (const t of cands) {
        if (t && palabra(t).test(q) && (!mejor || t.length > mejor.texto.length)) mejor = { curso: c, texto: t };
      }
    }
    return mejor;
  }

  function numero(s) { return parseFloat(s.replace(",", ".")); }

  function interpretar(texto, cursos, hoy) {
    hoy = hoy || new Date();
    let q = norm(texto);
    const r = { curso: null, min: null, minVotos: null, orden: null, desde: null, limite: null, resto: "", explicacion: [] };
    const quitar = (m) => { q = q.replace(m, " ").replace(/\s+/g, " ").trim(); };
    if (!q) return r;

    // Votos: «con más de 5 votos», «al menos 3 votos»
    let m = q.match(/(?:mas de|al menos|minimo|como minimo|>=?)\s*(\d+)\s*votos?/);
    if (m) {
      r.minVotos = parseInt(m[1], 10) + (/mas de|>(?!=)/.test(m[0]) ? 1 : 0);
      r.explicacion.push(`al menos ${r.minVotos} votos`);
      quitar(m[0]);
    }

    // Estrellas
    const N = "([1-5](?:[.,]\\d)?)";
    const reglas = [
      [new RegExp(`(?:mas de|mayor(?:es)? (?:a|que)|arriba de|superior(?:es)? a|>(?!=))\\s*${N}\\s*(?:estrellas?|★)?`), true],
      [new RegExp(`(?:al menos|minimo|como minimo|>=|desde)\\s*${N}\\s*(?:estrellas?|★)`), false],
      [new RegExp(`${N}\\s*(?:estrellas?|★)(?:\\s*(?:o mas|para arriba|en adelante|o superior))?`), false],
    ];
    for (const [re, estricto] of reglas) {
      m = q.match(re);
      if (m) {
        r.min = { valor: numero(m[1]), estricto };
        r.explicacion.push(`${estricto ? "más de" : "al menos"} ${r.min.valor} ★`);
        quitar(m[0]);
        break;
      }
    }

    // Fechas
    const hace = (dias, meses, anos) => {
      const d = new Date(hoy);
      d.setDate(d.getDate() - dias); d.setMonth(d.getMonth() - meses); d.setFullYear(d.getFullYear() - anos);
      return d.toISOString().slice(0, 10);
    };
    const fechas = [
      [/(?:de|desde|del|en)?\s*este ano/, () => [`${hoy.getFullYear()}-01-01`, `desde ${hoy.getFullYear()}`]],
      [/(?:de la |en la )?ultima semana/, () => [hace(7, 0, 0), "última semana"]],
      [/(?:del |en el )?ultimo mes/, () => [hace(0, 1, 0), "último mes"]],
      [/(?:de los |en los )?ultimos (\d+) meses/, (x) => [hace(0, +x[1], 0), `últimos ${x[1]} meses`]],
      [/(?:del |en el )?ultimo ano/, () => [hace(0, 0, 1), "último año"]],
      [/(?:desde|de|del|en)(?: el)?(?: ano)? (20\d\d)/, (x) => [`${x[1]}-01-01`, `desde ${x[1]}`]],
    ];
    for (const [re, f] of fechas) {
      m = q.match(re);
      if (m) {
        const [d, txt] = f(m);
        r.desde = d; r.explicacion.push(txt); quitar(m[0]);
        break;
      }
    }

    // Curso (después de estrellas y fechas para no confundir números)
    const c = buscarCurso(q, cursos);
    if (c) {
      r.curso = c.curso.sigla;
      r.explicacion.unshift(`${c.curso.sigla} ${c.curso.nombre}`);
      quitar(palabra(c.texto));
    }

    // Orden y límite
    m = q.match(/(?:los |las )?(?:top|primeros|mejores) (\d+)|(\d+) mejores/);
    if (m) { r.limite = parseInt(m[1] || m[2], 10); r.orden = "ranking"; quitar(m[0]); }
    else if (/(^|\s)(el|la|cual es el|cual es la|cual) mejor(\s|$)/.test(q) || /^mejor(\s|$)/.test(q)) { r.limite = 1; r.orden = "ranking"; }
    if (/mas votad|popular/.test(q)) r.orden = "votos";
    else if (/reciente|nuevo|ultimos apuntes|lo ultimo/.test(q)) r.orden = "fecha";
    else if (!r.orden && /mejor|recomend|top/.test(q)) r.orden = "ranking";
    if (r.orden === "votos") r.explicacion.push("más votados");
    if (r.orden === "fecha") r.explicacion.push("más recientes primero");
    if (r.limite === 1) r.explicacion.push("el mejor");
    else if (r.limite) r.explicacion.push(`los ${r.limite} mejores`);

    // Lo que sobra se usa como búsqueda de texto libre
    r.resto = q.split(" ").filter((w) => w && !VACIAS.has(w) && !/^(mas|votad\w*|popular\w*|recientes?|nuevos?|ultimos?)$/.test(w)).join(" ");
    return r;
  }

  const api = { interpretar, normalizar: norm };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else global.Consulta = api;
})(typeof window !== "undefined" ? window : globalThis);
