const state = {
  items: [],
  view: "Pour toi",
  category: "Tout",
  query: "",
  stats: {},
};

const feed = document.querySelector("#feed");
const empty = document.querySelector("#empty");
const counter = document.querySelector("#counter");
const updated = document.querySelector("#updated");
const filters = document.querySelector("#filters");
const tabs = document.querySelector("#tabs");
const search = document.querySelector("#search");
const template = document.querySelector("#card-template");
const stats = document.querySelector("#stats");

function timeAgo(iso) {
  const seconds = Math.max(1, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "à l’instant";
  if (seconds < 3600) return `il y a ${Math.floor(seconds / 60)} min`;
  if (seconds < 86400) return `il y a ${Math.floor(seconds / 3600)} h`;
  return `il y a ${Math.floor(seconds / 86400)} j`;
}

function categories() {
  const counts = new Map();
  state.items.flatMap(i => i.categories || []).forEach(c => {
    if (["Business", "France", "Europe", "Lancement", "Levée", "Acquisition"].includes(c)) return;
    counts.set(c, (counts.get(c) || 0) + 1);
  });
  return ["Tout", ...[...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10).map(([c]) => c)];
}

function renderFilters() {
  filters.innerHTML = "";
  categories().forEach(category => {
    const button = document.createElement("button");
    button.className = `filter${state.category === category ? " active" : ""}`;
    button.textContent = category;
    button.onclick = () => {
      state.category = category;
      renderFilters();
      render();
    };
    filters.appendChild(button);
  });
}

function matchesView(item) {
  if (state.view === "Pour toi") return true;
  if (state.view === "France") return item.region === "France";
  if (state.view === "Europe") return item.region === "Europe" || item.region === "France";
  if (state.view === "Nouveaux business") return item.event === "Lancement" || ["Product Hunt", "Show HN"].includes(item.source);
  if (state.view === "Levées & M&A") return ["Levée", "Acquisition"].includes(item.event);
  return true;
}

function visibleItems() {
  const q = state.query.trim().toLowerCase();
  return state.items
    .filter(item => {
      const viewOk = matchesView(item);
      const catOk = state.category === "Tout" || (item.categories || []).includes(state.category);
      const haystack = `${item.title} ${item.summary || ""} ${item.why || ""} ${(item.categories || []).join(" ")} ${item.source} ${item.region || ""}`.toLowerCase();
      return viewOk && catOk && (!q || haystack.includes(q));
    })
    .sort((a, b) => (b.score || 0) - (a.score || 0));
}

function renderTabs() {
  [...tabs.querySelectorAll("button")].forEach(button => {
    button.classList.toggle("active", button.dataset.view === state.view);
  });
}

function renderStats() {
  const s = state.stats || {};
  stats.innerHTML = [
    s.sources ? `<span><strong>${s.sources}</strong> sources</span>` : "",
    s.france ? `<span><strong>${s.france}</strong> signaux France</span>` : "",
    s.launches ? `<span><strong>${s.launches}</strong> lancements</span>` : "",
    s.funding_ma ? `<span><strong>${s.funding_ma}</strong> levées / M&A</span>` : "",
  ].filter(Boolean).join("");
}

function render() {
  feed.innerHTML = "";
  const items = visibleItems();
  counter.textContent = `${items.length} signal${items.length > 1 ? "s" : ""}`;
  empty.hidden = items.length > 0;

  items.forEach((item, index) => {
    const node = template.content.cloneNode(true);
    const article = node.querySelector(".card");
    if (index === 0) article.classList.add("featured");

    node.querySelector(".source").textContent = item.source;
    node.querySelector(".age").textContent = timeAgo(item.published_at);
    node.querySelector(".score").textContent = `${item.score}/100`;
    node.querySelector(".interest").textContent = item.interest || "À surveiller";
    node.querySelector("h2").textContent = item.title;

    const summary = node.querySelector(".summary");
    summary.textContent = item.summary || item.domain || "Ouvrir la source pour en savoir plus.";

    const why = node.querySelector(".why-text");
    why.textContent = item.why || "Signal business à surveiller.";

    const primaryTags = [];
    if (item.event && item.event !== "Business") primaryTags.push(item.event);
    if (item.region && item.region !== "International") primaryTags.push(item.region);
    (item.sectors || []).forEach(tag => primaryTags.push(tag));
    node.querySelector(".tags").innerHTML = [...new Set(primaryTags)].slice(0, 5).map(c => `<span class="tag">${escapeHtml(c)}</span>`).join("");

    const m = item.metrics || {};
    const metricText = [
      m.points ? `${m.points} points` : "",
      m.comments ? `${m.comments} commentaires` : "",
      item.domain && !item.domain.includes("news.google.com") ? item.domain : "",
    ].filter(Boolean).join(" · ");
    node.querySelector(".metrics").textContent = metricText;

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
    state.stats = data.stats || {};
    updated.textContent = `Mis à jour ${timeAgo(data.generated_at)} · automatique toutes les 6 h`;
    renderStats();
    renderFilters();
    renderTabs();
    render();
  } catch (error) {
    updated.textContent = "Impossible de charger le radar";
    feed.innerHTML = `<p class="empty">Erreur : ${escapeHtml(error.message)}</p>`;
  }
}

tabs.addEventListener("click", event => {
  const button = event.target.closest("button[data-view]");
  if (!button) return;
  state.view = button.dataset.view;
  state.category = "Tout";
  renderTabs();
  renderFilters();
  render();
});

search.addEventListener("input", e => {
  state.query = e.target.value;
  render();
});

document.querySelector("#refresh").addEventListener("click", load);
load();
