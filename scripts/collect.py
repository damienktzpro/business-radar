#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import ipaddress
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import quote_plus, urlparse

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "feed.json"
USER_AGENT = "BusinessRadar/2.1 (+personal entrepreneurship news reader; strict-link-mode)"
MAX_ITEMS = 120


def google_news_url(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=fr&gl=FR&ceid=FR:fr"


# V2.1 deliberately removes broad Google News searches. Every source is either
# first-party / editorially curated, or a discovery platform whose link stays on
# that platform. The collector rejects links outside the declared safe domains.
RSS_SOURCES = [
    {
        "name": "Product Hunt",
        "url": "https://www.producthunt.com/feed",
        "weight": 15,
        "region": "International",
        "default_event": "Lancement",
        "max": 25,
        "trust": "discovery",
        "trust_label": "Plateforme de découverte",
        "source_type": "launch_platform",
        "safe_domains": ["producthunt.com"],
        "display_domain": "producthunt.com",
    },
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "weight": 17,
        "region": "International",
        "max": 25,
        "trust": "editorial",
        "trust_label": "Média vérifié",
        "source_type": "media",
        "safe_domains": ["techcrunch.com"],
        "display_domain": "techcrunch.com",
    },
    {
        "name": "EU-Startups",
        "url": "https://www.eu-startups.com/feed/",
        "weight": 16,
        "region": "Europe",
        "max": 25,
        "trust": "editorial",
        "trust_label": "Média vérifié",
        "source_type": "media",
        "safe_domains": ["eu-startups.com"],
        "display_domain": "eu-startups.com",
    },
    {
        "name": "Maddyness",
        "url": google_news_url('site:maddyness.com (startup OR entrepreneur OR levée OR lance OR acquisition OR croissance)'),
        "weight": 18,
        "region": "France",
        "max": 25,
        "trust": "editorial",
        "trust_label": "Média vérifié",
        "source_type": "media",
        "safe_domains": ["news.google.com"],
        "display_domain": "maddyness.com",
        "publisher_patterns": [r"maddyness"],
    },
    {
        "name": "FrenchWeb",
        "url": google_news_url('site:frenchweb.fr (startup OR entrepreneur OR levée OR lance OR acquisition OR croissance)'),
        "weight": 17,
        "region": "France",
        "max": 25,
        "trust": "editorial",
        "trust_label": "Média vérifié",
        "source_type": "media",
        "safe_domains": ["news.google.com"],
        "display_domain": "frenchweb.fr",
        "publisher_patterns": [r"frenchweb"],
    },
    {
        "name": "Bpifrance",
        "url": google_news_url('site:bpifrance.fr OR site:presse.bpifrance.fr (startup OR innovation OR financement OR levée OR acquisition)'),
        "weight": 20,
        "region": "France",
        "max": 20,
        "trust": "official",
        "trust_label": "Source officielle",
        "source_type": "official",
        "safe_domains": ["news.google.com"],
        "display_domain": "bpifrance.fr",
        "publisher_patterns": [r"bpifrance"],
    },
    {
        "name": "La French Tech",
        "url": google_news_url('site:lafrenchtech.com (startup OR innovation OR lauréat OR programme OR financement)'),
        "weight": 20,
        "region": "France",
        "max": 18,
        "trust": "official",
        "trust_label": "Source officielle",
        "source_type": "official",
        "safe_domains": ["news.google.com"],
        "display_domain": "lafrenchtech.com",
        "publisher_patterns": [r"french tech"],
    },
    {
        "name": "Sifted",
        "url": google_news_url('site:sifted.eu (startup OR funding OR acquisition OR launch OR growth)'),
        "weight": 18,
        "region": "Europe",
        "max": 22,
        "trust": "editorial",
        "trust_label": "Média vérifié",
        "source_type": "media",
        "safe_domains": ["news.google.com"],
        "display_domain": "sifted.eu",
        "publisher_patterns": [r"sifted"],
    },
]

HN_ENDPOINTS = [
    {
        "name": "Show HN",
        "endpoint": "https://hacker-news.firebaseio.com/v0/showstories.json",
        "limit": 35,
        "weight": 12,
        "trust": "discovery",
        "trust_label": "Communauté · à vérifier",
        "source_type": "community",
        "safe_domains": ["news.ycombinator.com"],
        "display_domain": "news.ycombinator.com",
    }
]

TRUST_RANK = {"official": 3, "editorial": 2, "discovery": 1}

EVENT_PATTERNS = {
    "Levée": [
        r"\blev[ée]e de fonds\b", r"\btour de table\b", r"\bl[èe]ve\s+(?:plus de\s+)?(?:\d|\$|€)",
        r"\braises?\s+(?:\$|€|£|\d)", r"\braised\s+(?:\$|€|£|\d)", r"\bfunding round\b",
        r"\bseries\s+[a-e]\b", r"\bpre[- ]seed\b", r"\bseed round\b", r"\bventure round\b",
    ],
    "Acquisition": [
        r"\bacqui(?:res?|red|sition)\b", r"\bbuy(?:s|ing)?\b", r"\btakeover\b", r"\brachat\b",
        r"\brach[èe]te\b", r"\bacquisition\b", r"\bfusion\b", r"\bmerger\b",
    ],
    "Lancement": [
        r"\blaunch(?:es|ed|ing)?\b", r"\bunveil(?:s|ed)?\b", r"\bintroduc(?:es|ed|ing)\b",
        r"\blanc(?:e|ent|ement)\b", r"\bd[ée]voile\b", r"\bnouveau (?:produit|service|logiciel|saas|outil)\b",
        r"\bnouvelle (?:plateforme|application|offre|solution)\b", r"\bshow hn\b",
    ],
    "Croissance": [
        r"\bprofitable\b", r"\bprofitability\b", r"\bmrr\b", r"\barr\b", r"\brevenue\b",
        r"\bchiffre d['’]affaires\b", r"\bgrowth\b", r"\bcroissance\b", r"\bclients?\b",
    ],
}

SECTOR_PATTERNS = {
    "IA": [r"\bai\b", r"\bia\b", r"artificial intelligence", r"intelligence artificielle", r"\bllm\b", r"\bagentic\b", r"\bagents?\b", r"machine learning"],
    "SaaS": [r"\bsaas\b", r"software as a service", r"b2b software", r"logiciel b2b", r"subscription software"],
    "Fintech": [r"\bfintech\b", r"payments?", r"paiements?", r"banking", r"banque", r"insurtech"],
    "E-commerce": [r"e-?commerce", r"shopify", r"marketplace", r"retail", r"commerce en ligne"],
    "Deeptech": [r"deeptech", r"quantum", r"robotics?", r"robotique", r"semiconductor", r"chip", r"spacetech", r"space tech"],
    "Climate": [r"climat", r"climate", r"cleantech", r"green ?tech", r"carbon", r"d[ée]carbon"],
    "Healthtech": [r"healthtech", r"medtech", r"biotech", r"health care", r"healthcare", r"sant[ée]"],
    "Legaltech": [r"legaltech", r"legal tech", r"lawtech", r"juridique", r"legal software"],
    "Proptech": [r"proptech", r"real estate tech", r"immobilier"],
    "Cyber": [r"cyber", r"security", r"s[ée]curit[ée] informatique", r"infosec"],
    "Sales": [r"sales", r"prospection", r"crm", r"business development", r"lead generation"],
}

BUSINESS_TERMS = [
    "startup", "founder", "entrepreneur", "company", "business", "saas", "product", "launch", "customer",
    "revenue", "funding", "venture", "marketplace", "platform", "software", "commercial", "entreprise",
    "levée", "lance", "acquisition", "croissance", "chiffre d'affaires", "innovation", "scale-up", "scaleup",
]

EXCLUDE_PATTERNS = [
    r"\bjob(?:s)?\b", r"\bhiring\b", r"\bcareer(?:s)?\b", r"\brecrutement\b", r"\boffre d['’]emploi\b",
    r"\bpolitics?\b", r"\belection\b",
]

PERSONAL_BOOSTS = {
    "France": 8, "Lancement": 12, "Levée": 9, "Acquisition": 8, "SaaS": 8, "IA": 5,
    "Sales": 6, "Fintech": 4, "E-commerce": 4,
}

BLOCKED_DOWNLOAD_EXTENSIONS = (".exe", ".msi", ".dmg", ".pkg", ".apk", ".zip", ".rar", ".7z", ".iso")


def http_get(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, application/json, text/xml, */*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def http_json(url: str):
    return json.loads(http_get(url).decode("utf-8"))


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    value = html.unescape(re.sub(r"<[^>]+>", " ", value))
    return re.sub(r"\s+", " ", value).strip()


def short_text(value: str, max_chars: int = 300) -> str:
    value = clean_text(value)
    if len(value) <= max_chars:
        return value
    cut = value[: max_chars + 1]
    for sep in [". ", "! ", "? ", "; "]:
        pos = cut.rfind(sep)
        if pos > max_chars * 0.55:
            return cut[: pos + 1].strip()
    return cut[:max_chars].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def item_id(url: str, title: str) -> str:
    return hashlib.sha1(f"{url}|{title}".encode("utf-8")).hexdigest()[:14]


def parse_date(value: str | None) -> str:
    if not value:
        return datetime.now(timezone.utc).isoformat()
    value = value.strip()
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def age_hours(iso: str) -> float:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 3600)
    except Exception:
        return 999.0


def matches_any(patterns: list[str], text: str) -> bool:
    return any(re.search(pattern, text, flags=re.I) for pattern in patterns)


def host_matches(hostname: str, allowed: str) -> bool:
    hostname = hostname.lower().rstrip(".")
    allowed = allowed.lower().rstrip(".")
    return hostname == allowed or hostname.endswith("." + allowed)


def is_safe_url(url: str, safe_domains: list[str]) -> bool:
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme != "https" or not parsed.hostname:
            return False
        if parsed.username or parsed.password:
            return False
        host = parsed.hostname.lower().rstrip(".")
        if host.startswith("xn--") or ".xn--" in host:
            return False
        try:
            ipaddress.ip_address(host)
            return False
        except ValueError:
            pass
        if not any(host_matches(host, allowed) for allowed in safe_domains):
            return False
        path = parsed.path.lower()
        if any(path.endswith(ext) for ext in BLOCKED_DOWNLOAD_EXTENSIONS):
            return False
        return True
    except Exception:
        return False


def publisher_is_trusted(publisher: str, patterns: list[str] | None) -> bool:
    if not patterns:
        return True
    cleaned = clean_text(publisher).lower()
    return any(re.search(pattern, cleaned, flags=re.I) for pattern in patterns)


def detect_event(text: str, default_event: str | None = None) -> str:
    t = text.lower()
    for event in ["Levée", "Acquisition", "Lancement", "Croissance"]:
        if matches_any(EVENT_PATTERNS[event], t):
            return event
    return default_event or "Business"


def detect_sectors(text: str) -> list[str]:
    t = text.lower()
    sectors = []
    for label, patterns in SECTOR_PATTERNS.items():
        if matches_any(patterns, t):
            sectors.append(label)
    return sectors[:3]


def detect_region(text: str, default_region: str | None = None) -> str:
    t = text.lower()
    france_markers = ["france", "french", "français", "française", "paris", "station f", "lyon", "lille", "nantes", "bordeaux", "toulouse"]
    europe_markers = ["europe", "european", "eu startup", "berlin", "amsterdam", "madrid", "barcelona", "brussels", "lisbon"]
    if any(marker in t for marker in france_markers):
        return "France"
    if any(marker in t for marker in europe_markers):
        return "Europe"
    return default_region or "International"


def business_relevance(title: str, summary: str, source: str, event: str) -> int:
    t = f"{title} {summary} {source}".lower()
    score = sum(2 for term in BUSINESS_TERMS if term in t)
    if event != "Business":
        score += 5
    if source in {"Product Hunt", "Show HN", "EU-Startups", "Maddyness", "FrenchWeb", "Sifted"}:
        score += 4
    return score


def should_exclude(title: str, summary: str, source: str, event: str) -> bool:
    text = f"{title} {summary}".lower()
    if matches_any(EXCLUDE_PATTERNS, text):
        return True
    if source in {"Product Hunt", "Show HN"}:
        return False
    return business_relevance(title, summary, source, event) < 4


def why_interesting(event: str, sectors: list[str], region: str, source: str) -> str:
    sector = sectors[0] if sectors else "ce marché"
    if event == "Lancement":
        if source in {"Product Hunt", "Show HN"}:
            return f"Signal de lancement précoce : utile pour repérer un besoin, un positionnement ou un modèle économique émergent dans {sector}."
        return f"Nouveau produit ou service à surveiller : cela peut révéler une demande émergente ou une nouvelle façon d’adresser {sector}."
    if event == "Levée":
        return f"Une levée peut signaler de la traction et montre où les investisseurs concentrent du capital dans {sector}."
    if event == "Acquisition":
        return f"Cette opération peut signaler une consolidation du marché ou une valeur stratégique croissante attribuée à {sector}."
    if event == "Croissance":
        return "Signal de traction commerciale : croissance, revenus ou clients permettent d’identifier les modèles qui commencent à fonctionner."
    if region == "France":
        return "Signal entrepreneurial français à suivre pour repérer les entreprises, marchés et modèles qui gagnent en visibilité localement."
    return "Signal business à surveiller : il peut révéler une tendance, un nouvel acteur ou un changement de marché."


def score_item(title: str, summary: str, source_weight: int, trust: str, event: str, sectors: list[str], region: str,
               published_at: str, points: int = 0, comments: int = 0) -> int:
    score = 34 + source_weight + {"official": 8, "editorial": 5, "discovery": 0}.get(trust, 0)
    tags = [event, region, *sectors]
    score += sum(PERSONAL_BOOSTS.get(tag, 0) for tag in tags)
    hours = age_hours(published_at)
    if hours <= 6:
        score += 10
    elif hours <= 24:
        score += 7
    elif hours <= 72:
        score += 4
    elif hours > 24 * 14:
        score -= 8
    score += min(points // 20, 10)
    score += min(comments // 20, 6)
    text = f"{title} {summary}".lower()
    if any(k in text for k in ["mrr", "arr", "revenue", "chiffre d'affaires", "customers", "clients"]):
        score += 5
    return max(1, min(score, 99))


def interest_label(score: int) -> str:
    if score >= 86:
        return "À ne pas manquer"
    if score >= 74:
        return "Très intéressant"
    if score >= 62:
        return "À surveiller"
    return "Signal"


def first_text(node: ET.Element, names: list[str]) -> str:
    for name in names:
        found = node.find(name)
        if found is not None and found.text:
            return found.text.strip()
    return ""


def source_name_from_rss(entry: ET.Element, fallback: str) -> str:
    source_node = entry.find("source")
    if source_node is not None and source_node.text:
        return clean_text(source_node.text)
    return fallback


def fallback_summary(title: str, source: str, event: str) -> str:
    clean_title = re.sub(r"^Show HN:\s*", "", title, flags=re.I).strip()
    if source == "Show HN":
        return f"Projet présenté sur Show HN : {clean_title}. La fiche ouvre uniquement la discussion Hacker News, pas le site externe du projet."
    if source == "Product Hunt":
        return f"Produit repéré sur Product Hunt : {clean_title}."
    if event == "Levée":
        return f"Actualité de financement concernant : {clean_title}."
    if event == "Acquisition":
        return f"Actualité de rapprochement ou d’acquisition concernant : {clean_title}."
    return f"Actualité entrepreneuriale : {clean_title}."


def make_item(*, title: str, summary: str, url: str, source: str, published_at: str, source_weight: int,
              trust: str, trust_label: str, source_type: str, safe_domains: list[str], display_domain: str,
              default_region: str | None = None, default_event: str | None = None, points: int = 0,
              comments: int = 0) -> dict | None:
    title = clean_text(title)
    summary = short_text(summary, 340)
    if not title or not url or not is_safe_url(url, safe_domains):
        return None

    context = f"{title} {summary} {source}"
    event = detect_event(context, default_event)
    sectors = detect_sectors(context)
    region = detect_region(context, default_region)
    if should_exclude(title, summary, source, event):
        return None

    if not summary:
        summary = fallback_summary(title, source, event)

    score = score_item(title, summary, source_weight, trust, event, sectors, region, published_at, points, comments)
    categories = [event, *sectors]
    if region in {"France", "Europe"}:
        categories.append(region)
    categories = list(dict.fromkeys(categories))[:5]

    return {
        "id": item_id(url, title),
        "title": title,
        "summary": summary,
        "why": why_interesting(event, sectors, region, source),
        "url": url,
        "source": source,
        "published_at": published_at,
        "categories": categories,
        "event": event,
        "region": region,
        "sectors": sectors,
        "score": score,
        "interest": interest_label(score),
        "domain": display_domain,
        "metrics": {"points": points, "comments": comments} if points or comments else {},
        "trust": trust,
        "trust_rank": TRUST_RANK.get(trust, 0),
        "trust_label": trust_label,
        "source_type": source_type,
        "safe_link": True,
        "link_label": f"Ouvrir {source}",
    }


def fetch_rss(source: dict) -> list[dict]:
    root = ET.fromstring(http_get(source["url"]))
    entries = root.findall(".//item")
    is_atom = False
    if not entries:
        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        is_atom = True

    items = []
    for entry in entries[: source.get("max", 25)]:
        if is_atom:
            title = first_text(entry, ["{http://www.w3.org/2005/Atom}title"])
            summary = first_text(entry, ["{http://www.w3.org/2005/Atom}content", "{http://www.w3.org/2005/Atom}summary"])
            link_node = entry.find("{http://www.w3.org/2005/Atom}link[@rel='alternate']")
            if link_node is None:
                link_node = entry.find("{http://www.w3.org/2005/Atom}link")
            url = link_node.attrib.get("href", "") if link_node is not None else ""
            published_raw = first_text(entry, ["{http://www.w3.org/2005/Atom}published", "{http://www.w3.org/2005/Atom}updated"])
            publisher = source["name"]
        else:
            title = first_text(entry, ["title"])
            summary = first_text(entry, ["description", "{http://purl.org/rss/1.0/modules/content/}encoded"])
            url = first_text(entry, ["link"])
            published_raw = first_text(entry, ["pubDate", "{http://purl.org/dc/elements/1.1/}date"])
            publisher = source_name_from_rss(entry, source["name"])

        if not publisher_is_trusted(publisher, source.get("publisher_patterns")):
            continue

        item = make_item(
            title=title,
            summary=summary,
            url=url,
            source=source["name"],
            published_at=parse_date(published_raw),
            source_weight=source["weight"],
            trust=source["trust"],
            trust_label=source["trust_label"],
            source_type=source["source_type"],
            safe_domains=source["safe_domains"],
            display_domain=source["display_domain"],
            default_region=source.get("region"),
            default_event=source.get("default_event"),
        )
        if item:
            items.append(item)
    return items


def fetch_hn(spec: dict) -> list[dict]:
    ids = http_json(spec["endpoint"])[: spec["limit"]]
    items = []
    for story_id in ids:
        story = http_json(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json") or {}
        if story.get("type") != "story":
            continue
        title = clean_text(story.get("title"))
        # Strict mode: never link directly to the founder's arbitrary domain.
        # The card opens only the Hacker News discussion page.
        url = f"https://news.ycombinator.com/item?id={story_id}"
        summary = clean_text(story.get("text"))
        published = datetime.fromtimestamp(story.get("time", 0), tz=timezone.utc).isoformat()
        points = int(story.get("score", 0) or 0)
        comments = int(story.get("descendants", 0) or 0)
        item = make_item(
            title=title,
            summary=summary,
            url=url,
            source=spec["name"],
            published_at=published,
            source_weight=spec["weight"],
            trust=spec["trust"],
            trust_label=spec["trust_label"],
            source_type=spec["source_type"],
            safe_domains=spec["safe_domains"],
            display_domain=spec["display_domain"],
            default_event="Lancement",
            points=points,
            comments=comments,
        )
        if item:
            items.append(item)
    return items


def normalize_title(title: str) -> str:
    title = re.sub(r"\s+-\s+[^-]{2,45}$", "", title.strip())
    title = re.sub(r"\W+", "", title.lower())
    return title[:140]


def dedupe(items: Iterable[dict]) -> list[dict]:
    seen_titles = set()
    seen_urls = set()
    out = []
    for item in sorted(items, key=lambda x: (x.get("trust_rank", 0), x.get("score", 0), x.get("published_at", "")), reverse=True):
        title_key = normalize_title(item["title"])
        url_key = re.sub(r"[?#].*$", "", item["url"])
        if not title_key or title_key in seen_titles or url_key in seen_urls:
            continue
        seen_titles.add(title_key)
        seen_urls.add(url_key)
        out.append(item)
    return out[:MAX_ITEMS]


def build_demo() -> list[dict]:
    now = datetime.now(timezone.utc)
    demos = [
        {
            "title": "Une startup française lance un SaaS de prospection B2B assisté par IA",
            "summary": "Le produit automatise la qualification des prospects et la préparation des séquences commerciales pour les PME.",
            "url": "https://www.maddyness.com/article/demo",
            "source": "Maddyness",
            "published_at": now.isoformat(),
            "source_weight": 18,
            "trust": "editorial",
            "trust_label": "Média vérifié",
            "source_type": "media",
            "safe_domains": ["maddyness.com"],
            "display_domain": "maddyness.com",
            "default_region": "France",
            "default_event": "Lancement",
        },
        {
            "title": "Bpifrance annonce un nouveau programme d'accompagnement deeptech",
            "summary": "Le dispositif cible les jeunes entreprises innovantes et renforce l'accompagnement à l'industrialisation.",
            "url": "https://www.bpifrance.fr/demo",
            "source": "Bpifrance",
            "published_at": (now - timedelta(hours=2)).isoformat(),
            "source_weight": 20,
            "trust": "official",
            "trust_label": "Source officielle",
            "source_type": "official",
            "safe_domains": ["bpifrance.fr"],
            "display_domain": "bpifrance.fr",
            "default_region": "France",
        },
        {
            "title": "Show HN: an AI agent that turns customer calls into CRM actions",
            "summary": "",
            "url": "https://news.ycombinator.com/item?id=123456",
            "source": "Show HN",
            "published_at": (now - timedelta(hours=1)).isoformat(),
            "source_weight": 12,
            "trust": "discovery",
            "trust_label": "Communauté · à vérifier",
            "source_type": "community",
            "safe_domains": ["news.ycombinator.com"],
            "display_domain": "news.ycombinator.com",
            "default_event": "Lancement",
            "points": 98,
            "comments": 42,
        },
    ]
    items = []
    for demo in demos:
        item = make_item(**demo)
        if item:
            items.append(item)
    return items


def stats_for(items: list[dict]) -> dict:
    return {
        "sources": len({item.get("source") for item in items}),
        "france": sum(1 for item in items if item.get("region") == "France"),
        "launches": sum(1 for item in items if item.get("event") == "Lancement"),
        "funding_ma": sum(1 for item in items if item.get("event") in {"Levée", "Acquisition"}),
        "verified": sum(1 for item in items if item.get("trust") in {"official", "editorial"}),
        "safe_links": sum(1 for item in items if item.get("safe_link")),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Generate demo data without network access")
    args = parser.parse_args()

    items: list[dict] = []
    errors: list[str] = []

    if args.demo:
        items = build_demo()
    else:
        for source in RSS_SOURCES:
            try:
                items.extend(fetch_rss(source))
            except Exception as exc:
                errors.append(f"{source['name']}: {exc}")
        for spec in HN_ENDPOINTS:
            try:
                items.extend(fetch_hn(spec))
            except Exception as exc:
                errors.append(f"{spec['name']}: {exc}")
        items = dedupe(items)

    payload = {
        "version": "2.1",
        "strict_link_mode": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(items),
        "stats": stats_for(items),
        "errors": errors,
        "items": items,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(items)} items to {OUT}")
    if errors:
        print("Warnings:", *errors, sep="\n- ", file=sys.stderr)
    return 0 if items else 1


if __name__ == "__main__":
    raise SystemExit(main())
