/* Referencias — © 2026 Gabriel Da Costa Porto Luzardo — GPL-3.0 */
"use strict";

// ───────────────────────── Estado ─────────────────────────

const estado = {
  norma: localStorage.getItem("norma") || "apa7",
  normasCfg: null,           // configuración de normas.json (vía /api/normas)
  plantillas: JSON.parse(localStorage.getItem("plantillas") || "{}"),
  registro: null,            // meta en edición
  resultados: [],            // última búsqueda
  filtroAutor: null,
  biblio: JSON.parse(localStorage.getItem("biblio") || "[]"),
  editandoBiblio: null,      // índice de la biblio que se está editando
};

const NOMBRES_NORMA = { apa7: "APA 7", vancouver: "Vancouver", iso690: "ISO 690", chicago: "Chicago" };

const $ = (id) => document.getElementById(id);

const sinAcentos = (t) => t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

// ─────────────────── Esquema de campos por tipo ───────────────────

const HOY = (() => {
  const m = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto",
             "septiembre","octubre","noviembre","diciembre"];
  const h = new Date();
  return `${h.getDate()} de ${m[h.getMonth()]} de ${h.getFullYear()}`;
})();

// Cada campo: [id, etiqueta, pista, tipo de control, ¿ancho total?]
const ESQUEMAS = {
  articulo: [
    ["autores", "Autores", "Una persona por línea, como «Apellido, Nombre»", "textarea", true],
    ["titulo", "Título del artículo", "", "text", true],
    ["revista", "Revista", "", "text", true],
    ["anio", "Año", "", "text"],
    ["volumen", "Volumen", "", "text"],
    ["numero", "Número", "", "text"],
    ["paginas", "Páginas", "ej.: 19-27", "text"],
    ["doi", "DOI", "ej.: 10.1097/j.pain…", "text"],
    ["url", "URL", "si no hay DOI", "text"],
  ],
  libro: [
    ["autores", "Autores", "Una persona por línea, como «Apellido, Nombre»", "textarea", true],
    ["titulo", "Título", "", "text", true],
    ["subtitulo", "Subtítulo", "", "text", true],
    ["edicion", "Edición", "ej.: 3.ª ed.", "text"],
    ["anio", "Año", "", "text"],
    ["lugar", "Lugar", "ej.: Montevideo", "text"],
    ["editorial", "Editorial", "", "text"],
    ["isbn", "ISBN", "", "text"],
    ["paginasTotales", "Páginas (total)", "", "text"],
    ["url", "URL o DOI", "para libros en línea", "text", true],
  ],
  capitulo: [
    ["autores", "Autores del capítulo", "Una persona por línea, «Apellido, Nombre»", "textarea", true],
    ["titulo", "Título del capítulo o artículo", "La analítica: la parte que se cita", "text", true],
    ["editores", "Editores o coordinadores del libro", "Una persona por línea, «Apellido, Nombre»", "textarea", true],
    ["libro", "Título del libro o compilación", "La obra que contiene el capítulo", "text", true],
    ["anio", "Año", "", "text"],
    ["paginas", "Páginas del capítulo", "ej.: 45-72", "text"],
    ["lugar", "Lugar", "", "text"],
    ["editorial", "Editorial", "", "text"],
    ["isbn", "ISBN", "", "text"],
    ["doi", "DOI", "", "text"],
  ],
  web: [
    ["autores", "Autor o institución", "Si es un organismo, escribí el nombre completo en una línea", "textarea", true],
    ["titulo", "Título de la página", "", "text", true],
    ["sitio", "Nombre del sitio", "ej.: gub.uy", "text"],
    ["anio", "Año", "", "text"],
    ["fechaTexto", "Fecha completa", "ej.: 14 de mayo de 2024 (si se conoce)", "text", true],
    ["url", "URL", "", "text", true],
    ["fechaAcceso", "Fecha de consulta", "Editable; por defecto, hoy", "text", true],
  ],
  blog: [
    ["autores", "Autor de la entrada", "«Apellido, Nombre»", "textarea", true],
    ["titulo", "Título de la entrada", "", "text", true],
    ["sitio", "Nombre del blog", "", "text"],
    ["anio", "Año", "", "text"],
    ["fechaTexto", "Fecha completa", "ej.: 14 de mayo de 2024", "text", true],
    ["url", "URL", "", "text", true],
    ["fechaAcceso", "Fecha de consulta", "", "text", true],
  ],
  video: [
    ["autores", "Autor o canal", "Nombre del canal en una línea", "textarea", true],
    ["titulo", "Título del video", "", "text", true],
    ["sitio", "Plataforma", "ej.: YouTube", "text"],
    ["anio", "Año", "", "text"],
    ["fechaTexto", "Fecha de publicación", "ej.: 14 de mayo de 2024", "text", true],
    ["url", "URL", "", "text", true],
    ["fechaAcceso", "Fecha de consulta", "", "text", true],
  ],
  tesis: [
    ["autores", "Autor", "«Apellido, Nombre»", "textarea", true],
    ["titulo", "Título de la tesis", "", "text", true],
    ["clase", "Tipo de tesis", "ej.: Tesis de maestría", "text"],
    ["anio", "Año", "", "text"],
    ["editorial", "Institución", "ej.: Universidad de la República", "text", true],
    ["url", "URL", "si está en un repositorio", "text", true],
  ],
  informe: [
    ["autores", "Autor o institución", "", "textarea", true],
    ["titulo", "Título del informe", "", "text", true],
    ["anio", "Año", "", "text"],
    ["editorial", "Institución o editorial", "", "text"],
    ["lugar", "Lugar", "", "text"],
    ["url", "URL", "", "text", true],
  ],
};

const NOMBRES_TIPO = {
  articulo: "Artículo de revista", libro: "Libro",
  capitulo: "Capítulo o contribución en libro", web: "Página web",
  blog: "Entrada de blog", video: "Video", tesis: "Tesis", informe: "Informe",
};

// ─────────────── Conversión formulario ⇄ meta ───────────────

function parseAutores(texto) {
  return texto.split("\n").map(l => l.trim()).filter(Boolean).map(l => {
    if (l.includes(",")) {
      const [fam, dado] = l.split(/,(.+)/);
      return { family: fam.trim(), given: (dado || "").trim() };
    }
    const partes = l.split(" ");
    if (partes.length === 1 || partes.length > 3) return { family: l, given: "", _literal: partes.length > 3 };
    const fam = partes.pop();
    return { family: fam, given: partes.join(" ") };
  });
}

function autoresATexto(lista) {
  return (lista || []).map(a =>
    a.given ? `${a.family}, ${a.given}` : a.family || ""
  ).filter(Boolean).join("\n");
}

function formAMeta() {
  const tipo = $("campo-tipo").value;
  const v = (id) => { const el = $("f-" + id); return el ? el.value.trim() : ""; };
  const meta = {
    _tipo: tipo,
    _fuente: estado.registro?._fuente || "Manual",
    title: [v("titulo")],
    author: parseAutores(v("autores")),
    published: { "date-parts": [[v("anio")]] },
  };
  if (v("subtitulo")) meta.subtitle = v("subtitulo");
  if (v("editores")) meta.editor = parseAutores(v("editores"));
  const cont = v("revista") || v("libro") || v("sitio");
  if (cont) meta["container-title"] = [cont];
  if (v("volumen")) meta.volume = v("volumen");
  if (v("numero")) meta.issue = v("numero");
  if (v("paginas")) meta.page = v("paginas");
  if (v("paginasTotales")) meta["number-of-pages"] = v("paginasTotales");
  if (v("editorial")) meta.publisher = v("editorial");
  if (v("lugar")) meta["publisher-location"] = v("lugar");
  if (v("edicion")) meta.edition = v("edicion");
  if (v("isbn")) meta.ISBN = v("isbn");
  if (v("doi")) meta.DOI = v("doi");
  if (v("clase")) meta.genre = v("clase");
  if (v("url")) meta._url = v("url");
  if (v("fechaTexto")) meta._fecha_texto = v("fechaTexto");
  if (v("fechaAcceso")) meta._fecha_acceso = v("fechaAcceso");
  return meta;
}

function metaAForm(meta) {
  const tipo = meta._tipo || "articulo";
  $("campo-tipo").value = tipo;
  construirCampos(tipo);
  const set = (id, val) => { const el = $("f-" + id); if (el) el.value = val || ""; };
  const cont = Array.isArray(meta["container-title"])
    ? (meta["container-title"][0] || "") : (meta["container-title"] || "");
  set("autores", autoresATexto(meta.author));
  set("editores", autoresATexto(meta.editor));
  set("titulo", Array.isArray(meta.title) ? meta.title[0] || "" : meta.title || "");
  set("subtitulo", Array.isArray(meta.subtitle) ? meta.subtitle[0] : meta.subtitle);
  set("revista", cont); set("libro", cont); set("sitio", cont);
  set("anio", anioDe(meta));
  set("volumen", meta.volume); set("numero", meta.issue);
  set("paginas", meta.page); set("paginasTotales", meta["number-of-pages"]);
  set("editorial", meta.publisher); set("lugar", meta["publisher-location"]);
  set("edicion", meta.edition); set("isbn", meta.ISBN);
  set("doi", meta.DOI); set("clase", meta.genre);
  set("url", meta._url);
  set("fechaTexto", meta._fecha_texto);
  set("fechaAcceso", meta._fecha_acceso ||
      (["web", "blog", "video"].includes(tipo) ? HOY : ""));
  $("insignia-fuente").textContent = meta._fuente || "Manual";
}

function anioDe(meta) {
  const p = meta.published || meta.issued;
  if (p && p["date-parts"] && p["date-parts"][0] && p["date-parts"][0][0]) {
    return String(p["date-parts"][0][0]);
  }
  return "";
}

// ─────────────── Construcción del formulario ───────────────

function construirCampos(tipo) {
  const cont = $("campos");
  cont.innerHTML = "";
  for (const [id, etiqueta, pista, control, ancho] of ESQUEMAS[tipo]) {
    const div = document.createElement("div");
    if (ancho) div.className = "ancho-total";
    const lab = document.createElement("label");
    lab.htmlFor = "f-" + id;
    lab.textContent = etiqueta;
    if (pista) {
      const p = document.createElement("span");
      p.className = "pista";
      p.textContent = pista;
      lab.appendChild(p);
    }
    const el = control === "textarea"
      ? document.createElement("textarea")
      : Object.assign(document.createElement("input"), { type: "text" });
    el.id = "f-" + id;
    el.addEventListener("input", previsualizarConRetardo);
    div.append(lab, el);
    cont.appendChild(div);
  }
  if (["web", "blog", "video"].includes(tipo)) {
    const fa = $("f-fechaAcceso");
    if (fa && !fa.value) fa.value = HOY;
  }
}

function poblarSelectorTipo() {
  const sel = $("campo-tipo");
  sel.innerHTML = "";
  for (const [valor, nombre] of Object.entries(NOMBRES_TIPO)) {
    sel.appendChild(new Option(nombre, valor));
  }
  sel.addEventListener("change", () => {
    const previo = formAMeta();
    construirCampos(sel.value);
    previo._tipo = sel.value;
    metaAForm(previo);
    previsualizar();
  });
}

// ─────────────────────── Red ───────────────────────

async function api(ruta, cuerpo) {
  const r = await fetch(ruta, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cuerpo),
  });
  const datos = await r.json().catch(() => ({}));
  if (!r.ok) {
    const err = new Error(datos.error || "Error de conexión con el servidor.");
    err.derivar = datos.derivar;
    throw err;
  }
  return datos;
}

function ponerEstado(texto, clase) {
  const el = $("estado");
  el.textContent = texto;
  el.className = "estado " + (clase || "");
}

// ─────────────────────── Búsqueda ───────────────────────

function fuentesElegidas() {
  return [...document.querySelectorAll(".chk-fuente:checked")].map(c => c.value);
}

async function buscar(avanzada) {
  ponerEstado("Buscando en las bases…", "ocupado");
  $("zona-resultados").hidden = true;
  $("zona-autores").hidden = true;
  estado.filtroAutor = null;
  try {
    let datos;
    if (avanzada) {
      datos = await api("/api/avanzada", {
        titulo: $("av-titulo").value, autor: $("av-autor").value,
        anio: $("av-anio").value, fuentes: fuentesElegidas(),
      });
    } else {
      datos = await api("/api/buscar", { q: $("q").value, fuentes: fuentesElegidas() });
    }
    estado.resultados = datos.resultados || [];
    if (estado.resultados.length === 1) {
      ponerEstado("✓ Registro encontrado. Revisalo y corregí lo que haga falta.", "ok");
      cargarRegistro(estado.resultados[0]);
      return;
    }
    ponerEstado(`✓ ${estado.resultados.length} resultados. Elegí la publicación correcta.`, "ok");
    mostrarChipsAutores(avanzada ? $("av-autor").value.trim() : "");
    mostrarResultados();
  } catch (e) {
    if (e.derivar === "avanzada") {
      const det = document.querySelector(".avanzada");
      det.open = true;
      $("av-titulo").value = $("q").value.trim();
      $("av-titulo").focus();
      ponerEstado(e.message, "ocupado");
    } else {
      ponerEstado(e.message, "error");
    }
  }
}

function nombreCompleto(a) {
  return (a.given ? a.given + " " : "") + (a.family || "");
}

function mostrarChipsAutores(consultaAutor) {
  const vistos = new Map();
  for (const m of estado.resultados) {
    for (const a of (m.author || [])) {
      const clave = nombreCompleto(a).toLowerCase().trim();
      if (clave && !vistos.has(clave)) vistos.set(clave, nombreCompleto(a));
    }
  }
  // Si la búsqueda fue por autor, los chips muestran solo las personas
  // cuyo nombre coincide con lo consultado (desambiguación de homónimos).
  if (consultaAutor) {
    const términos = sinAcentos(consultaAutor).split(/\s+/).filter(Boolean);
    const coinciden = new Map(
      [...vistos].filter(([clave]) =>
        términos.some(t => sinAcentos(clave).includes(t)))
    );
    if (coinciden.size) {
      vistos.clear();
      for (const [k, v] of coinciden) vistos.set(k, v);
    }
  }
  const zona = $("zona-autores");
  const cont = $("chips-autores");
  cont.innerHTML = "";
  if (vistos.size < 2 || vistos.size > 40) { zona.hidden = true; return; }
  for (const [clave, nombre] of vistos) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip";
    b.textContent = nombre;
    b.setAttribute("aria-pressed", "false");
    b.addEventListener("click", () => {
      estado.filtroAutor = estado.filtroAutor === clave ? null : clave;
      for (const otro of cont.children) otro.setAttribute("aria-pressed", "false");
      if (estado.filtroAutor) b.setAttribute("aria-pressed", "true");
      mostrarResultados();
    });
    cont.appendChild(b);
  }
  zona.hidden = false;
}

function mostrarResultados() {
  const lista = $("lista-resultados");
  lista.innerHTML = "";
  let visibles = estado.resultados;
  if (estado.filtroAutor) {
    visibles = visibles.filter(m => (m.author || [])
      .some(a => nombreCompleto(a).toLowerCase().trim() === estado.filtroAutor));
  }
  $("cuenta-resultados").textContent = visibles.length;
  for (const m of visibles) {
    const li = document.createElement("li");
    const b = document.createElement("button");
    b.type = "button";
    const titulo = Array.isArray(m.title) ? m.title[0] : m.title;
    const autores = (m.author || []).slice(0, 3).map(a => a.family).filter(Boolean).join("; ");
    b.innerHTML = "";
    const fuerte = document.createElement("strong");
    fuerte.textContent = titulo || "[Sin título]";
    const linea = document.createElement("span");
    linea.className = "meta-linea";
    linea.textContent = [autores, anioDe(m) || "s. f.",
      NOMBRES_TIPO[m._tipo] || m._tipo, m._fuente].filter(Boolean).join(" · ");
    b.append(fuerte, linea);
    b.addEventListener("click", () => cargarRegistro(m));
    li.appendChild(b);
    lista.appendChild(li);
  }
  $("zona-resultados").hidden = false;
}

// ─────────────────────── Registro y vista previa ───────────────────────

function cargarRegistro(meta, indiceBiblio = null) {
  estado.registro = JSON.parse(JSON.stringify(meta));
  estado.editandoBiblio = indiceBiblio;
  $("sin-registro").hidden = true;
  $("form-registro").hidden = false;
  $("zona-vista").hidden = false;
  $("btn-agregar").textContent = indiceBiblio === null
    ? "Añadir a la bibliografía ↓" : "Guardar cambios en la bibliografía ↓";
  metaAForm(estado.registro);
  previsualizar();
  if (window.matchMedia("(max-width: 880px)").matches) {
    $("panel-registro").scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

let temporizador = null;
function previsualizarConRetardo() {
  clearTimeout(temporizador);
  temporizador = setTimeout(previsualizar, 350);
}

let fichaVista = 0;   // descarta respuestas que llegan fuera de orden
async function previsualizar() {
  if ($("form-registro").hidden) return;
  const ficha = ++fichaVista;
  const meta = formAMeta();
  try {
    const r = await api("/api/formatear", { meta, norma: estado.norma, plantillas: estado.plantillas });
    if (ficha !== fichaVista) return;
    $("vista-ref").innerHTML = r.html;
    $("vista-en-texto").textContent = r.en_texto;
    $("nombre-norma").textContent = nombreNorma(estado.norma);
    const av = $("avisos");
    if (r.avisos && r.avisos.length) {
      av.textContent = "Falta: " + r.avisos.join(", ") + ".";
      av.hidden = false;
    } else {
      av.hidden = true;
    }
  } catch (e) { /* sin conexión momentánea: se reintenta al próximo cambio */ }
}

// ─────────────────────── Copiado con formato ───────────────────────

async function copiarRico(html, texto) {
  try {
    if (navigator.clipboard && window.ClipboardItem) {
      await navigator.clipboard.write([new ClipboardItem({
        "text/html": new Blob([html], { type: "text/html" }),
        "text/plain": new Blob([texto], { type: "text/plain" }),
      })]);
      return true;
    }
  } catch (e) { /* sigue al plan B */ }
  try {
    await navigator.clipboard.writeText(texto);
    return true;
  } catch (e) { return false; }
}

function htmlAPlano(html) {
  const d = document.createElement("div");
  d.innerHTML = html;
  return d.textContent;
}

// ─────────────────────── Bibliografía ───────────────────────

function guardarBiblio() {
  localStorage.setItem("biblio", JSON.stringify(estado.biblio));
}

function nombreNorma(clave) {
  return estado.normasCfg?.[clave]?.nombre || NOMBRES_NORMA[clave] || clave;
}

let fichaBiblio = 0;
async function pintarBiblio() {
  const lista = $("lista-biblio");
  const vacia = $("biblio-vacia");
  const acciones = $("acciones-biblio");
  $("cuenta-biblio").textContent = estado.biblio.length || "";
  $("nota-orden").textContent = estado.norma === "vancouver"
    ? "Vancouver: numerada según el orden en que añadiste cada fuente. Podés reordenarlas con ↑ ↓."
    : "Ordenada alfabéticamente por autor, como exige la norma.";
  if (!estado.biblio.length) {
    lista.innerHTML = "";
    lista.hidden = true; vacia.hidden = false; acciones.hidden = true;
    return;
  }
  vacia.hidden = true; lista.hidden = false; acciones.hidden = false;
  const ficha = ++fichaBiblio;
  try {
    const r = await api("/api/biblio", { refs: estado.biblio, norma: estado.norma, plantillas: estado.plantillas });
    if (ficha !== fichaBiblio) return;
    lista.innerHTML = "";
    for (const item of r.items) {
      const li = document.createElement("li");
      li.className = "item-ref";

      const texto = document.createElement("div");
      texto.className = "texto-ref";
      texto.innerHTML = (item.numero ? `<span class="num">${item.numero}.</span> ` : "") + item.html;

      const herr = document.createElement("div");
      herr.className = "herramientas";
      const mkBtn = (rotulo, titulo, fn) => {
        const b = document.createElement("button");
        b.type = "button"; b.textContent = rotulo; b.title = titulo;
        b.setAttribute("aria-label", titulo);
        b.addEventListener("click", fn);
        return b;
      };
      herr.append(
        mkBtn("⧉", "Copiar esta referencia con formato", async () => {
          await copiarRico(item.html, item.texto);
          ponerEstadoBiblio("✓ Referencia copiada.");
        }),
        mkBtn("✎", "Editar esta referencia", () => {
          cargarRegistro(estado.biblio[item.indice], item.indice);
        }),
        mkBtn("↑", "Subir (cambia el número en Vancouver)", () => moverRef(item.indice, -1)),
        mkBtn("↓", "Bajar", () => moverRef(item.indice, +1)),
        mkBtn("✕", "Quitar de la bibliografía", () => {
          estado.biblio.splice(item.indice, 1);
          if (estado.editandoBiblio === item.indice) estado.editandoBiblio = null;
          guardarBiblio(); pintarBiblio();
        }),
      );

      li.append(texto, herr);

      const pie = document.createElement("div");
      pie.className = "pie-item";
      let piezas = [`Cita en el texto: ${item.en_texto}`];
      if (item.avisos.length) {
        piezas.push(`⚠ falta: ${item.avisos.join(", ")}`);
      }
      pie.textContent = piezas.join("   ·   ");
      if (item.avisos.length) pie.classList.add("aviso-mini");
      li.appendChild(pie);

      lista.appendChild(li);
    }
  } catch (e) {
    lista.innerHTML = "";
    ponerEstadoBiblio(e.message);
  }
}

function moverRef(indice, delta) {
  const destino = indice + delta;
  if (destino < 0 || destino >= estado.biblio.length) return;
  const [m] = estado.biblio.splice(indice, 1);
  estado.biblio.splice(destino, 0, m);
  guardarBiblio(); pintarBiblio();
}

let avisoBiblioTmp = null;
function ponerEstadoBiblio(texto) {
  const nota = $("nota-orden");
  const original = nota.dataset.original || nota.textContent;
  nota.dataset.original = original;
  nota.textContent = texto;
  clearTimeout(avisoBiblioTmp);
  avisoBiblioTmp = setTimeout(() => { nota.textContent = nota.dataset.original; }, 2500);
}

async function copiarBiblioCompleta() {
  if (!estado.biblio.length) return;
  const r = await api("/api/biblio", { refs: estado.biblio, norma: estado.norma, plantillas: estado.plantillas });
  const html = r.items.map(i =>
    `<p style="padding-left:2em;text-indent:-2em">${i.numero ? i.numero + ". " : ""}${i.html}</p>`
  ).join("\n");
  const texto = r.items.map(i => (i.numero ? i.numero + ". " : "") + i.texto).join("\n\n");
  await copiarRico(html, texto);
  ponerEstadoBiblio("✓ Bibliografía completa copiada con formato.");
}

async function exportarBiblio() {
  if (!estado.biblio.length) return;
  const formato = $("sel-exportar").value;
  const r = await fetch("/api/exportar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refs: estado.biblio, norma: estado.norma, formato, plantillas: estado.plantillas }),
  });
  const blob = await r.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  const ext = { rtf: "rtf", html: "html", ris: "ris", bibtex: "bib", txt: "txt" }[formato];
  a.download = `referencias-${estado.norma}.${ext}`;
  a.click();
  URL.revokeObjectURL(a.href);
}

// ─────────────────────── Tema ───────────────────────

function aplicarTema(t) {
  const raiz = document.documentElement;
  if (t === "auto") {
    t = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  raiz.dataset.theme = t;
}

function alternarTema() {
  const actual = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  localStorage.setItem("tema", actual);
  aplicarTema(actual);
}

// ─────────────────────── Arranque ───────────────────────

document.addEventListener("DOMContentLoaded", async () => {
  poblarSelectorTipo();
  aplicarTema(localStorage.getItem("tema") || "auto");
  $("btn-tema").addEventListener("click", alternarTema);

  // Normas: configuración desde el servidor → selector dinámico + editor
  try {
    const r = await fetch("/api/normas");
    estado.normasCfg = await r.json();
  } catch (e) { estado.normasCfg = null; }
  construirSelectorNormas();
  iniciarEditorNormas();

  // Búsqueda
  $("btn-buscar").addEventListener("click", () => buscar(false));
  $("q").addEventListener("keydown", (e) => { if (e.key === "Enter") buscar(false); });
  $("btn-avanzada").addEventListener("click", () => buscar(true));

  // Entrada manual
  $("btn-manual").addEventListener("click", () => {
    const tipo = $("tipo-manual").value;
    cargarRegistro({ _tipo: tipo, _fuente: "Manual", title: [""], author: [] });
  });

  // Vista previa y bibliografía
  $("btn-copiar-ref").addEventListener("click", async () => {
    const ok = await copiarRico($("vista-ref").innerHTML, htmlAPlano($("vista-ref").innerHTML));
    ponerEstado(ok ? "✓ Copiada con formato, lista para pegar." : "No se pudo copiar.", ok ? "ok" : "error");
  });
  $("btn-copiar-texto").addEventListener("click", async () => {
    await navigator.clipboard.writeText(htmlAPlano($("vista-ref").innerHTML));
    ponerEstado("✓ Copiada como texto plano.", "ok");
  });
  $("btn-agregar").addEventListener("click", () => {
    const meta = formAMeta();
    if (estado.editandoBiblio !== null) {
      estado.biblio[estado.editandoBiblio] = meta;
      estado.editandoBiblio = null;
      $("btn-agregar").textContent = "Añadir a la bibliografía ↓";
    } else {
      estado.biblio.push(meta);
    }
    guardarBiblio();
    pintarBiblio();
    $("panel-biblio").scrollIntoView({ behavior: "smooth", block: "start" });
  });

  $("btn-copiar-biblio").addEventListener("click", copiarBiblioCompleta);
  $("btn-exportar").addEventListener("click", exportarBiblio);
  $("btn-limpiar").addEventListener("click", () => {
    if (confirm("¿Vaciar la bibliografía de esta sesión? Esta acción no se puede deshacer.")) {
      estado.biblio = [];
      estado.editandoBiblio = null;
      guardarBiblio();
      pintarBiblio();
    }
  });

  pintarBiblio();
});

// ─────────────── Selector dinámico de normas (panel 2) ───────────────

function construirSelectorNormas() {
  const cont = $("selector-normas");
  if (!cont) return;
  const cfg = estado.normasCfg || {
    apa7: { nombre: "APA 7" }, vancouver: { nombre: "Vancouver" },
    iso690: { nombre: "ISO 690" }, chicago: { nombre: "Chicago" },
  };
  if (!cfg[estado.norma]) estado.norma = Object.keys(cfg)[0];
  for (const [clave, datos] of Object.entries(cfg)) {
    const label = document.createElement("label");
    const radio = Object.assign(document.createElement("input"),
      { type: "radio", name: "norma", value: clave, checked: clave === estado.norma });
    const span = document.createElement("span");
    span.textContent = datos.nombre || clave;
    radio.addEventListener("change", () => {
      estado.norma = clave;
      localStorage.setItem("norma", clave);
      $("nombre-norma").textContent = datos.nombre || clave;
      previsualizar();
      pintarBiblio();
      sincronizarEditor();
    });
    label.append(radio, span);
    cont.appendChild(label);
  }
}

// ─────────────── Editor de normas (panel 4) ───────────────

const EJEMPLOS = {
  articulo: { _tipo: "articulo", title: ["Acceso abierto en las universidades"],
    author: [{ family: "Fontans", given: "Exequiel" }, { family: "Pérez", given: "Ana" }],
    published: { "date-parts": [["2021"]] }, "container-title": ["Informatio"],
    volume: "26", issue: "1", page: "12-34", DOI: "10.35643/info.26.1.2" },
  libro: { _tipo: "libro", title: ["Conservación preventiva en museos"],
    author: [{ family: "Silva", given: "Luis" }], published: { "date-parts": [["2024"]] },
    publisher: "Ediciones FIC", "publisher-location": "Montevideo",
    edition: "2.ª ed.", "number-of-pages": "240", ISBN: "9789974000000" },
  capitulo: { _tipo: "capitulo", title: ["La luz como agente de deterioro"],
    author: [{ family: "Da Costa", given: "Gabriel" }],
    editor: [{ family: "Pérez", given: "Ana" }, { family: "Silva", given: "Luis" }],
    "container-title": ["Conservación preventiva en museos"],
    published: { "date-parts": [["2024"]] }, page: "45-72",
    publisher: "Ediciones FIC", "publisher-location": "Montevideo", ISBN: "9789974000000" },
  web: { _tipo: "web", title: ["Trámites en línea"], author: [],
    published: { "date-parts": [["2023"]] }, "container-title": ["gub.uy"],
    _url: "https://www.gub.uy/tramites", _fecha_acceso: HOY },
  blog: { _tipo: "blog", title: ["Novedades de LibreOffice 25"],
    author: [{ family: "González", given: "Marta" }],
    published: { "date-parts": [["2025"]] }, _fecha_texto: "3 de marzo de 2025",
    "container-title": ["El blog del documento"], _url: "https://ejemplo.uy/entrada", _fecha_acceso: HOY },
  video: { _tipo: "video", title: ["Exportar PDF con LibreOffice"],
    author: [{ family: "Canal EDD", given: "", _literal: true }],
    published: { "date-parts": [["2025"]] }, _fecha_texto: "3 de marzo de 2025",
    "container-title": ["YouTube"], _url: "https://youtu.be/ejemplo", _fecha_acceso: HOY },
  tesis: { _tipo: "tesis", title: ["Acceso abierto en Uruguay"],
    author: [{ family: "Rodríguez", given: "Paula" }],
    published: { "date-parts": [["2020"]] }, publisher: "Universidad de la República",
    genre: "Tesis de maestría", _url: "https://colibri.udelar.edu.uy/ejemplo" },
  informe: { _tipo: "informe", title: ["Estado de los archivos universitarios"],
    author: [{ family: "Comisión Sectorial de Investigación Científica", given: "", _literal: true }],
    published: { "date-parts": [["2022"]] }, publisher: "Udelar",
    _url: "https://ejemplo.uy/informe" },
};

function plantillaBase(norma, tipo) {
  return estado.normasCfg?.[norma]?.tipos?.[tipo] ?? "";
}

function plantillaVigente(norma, tipo) {
  return estado.plantillas?.[norma]?.[tipo] ?? plantillaBase(norma, tipo);
}

function guardarPlantillas() {
  // Poda ramas vacías para que «Editada» refleje la realidad
  for (const n of Object.keys(estado.plantillas)) {
    if (!Object.keys(estado.plantillas[n]).length) delete estado.plantillas[n];
  }
  localStorage.setItem("plantillas", JSON.stringify(estado.plantillas));
}

function sincronizarEditor() {
  const selN = $("ed-norma");
  if (!selN || !estado.normasCfg) return;
  if (selN.value !== estado.norma && estado.normasCfg[estado.norma]) selN.value = estado.norma;
  refrescarEditor();
}

function refrescarEditor() {
  const norma = $("ed-norma").value;
  const tipo = $("ed-tipo").value;
  $("ed-plantilla").value = plantillaVigente(norma, tipo);
  $("insignia-editada").hidden = !(estado.plantillas?.[norma]?.[tipo]);
  previsualizarEditor();
}

let tmpEditor = null;
function previsualizarEditorConRetardo() {
  clearTimeout(tmpEditor);
  tmpEditor = setTimeout(previsualizarEditor, 350);
}

async function previsualizarEditor() {
  const norma = $("ed-norma").value;
  const tipo = $("ed-tipo").value;
  const tipoBase = tipo.replace("_sin_autor", "");
  const meta = JSON.parse(JSON.stringify(EJEMPLOS[tipoBase] || EJEMPLOS.articulo));
  if (tipo.endsWith("_sin_autor")) meta.author = [];
  const prueba = { [norma]: { [tipo]: $("ed-plantilla").value } };
  try {
    const r = await api("/api/formatear", { meta, norma, plantillas: prueba });
    $("ed-vista").innerHTML = r.html;
  } catch (e) { /* se reintenta al próximo cambio */ }
}

function iniciarEditorNormas() {
  const selN = $("ed-norma");
  if (!selN || !estado.normasCfg) return;

  for (const [clave, datos] of Object.entries(estado.normasCfg)) {
    selN.appendChild(new Option(datos.nombre || clave, clave));
  }
  selN.value = estado.norma;

  const selT = $("ed-tipo");
  const poblarTipos = () => {
    const previo = selT.value;
    selT.innerHTML = "";
    const tipos = Object.keys(estado.normasCfg[selN.value]?.tipos || {});
    for (const t of tipos) {
      const base = t.replace("_sin_autor", "");
      const nombre = (NOMBRES_TIPO[base] || base) + (t.endsWith("_sin_autor") ? " — sin autor" : "");
      selT.appendChild(new Option(nombre, t));
    }
    if ([...selT.options].some(o => o.value === previo)) selT.value = previo;
  };
  poblarTipos();

  selN.addEventListener("change", () => { poblarTipos(); refrescarEditor(); });
  selT.addEventListener("change", refrescarEditor);
  $("ed-plantilla").addEventListener("input", previsualizarEditorConRetardo);

  $("ed-guardar").addEventListener("click", () => {
    const norma = selN.value, tipo = selT.value;
    const valor = $("ed-plantilla").value.trim();
    if (!estado.plantillas[norma]) estado.plantillas[norma] = {};
    if (valor && valor !== plantillaBase(norma, tipo)) {
      estado.plantillas[norma][tipo] = valor;
    } else {
      delete estado.plantillas[norma][tipo];
    }
    guardarPlantillas();
    refrescarEditor();
    previsualizar();
    pintarBiblio();
    ponerEstadoBiblio("✓ Plantilla guardada.");
  });

  $("ed-reset-tipo").addEventListener("click", () => {
    const norma = selN.value, tipo = selT.value;
    if (estado.plantillas[norma]) delete estado.plantillas[norma][tipo];
    guardarPlantillas(); refrescarEditor(); previsualizar(); pintarBiblio();
  });

  $("ed-reset-norma").addEventListener("click", () => {
    delete estado.plantillas[selN.value];
    guardarPlantillas(); refrescarEditor(); previsualizar(); pintarBiblio();
  });

  $("ed-reset-todo").addEventListener("click", () => {
    if (confirm("¿Restablecer todas las normas a las plantillas originales de la aplicación?")) {
      estado.plantillas = {};
      guardarPlantillas(); refrescarEditor(); previsualizar(); pintarBiblio();
    }
  });

  $("ed-exportar").addEventListener("click", () => {
    const blob = new Blob([JSON.stringify(estado.plantillas, null, 2)],
      { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "plantillas-editadas.json";
    a.click();
    URL.revokeObjectURL(a.href);
  });

  $("ed-importar").addEventListener("change", async (ev) => {
    const archivo = ev.target.files[0];
    if (!archivo) return;
    try {
      const datos = JSON.parse(await archivo.text());
      if (typeof datos !== "object" || Array.isArray(datos)) throw new Error();
      estado.plantillas = datos;
      guardarPlantillas(); refrescarEditor(); previsualizar(); pintarBiblio();
      ponerEstadoBiblio("✓ Plantillas importadas.");
    } catch (e) {
      ponerEstadoBiblio("El archivo no tiene el formato esperado.");
    }
    ev.target.value = "";
  });

  refrescarEditor();
}
