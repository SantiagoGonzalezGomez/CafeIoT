// Panel único del proceso. Consulta la API cada 5 segundos.
const INTERVALO_MS = 5000;
const ESTADOS = {
  normal: "Normal", alerta: "Alerta", critica: "Crítica",
  desactualizada: "Sin datos recientes", sin_datos: "Sin datos",
};
const NOMBRES_VARIABLE = {
  temperatura: "Temperatura", humedad_relativa: "Humedad relativa", humedad_suelo: "Humedad del suelo",
  humedad_grano: "Humedad del grano", ph: "pH", co2: "CO₂", radiacion_solar: "Radiación solar",
};
const COLORES = ["#00874a", "#4f81bd", "#c55a11", "#7a4fa3"];

let seleccionada = null;
let reglas = [];
let ultimoEstado = null;

const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const hora = (iso) => new Date(iso).toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const num = (v) => Number(v).toLocaleString("es-CO", { maximumFractionDigits: 1 });

async function api(ruta) {
  const r = await fetch(ruta);
  if (!r.ok) throw new Error(`${ruta}: ${r.status}`);
  return r.json();
}

function valoresEtapa(etapa) {
  if (!etapa.lecturas.length) return "Sin lecturas";
  const porVariable = {};
  for (const l of etapa.lecturas) (porVariable[l.variable] ??= []).push(l);
  return Object.entries(porVariable).map(([v, ls]) => {
    const prom = ls.reduce((s, l) => s + l.valor, 0) / ls.length;
    return `${esc(NOMBRES_VARIABLE[v] ?? v)}: <b>${num(prom)} ${esc(ls[0].unidad)}</b>`;
  }).join("<br>");
}

function pintarFases(datos) {
  const cont = document.getElementById("fases");
  cont.innerHTML = datos.fases.map((f) => `
    <section class="fase">
      <div class="fase-cab"><h2>${esc(f.nombre)}</h2>
        <small>${f.tecnologia === "camaras" ? "Cámaras y visión artificial (próxima iteración)" : "Sensores IoT"}</small></div>
      <div class="etapas">
        ${f.etapas.map((e) => `
          <button type="button" class="etapa ${e.estado} ${e.codigo === seleccionada ? "sel" : ""}" data-etapa="${esc(e.codigo)}">
            <h3>${esc(e.nombre)}</h3>
            <span class="chip ${e.estado}">${ESTADOS[e.estado]}${e.alertas_abiertas ? ` · ${e.alertas_abiertas}` : ""}</span>
            <span class="valores">${valoresEtapa(e)}</span>
          </button>`).join("")}
      </div>
    </section>`).join("");
  cont.querySelectorAll(".etapa").forEach((b) => b.addEventListener("click", () => abrirDetalle(b.dataset.etapa)));
}

function pintarAlertas(lista) {
  const ol = document.getElementById("alertas");
  if (!lista.length) { ol.innerHTML = `<li class="vacio">No hay alertas abiertas.</li>`; return; }
  ol.innerHTML = lista.map((a) => `
    <li class="${esc(a.severidad)}">
      <strong>${esc(a.mensaje)}</strong>
      <div class="meta">${esc(a.etapa)} · ${esc(a.sensor_id)} · valor ${num(a.valor_ultimo)} (${esc(a.umbral)})</div>
      <div class="meta">Desde ${hora(a.inicio)}</div>
    </li>`).join("");
}

async function actualizar() {
  try {
    const datos = await api("/api/estado");
    ultimoEstado = datos;
    pintarFases(datos);
    pintarAlertas(datos.alertas_abiertas);
    document.getElementById("n-alertas").textContent = datos.alertas_abiertas.length;
    document.getElementById("n-rechazos").textContent = datos.rechazos_ultima_hora;
    document.getElementById("actualizado").textContent = hora(datos.generado);
    if (seleccionada) pintarDetalle(seleccionada);
  } catch (e) {
    document.getElementById("actualizado").textContent = "sin conexión";
    console.error(e);
  }
}

function grafica(serie, umbrales) {
  const W = 320, H = 140, M = { i: 34, d: 8, s: 8, b: 20 };
  if (!serie.puntos.length) return `<p class="vacio">Sin datos en las últimas 6 horas.</p>`;
  const pts = serie.puntos.map((p) => ({ t: new Date(p.ts).getTime(), v: p.valor, s: p.sensor_id }));
  const valores = pts.map((p) => p.v).concat(umbrales);
  let min = Math.min(...valores), max = Math.max(...valores);
  if (min === max) { min -= 1; max += 1; }
  const pad = (max - min) * 0.1; min -= pad; max += pad;
  const t0 = pts[0].t, t1 = Math.max(pts[pts.length - 1].t, t0 + 1);
  const x = (t) => M.i + ((t - t0) / (t1 - t0)) * (W - M.i - M.d);
  const y = (v) => H - M.b - ((v - min) / (max - min)) * (H - M.s - M.b);
  const sensores = [...new Set(pts.map((p) => p.s))];
  const lineas = sensores.map((s, k) => {
    const d = pts.filter((p) => p.s === s).map((p, j) => `${j ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`).join("");
    return `<path class="linea" d="${d}" style="stroke:${COLORES[k % COLORES.length]}"><title>${esc(s)}</title></path>`;
  }).join("");
  const marcas = [min + pad, (min + max) / 2, max - pad].map((v) =>
    `<line class="rejilla" x1="${M.i}" x2="${W - M.d}" y1="${y(v)}" y2="${y(v)}"/><text class="eje" x="${M.i - 4}" y="${y(v) + 3}" text-anchor="end">${num(v)}</text>`).join("");
  const lineasUmbral = umbrales.map((u) => `<line class="umbral" x1="${M.i}" x2="${W - M.d}" y1="${y(u)}" y2="${y(u)}"><title>Umbral ${num(u)}</title></line>`).join("");
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Serie de ${esc(serie.variable)}">
    ${marcas}${lineasUmbral}${lineas}
    <text class="eje" x="${M.i}" y="${H - 5}">${hora(pts[0].t)}</text>
    <text class="eje" x="${W - M.d}" y="${H - 5}" text-anchor="end">${hora(pts[pts.length - 1].t)}</text>
  </svg>`;
}

async function pintarDetalle(codigo) {
  const etapa = ultimoEstado?.fases.flatMap((f) => f.etapas).find((e) => e.codigo === codigo);
  if (!etapa) return;
  document.getElementById("detalle-titulo").textContent = `${etapa.nombre} · últimas 6 horas`;
  const variables = [...new Set(etapa.lecturas.map((l) => l.variable))];
  const cuerpo = document.getElementById("detalle-cuerpo");
  if (!variables.length) { cuerpo.innerHTML = `<p class="vacio">Esta etapa todavía no tiene sensores enviando datos.</p>`; return; }
  const series = await Promise.all(variables.map((v) => api(`/api/serie?etapa=${encodeURIComponent(codigo)}&variable=${encodeURIComponent(v)}&horas=6`)));
  cuerpo.innerHTML = series.map((s) => {
    const umbrales = reglas.filter((r) => r.etapa === codigo && r.variable === s.variable)
      .flatMap((r) => (r.umbral.match(/-?\d+(\.\d+)?/g) ?? []).map(Number));
    return `<div class="grafica"><h3>${esc(NOMBRES_VARIABLE[s.variable] ?? s.variable)} (${esc(s.unidad)})</h3>${grafica(s, umbrales)}</div>`;
  }).join("");
}

function abrirDetalle(codigo) {
  seleccionada = codigo;
  document.getElementById("detalle").hidden = false;
  document.querySelectorAll(".etapa").forEach((b) => b.classList.toggle("sel", b.dataset.etapa === codigo));
  pintarDetalle(codigo);
}

document.getElementById("cerrar").addEventListener("click", () => {
  seleccionada = null;
  document.getElementById("detalle").hidden = true;
  document.querySelectorAll(".etapa").forEach((b) => b.classList.remove("sel"));
});

api("/api/reglas").then((r) => { reglas = r; }).catch(() => {});
actualizar();
setInterval(actualizar, INTERVALO_MS);
