// Página del ranking: lee data/puntuaciones.json (generado por GitHub Actions)
// y lo muestra con filtros. Sin dependencias ni paso de compilación.
(function () {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const f = { texto: $("#f-texto"), curso: $("#f-curso"), min: $("#f-min"), fecha: $("#f-fecha"), orden: $("#f-orden") };
  let datos = null;

  const sinTildes = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const rutaURL = (r) => r.split("/").map(encodeURIComponent).join("/");
  const fechaCorta = (iso) => new Date(iso).toLocaleDateString("es-CR", { year: "numeric", month: "short", day: "numeric" });
  const estrellas = (x) => {
    if (x == null) return "☆☆☆☆☆";
    const llenas = Math.min(5, Math.floor(x + 0.25));
    return "★".repeat(llenas) + "☆".repeat(5 - llenas);
  };

  function urlGitHub(ruta) { return `https://github.com/${datos.repositorio}${ruta}`; }
  function urlAbrir(a) { return urlGitHub(`/blob/${datos.rama}/${rutaURL(a.ruta)}`); }
  function urlVotar(a) {
    const p = new URLSearchParams({ template: "puntuar-apunte.yml", title: `Voto: ${a.titulo} (${a.curso})`, apunte: a.ruta });
    return urlGitHub(`/issues/new?${p}`);
  }

  function leerURL() {
    const p = new URLSearchParams(location.search);
    for (const k of Object.keys(f)) if (p.has(k)) f[k].value = p.get(k);
  }
  function escribirURL() {
    const p = new URLSearchParams();
    for (const [k, el] of Object.entries(f)) if (el.value && !(k === "min" && el.value === "0") && !(k === "orden" && el.value === "ranking")) p.set(k, el.value);
    history.replaceState(null, "", p.toString() ? `?${p}` : location.pathname);
  }

  // Combina los controles con lo que se entendió de la consulta escrita (la consulta manda).
  function filtrosEfectivos() {
    const c = window.Consulta.interpretar(f.texto.value, datos.cursos);
    const minCtrl = parseFloat(f.min.value);
    return {
      consulta: c,
      curso: c.curso || f.curso.value,
      sinVotos: !c.min && minCtrl === -1,
      min: c.min || (minCtrl > 0 ? { valor: minCtrl, estricto: false } : null),
      minVotos: c.minVotos,
      desde: c.desde ? new Date(c.desde) : (f.fecha.value ? new Date(f.fecha.value) : null),
      orden: c.orden || f.orden.value,
      texto: c.resto,
    };
  }

  function filtrar(e) {
    const q = e.texto.split(" ").filter(Boolean);
    let lista = datos.apuntes.filter((a) => {
      if (e.curso && a.curso !== e.curso) return false;
      if (e.sinVotos && a.votos > 0) return false;
      if (e.min && (a.promedio == null || (e.min.estricto ? a.promedio <= e.min.valor : a.promedio < e.min.valor))) return false;
      if (e.minVotos && a.votos < e.minVotos) return false;
      if (e.desde && new Date(a.fecha) < e.desde) return false;
      if (q.length) {
        const heno = sinTildes(`${a.titulo} ${a.autor} ${a.curso} ${a.ruta}`);
        if (!q.every((w) => heno.includes(w))) return false;
      }
      return true;
    });
    const orden = {
      ranking: (a, b) => b.puntaje_ranking - a.puntaje_ranking || b.votos - a.votos,
      votos: (a, b) => b.votos - a.votos || b.puntaje_ranking - a.puntaje_ranking,
      fecha: (a, b) => new Date(b.fecha) - new Date(a.fecha),
    }[e.orden];
    lista.sort(orden);
    return e.consulta.limite ? lista.slice(0, e.consulta.limite) : lista;
  }

  function tarjeta(a) {
    const n = $("#tpl-apunte").content.cloneNode(true);
    n.querySelector(".titulo").textContent = a.titulo;
    n.querySelector(".sigla").textContent = a.curso;
    n.querySelector(".autor").textContent = a.autor;
    n.querySelector(".fecha").textContent = fechaCorta(a.fecha);
    n.querySelector(".formato").textContent = a.formato.toUpperCase();
    n.querySelector(".estrellas").textContent = estrellas(a.promedio);
    n.querySelector(".valor").textContent = a.votos ? `${a.promedio.toFixed(1)} · ${a.votos} voto${a.votos === 1 ? "" : "s"}` : "Sin votos";
    n.querySelector(".puntaje").title = a.votos ? `Promedio ${a.promedio} de ${a.votos} votos` : "Aún no tiene votos";
    n.querySelector(".abrir").href = urlAbrir(a);
    n.querySelector(".puntuar").href = urlVotar(a);
    const det = n.querySelector(".opiniones");
    if (!a.opiniones.length) det.remove();
    else {
      det.querySelector("summary").textContent = `Ver opiniones (${a.opiniones.length})`;
      const ul = det.querySelector("ul");
      for (const o of a.opiniones) {
        const li = document.createElement("li");
        li.append(`${"★".repeat(o.puntuacion)} — ${o.justificacion} `);
        const enlace = document.createElement("a");
        enlace.href = o.url; enlace.target = "_blank"; enlace.rel = "noopener";
        enlace.textContent = `@${o.usuario}, ${fechaCorta(o.fecha)}`;
        li.append(enlace);
        ul.append(li);
      }
    }
    return n;
  }

  function mostrarInterpretacion(e) {
    const caja = $("#interpretacion");
    const texto = f.texto.value.trim();
    caja.hidden = !texto;
    if (!texto) return;
    const partes = [...e.consulta.explicacion];
    if (e.texto) partes.push(`texto «${e.texto}»`);
    $("#entendi").textContent = partes.length ? `Entendí: ${partes.join(" · ")}` : "";
    const p = new URLSearchParams({ template: "preguntar.yml", title: `Pregunta: ${texto.slice(0, 80)}`, pregunta: texto });
    $("#preguntar-ia").href = urlGitHub(`/issues/new?${p}`);
  }

  function pintar() {
    escribirURL();
    const e = filtrosEfectivos();
    const lista = filtrar(e);
    const cont = $("#resultados");
    cont.replaceChildren();
    mostrarInterpretacion(e);
    const mejor = e.consulta.limite === 1 && lista[0];
    $("#resumen").textContent = mejor
      ? `${mejor.votos ? "El mejor puntuado" : "No hay votos todavía; el primero de la lista"} es «${mejor.titulo}»` +
        (mejor.votos ? ` (${mejor.promedio.toFixed(1)} ★, ${mejor.votos} voto${mejor.votos === 1 ? "" : "s"}).` : ".")
      : `${lista.length} apunte${lista.length === 1 ? "" : "s"}` +
        (lista.length !== datos.apuntes.length ? ` (de ${datos.apuntes.length})` : "");

    if (!lista.length) {
      const d = document.createElement("div");
      d.className = "vacio";
      d.innerHTML = datos.apuntes.length ? "Ningún apunte coincide con los filtros." :
        `Todavía no hay apuntes. <a href="${urlGitHub("/issues/new?template=subir-apunte.yml")}">¡Sube el primero!</a>`;
      cont.append(d);
      return;
    }
    // Con "Todos los cursos" se agrupa por curso (en orden del plan de estudios).
    const grupos = e.curso ? [[datos.cursos.find((c) => c.sigla === e.curso), lista]]
      : datos.cursos.map((c) => [c, lista.filter((a) => a.curso === c.sigla)]).filter(([, l]) => l.length);
    for (const [curso, items] of grupos) {
      const sec = document.createElement("section");
      sec.className = "grupo";
      const h = document.createElement("h2");
      h.textContent = `${curso.sigla} ${curso.nombre} `;
      const s = document.createElement("small");
      s.textContent = `· ciclo ${curso.ciclo}`;
      h.append(s);
      sec.append(h);
      for (const a of items) sec.append(tarjeta(a));
      cont.append(sec);
    }
  }

  async function iniciar() {
    try {
      const r = await fetch("data/puntuaciones.json", { cache: "no-cache" });
      datos = await r.json();
    } catch (e) {
      $("#resumen").textContent = "No se pudieron cargar los datos. Intenta recargar la página.";
      return;
    }
    let ciclo = null, grupo = null;
    for (const c of datos.cursos) {
      if (c.ciclo !== ciclo) {
        ciclo = c.ciclo;
        grupo = document.createElement("optgroup");
        grupo.label = `Ciclo ${ciclo}`;
        f.curso.append(grupo);
      }
      grupo.append(new Option(`${c.sigla} ${c.nombre}`, c.sigla));
    }
    $("#btn-subir").href = urlGitHub("/issues/new?template=subir-apunte.yml");
    $("#btn-repo").href = urlGitHub("");
    $("#generado").textContent = `Datos actualizados: ${new Date(datos.generado).toLocaleString("es-CR")}`;
    leerURL();
    for (const el of Object.values(f)) el.addEventListener("input", pintar);
    pintar();
  }
  iniciar();
})();
