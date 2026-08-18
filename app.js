function readStorageJson(keys, fallback) {
  for (const key of keys) {
    try {
      const raw = localStorage.getItem(key);
      if (raw) return JSON.parse(raw);
    } catch (_) {}
  }
  return fallback;
}

const state = {
  items: [],
  view: "Pour toi",
  category: "Tout",
  confidence: "Fiables",
  query: "",
  stats: {},
  favorites: new Set(readStorageJson(["businessRadarFavoritesV28", "businessRadarFavoritesV27", "businessRadarFavoritesV26", "businessRadarFavoritesV25", "businessRadarFavoritesV24", "businessRadarFavoritesV23", "businessRadarFavoritesV22"], [])),
  preferences: readStorageJson(["businessRadarPreferencesV28", "businessRadarPreferencesV27", "businessRadarPreferencesV26", "businessRadarPreferencesV25", "businessRadarPreferencesV24", "businessRadarPreferencesV23", "businessRadarPreferencesV22"], {}),
  companyHistory: readStorageJson(["businessRadarCompanyHistoryV28", "businessRadarCompanyHistoryV27"], {}),
  historySeededAt: null,
};

const SAFE_HOSTS = [
  "presse.bpifrance.fr",
  "bpifrance.fr",
  "lafrenchtech.gouv.fr",
  "eic.ec.europa.eu",
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
const confidenceFilters = document.querySelector("#confidence-filters");
const tabs = document.querySelector("#tabs");
const search = document.querySelector("#search");
const template = document.querySelector("#card-template");
const stats = document.querySelector("#stats");
const briefText = document.querySelector("#brief-text");
const briefHighlights = document.querySelector("#brief-highlights");
const dailyTop = document.querySelector("#daily-top");
const sourceHealth = document.querySelector("#source-health");
const watchlist = document.querySelector("#watchlist");
const watchEmpty = document.querySelector("#watch-empty");
const watchSection = document.querySelector("#watch-section");
const themeButtons = [...document.querySelectorAll("[data-theme-choice]")];
const themeColor = document.querySelector('meta[name="theme-color"]');

function timeAgo(iso) {
  const seconds = Math.max(1, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "à l’instant";
  if (seconds < 3600) return `il y a ${Math.floor(seconds / 60)} min`;
  if (seconds < 86400) return `il y a ${Math.floor(seconds / 3600)} h`;
  return `il y a ${Math.floor(seconds / 86400)} j`;
}

const HISTORY_DAYS = 45;
const WATCH_DAYS = 30;
const INSTITUTION_KEYS = new Set([
  "bpifrance", "la french tech", "french tech", "european innovation council", "eic",
  "spotify", "apple", "google", "microsoft", "meta", "amazon", "netflix", "tiktok", "youtube", "snap", "snapchat"
]);

function normalizedCompanyKey(item) {
  const raw = String(item.company_key || item.company || "").trim().toLowerCase();
  return raw.replace(/[^a-zà-ÿ0-9+.-]+/g, " ").replace(/\s+/g, " ").trim();
}

function historySignalsFor(itemOrKey, days = WATCH_DAYS) {
  const key = typeof itemOrKey === "string" ? itemOrKey : normalizedCompanyKey(itemOrKey);
  const entry = state.companyHistory[key];
  if (!entry || !Array.isArray(entry.signals)) return [];
  const cutoff = Date.now() - days * 86400000;
  return entry.signals.filter(signal => new Date(signal.published_at || signal.seen_at || 0).getTime() >= cutoff);
}

function ingestCompanyHistory(items) {
  const cutoff = Date.now() - HISTORY_DAYS * 86400000;
  const next = {};

  // Keep only recent, previously recorded history.
  Object.entries(state.companyHistory || {}).forEach(([key, entry]) => {
    const signals = Array.isArray(entry?.signals) ? entry.signals.filter(signal => new Date(signal.published_at || signal.seen_at || 0).getTime() >= cutoff) : [];
    if (signals.length) next[key] = { name: entry.name || key, signals };
  });

  items.filter(isVerified).forEach(item => {
    const key = normalizedCompanyKey(item);
    if (!key || key.length < 2 || INSTITUTION_KEYS.has(key)) return;
    const published = new Date(item.published_at || 0).getTime();
    if (!Number.isFinite(published) || published < cutoff) return;
    const signalKey = item.signal_key || item.id;
    if (!signalKey) return;
    if (!next[key]) next[key] = { name: item.company || item.entity || key, signals: [] };
    const compact = {
      signal_key: signalKey,
      id: item.id,
      title: item.title,
      event: item.event || "Business",
      event_amount: item.event_amount || "",
      source: item.source,
      published_at: item.published_at,
      score: item.score || 0,
      confidence_level: item.confidence_level || "selected",
      region: item.region || "International",
    };
    const existingIndex = next[key].signals.findIndex(signal => signal.signal_key === signalKey);
    if (existingIndex >= 0) next[key].signals[existingIndex] = compact;
    else next[key].signals.push(compact);
    next[key].name = item.company || next[key].name || item.entity || key;
  });

  // Limit storage so the radar remains lightweight on mobile browsers.
  const compactEntries = Object.entries(next)
    .map(([key, entry]) => {
      entry.signals.sort((a, b) => new Date(b.published_at) - new Date(a.published_at));
      entry.signals = entry.signals.slice(0, 20);
      return [key, entry];
    })
    .sort((a, b) => new Date(b[1].signals[0]?.published_at || 0) - new Date(a[1].signals[0]?.published_at || 0))
    .slice(0, 80);
  state.companyHistory = Object.fromEntries(compactEntries);
  saveCompanyHistory();
}

function momentumScoreFor(entry) {
  const signals = entry.signals || [];
  if (!signals.length) return 0;
  const events = [...new Set(signals.map(s => s.event).filter(e => e && e !== "Business"))];
  const confirmed = signals.filter(s => ["confirmed", "official_confirmed"].includes(s.confidence_level)).length;
  const official = signals.some(s => ["official", "official_confirmed"].includes(s.confidence_level));
  const best = Math.max(0, ...signals.map(s => Number(s.score || 0)));
  const latestMs = Math.max(0, ...signals.map(s => new Date(s.published_at || s.seen_at || 0).getTime()));
  const ageHours = latestMs ? Math.max(0, (Date.now() - latestMs) / 3600000) : 9999;

  let value = Math.min(44, signals.length * 18);
  value += Math.min(15, events.length * 6);
  value += Math.min(14, confirmed * 8);
  if (official) value += 8;
  value += Math.min(18, best * 0.20);
  if (ageHours <= 24) value += 8;
  else if (ageHours <= 72) value += 6;
  else if (ageHours <= 168) value += 4;
  else if (ageHours <= 336) value += 2;

  const eventSet = new Set(events);
  if (eventSet.has("Acquisition")) value += 7;
  if (eventSet.has("Levée")) value += 6;
  if (eventSet.has("Expansion")) value += 5;
  if (eventSet.has("Croissance")) value += 5;
  if (eventSet.has("Partenariat")) value += 4;
  if (eventSet.has("Lancement")) value += 3;
  return Math.max(0, Math.min(100, Math.round(value)));
}

function momentumStatus(entry) {
  const count = entry.signals.length;
  const best = Math.max(0, ...entry.signals.map(s => Number(s.score || 0)));
  const level = entry.signals[0]?.confidence_level || "selected";
  const strongEvent = entry.events.some(e => ["Levée", "Acquisition", "Expansion", "Croissance", "Partenariat"].includes(e));
  if (count >= 3 || (count >= 2 && entry.momentum >= 75)) return "Accélère";
  if (count >= 2) return "À surveiller";
  if (count === 1 && entry.momentum >= 54 && (best >= 80 || strongEvent || ["confirmed", "official", "official_confirmed"].includes(level))) return "Émergent";
  return "";
}

function companyMomentumEntries() {
  return Object.entries(state.companyHistory || {}).map(([key, entry]) => {
    const signals = historySignalsFor(key, WATCH_DAYS);
    const events = [...new Set(signals.map(s => s.event).filter(e => e && e !== "Business"))];
    const confirmed = signals.filter(s => ["confirmed", "official_confirmed"].includes(s.confidence_level)).length;
    const official = signals.filter(s => ["official", "official_confirmed"].includes(s.confidence_level)).length;
    const current = state.items
      .filter(item => normalizedCompanyKey(item) === key)
      .sort((a, b) => new Date(b.published_at) - new Date(a.published_at))[0] || null;
    const base = { key, name: entry.name || key, signals, events, confirmed, official, current };
    base.momentum = momentumScoreFor(base);
    base.status = momentumStatus(base);
    return base;
  }).filter(entry => entry.status)
    .sort((a, b) => b.momentum - a.momentum || b.signals.length - a.signals.length || new Date(b.signals[0]?.published_at || 0) - new Date(a.signals[0]?.published_at || 0))
    .slice(0, 8);
}

function momentumWhy(entry) {
  const bits = [];
  if (entry.signals.length >= 2) bits.push(`${entry.signals.length} signaux distincts`);
  else if (entry.events[0]) bits.push(entry.signals[0]?.event_amount ? `${entry.events[0]} ${entry.signals[0].event_amount}` : entry.events[0]);
  if (entry.confirmed) bits.push(`${entry.confirmed} recoupé${entry.confirmed > 1 ? "s" : ""}`);
  if (entry.official) bits.push("source officielle");
  const best = Math.max(0, ...entry.signals.map(s => Number(s.score || 0)));
  if (best >= 85) bits.push("signal fort");
  return bits.slice(0, 3).join(" · ") || "activité business récente";
}

function showCompanySignals(companyName) {
  state.view = "Pour toi";
  state.category = "Tout";
  state.confidence = "Fiables";
  state.query = companyName;
  search.value = companyName;
  renderTabs(); renderFilters(); renderConfidenceFilters(); render();
  document.querySelector(".results-head")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderWatchlist() {
  if (!watchlist || !watchEmpty) return;
  const entries = companyMomentumEntries();
  watchEmpty.hidden = entries.length > 0;
  watchlist.innerHTML = entries.map(entry => {
    const latest = entry.signals[0];
    const count = entry.signals.length;
    const events = entry.events.slice(0, 4);
    const trend = entry.momentum >= 80 ? "↑ fort" : entry.momentum >= 65 ? "↗ actif" : "• émergent";
    return `
      <article class="watch-card watch-${entry.status === "Émergent" ? "emerging" : "active"}">
        <div class="watch-card-top">
          <div class="watch-title-wrap">
            <span class="watch-status">${escapeHtml(entry.status)}</span>
            <h3 class="watch-company">${escapeHtml(entry.name)}</h3>
          </div>
          <div class="momentum-score" title="Score entreprise sur 30 jours"><strong>${entry.momentum}</strong><span>/100</span></div>
        </div>
        <div class="momentum-bar" aria-hidden="true"><span style="width:${entry.momentum}%"></span></div>
        <p class="watch-meta">${escapeHtml(trend)} · dernière apparition ${escapeHtml(timeAgo(latest.published_at))} · ${escapeHtml(momentumWhy(entry))}</p>
        <div class="watch-events">${events.map(event => `<span class="watch-event">${escapeHtml(event)}</span>`).join("")}</div>
        <div class="watch-actions">
          <button type="button" class="watch-company-search" data-watch-company="${escapeAttr(entry.name)}">Voir les signaux</button>
          ${entry.current ? `<button type="button" class="watch-latest" data-watch-signal="${escapeAttr(entry.current.id)}">Dernier signal ↓</button>` : ""}
        </div>
      </article>`;
  }).join("");
  watchlist.querySelectorAll("[data-watch-signal]").forEach(button => button.addEventListener("click", () => jumpToSignal(button.dataset.watchSignal)));
  watchlist.querySelectorAll("[data-watch-company]").forEach(button => button.addEventListener("click", () => showCompanySignals(button.dataset.watchCompany)));
}

function momentumEntryForItem(item) {
  const key = normalizedCompanyKey(item);
  if (!key) return null;
  return companyMomentumEntries().find(entry => entry.key === key) || null;
}

function dailyReason(item) {
  const reasons = [];
  if (item.event && item.event !== "Business") reasons.push(item.event);
  if (["official_confirmed", "confirmed"].includes(item.confidence_level)) reasons.push(`${item.trusted_confirmation_count || item.confirmation_count || 2} sources convergentes`);
  else if (item.confidence_level === "official") reasons.push("source officielle");
  const momentumEntry = momentumEntryForItem(item);
  if (momentumEntry?.signals.length >= 2) reasons.push(`${momentumEntry.signals.length} apparitions en 30 j`);
  else if (momentumEntry?.status === "Émergent") reasons.push(`émergent · momentum ${momentumEntry.momentum}`);
  if (item.region === "France") reasons.push("France");
  else if (item.region === "Europe") reasons.push("Europe");
  return reasons.slice(0, 3).join(" · ") || "signal entrepreneurial prioritaire";
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
  localStorage.setItem("businessRadarFavoritesV28", JSON.stringify([...state.favorites]));
  localStorage.setItem("businessRadarPreferencesV28", JSON.stringify(state.preferences));
}

function saveCompanyHistory() {
  try { localStorage.setItem("businessRadarCompanyHistoryV28", JSON.stringify(state.companyHistory)); } catch (_) {}
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
    if (["Business", "France", "Europe", "Lancement", "Levée", "Acquisition", "Expansion", "Partenariat", "Croissance"].includes(c)) return;
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

function renderConfidenceFilters() {
  [...confidenceFilters.querySelectorAll("button")].forEach(button => {
    button.classList.toggle("active", button.dataset.confidence === state.confidence);
  });
}

function isVerified(item) {
  return ["official", "reference", "editorial"].includes(item.trust);
}

function matchesView(item) {
  if (state.view === "Favoris") return state.favorites.has(item.id);
  if (state.view === "Pour toi") return isVerified(item);
  if (state.view === "France") return isVerified(item) && item.region === "France";
  if (state.view === "Europe") return isVerified(item) && ["Europe", "France"].includes(item.region);
  if (state.view === "Nouveaux business") return isVerified(item) && ["Lancement", "Expansion", "Partenariat"].includes(item.event);
  if (state.view === "Levées & M&A") return isVerified(item) && ["Levée", "Acquisition"].includes(item.event);
  if (state.view === "Découverte") return item.trust === "discovery";
  return isVerified(item);
}

function matchesConfidence(item) {
  const level = item.confidence_level || "selected";
  if (state.confidence === "Fiables") return !["discovery", "conflict"].includes(level);
  if (state.confidence === "Confirmés") return ["confirmed", "official_confirmed"].includes(level);
  if (state.confidence === "Officiels") return ["official", "official_confirmed"].includes(level);
  if (state.confidence === "Source unique") return level === "selected";
  if (state.confidence === "À vérifier") return ["conflict", "discovery"].includes(level);
  return true;
}

function rankingScore(item) {
  return (item.entrepreneurship_priority ?? item.score ?? 0) + personalBoost(item);
}

function dailyPriority(item) {
  let value = rankingScore(item);
  const level = item.confidence_level || "selected";
  if (level === "official_confirmed") value += 18;
  else if (level === "confirmed") value += 13;
  else if (level === "official") value += 10;
  if (item.region === "France") value += 6;
  else if (item.region === "Europe") value += 3;
  if (["Levée", "Acquisition", "Expansion", "Croissance", "Partenariat"].includes(item.event)) value += 7;
  const momentumEntry = momentumEntryForItem(item);
  if (momentumEntry) value += Math.min(15, Math.round(momentumEntry.momentum / 7));
  return value;
}

function pickDailyTop(items, limit = 3) {
  const ordered = [...items]
    .filter(item => item.confidence_level !== "conflict")
    .sort((a, b) => dailyPriority(b) - dailyPriority(a));

  // First pass: no publisher can monopolise the brief.
  const chosen = [];
  const usedSources = new Set();
  for (const item of ordered) {
    if (usedSources.has(item.source)) continue;
    chosen.push(item);
    usedSources.add(item.source);
    if (chosen.length === limit) return chosen;
  }
  // Fallback only when there are too few distinct sources.
  for (const item of ordered) {
    if (chosen.some(x => x.id === item.id)) continue;
    chosen.push(item);
    if (chosen.length === limit) break;
  }
  return chosen;
}

function visibleItems() {
  const q = state.query.trim().toLowerCase();
  return state.items
    .filter(item => {
      const catOk = state.category === "Tout" || (item.categories || []).includes(state.category);
      const haystack = `${item.title} ${item.summary || ""} ${item.why || ""} ${(item.categories || []).join(" ")} ${item.source} ${item.region || ""} ${(item.confirmation_sources || []).join(" ")}`.toLowerCase();
      return matchesView(item) && matchesConfidence(item) && catOk && (!q || haystack.includes(q));
    })
    .sort((a, b) => rankingScore(b) - rankingScore(a));
}

function renderTabs() {
  [...tabs.querySelectorAll("button")].forEach(button => {
    button.classList.toggle("active", button.dataset.view === state.view);
  });
}

function statCard(value, label, tone = "", title = "") {
  return `<div class="stat-card ${tone}"${title ? ` title="${escapeAttr(title)}"` : ""}><strong>${value}</strong><span>${label}</span></div>`;
}

function itemIsFresh(item, hours = 24) {
  return (Date.now() - new Date(item.published_at).getTime()) <= hours * 3600 * 1000;
}

function topSector(items) {
  const counts = new Map();
  items.forEach(item => (item.sectors || []).forEach(sector => counts.set(sector, (counts.get(sector) || 0) + 1)));
  return [...counts.entries()].sort((a, b) => b[1] - a[1])[0] || null;
}

function renderDailyBrief() {
  const trusted = state.items.filter(isVerified);
  const fresh = trusted.filter(item => itemIsFresh(item, 24));
  const base = fresh.length ? fresh : trusted.slice(0, 30);
  const raises = base.filter(i => i.event === "Levée").length;
  const launches = base.filter(i => i.event === "Lancement").length;
  const acquisitions = base.filter(i => i.event === "Acquisition").length;
  const france = base.filter(i => i.region === "France").length;
  const confirmed = base.filter(i => ["confirmed", "official_confirmed"].includes(i.confidence_level)).length;
  const official = base.filter(i => ["official", "official_confirmed"].includes(i.confidence_level)).length;
  const sector = topSector(base);

  if (!base.length) {
    briefText.textContent = "Aucun signal fiable récent n’est disponible pour le moment.";
    briefHighlights.innerHTML = "";
    dailyTop.innerHTML = "";
    return;
  }

  const windowLabel = fresh.length ? "sur les dernières 24 h" : "parmi les signaux récents";
  briefText.textContent = `${base.length} signal${base.length > 1 ? "aux" : ""} fiable${base.length > 1 ? "s" : ""} ${windowLabel}` +
    (sector ? ` · ${sector[0]} est le secteur le plus présent.` : ".");

  // Top 3 V2.7: valeur entrepreneuriale + fiabilité + diversité + historique de l’entreprise.
  const top = pickDailyTop(base, 3);

  dailyTop.innerHTML = top.map((item, index) => `
    <button type="button" class="daily-top-item" data-jump-id="${escapeAttr(item.id)}" title="Voir ce signal dans le radar">
      <span class="daily-rank">${index + 1}</span>
      <div>
        <strong>${escapeHtml(item.title)}</strong>
        <small>${escapeHtml(item.source)} · ${escapeHtml(item.confidence_label || "Source sélectionnée")}</small>
        <span class="daily-reason">Pourquoi : ${escapeHtml(dailyReason(item))}</span>
      </div>
      <span class="daily-jump" aria-hidden="true">↓</span>
    </button>
  `).join("");

  dailyTop.querySelectorAll("[data-jump-id]").forEach(button => {
    button.addEventListener("click", () => jumpToSignal(button.dataset.jumpId));
  });

  const chips = [
    raises ? [raises, "levée" + (raises > 1 ? "s" : "")] : null,
    launches ? [launches, "lancement" + (launches > 1 ? "s" : "")] : null,
    acquisitions ? [acquisitions, "M&A"] : null,
    france ? [france, "France"] : null,
    confirmed ? [confirmed, "recoupé" + (confirmed > 1 ? "s" : "")] : null,
    official ? [official, "officiel" + (official > 1 ? "s" : "")] : null,
    sector ? [sector[1], sector[0]] : null,
  ].filter(Boolean).slice(0, 6);
  briefHighlights.innerHTML = chips.map(([value, label]) => `<span class="brief-chip"><strong>${value}</strong>${escapeHtml(label)}</span>`).join("");
}
function renderStats() {
  const s = state.stats || {};
  const active = Number(s.sources_active || s.sources || 0);
  const expected = Number(s.sources_expected || active);
  const confirmed = Number(s.confirmed || 0);
  const official = Number(s.official || 0);
  const blocked = Number(s.links_blocked || 0);
  const conflicts = Number(s.conflicts || 0);
  const failedNames = Array.isArray(s.source_failures) ? s.source_failures : [];
  const emptyNames = Array.isArray(s.source_empty) ? s.source_empty : [];

  stats.innerHTML = [
    statCard(`${active}/${expected}`, "sources actives", active === expected ? "good" : "warn", failedNames.length ? `Indisponible : ${failedNames.join(", ")}` : "Toutes les sources répondent"),
    statCard(confirmed, "multi-confirmés", confirmed ? "good" : "", confirmed ? "Signaux recoupés par plusieurs sources sélectionnées" : "Aucun signal multi-confirmé actuellement"),
    statCard(official, "signaux officiels", official ? "official" : "", "Signaux provenant directement d’une source officielle autorisée"),
    statCard(blocked, "liens bloqués", blocked ? "warn" : "good", "Liens rejetés par le filtre de sécurité"),
  ].join("");

  const checked = Number(s.links_checked || 0);
  const failed = failedNames.length || Number(s.sources_failed || 0);
  sourceHealth.innerHTML = failed
    ? failedNames.map(name => `<span class="health-chip warn">⚠ ${escapeHtml(name)} indisponible</span>`).join("") +
      (emptyNames.length ? emptyNames.map(name => `<span class="health-chip">○ ${escapeHtml(name)} sans signal récent</span>`).join("") : "")
    : `<span class="health-chip ok">✓ Toutes les sources répondent</span>${emptyNames.map(name => `<span class="health-chip">○ ${escapeHtml(name)} sans signal récent</span>`).join("")}`;

  if (conflicts) sourceHealth.innerHTML += `<span class="health-chip warn">⚠ ${conflicts} divergence${conflicts > 1 ? "s" : ""} détectée${conflicts > 1 ? "s" : ""}</span>`;
  sourceHealth.innerHTML += `<span class="health-chip">${checked} liens contrôlés</span>`;
  renderDailyBrief();
}

function confidenceClass(level) {
  return ["official", "official_confirmed", "confirmed", "selected", "discovery", "conflict"].includes(level) ? level : "selected";
}

function sourceInitial(source) {
  const words = String(source || "BR").replace(/[^A-Za-zÀ-ÿ0-9 ]/g, " ").trim().split(/\s+/).filter(Boolean);
  if (!words.length) return "BR";
  return (words.length === 1 ? words[0].slice(0, 2) : `${words[0][0]}${words[1][0]}`).toUpperCase();
}

function verificationTitle(item) {
  if (item.confidence_level === "conflict") return "Information à recouper";
  if (["official", "official_confirmed"].includes(item.confidence_level)) return "Provenance officielle";
  if (item.confidence_level === "confirmed") return "Information recoupée";
  if (item.confidence_level === "discovery") return "Signal de découverte";
  return "Source éditoriale sélectionnée";
}

function makeConfirmationLink(source) {
  const safe = source && source.url && isSafeBrowserLink(source.url);
  if (!safe) return "";
  return `<a href="${escapeAttr(source.url)}" target="_blank" rel="noopener noreferrer" title="${escapeAttr(source.domain || source.source || "Source")}">${escapeHtml(source.source || source.domain || "Source")} <span>↗</span></a>`;
}

function render() {
  feed.innerHTML = "";
  const items = visibleItems();
  counter.textContent = `${items.length} signal${items.length > 1 ? "s" : ""}`;
  empty.hidden = items.length > 0;

  items.forEach((item, index) => {
    const node = template.content.cloneNode(true);
    const article = node.querySelector(".card");
    article.dataset.itemId = item.id;
    if (index === 0) article.classList.add("featured");
    article.dataset.confidence = confidenceClass(item.confidence_level);
    article.classList.toggle("is-confirmed", ["confirmed", "official_confirmed"].includes(item.confidence_level));
    article.classList.toggle("is-official", ["official", "official_confirmed"].includes(item.confidence_level));

    const sourceMark = node.querySelector(".source-mark");
    sourceMark.textContent = sourceInitial(item.source);
    sourceMark.classList.toggle("official-mark", item.trust === "official");
    if (item.trust === "official") sourceMark.title = "Source officielle";
    node.querySelector(".source").textContent = item.source;
    node.querySelector(".age").textContent = timeAgo(item.published_at);
    node.querySelector(".score").textContent = `${item.score}/100`;
    node.querySelector(".interest").textContent = item.interest || "À surveiller";
    node.querySelector("h3").textContent = item.title;

    const trust = node.querySelector(".trust");
    trust.textContent = item.trust_label || "Source filtrée";
    trust.classList.add(`trust-${item.trust || "editorial"}`);

    const confidence = node.querySelector(".confidence");
    confidence.textContent = item.confidence_label || "Source unique sélectionnée";
    confidence.classList.add(`confidence-${confidenceClass(item.confidence_level)}`);
    confidence.title = item.confidence_note || "";

    node.querySelector(".summary").textContent = item.summary || "Résumé indisponible.";
    node.querySelector(".why-text").textContent = item.why || "Signal business à surveiller.";

    node.querySelector(".verification-title").textContent = verificationTitle(item);
    node.querySelector(".confidence-note").textContent = item.confidence_note || "";
    const sourceLinks = (item.confirmation_links || []).map(makeConfirmationLink).filter(Boolean);
    const linksWrap = node.querySelector(".confirmation-links");
    linksWrap.innerHTML = sourceLinks.join("");
    if (!sourceLinks.length) linksWrap.hidden = true;

    const primaryTags = [];
    if (item.event && item.event !== "Business") primaryTags.push(item.event);
    if (item.region && item.region !== "International") primaryTags.push(item.region);
    (item.sectors || []).forEach(tag => primaryTags.push(tag));
    node.querySelector(".tags").innerHTML = [...new Set(primaryTags)].slice(0, 5).map(c => `<span class="tag">${escapeHtml(c)}</span>`).join("");

    const historyNote = node.querySelector(".company-history-note");
    const momentumEntry = momentumEntryForItem(item);
    if (historyNote && momentumEntry) {
      historyNote.hidden = false;
      historyNote.textContent = momentumEntry.signals.length >= 2
        ? `↗ ${momentumEntry.signals.length} apparitions en 30 jours · Momentum ${momentumEntry.momentum}/100`
        : `↑ Émergent · Momentum ${momentumEntry.momentum}/100`;
    }

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

function escapeAttr(text) {
  return String(text || "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function setTheme(theme) {
  const allowed = ["blue", "green", "violet"];
  const next = allowed.includes(theme) ? theme : "blue";
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem("businessRadarTheme", next); } catch (_) {}
  themeButtons.forEach(button => button.classList.toggle("active", button.dataset.themeChoice === next));
  if (themeColor) {
    themeColor.setAttribute("content", next === "green" ? "#08090a" : next === "violet" ? "#0b0914" : "#07111d");
  }
}

themeButtons.forEach(button => button.addEventListener("click", () => setTheme(button.dataset.themeChoice)));
setTheme(document.documentElement.dataset.theme || "blue");

async function load() {
  try {
    const response = await fetch(`data/feed.json?v=${Date.now()}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.items = data.items || [];
    state.stats = data.stats || {};
    ingestCompanyHistory(state.items);
    try {
      if (!localStorage.getItem("businessRadarHistorySeedV28")) localStorage.setItem("businessRadarHistorySeedV28", new Date().toISOString());
      state.historySeededAt = localStorage.getItem("businessRadarHistorySeedV28");
    } catch (_) {}
    updated.textContent = `Mis à jour ${timeAgo(data.generated_at)} · sources directes uniquement · historique local 45 j · Momentum 30 j · automatique toutes les 6 h`;
    renderStats();
    renderFilters();
    renderConfidenceFilters();
    renderTabs();
    render();
    renderWatchlist();
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
  state.confidence = state.view === "Découverte" ? "À vérifier" : "Fiables";
  renderTabs();
  renderFilters();
  renderConfidenceFilters();
  render();
});

confidenceFilters.addEventListener("click", event => {
  const button = event.target.closest("button[data-confidence]");
  if (!button) return;
  state.confidence = button.dataset.confidence;
  renderConfidenceFilters();
  render();
});

search.addEventListener("input", e => {
  state.query = e.target.value;
  render();
});

document.querySelector("#refresh").addEventListener("click", load);
load();
