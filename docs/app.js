"use strict";

const listEl = document.getElementById("list");
const sourceBtn = document.getElementById("sourceBtn");
const topicBtn = document.getElementById("topicBtn");
const sourcePanel = document.getElementById("sourcePanel");
const topicPanel = document.getElementById("topicPanel");
const statusEl = document.getElementById("status");
const refreshBtn = document.getElementById("refresh");
const readerEl = document.getElementById("reader");

const FILTER_KEY = "uutiset.filter";
// Tallennetaan pois päältä olevat aiheet, jotta uudet aiheet ovat oletuksena päällä.
const TOPICS_OFF_KEY = "uutiset.topicsOff";
// Henkirikosuutiset ovat oletuksena piilossa; tallennetaan vain, jos käyttäjä näyttää ne.
const HOMICIDE_KEY = "uutiset.showHomicide";
// HS ja Aamulehti kirjoittavat aiheen otsikon eteen ("Aihe | Otsikko"); muilla aihe on kategoria.
const INLINE_KICKER = new Set(["hs", "al"]);

let data = { items: [], sources: [] };
let filter = readFilter();
let topicsOff = readTopicsOff();
let showHomicide = readShowHomicide();
let itemsById = new Map();

function readFilter() {
  try { return localStorage.getItem(FILTER_KEY) || "all"; } catch { return "all"; }
}
function saveFilter(value) {
  try { localStorage.setItem(FILTER_KEY, value); } catch { /* yksityinen tila tms. */ }
}
function readTopicsOff() {
  try { return new Set(JSON.parse(localStorage.getItem(TOPICS_OFF_KEY) || "[]")); } catch { return new Set(); }
}
function saveTopicsOff() {
  try { localStorage.setItem(TOPICS_OFF_KEY, JSON.stringify([...topicsOff])); } catch { /* ei tallennusta */ }
}

function readShowHomicide() {
  try { return localStorage.getItem(HOMICIDE_KEY) === "1"; } catch { return false; }
}
function saveShowHomicide() {
  try { localStorage.setItem(HOMICIDE_KEY, showHomicide ? "1" : "0"); } catch { /* ei tallennusta */ }
}

const topicOf = (it) => it.topic || "muut";
const matchesSource = (it) => filter === "all" || it.source === filter;
const matchesTopic = (it) => !topicsOff.has(topicOf(it));
const matchesHomicide = (it) => showHomicide || !it.homicide;

const escapeHtml = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// Jutun teksti tulee kevyenä markdownina: **lihavointi**, *kursiivi*, [linkki](url), "## " väliotsikko.
function inline(text) {
  return escapeHtml(text)
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/(^|[^*])\*([^*]+)\*/g, "$1<i>$2</i>");
}
function renderParagraph(text) {
  return text.startsWith("## ") ? `<h3>${inline(text.slice(3))}</h3>` : `<p>${inline(text)}</p>`;
}

const timeFmt = new Intl.DateTimeFormat("fi-FI", { hour: "2-digit", minute: "2-digit" });
const dayFmt = new Intl.DateTimeFormat("fi-FI", { weekday: "long", day: "numeric", month: "numeric" });
const fullFmt = new Intl.DateTimeFormat("fi-FI", { weekday: "long", day: "numeric", month: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" });

function dayLabel(date) {
  const today = new Date();
  const startOf = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const diff = Math.round((startOf(today) - startOf(date)) / 86400000);
  if (diff === 0) return "Tänään";
  if (diff === 1) return "Eilen";
  return dayFmt.format(date);
}

function relative(date) {
  const min = Math.round((Date.now() - date.getTime()) / 60000);
  if (min < 1) return "juuri nyt";
  if (min < 60) return `${min} min sitten`;
  const h = Math.floor(min / 60);
  return h < 24 ? `${h} t sitten` : dayLabel(date).toLowerCase();
}

function sourceName(id) {
  return (data.sources.find((s) => s.id === id) || { name: id }).name;
}

const logo = (id, cls = "") => `<img class="${cls}" src="logos/${id}.svg" alt="" width="20" height="20">`;

// Määrät kertovat, montako juttua valinta näyttäisi muiden valintojen kanssa.
function renderPickers() {
  const sourceCounts = {};
  const topicCounts = {};
  let total = 0;
  let homicides = 0;
  for (const it of data.items) {
    if (matchesTopic(it) && matchesHomicide(it)) {
      sourceCounts[it.source] = (sourceCounts[it.source] || 0) + 1;
      total++;
    }
    if (matchesSource(it) && matchesHomicide(it)) topicCounts[topicOf(it)] = (topicCounts[topicOf(it)] || 0) + 1;
    if (it.homicide && matchesSource(it) && matchesTopic(it)) homicides++;
  }

  document.getElementById("sourceVal").textContent = filter === "all" ? "Kaikki" : sourceName(filter);
  const sourceOpt = (id, name, n, icon) => `
    <label class="opt">
      <input type="radio" name="source" value="${id}" ${id === filter ? "checked" : ""}>
      ${icon}<span class="name">${escapeHtml(name)}</span><span class="n">${n}</span>
    </label>`;
  sourcePanel.innerHTML = `<div class="panel-inner">` +
    sourceOpt("all", "Kaikki lähteet", total, "") +
    data.sources.map((s) => sourceOpt(s.id, s.name, sourceCounts[s.id] || 0, logo(s.id))).join("") +
    `</div>`;

  const topics = (data.topics || []).filter((t) => topicCounts[t.id] || topicsOff.has(t.id));
  const on = topics.filter((t) => !topicsOff.has(t.id)).length;
  document.getElementById("topicVal").textContent = topicsOff.size === 0 ? "Kaikki" : `${on}/${topics.length} valittu`;
  topicPanel.innerHTML = `<div class="panel-inner">
    <label class="opt">
      <input type="checkbox" data-topic="all" ${topicsOff.size === 0 ? "checked" : ""}>
      <span class="name"><b>Kaikki aiheet</b></span>
    </label>` +
    topics.map((t) => `
    <label class="opt">
      <input type="checkbox" data-topic="${t.id}" ${topicsOff.has(t.id) ? "" : "checked"}>
      <span class="name">${escapeHtml(t.name)}</span><span class="n">${topicCounts[t.id] || 0}</span>
    </label>`).join("") + `
    <div class="opt-sep"></div>
    <label class="opt">
      <input type="checkbox" data-homicide ${showHomicide ? "checked" : ""}>
      <span class="name">Henkirikokset<small>Oletuksena piilossa, koskee kaikkia aiheita</small></span><span class="n">${homicides}</span>
    </label>
    <button class="panel-done" type="button" data-done>Valmis</button>
  </div>`;
}

function titleHtml(it) {
  if (INLINE_KICKER.has(it.source)) {
    const i = it.title.indexOf(" | ");
    if (i > 0) {
      return { kicker: "", title: `<span class="k">${escapeHtml(it.title.slice(0, i))} |</span> ${escapeHtml(it.title.slice(i + 3))}` };
    }
    return { kicker: "", title: escapeHtml(it.title) };
  }
  const topic = (it.categories || [])[0];
  return { kicker: topic ? `<p class="kicker">${escapeHtml(topic)}</p>` : "", title: escapeHtml(it.title) };
}

function renderCard(it) {
  const date = new Date(it.published);
  const { kicker, title } = titleHtml(it);
  return `
    <a class="card" data-src="${escapeHtml(it.source)}" data-id="${escapeHtml(it.id)}" href="${escapeHtml(it.link)}">
      <div class="card-meta">
        ${logo(it.source, "logo")}
        <span class="src">${escapeHtml(sourceName(it.source))}</span>
        <time datetime="${escapeHtml(it.published)}">${timeFmt.format(date)}</time>
      </div>
      <div class="card-main">
        <div class="card-text">
          ${kicker}
          <h3 class="title">${title}</h3>
        </div>
        ${it.image ? `<img class="thumb" src="${escapeHtml(it.image)}" alt="" loading="lazy" decoding="async">` : ""}
      </div>
      ${it.summary ? `<p class="lead">${escapeHtml(it.summary)}</p>` : ""}
    </a>`;
}

function renderList() {
  const items = data.items.filter((it) => matchesSource(it) && matchesTopic(it) && matchesHomicide(it));
  if (!items.length) {
    const msg = data.items.some(matchesSource)
      ? "Valituista aiheista ei ole juttuja. Valitse lisää aiheita yltä."
      : filter === "all" ? "Ei juttuja." : `Ei ilmaisia juttuja lähteeltä ${escapeHtml(sourceName(filter))} juuri nyt.`;
    listEl.innerHTML = `<p class="empty">${msg}</p>`;
    return;
  }
  let html = "";
  let lastDay = "";
  for (const it of items) {
    const day = dayLabel(new Date(it.published));
    if (day !== lastDay) {
      html += `<h2 class="day">${escapeHtml(day)}</h2>`;
      lastDay = day;
    }
    html += renderCard(it);
  }
  listEl.innerHTML = html;
}

// --- Lukunäkymä: juttu luetaan sovelluksessa, alkuperäinen sivu vain linkkinä ---

function renderReader(it) {
  const { kicker, title } = titleHtml(it);
  const body = (it.content || []).length
    ? it.content.map(renderParagraph).join("")
    : '<p class="note">Jutun tekstiä ei saatu haettua. Lue se alkuperäiseltä sivulta.</p>';
  readerEl.dataset.src = it.source;
  readerEl.innerHTML = `
    <div class="reader-bar">
      <button class="back" type="button" data-close>
        <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" d="M15 5l-7 7 7 7"/></svg>
        Uutiset
      </button>
      <span class="src">${escapeHtml(sourceName(it.source))}</span>
      ${logo(it.source, "logo")}
    </div>
    <article class="article">
      ${kicker}
      <h1>${title}</h1>
      <p class="when">${escapeHtml(fullFmt.format(new Date(it.published)))}</p>
      ${it.hero ? `<img class="hero" src="${escapeHtml(it.hero)}" alt="">` : ""}
      ${it.summary ? `<p class="lede">${escapeHtml(it.summary)}</p>` : ""}
      <div class="body">${body}</div>
      <a class="original" href="${escapeHtml(it.link)}" target="_blank" rel="noopener">Avaa alkuperäinen juttu ↗</a>
    </article>`;
  readerEl.hidden = false;
  readerEl.scrollTop = 0;
  document.body.classList.add("reading");
}

function closeReader() {
  readerEl.hidden = true;
  readerEl.innerHTML = "";
  document.body.classList.remove("reading");
}

listEl.addEventListener("click", (e) => {
  const card = e.target.closest("a.card");
  if (!card || e.metaKey || e.ctrlKey || e.shiftKey) return;
  const it = itemsById.get(card.dataset.id);
  if (!it) return;
  e.preventDefault();
  history.pushState({ reading: it.id }, "");
  renderReader(it);
});

// Takaisin-painike, Androidin takaisin-ele ja iPhonen pyyhkäisy sulkevat jutun.
readerEl.addEventListener("click", (e) => {
  if (e.target.closest("[data-close]")) history.back();
});
window.addEventListener("popstate", (e) => {
  const it = e.state && itemsById.get(e.state.reading);
  if (it) renderReader(it); else closeReader();
});

// Rikkinäinen pikkukuva piilotetaan, jotta kortti ei jää tyhjällä laatikolla.
listEl.addEventListener("error", (e) => {
  if (e.target.matches && e.target.matches("img.thumb")) e.target.remove();
}, true);

// --- Avattavat listat ---------------------------------------------------------

function togglePanel(btn, panel, open = panel.hidden) {
  for (const [b, p] of [[sourceBtn, sourcePanel], [topicBtn, topicPanel]]) {
    const isThis = p === panel && open;
    p.hidden = !isThis;
    b.setAttribute("aria-expanded", String(isThis));
  }
}
sourceBtn.addEventListener("click", () => togglePanel(sourceBtn, sourcePanel));
topicBtn.addEventListener("click", () => togglePanel(topicBtn, topicPanel));
document.addEventListener("click", (e) => {
  if (!e.target.closest(".pickers, .panel")) togglePanel(null, null, false);
});

sourcePanel.addEventListener("change", (e) => {
  filter = e.target.value;
  saveFilter(filter);
  togglePanel(null, null, false);  // yksi valinta: lista sulkeutuu
  renderPickers();
  renderList();
});

topicPanel.addEventListener("change", (e) => {
  const input = e.target;
  if (input.matches("[data-homicide]")) {
    showHomicide = input.checked;
    saveShowHomicide();
  } else if (input.dataset.topic === "all") {
    // "Kaikki aiheet" pois päältä tyhjentää valinnat, jolloin yksittäisen aiheen voi valita helposti.
    topicsOff = input.checked ? new Set() : new Set((data.topics || []).map((t) => t.id));
  } else if (input.checked) {
    topicsOff.delete(input.dataset.topic);
  } else {
    topicsOff.add(input.dataset.topic);
  }
  saveTopicsOff();
  renderPickers();
  renderList();
});
topicPanel.addEventListener("click", (e) => {
  if (e.target.closest("[data-done]")) togglePanel(null, null, false);
});

function renderStatus() {
  if (!data.updated) return;
  const failed = Object.entries(data.status || {}).filter(([, s]) => !s.ok).map(([id]) => sourceName(id));
  statusEl.textContent = `Päivitetty ${relative(new Date(data.updated))} · vain ilmaiset jutut, ei videoita` +
    (failed.length ? ` · ei saatu: ${failed.join(", ")}` : "");
}

async function load() {
  refreshBtn.classList.add("spin");
  try {
    const res = await fetch(`news.json?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error(res.status);
    data = await res.json();
    if (filter !== "all" && !data.sources.some((s) => s.id === filter)) filter = "all";
    itemsById = new Map(data.items.map((it) => [it.id, it]));
    renderPickers();
    renderList();
    renderStatus();
  } catch (err) {
    statusEl.textContent = "Uutisten haku epäonnistui. " + (navigator.onLine ? "" : "Ei verkkoyhteyttä.");
  } finally {
    refreshBtn.classList.remove("spin");
  }
}

refreshBtn.addEventListener("click", load);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && readerEl.hidden) load();
});
setInterval(renderStatus, 60000);

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js").catch(() => {});
}

load();
