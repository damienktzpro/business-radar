const state = {
  items: [],
  view: "Pour toi",
  category: "Tout",
  query: "",
  stats: {},
  favorites: new Set(JSON.parse(localStorage.getItem("businessRadarFavoritesV22") || "[]")),
  preferences: JSON.parse(localStorage.getItem("businessRadarPreferencesV22") || "{}"),
};

// V2.2: every trusted link must point directly to an explicitly allowed domain.
// No Google News redirector and no arbitrary founder website in the trusted feed.
const SAFE_HOSTS = [
  "presse.bpifrance.fr",
  "bpifrance.fr",
  "maddyness.com",
  "frenchweb.fr",
  "sifted.eu",
  "eu-startups.com",
  "techcrunch.com",
  "producthunt.com",
  "news.ycombinator.com",
];
const BLOCKED_EXTENSIONS = [".exe", ".msi", ".dmg", ".pkg", ".apk", ".zip", ".rar", ".7z", ".iso"];

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

function hostnameAllowed(hostname) {
  const host = hostname.toLowerCase().replace(/\.$/, "");
  return SAFE_HOSTS.some(allowed => host === allowed || host.endsWith(`.${allowed}`));
}

function isSafeBrowserLink(rawUrl) {
  try {
    const url = new URL(rawUrl);
    if (url.protocol !== "https:" || url.username || url.password) return false;
    if (!url.hostname || url.hostname.includes("xn--") || !hostnameAllowed(url.hostname)) return false;
    return !BLOCKED_EXTENSIONS.some(ext => url.pathname.toLowerCase().endsWith(ext));
  } catch {
    return false;
  }
}

function savePersonalization() {
  localStorage.setItem("businessRadarFavoritesV22", JSON.stringify([...state.favorites]));
  localStorage.setItem("businessRadarPreferencesV22", JSON.stringify(state.preferences));
}

function personalizationTags(item) {
  return [...new Set([item.event, item.region, ...(item.sectors || [])].filter(Boolean))];
}

function personalBoost(item) {
  return personalizationTags(item).reduce((sum, tag) => sum + (state.preferences[tag] || 0) * 3, 0);
}

function updatePreference(item, delta) {
  personalizationTags(item).forEach(tag => {
    state.preferences[tag] = Math.max(-3, Math.min(3, (state.preferences[tag] || 0) + delta));
  });
  savePersonalization();
  render();
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

function isVerified(item) {
  return ["official", "editorial"].includes(item.trust);
}

function matchesView(item) {
  if (state.view === "Favoris") return state.favorites.has(item.id);
  if (state.view === "Pour toi") return isVerified(item);
  if (state.view === "France") return isVerified(item) && item.region === "France";
  if (state.view === "Europe") return isVerified(item) && ["Europe", "France"].includes(item.region);
  if (state.view === "Nouveaux business") return isVerified(item) && item.event === "Lancement";
  if (state.view === "Levées & M&A") return isVerified(item) && ["Levée", "Acquisition"].includes(item.event);
  if (state.view === "Découverte") return item.trust === "discovery";
  return isVerified(item);
}

function visibleItems() {
  const q = state.query.trim().toLowerCase();
  return state.items
    .filter(item => {
      const catOk = state.category === "Tout" || (item.categories || []).includes(state.category);
      const haystack = `${item.title} ${item.summary || ""} ${item.why || ""} ${(item.categories || []).join(" ")} ${item.source} ${item.region || ""}`.toLowerCase();
      return matchesView(item) && catOk && (!q || haystack.includes(q));
    })
    .sort((a, b) => ((b.score || 0) + personalBoost(b)) - ((a.score || 0) + personalBoost(a)));
}

function renderTabs() {
  [...tabs.querySelectorAll("button")].forEach(button => {
    button.classList.toggle("active", button.dataset.view === state.view);
  });
}

function renderStats() {
  const s = state.stats || {};
  const checked = Number(s.links_checked || 0);
  const blocked = Number(s.links_blocked || 0);
  stats.innerHTML = [
    s.sources ? `<span><strong>${s.sources}</strong> sources actives</span>` : "",
    s.confirmed ? `<span><strong>${s.confirmed}</strong> signaux multi-confirmés</span>` : "",
    s.official ? `<span><strong>${s.official}</strong> sources officielles</span>` : "",
    checked ? `<span><strong>${checked}</strong> liens contrôlés · <strong>${blocked}</strong> bloqué${blocked > 1 ? "s" : ""}</span>` : "",
  ].filter(Boolean).join("");
}

function confidenceClass(level) {
  return ["official", "confirmed", "selected", "discovery"].includes(level) ? level : "selected";
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

    const trust = node.querySelector(".trust");
    trust.textContent = item.trust_label || "Source filtrée";
    trust.classList.add(`trust-${item.trust || "editorial"}`);

    const confidence = node.querySelector(".confidence");
    confidence.textContent = item.confidence_label || "Source unique sélectionnée";
    confidence.classList.add(`confidence-${confidenceClass(item.confidence_level)}`);
    confidence.title = item.confidence_note || "";

    node.querySelector(".summary").textContent = item.summary || "Résumé indisponible.";
    node.querySelector(".why-text").textContent = item.why || "Signal business à surveiller.";

    const sourceNames = (item.confirmation_sources || []).filter(Boolean);
    const note = node.querySelector(".confidence-note");
    note.textContent = item.confirmation_count > 1
      ? `${item.confidence_note || "Signal confirmé."} Sources : ${sourceNames.join(" · ")}.`
      : (item.confidence_note || "");

    const primaryTags = [];
    if (item.event && item.event !== "Business") primaryTags.push(item.event);
    if (item.region && item.region !== "International") primaryTags.push(item.region);
    (item.sectors || []).forEach(tag => primaryTags.push(tag));
    node.querySelector(".tags").innerHTML = [...new Set(primaryTags)].slice(0, 5).map(c => `<span class="tag">${escapeHtml(c)}</span>`).join("");

    const reasons = node.querySelector(".score-reasons");
    reasons.innerHTML = (item.score_reasons || []).map(reason => `<span>${escapeHtml(reason)}</span>`).join("") || "<span>Score calculé selon la source, la fraîcheur et le signal business.</span>";

    const excerptWrap = node.querySelector(".source-excerpt-wrap");
    if (item.source_excerpt) {
      node.querySelector(".source-excerpt").textContent = item.source_excerpt;
    } else {
      excerptWrap.hidden = true;
    }

    const m = item.metrics || {};
    node.querySelector(".metrics").textContent = [
      m.points ? `${m.points} points` : "",
      m.comments ? `${m.comments} commentaires` : "",
      item.domain || "",
    ].filter(Boolean).join(" · ");

    const favorite = node.querySelector(".favorite");
    const refreshFavorite = () => {
      const active = state.favorites.has(item.id);
      favorite.textContent = active ? "★ Favori" : "☆ Favori";
      favorite.classList.toggle("active", active);
    };
    refreshFavorite();
    favorite.onclick = () => {
      if (state.favorites.has(item.id)) state.favorites.delete(item.id); else state.favorites.add(item.id);
      savePersonalization();
      if (state.view === "Favoris") render(); else refreshFavorite();
    };
    node.querySelector(".more").onclick = () => updatePreference(item, 1);
    node.querySelector(".less").onclick = () => updatePreference(item, -1);

    const link = node.querySelector(".read");
    const safe = item.safe_link === true && isSafeBrowserLink(item.url);
    if (safe) {
      link.href = item.url;
      link.querySelector(".read-label").textContent = item.link_label || `Ouvrir ${item.source}`;
      link.title = `Lien direct contrôlé : ${item.domain}`;
    } else {
      link.removeAttribute("href");
      link.classList.add("blocked");
      link.querySelector(".read-label").textContent = "Lien bloqué par sécurité";
      link.title = "Ce lien ne correspond pas à la liste blanche du Business Radar.";
    }
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
    updated.textContent = `Mis à jour ${timeAgo(data.generated_at)} · sources directes uniquement · automatique toutes les 6 h`;
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
