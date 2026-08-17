const state = { items: [], category: "Tout", query: "" };
const feed = document.querySelector("#feed");
const empty = document.querySelector("#empty");
const counter = document.querySelector("#counter");
const updated = document.querySelector("#updated");
const filters = document.querySelector("#filters");
const search = document.querySelector("#search");
const template = document.querySelector("#card-template");

function timeAgo(iso) {
  const seconds = Math.max(1, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 3600) return `il y a ${Math.floor(seconds / 60)} min`;
  if (seconds < 86400) return `il y a ${Math.floor(seconds / 3600)} h`;
  return `il y a ${Math.floor(seconds / 86400)} j`;
}

function categories() {
  const counts = new Map();
  state.items.flatMap(i => i.categories || []).forEach(c => counts.set(c, (counts.get(c) || 0) + 1));
  return ["Tout", ...[...counts.entries()].sort((a,b) => b[1]-a[1]).map(([c]) => c)];
}

function renderFilters() {
  filters.innerHTML = "";
  categories().forEach(category => {
    const button = document.createElement("button");
    button.className = `filter${state.category === category ? " active" : ""}`;
    button.textContent = category;
    button.onclick = () => { state.category = category; renderFilters(); render(); };
    filters.appendChild(button);
  });
}

function visibleItems() {
  const q = state.query.trim().toLowerCase();
  return state.items.filter(item => {
    const catOk = state.category === "Tout" || (item.categories || []).includes(state.category);
    const haystack = `${item.title} ${item.summary || ""} ${(item.categories || []).join(" ")} ${item.source}`.toLowerCase();
    return catOk && (!q || haystack.includes(q));
  });
}

function render() {
  feed.innerHTML = "";
  const items = visibleItems();
  counter.textContent = `${items.length} signal${items.length > 1 ? "s" : ""}`;
  empty.hidden = items.length > 0;
  items.forEach(item => {
    const node = template.content.cloneNode(true);
    node.querySelector(".source").textContent = item.source;
    node.querySelector(".age").textContent = timeAgo(item.published_at);
    node.querySelector(".score").textContent = `${item.score}/100`;
    node.querySelector("h2").textContent = item.title;
    const summary = node.querySelector(".summary");
    summary.textContent = item.summary || item.domain || "Ouvrir la source pour en savoir plus.";
    node.querySelector(".tags").innerHTML = (item.categories || []).map(c => `<span class="tag">${escapeHtml(c)}</span>`).join("");
    const m = item.metrics || {};
    node.querySelector(".metrics").textContent = [m.points ? `${m.points} points` : "", m.comments ? `${m.comments} commentaires` : ""].filter(Boolean).join(" · ");
    const link = node.querySelector(".read");
    link.href = item.url;
    feed.appendChild(node);
  });
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

async function load() {
  try {
    const response = await fetch(`data/feed.json?v=${Date.now()}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.items = data.items || [];
    updated.textContent = `Mis à jour ${timeAgo(data.generated_at)} · ${state.items.length} éléments`;
    renderFilters();
    render();
  } catch (error) {
    updated.textContent = "Impossible de charger le radar";
    feed.innerHTML = `<p class="empty">Erreur : ${escapeHtml(error.message)}</p>`;
  }
}

search.addEventListener("input", e => { state.query = e.target.value; render(); });
document.querySelector("#refresh").addEventListener("click", load);
load();
