// Pruebas del intérprete de consultas:  node tests/test_consulta.js
const assert = require("assert");
const path = require("path");
const fs = require("fs");
const { interpretar } = require(path.join(__dirname, "..", "sitio", "consulta.js"));
const cursos = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "cursos.json"), "utf8")).cursos;
const hoy = new Date("2026-09-30T12:00:00Z");
const q = (t) => interpretar(t, cursos, hoy);

const casos = [
  ["¿cuál es el mejor apunte de regresión?", { curso: "XS-2130", limite: 1, orden: "ranking", resto: "" }],
  ["apuntes de DOE con más de 4 estrellas", { curso: "XS-3150", min: { valor: 4, estricto: true }, resto: "" }],
  ["XS-3150 al menos 3.5 estrellas", { curso: "XS-3150", min: { valor: 3.5, estricto: false } }],
  ["inferencia bayesiana", { curso: "XS-0128", resto: "" }],
  ["principios de inferencia", { curso: "XS-1130" }],
  ["series de tiempo más recientes", { curso: "XS-0127", orden: "fecha" }],
  ["apuntes de 2130 de este año", { curso: "XS-2130", desde: "2026-01-01" }],
  ["top 3 de muestreo", { curso: "XS-3110", limite: 3 }],
  ["probabilidad con al menos 5 votos", { curso: "XS-0122", minVotos: 5 }],
  ["regresión lineal múltiple", { curso: "XS-2130", resto: "lineal multiple" }],
  ["XS2310", { curso: "XS-0122" }],
  ["cálculo 1 desde 2025", { curso: "MA-0155", desde: "2025-01-01" }],
  ["resumen parcial", { curso: null, resto: "resumen parcial" }],
  ["los más votados de bayes", { curso: "XS-0128", orden: "votos" }],
  ["4 estrellas o más", { min: { valor: 4, estricto: false } }],
];
let fallos = 0;
for (const [texto, esperado] of casos) {
  const r = q(texto);
  for (const [k, v] of Object.entries(esperado)) {
    try { assert.deepStrictEqual(r[k], v); }
    catch { fallos++; console.error(`✗ «${texto}» → ${k}: ${JSON.stringify(r[k])} (esperado ${JSON.stringify(v)})`); }
  }
}
console.log(fallos ? `${fallos} fallos` : `✓ ${casos.length} consultas interpretadas correctamente`);
process.exit(fallos ? 1 : 0);
