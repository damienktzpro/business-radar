(() => {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const clamp = (n, min = 0, max = 100) => Math.max(min, Math.min(max, n));
  const esc = (value) => {
    const div = document.createElement("div");
    div.textContent = String(value ?? "");
    return div.innerHTML;
  };
  const attr = (value) => String(value ?? "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  const CONFIDENCE_WEIGHT = {
    official_confirmed: 1.25,
    confirmed: 1.18,
    official: 1.12,
    selected: 1,
    discovery: 0.62,
    conflict: 0.35,
  };

  const SECTOR_LABELS = {
    IA: "Intelligence artificielle",
    SaaS: "Logiciels par abonnement",
    Fintech: "Technologies financières",
    "E-commerce": "Commerce en ligne",
    Deeptech: "Technologies de rupture",
    Climat: "Climat",
    Healthtech: "Santé numérique",
    Legaltech: "Technologies juridiques",
    Proptech: "Technologies immobilières",
    Cyber: "Cybersécurité",
    Sales: "Vente B2B",
  };

  function sectorLabel(sector) {
    return SECTOR_LABELS[sector] || sector || "Autre";
  }
  const EVENT_WEIGHT = {
    "Levée": 1.18,
    Acquisition: 1.14,
    Croissance: 1.12,
    Expansion: 1.10,
    Partenariat: 1.05,
    Lancement: 0.96,
    Business: 0.82,
  };

  const PLAYBOOKS = {
    IA: {
      title: "Automatiser un processus métier précis avec l’IA",
      problem: "De nombreuses PME veulent utiliser l’intelligence artificielle mais n’ont ni le temps ni les compétences pour transformer leurs tâches répétitives en automatisations réellement fiables.",
      opportunity: "Créer une solution verticale qui automatise un processus très précis pour un métier donné : traitement de documents, qualification, reporting, support ou préparation commerciale.",
      clients: ["PME", "équipes commerciales", "cabinets spécialisés", "professions de services"],
      model: "Abonnement logiciel + frais de mise en place",
      pricing: "49 à 499 € / mois selon le cas d’usage",
      minBudget: 1000, time: "partiel", skills: ["commerce", "tech", "marketing"], type: "saas", market: "entreprises", risk: "modere",
      feasibility: 78, scalability: 92, competition: 61, capital: 83, marketBase: 86,
      plan: ["Choisir un métier et un seul problème", "Interroger 10 à 15 professionnels", "Construire une démonstration manuelle ou semi-automatique", "Obtenir 2 premiers tests payants"],
    },
    SaaS: {
      title: "Créer un logiciel vertical pour une profession encore mal outillée",
      problem: "Beaucoup de petites professions travaillent encore avec des tableurs, des emails et plusieurs logiciels généralistes qui communiquent mal entre eux.",
      opportunity: "Construire un logiciel simple centré sur un flux de travail critique d’un métier précis, plutôt qu’un outil généraliste supplémentaire.",
      clients: ["TPE", "PME", "indépendants", "réseaux spécialisés"],
      model: "Abonnement mensuel par entreprise ou utilisateur",
      pricing: "29 à 199 € / mois",
      minBudget: 1000, time: "partiel", skills: ["commerce", "tech", "gestion"], type: "saas", market: "entreprises", risk: "modere",
      feasibility: 82, scalability: 90, competition: 67, capital: 86, marketBase: 82,
      plan: ["Identifier une profession mal servie", "Lister les trois tâches les plus pénibles", "Créer une maquette testable", "Vendre avant de développer toutes les fonctions"],
    },
    Fintech: {
      title: "Simplifier le pilotage financier des petites entreprises",
      problem: "Les dirigeants de petites structures manquent souvent d’une vision simple et immédiatement exploitable de leur trésorerie, de leurs échéances et de leurs décisions financières.",
      opportunity: "Créer une couche de pilotage, d’alerte ou d’analyse qui se connecte aux outils existants sans chercher à devenir une banque.",
      clients: ["TPE", "PME", "experts-comptables", "dirigeants"],
      model: "Abonnement B2B",
      pricing: "39 à 249 € / mois",
      minBudget: 3000, time: "partiel", skills: ["finance", "tech", "commerce"], type: "saas", market: "entreprises", risk: "eleve",
      feasibility: 67, scalability: 88, competition: 55, capital: 66, marketBase: 88,
      plan: ["Cibler un problème non bancaire", "Valider les contraintes réglementaires", "Tester avec des données fictives", "Signer un partenaire ou quelques PME pilotes"],
    },
    "E-commerce": {
      title: "Aider les e-commerçants à protéger leur marge et leurs stocks",
      problem: "L’acquisition coûte plus cher et beaucoup de marchands pilotent encore leurs marges, promotions et stocks avec des données éclatées.",
      opportunity: "Proposer un outil de recommandation simple pour prioriser les produits, promotions, réapprovisionnements et actions rentables.",
      clients: ["marques D2C", "petits e-commerçants", "agences e-commerce"],
      model: "Abonnement + éventuelle part variable",
      pricing: "49 à 299 € / mois",
      minBudget: 1500, time: "partiel", skills: ["commerce", "marketing", "tech"], type: "saas", market: "entreprises", risk: "modere",
      feasibility: 80, scalability: 87, competition: 60, capital: 80, marketBase: 80,
      plan: ["Choisir Shopify ou une seule plateforme", "Analyser 5 boutiques", "Construire un tableau de bord minimal", "Mesurer un gain concret sur marge ou stock"],
    },
    Deeptech: {
      title: "Mettre en relation innovations deeptech et besoins industriels",
      problem: "Les jeunes entreprises deeptech ont souvent une excellente technologie mais un accès commercial long et complexe aux industriels capables de l’adopter.",
      opportunity: "Créer un service ou une plateforme très spécialisée de qualification des besoins industriels et de mise en relation avec des solutions deeptech pertinentes.",
      clients: ["startups deeptech", "ETI industrielles", "directions innovation", "fonds spécialisés"],
      model: "Abonnement professionnel + mise en relation qualifiée",
      pricing: "500 à 3 000 € / mois selon le service",
      minBudget: 2000, time: "partiel", skills: ["commerce", "marketing", "gestion"], type: "service", market: "entreprises", risk: "modere",
      feasibility: 76, scalability: 76, competition: 72, capital: 82, marketBase: 78,
      plan: ["Choisir une verticale industrielle", "Cartographier 30 acteurs", "Qualifier 10 besoins acheteurs", "Tester une première mise en relation payante"],
    },
    Climat: {
      title: "Simplifier le suivi des obligations de décarbonation des PME",
      problem: "Les obligations et demandes de reporting environnemental se diffusent dans les chaînes de valeur, alors que les petites entreprises manquent de temps et d’expertise.",
      opportunity: "Créer un service logiciel léger qui centralise les données, échéances, preuves et actions nécessaires sans remplacer les cabinets experts.",
      clients: ["PME", "fournisseurs de grands groupes", "gestionnaires de bâtiments"],
      model: "Abonnement + accompagnement",
      pricing: "79 à 399 € / mois",
      minBudget: 2000, time: "partiel", skills: ["gestion", "commerce", "droit"], type: "saas", market: "entreprises", risk: "modere",
      feasibility: 74, scalability: 84, competition: 66, capital: 78, marketBase: 86,
      plan: ["Choisir une obligation ou un secteur", "Faire valider le besoin par 10 PME", "Créer un parcours de conformité simple", "Tester avec un expert partenaire"],
    },
    Healthtech: {
      title: "Réduire l’administratif des professionnels de santé",
      problem: "Les professionnels de santé perdent du temps sur des tâches administratives, documentaires et organisationnelles qui ne nécessitent pas toujours une expertise médicale.",
      opportunity: "Automatiser une tâche administrative non clinique et clairement délimitée, avec une attention forte à la confidentialité et aux règles du secteur.",
      clients: ["cabinets", "centres de santé", "professionnels libéraux"],
      model: "Abonnement professionnel",
      pricing: "39 à 249 € / mois",
      minBudget: 3000, time: "plein", skills: ["tech", "gestion", "commerce"], type: "saas", market: "entreprises", risk: "eleve",
      feasibility: 62, scalability: 84, competition: 64, capital: 61, marketBase: 90,
      plan: ["Éviter tout acte clinique dans la V1", "Valider sécurité et données", "Observer 5 professionnels", "Automatiser une seule tâche administrative"],
    },
    Legaltech: {
      title: "Créer un assistant de conformité pour TPE et PME",
      problem: "Les petites entreprises doivent suivre de nombreuses obligations mais n’ont pas toujours de juriste interne ni de système simple pour piloter les échéances et documents.",
      opportunity: "Créer un outil de suivi, collecte et préparation documentaire sur un domaine réglementaire très précis, avec validation humaine lorsque nécessaire.",
      clients: ["TPE", "PME", "cabinets de conseil", "directions administratives"],
      model: "Abonnement + services partenaires",
      pricing: "49 à 299 € / mois",
      minBudget: 1500, time: "partiel", skills: ["droit", "commerce", "tech"], type: "saas", market: "entreprises", risk: "modere",
      feasibility: 78, scalability: 85, competition: 68, capital: 84, marketBase: 82,
      plan: ["Choisir une obligation récurrente", "Cartographier le parcours actuel", "Créer un prototype de suivi", "Faire tester par des entreprises et un professionnel du droit"],
    },
    Proptech: {
      title: "Automatiser la conformité et les documents de gestion immobilière",
      problem: "Agences, petits gestionnaires et propriétaires doivent suivre de nombreux documents, échéances et obligations avec des outils souvent dispersés.",
      opportunity: "Créer un assistant de gestion documentaire et d’alertes qui centralise les obligations d’un portefeuille immobilier et prépare les actions à effectuer.",
      clients: ["agences immobilières", "administrateurs de biens", "syndics indépendants", "propriétaires professionnels"],
      model: "Abonnement par portefeuille ou agence",
      pricing: "49 à 249 € / mois",
      minBudget: 1500, time: "partiel", skills: ["immobilier", "commerce", "droit", "tech"], type: "saas", market: "entreprises", risk: "modere",
      feasibility: 82, scalability: 88, competition: 72, capital: 84, marketBase: 84,
      plan: ["Choisir un type de gestionnaire", "Lister les échéances réellement pénibles", "Construire un tableau de suivi", "Tester sur 2 à 3 portefeuilles"],
    },
    Cyber: {
      title: "Proposer une cybersécurité managée et lisible aux petites entreprises",
      problem: "Les PME sont exposées aux risques cyber mais disposent rarement d’une équipe dédiée et peinent à traduire des outils techniques en actions concrètes.",
      opportunity: "Créer une offre packagée de diagnostic, surveillance légère, priorisation et accompagnement avec un périmètre très clair.",
      clients: ["PME", "cabinets", "commerces multi-sites", "prestataires B2B"],
      model: "Abonnement de service",
      pricing: "199 à 1 500 € / mois",
      minBudget: 3000, time: "plein", skills: ["tech", "commerce", "gestion"], type: "service", market: "entreprises", risk: "eleve",
      feasibility: 65, scalability: 78, competition: 58, capital: 67, marketBase: 91,
      plan: ["Définir un périmètre de responsabilité strict", "Construire une offre standard", "S’appuyer sur des outils existants", "Signer 3 PME pilotes"],
    },
    Sales: {
      title: "Automatiser la préparation et le suivi de la prospection B2B",
      problem: "Les petites équipes commerciales passent encore beaucoup de temps à rechercher, qualifier, préparer et suivre leurs prospects plutôt qu’à vendre.",
      opportunity: "Créer un assistant centré sur une étape de prospection précise avec données propres, intégration CRM et validation humaine.",
      clients: ["PME B2B", "agences", "éditeurs de logiciels", "équipes commerciales"],
      model: "Abonnement par équipe ou utilisateur",
      pricing: "39 à 199 € / mois",
      minBudget: 1000, time: "partiel", skills: ["commerce", "marketing", "tech"], type: "saas", market: "entreprises", risk: "modere",
      feasibility: 86, scalability: 89, competition: 50, capital: 88, marketBase: 85,
      plan: ["Choisir une étape de prospection", "Tester le flux manuellement", "Mesurer le temps économisé", "Faire payer les premiers utilisateurs avant d’élargir"],
    },
  };

  const state = {
    items: [],
    trends: [],
    opportunities: [],
    view: "accueil",
    filter: "toutes",
    saved: new Set(readSaved()),
  };

  function readSaved() {
    try { return JSON.parse(localStorage.getItem("radarOpportunityFavoritesV30") || "[]"); }
    catch (_) { return []; }
  }
  function saveSaved() {
    try { localStorage.setItem("radarOpportunityFavoritesV30", JSON.stringify([...state.saved])); } catch (_) {}
  }

  function ageDays(item) {
    const ms = Date.now() - new Date(item.published_at || 0).getTime();
    return Number.isFinite(ms) ? Math.max(0, ms / 86400000) : 999;
  }
  function isTrusted(item) {
    return !["conflict"].includes(item.confidence_level) && item.safe_link === true;
  }
  function dominantRegion(items) {
    const counts = new Map();
    items.forEach(i => counts.set(i.region || "International", (counts.get(i.region || "International") || 0) + 1));
    return [...counts.entries()].sort((a,b) => b[1] - a[1])[0]?.[0] || "International";
  }

  function buildTrends(items) {
    const groups = new Map();
    items.filter(isTrusted).forEach(item => {
      (item.sectors || []).forEach(sector => {
        if (!groups.has(sector)) groups.set(sector, []);
        groups.get(sector).push(item);
      });
    });

    return [...groups.entries()].map(([sector, signals]) => {
      const uniqueSources = new Set(signals.map(s => s.source)).size;
      const uniqueCompanies = new Set(signals.map(s => s.company_key || s.company).filter(Boolean)).size;
      const events = new Set(signals.map(s => s.event).filter(Boolean));
      const qualityValues = signals.map(item => {
        const recency = clamp(1 - ageDays(item) / 45, .35, 1);
        return clamp(Number(item.score || 0) * (CONFIDENCE_WEIGHT[item.confidence_level] || .9) * (EVENT_WEIGHT[item.event] || .9) * recency, 0, 100);
      });
      const quality = qualityValues.reduce((a,b) => a+b, 0) / Math.max(1, qualityValues.length);
      const volume = clamp(signals.length * 14, 0, 100);
      const diversity = clamp(uniqueSources * 20, 0, 100);
      const eventDiversity = clamp(events.size * 18, 0, 100);
      const recency = signals.reduce((sum, item) => sum + clamp(100 - ageDays(item) * 5, 20, 100), 0) / Math.max(1, signals.length);
      const force = Math.round(clamp(quality * .38 + volume * .25 + diversity * .18 + recency * .12 + eventDiversity * .07));
      const ordered = [...signals].sort((a,b) => (Number(b.score)||0) - (Number(a.score)||0) || new Date(b.published_at)-new Date(a.published_at));
      return {
        sector, force, count: signals.length, uniqueSources, uniqueCompanies, events: [...events], region: dominantRegion(signals),
        signals: ordered,
        raises: signals.filter(i => i.event === "Levée").length,
        launches: signals.filter(i => i.event === "Lancement").length,
        growth: signals.filter(i => i.event === "Croissance").length,
        confirmed: signals.filter(i => ["confirmed", "official_confirmed"].includes(i.confidence_level)).length,
        fresh: signals.filter(i => ageDays(i) <= 7).length,
      };
    }).filter(t => t.count >= 1).sort((a,b) => b.force - a.force || b.count - a.count);
  }

  function opportunityFromTrend(trend) {
    const p = PLAYBOOKS[trend.sector];
    if (!p) return null;
    const signalsScore = trend.force;
    const freshRatio = trend.count ? trend.fresh / trend.count : 0;
    const moment = Math.round(clamp(55 + freshRatio * 25 + Math.min(12, trend.raises * 3 + trend.growth * 3 + trend.launches * 1.5), 45, 96));
    const market = Math.round(clamp(p.marketBase + Math.min(10, trend.count * 1.3), 50, 96));
    const feasibility = p.feasibility;
    const scalability = p.scalability;
    const competition = Math.round(clamp(p.competition - Math.max(0, trend.launches - 1) * 2 - Math.max(0, trend.raises - 1), 35, 92));
    const capital = p.capital;
    const score = Math.round(signalsScore * .25 + moment * .20 + market * .15 + feasibility * .15 + scalability * .10 + competition * .10 + capital * .05);
    const id = `opp-${trend.sector.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-")}`;
    const pieces = [`${trend.count} signal${trend.count > 1 ? "aux" : ""} détecté${trend.count > 1 ? "s" : ""}`];
    if (trend.fresh) pieces.push(`${trend.fresh} depuis moins de 7 jours`);
    if (trend.raises) pieces.push(`${trend.raises} levée${trend.raises > 1 ? "s" : ""}`);
    if (trend.launches) pieces.push(`${trend.launches} lancement${trend.launches > 1 ? "s" : ""}`);
    if (trend.growth) pieces.push(`${trend.growth} signal${trend.growth > 1 ? "aux" : ""} de croissance`);
    if (trend.confirmed) pieces.push(`${trend.confirmed} recoupé${trend.confirmed > 1 ? "s" : ""}`);
    const label = score >= 85 ? "Très prometteuse" : score >= 76 ? "Prometteuse" : score >= 66 ? "À étudier" : "Exploratoire";
    return {
      id, sector: trend.sector, region: trend.region, score, label,
      title: p.title, problem: p.problem, opportunity: p.opportunity, clients: p.clients, model: p.model, pricing: p.pricing,
      minBudget: p.minBudget, time: p.time, skills: p.skills, type: p.type, market: p.market, risk: p.risk, plan: p.plan,
      scores: { signaux: signalsScore, moment, marche: market, faisabilite: feasibility, developpement: scalability, concurrence: competition, capital },
      trend,
      whyNow: `Le radar observe ${pieces.join(" · ")} dans le secteur ${sectorLabel(trend.sector)}. Ces éléments ne prouvent pas qu’un marché est gagné d’avance, mais ils justifient une validation terrain rapide.`,
    };
  }

  function buildOpportunities(trends) {
    return trends.map(opportunityFromTrend).filter(Boolean).filter(o => o.score >= 58).sort((a,b) => b.score - a.score);
  }

  function switchView(view) {
    if (view === "favoris") {
      view = "radar";
      setTimeout(() => {
        const favoriteTab = $('#tabs button[data-view="Favoris"]');
        if (favoriteTab) favoriteTab.click();
      }, 30);
    }
    state.view = view;
    $$("[data-v3-panel]").forEach(panel => panel.classList.toggle("active", panel.dataset.v3Panel === view));
    $$("[data-v3-view]").forEach(btn => btn.classList.toggle("active", btn.dataset.v3View === view || (btn.dataset.v3View === "favoris" && view === "radar" && false)));
    if (view === "radar") $('[data-v3-view="radar"]')?.classList.add("active");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function scoreBadge(score) {
    return `<div class="v3-score"><strong>${score}</strong><span>/100</span></div>`;
  }
  function opportunityCard(o, match = null) {
    const saved = state.saved.has(o.id);
    return `<article class="v3-opportunity-card ${o.score >= 80 ? "is-strong" : ""}" data-opportunity-id="${attr(o.id)}">
      <div class="v3-card-top">
        <div class="v3-card-heading"><span class="v3-label">${esc(o.label)} · ${esc(sectorLabel(o.sector))}</span>${match !== null ? `<div class="v3-match"><span>Correspondance</span><strong>${match}/100</strong></div>` : ""}</div>
        ${scoreBadge(o.score)}
      </div>
      <h3>${esc(o.title)}</h3>
      <p class="v3-card-copy">${esc(cardInsight(o))}</p>
      <div class="v3-tags"><span>${esc(o.region)}</span><span>${esc(typeLabel(o.type))}</span><span>Budget dès ${formatEuro(o.minBudget)}</span></div>
      <div class="v3-card-actions">
        <button class="v3-open-btn" type="button" data-open-opportunity="${attr(o.id)}">Approfondir</button>
        <button class="v3-save-btn ${saved ? "active" : ""}" type="button" data-save-opportunity="${attr(o.id)}">${saved ? "★ Enregistrée" : "☆ Enregistrer"}</button>
      </div>
    </article>`;
  }

  function cardInsight(o) {
    const t = o.trend;
    const parts = [
      `${t.count} signal${t.count > 1 ? "aux" : ""}`,
      `${t.uniqueSources} source${t.uniqueSources > 1 ? "s" : ""}`,
    ];
    if (t.fresh) parts.push(`${t.fresh} récent${t.fresh > 1 ? "s" : ""}`);
    if (t.raises) parts.push(`${t.raises} levée${t.raises > 1 ? "s" : ""}`);
    if (t.launches) parts.push(`${t.launches} lancement${t.launches > 1 ? "s" : ""}`);
    return `${parts.join(" · ")}. ${o.score >= 80 ? "À valider rapidement sur le terrain." : "À surveiller et à tester avant d’investir."}`;
  }

  function typeLabel(type) {
    return ({ saas: "Logiciel par abonnement", service: "Service", marketplace: "Place de marché", commerce: "Commerce" })[type] || "Activité";
  }
  function riskLabel(risk) {
    return ({ faible: "Faible", modere: "Modéré", eleve: "Élevé" })[risk] || risk;
  }
  function timeLabel(time) {
    return ({ faible: "Quelques heures / semaine", partiel: "Temps partiel", plein: "Temps plein" })[time] || time;
  }
  function formatEuro(n) {
    return new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(n);
  }

  function renderOverview() {
    const trusted = state.items.filter(isTrusted).length;
    const strong = state.opportunities.filter(o => o.score >= 80).length;
    const topTrend = state.trends[0];
    $("#v3-overview-stats").innerHTML = [
      [trusted, trusted === 1 ? "signal exploitable" : "signaux exploitables"],
      [state.trends.length, state.trends.length === 1 ? "dynamique suivie" : "dynamiques suivies"],
      [strong, strong === 1 ? "opportunité ≥ 80" : "opportunités ≥ 80"],
      [topTrend ? `${topTrend.force}/100` : "—", topTrend ? `tendance principale · ${sectorLabel(topTrend.sector)}` : "tendance principale"],
    ].map(([v,l]) => `<div class="v3-overview-stat"><strong>${esc(v)}</strong><span>${esc(l)}</span></div>`).join("");

    $("#v3-home-opportunities").innerHTML = state.opportunities.slice(0,3).map(o => opportunityCard(o)).join("") || emptyBlock("Pas encore assez de signaux sectoriels pour calculer des opportunités.");
    $("#v3-home-trends").innerHTML = state.trends.slice(0,6).map(t => `<div class="v3-trend-row"><strong>${esc(sectorLabel(t.sector))}</strong><div class="v3-progress"><span style="width:${t.force}%"></span></div><span class="v3-trend-meta">${t.force}/100 · ${t.count} signal${t.count>1?"aux":""}</span></div>`).join("") || emptyBlock("Aucune tendance disponible.");
    const recent = [...state.items].filter(isTrusted).sort((a,b) => new Date(b.published_at)-new Date(a.published_at)).slice(0,6);
    $("#v3-home-signals").innerHTML = recent.map(i => `<article class="v3-signal-mini"><span>${esc(i.event || "Signal")} · ${esc(i.region || "International")}</span><strong>${esc(i.title)}</strong><small>${esc(i.source)} · ${Math.round(i.score || 0)}/100</small></article>`).join("");
  }

  function renderTrends() {
    $("#v3-trends").innerHTML = state.trends.map(t => `<article class="v3-trend-card">
      <div class="v3-trend-card-head"><div><span class="v3-label">${esc(t.region)} · ${t.events.length} type${t.events.length>1?"s":""} de signal</span><h3>${esc(sectorLabel(t.sector))}</h3></div><div class="v3-trend-score">${t.force}</div></div>
      <div class="v3-progress"><span style="width:${t.force}%"></span></div>
      <div class="v3-trend-details">
        <span><b>${t.count}</b>signaux</span><span><b>${t.uniqueSources}</b>sources</span><span><b>${t.uniqueCompanies}</b>entreprises</span><span><b>${t.fresh}</b>&lt; 7 jours</span>
      </div>
      <p class="v3-card-copy">${trendExplanation(t)}</p>
      <div class="v3-sources-preview">${t.signals.slice(0,3).map(i => `<div class="v3-source-mini"><b>${esc(i.source)}</b> · ${esc(i.title)}</div>`).join("")}</div>
    </article>`).join("") || emptyBlock("Aucune tendance calculable pour le moment.");
  }

  function trendExplanation(t) {
    const bits = [];
    if (t.raises) bits.push(`${t.raises} levée${t.raises>1?"s":""}`);
    if (t.launches) bits.push(`${t.launches} lancement${t.launches>1?"s":""}`);
    if (t.growth) bits.push(`${t.growth} croissance${t.growth>1?"s":""}`);
    if (t.confirmed) bits.push(`${t.confirmed} signal${t.confirmed>1?"aux":""} recoupé${t.confirmed>1?"s":""}`);
    return bits.length ? `La force de cette tendance repose notamment sur ${bits.join(", ")}, avec ${t.uniqueSources} source${t.uniqueSources>1?"s":""} distincte${t.uniqueSources>1?"s":""}.` : `Cette tendance repose principalement sur la répétition et la fraîcheur des signaux détectés par ${t.uniqueSources} source${t.uniqueSources>1?"s":""}.`;
  }

  function renderOpportunities() {
    $$("[data-opportunity-filter]").forEach(btn => btn.classList.toggle("active", btn.dataset.opportunityFilter === state.filter));
    let list = [...state.opportunities];
    if (state.filter === "fortes") list = list.filter(o => o.score >= 80);
    if (state.filter === "enregistrees") list = list.filter(o => state.saved.has(o.id));
    $("#v3-opportunities").innerHTML = list.map(o => opportunityCard(o)).join("") || emptyBlock(state.filter === "enregistrees" ? "Aucune opportunité enregistrée." : "Aucune opportunité ne correspond à ce filtre.");
  }

  function emptyBlock(text) {
    return `<div class="v3-opportunity-card"><p class="v3-card-copy">${esc(text)}</p></div>`;
  }

  function matchOpportunity(o, formData) {
    const budget = Number(formData.get("budget"));
    const time = formData.get("time");
    const skill = formData.get("skill");
    const type = formData.get("type");
    const zone = formData.get("zone");
    const risk = formData.get("risk");
    let score = 0;
    score += budget >= o.minBudget ? 25 : Math.max(0, 25 * (budget / o.minBudget));
    const timeRank = { faible: 1, partiel: 2, plein: 3 };
    score += timeRank[time] >= timeRank[o.time] ? 15 : 5;
    score += o.skills.includes(skill) ? 20 : 5;
    score += type === "tous" || type === o.type ? 15 : 4;
    if (zone === o.region) score += 15;
    else if (zone === "International") score += 12;
    else if (zone === "Europe" && o.region === "France") score += 11;
    else score += 5;
    const riskRank = { faible: 1, modere: 2, eleve: 3 };
    score += riskRank[risk] >= riskRank[o.risk] ? 10 : 2;
    return Math.round(clamp(score));
  }

  function runExplorer(form) {
    const fd = new FormData(form);
    const ranked = state.opportunities.map(o => ({ o, match: matchOpportunity(o, fd) })).sort((a,b) => b.match - a.match || b.o.score - a.o.score);
    $("#v3-explorer-results").innerHTML = ranked.slice(0,9).map(({o,match}) => opportunityCard(o, match)).join("") || emptyBlock("Aucune opportunité disponible pour le moment.");
  }

  function openOpportunity(id) {
    const o = state.opportunities.find(x => x.id === id);
    if (!o) return;
    const scoreRows = [
      ["Signaux", o.scores.signaux], ["Moment", o.scores.moment], ["Marché", o.scores.marche], ["Faisabilité", o.scores.faisabilite],
      ["Développement", o.scores.developpement], ["Concurrence", o.scores.concurrence], ["Capital", o.scores.capital], ["Indice final", o.score],
    ];
    const safeSignals = o.trend.signals.filter(i => i.safe_link === true).slice(0,6);
    $("#v3-dialog-content").innerHTML = `<div class="v3-dialog-body">
      <span class="v3-label">${esc(o.label)} · ${esc(sectorLabel(o.sector))} · ${esc(o.region)}</span>
      <h2>${esc(o.title)}</h2>
      <p class="v3-dialog-lead">${esc(o.whyNow)}</p>
      <div class="v3-score-grid">${scoreRows.map(([label,value]) => `<div class="v3-score-cell"><strong>${value}/100</strong><span>${esc(label)}</span></div>`).join("")}</div>
      <div class="v3-detail-grid">
        <div class="v3-detail-block"><h3>Le problème</h3><p>${esc(o.problem)}</p></div>
        <div class="v3-detail-block"><h3>L’opportunité</h3><p>${esc(o.opportunity)}</p></div>
        <div class="v3-detail-block"><h3>Clients potentiels</h3><ul>${o.clients.map(c=>`<li>${esc(c)}</li>`).join("")}</ul></div>
        <div class="v3-detail-block"><h3>Modèle économique</h3><p><b>${esc(o.model)}</b><br>${esc(o.pricing)}</p></div>
        <div class="v3-detail-block"><h3>Conditions de départ</h3><p>Budget indicatif dès <b>${formatEuro(o.minBudget)}</b><br>Temps : ${esc(timeLabel(o.time))}<br>Risque : ${esc(riskLabel(o.risk))}</p></div>
        <div class="v3-detail-block"><h3>Compétences utiles</h3><p>${o.skills.map(s => esc(skillLabel(s))).join(" · ")}</p></div>
        <div class="v3-detail-block" style="grid-column:1/-1"><h3>Plan de validation sur 30 jours</h3><ol>${o.plan.map(x=>`<li>${esc(x)}</li>`).join("")}</ol></div>
      </div>
      <div class="v3-dialog-signals"><p class="v3-kicker">SIGNAUX À L’ORIGINE DE L’ANALYSE</p>${safeSignals.map(i => `<a href="${attr(i.url)}" target="_blank" rel="noopener noreferrer"><b>${esc(i.source)}</b> · ${esc(i.title)} ↗</a>`).join("") || "<p>Aucun lien source disponible.</p>"}</div>
    </div>`;
    const dialog = $("#v3-opportunity-dialog");
    if (typeof dialog.showModal === "function") dialog.showModal(); else dialog.setAttribute("open", "");
  }

  function skillLabel(s) {
    return ({ commerce: "Commerce / vente", marketing: "Marketing", tech: "Technologie", finance: "Finance", immobilier: "Immobilier", droit: "Droit", gestion: "Gestion" })[s] || s;
  }

  function toggleSave(id) {
    if (state.saved.has(id)) state.saved.delete(id); else state.saved.add(id);
    saveSaved();
    renderOverview();
    renderOpportunities();
    const form = $("#v3-explorer-form");
    if (form) runExplorer(form);
  }

  function bindEvents() {
    $("#v3-nav")?.addEventListener("click", e => {
      const btn = e.target.closest("[data-v3-view]");
      if (!btn) return;
      if (btn.dataset.v3View === "favoris") {
        switchView("radar");
        setTimeout(() => $('#tabs button[data-view="Favoris"]')?.click(), 10);
        $$("[data-v3-view]").forEach(b => b.classList.toggle("active", b.dataset.v3View === "favoris"));
      } else switchView(btn.dataset.v3View);
    });
    document.addEventListener("click", e => {
      const openView = e.target.closest("[data-open-view]");
      if (openView) switchView(openView.dataset.openView);
      const open = e.target.closest("[data-open-opportunity]");
      if (open) openOpportunity(open.dataset.openOpportunity);
      const save = e.target.closest("[data-save-opportunity]");
      if (save) toggleSave(save.dataset.saveOpportunity);
      const filter = e.target.closest("[data-opportunity-filter]");
      if (filter) { state.filter = filter.dataset.opportunityFilter; renderOpportunities(); }
    });
    $("#v3-explorer-form")?.addEventListener("submit", e => { e.preventDefault(); runExplorer(e.currentTarget); });
    $("#v3-opportunity-dialog .v3-dialog-close")?.addEventListener("click", () => $("#v3-opportunity-dialog")?.close());
    $("#v3-opportunity-dialog")?.addEventListener("click", e => {
      if (e.target === e.currentTarget) e.currentTarget.close();
    });
  }

  function translateLegacyUi() {
    const selectors = ["#updated", "#sort-kicker", ".watch-meta", ".company-history-note", ".momentum-details summary", ".watch-note"];
    $$(selectors.join(",")).forEach(el => {
      if (!el || !el.textContent) return;
      const next = el.textContent
        .replace(/Momentum/g, "Dynamique")
        .replace(/momentum/g, "dynamique")
        .replace(/business récente/g, "entrepreneuriale récente")
        .replace(/signal business/g, "signal entrepreneurial");
      if (next !== el.textContent) el.textContent = next;
    });
  }

  async function loadV3() {
    try {
      const response = await fetch(`data/feed.json?v=${Date.now()}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      state.items = data.items || [];
      state.trends = buildTrends(state.items);
      state.opportunities = buildOpportunities(state.trends);
      renderOverview();
      renderTrends();
      renderOpportunities();
      runExplorer($("#v3-explorer-form"));
      translateLegacyUi();
      setTimeout(translateLegacyUi, 500);
    } catch (error) {
      const msg = `Impossible de calculer les tendances et opportunités : ${error.message}`;
      ["#v3-home-opportunities", "#v3-trends", "#v3-opportunities", "#v3-explorer-results"].forEach(sel => { if ($(sel)) $(sel).innerHTML = emptyBlock(msg); });
    }
  }

  bindEvents();
  switchView("accueil");
  const observer = new MutationObserver(() => translateLegacyUi());
  const watch = $("#watchlist");
  const feed = $("#feed");
  if (watch) observer.observe(watch, { childList: true, subtree: true });
  if (feed) observer.observe(feed, { childList: true, subtree: true });
  loadV3();
})();
