#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
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
USER_AGENT = "BusinessRadar/2.0 (+personal entrepreneurship news reader)"
MAX_ITEMS = 150


def google_news_url(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=fr&gl=FR&ceid=FR:fr"


RSS_SOURCES = [
    {
        "name": "Product Hunt",
        "url": "https://www.producthunt.com/feed",
        "weight": 18,
        "region": "International",
        "default_event": "Lancement",
        "max": 30,
    },
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "weight": 10,
        "region": "International",
        "max": 25,
    },
    {
        "name": "EU-Startups",
        "url": "https://www.eu-startups.com/feed/",
        "weight": 13,
        "region": "Europe",
        "max": 25,
    },
    {
        "name": "France · Startups",
        "url": google_news_url('(startup OR "jeune pousse" OR scale-up OR scaleup) France -emploi -jobs'),
        "weight": 14,
        "region": "France",
        "max": 30,
    },
    {
        "name": "France · Levées",
        "url": google_news_url('(startup OR scale-up) ("levée de fonds" OR "lève" OR "tour de table" OR "série A" OR "série B" OR seed) France'),
        "weight": 18,
        "region": "France",
        "default_event": "Levée",
        "max": 25,
    },
    {
        "name": "France · Lancements",
        "url": google_news_url('(startup OR entrepreneur) (lance OR lancement OR dévoile OR "nouveau service" OR "nouvelle plateforme" OR "nouveau produit") France'),
        "weight": 17,
        "region": "France",
        "default_event": "Lancement",
        "max": 25,
    },
    {
        "name": "France · M&A",
        "url": google_news_url('(startup OR scale-up) (acquisition OR rachat OR rachète OR fusion OR cède) France'),
        "weight": 17,
        "region": "France",
        "default_event": "Acquisition",
        "max": 20,
    },
    {
        "name": "Maddyness",
        "url": google_news_url('site:maddyness.com (startup OR entrepreneur OR levée OR lance OR acquisition)'),
        "weight": 16,
        "region": "France",
        "max": 25,
    },
    {
        "name": "FrenchWeb",
        "url": google_news_url('site:frenchweb.fr (startup OR entrepreneur OR levée OR lance OR acquisition)'),
        "weight": 15,
        "region": "France",
        "max": 25,
    },
    {
        "name": "Bpifrance",
        "url": google_news_url('site:bpifrance.fr (startup OR entrepreneur OR innovation OR financement)'),
        "weight": 11,
        "region": "France",
        "max": 18,
    },
]

HN_ENDPOINTS = [
    ("Show HN", "https://hacker-news.firebaseio.com/v0/showstories.json", 40, 15),
]

# Strong event patterns: intentionally stricter than V1 to avoid tagging generic
# articles about public/research funding as startup fundraising.
EVENT_PATTERNS = {
    "Levée": [
        r"\blev[ée]e de fonds\b",
        r"\btour de table\b",
        r"\bl[èe]ve\s+(?:plus de\s+)?(?:\d|\$|€)",
        r"\braises?\s+(?:\$|€|£|\d)",
        r"\braised\s+(?:\$|€|£|\d)",
        r"\bfunding round\b",
        r"\bseries\s+[a-e]\b",
        r"\bpre[- ]seed\b",
        r"\bseed round\b",
        r"\bventure round\b",
    ],
    "Acquisition": [
        r"\bacqui(?:res?|red|sition)\b",
        r"\bbuy(?:s|ing)?\b",
        r"\btakeover\b",
        r"\brachat\b",
        r"\brach[èe]te\b",
        r"\bacquisition\b",
        r"\bfusion\b",
        r"\bmerger\b",
    ],
    "Lancement": [
        r"\blaunch(?:es|ed|ing)?\b",
        r"\bunveil(?:s|ed)?\b",
        r"\bintroduc(?:es|ed|ing)\b",
        r"\blanc(?:e|ent|ement)\b",
        r"\bd[ée]voile\b",
        r"\bnouveau (?:produit|service|logiciel|saas|outil)\b",
        r"\bnouvelle (?:plateforme|application|offre|solution)\b",
        r"\bshow hn\b",
    ],
    "Croissance": [
        r"\bprofitable\b",
        r"\bprofitability\b",
        r"\bmrr\b",
        r"\barr\b",
        r"\brevenue\b",
        r"\bchiffre d['’]affaires\b",
        r"\bgrowth\b",
        r"\bcroissance\b",
        r"\bclients?\b",
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
    "startup", "founder", "entrepreneur", "company", "business", "saas", "product",
    "launch", "customer", "revenue", "funding", "venture", "marketplace", "platform",
    "software", "commercial", "entreprise", "levée", "lance", "acquisition", "croissance",
    "chiffre d'affaires", "innovation", "scale-up", "scaleup",
]

EXCLUDE_PATTERNS = [
    r"\bjob(?:s)?\b",
    r"\bhiring\b",
    r"\bcareer(?:s)?\b",
    r"\brecrutement\b",
    r"\boffre d['’]emploi\b",
    r"\bpolitics?\b",
    r"\belection\b",
]

PERSONAL_BOOSTS = {
    "France": 8,
    "Lancement": 12,
    "Levée": 9,
    "Acquisition": 8,
    "SaaS": 8,
    "IA": 5,
    "Sales": 6,
    "Fintech": 4,
    "E-commerce": 4,
}


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
    value = re.sub(r"\s+", " ", value).strip()
    return value


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
    score = 0
    score += sum(2 for term in BUSINESS_TERMS if term in t)
    if event != "Business":
        score += 5
    if source in {"Product Hunt", "Show HN", "EU-Startups", "Maddyness", "FrenchWeb"}:
        score += 4
    return score


def should_exclude(title: str, summary: str, source: str, event: str) -> bool:
    text = f"{title} {summary}".lower()
    if matches_any(EXCLUDE_PATTERNS, text):
        return True
    # Product Hunt and Show HN are creation/lauch sources, so keep them even if
    # the title does not contain generic business words.
    if source in {"Product Hunt", "Show HN"}:
        return False
    return business_relevance(title, summary, source, event) < 4


def why_interesting(event: str, sectors: list[str], region: str, source: str) -> str:
    sector = sectors[0] if sectors else "ce marché"
    if event == "Lancement":
        if source in {"Product Hunt", "Show HN"}:
            return f"Un produit vient d’être mis sur le marché : utile pour repérer tôt un besoin, un positionnement ou un modèle économique dans {sector}."
        return f"Nouveau produit ou service à surveiller : cela peut révéler une demande émergente ou une nouvelle façon d’adresser {sector}."
    if event == "Levée":
        return f"Une levée est un signal de traction et de conviction des investisseurs ; elle indique aussi où le capital se dirige dans {sector}."
    if event == "Acquisition":
        return f"Cette opération montre un mouvement de consolidation ou une valeur stratégique attribuée à {sector}."
    if event == "Croissance":
        return "Signal de traction commerciale : les données de croissance, revenus ou clients permettent de voir quels modèles fonctionnent réellement."
    if region == "France":
        return "Signal entrepreneurial français à suivre pour repérer les entreprises, marchés et modèles qui gagnent en visibilité localement."
    return "Signal business à surveiller : il peut révéler une tendance, un nouvel acteur ou un changement de marché avant qu’il ne devienne évident."


def score_item(
    title: str,
    summary: str,
    source_weight: int,
    event: str,
    sectors: list[str],
    region: str,
    published_at: str,
    points: int = 0,
    comments: int = 0,
) -> int:
    score = 38 + source_weight
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


def make_item(
    *,
    title: str,
    summary: str,
    url: str,
    source: str,
    published_at: str,
    source_weight: int,
    default_region: str | None = None,
    default_event: str | None = None,
    points: int = 0,
    comments: int = 0,
) -> dict | None:
    title = clean_text(title)
    summary = short_text(summary, 320)
    if not title or not url:
        return None

    context = f"{title} {summary} {source}"
    event = detect_event(context, default_event)
    sectors = detect_sectors(context)
    region = detect_region(context, default_region)

    if should_exclude(title, summary, source, event):
        return None

    score = score_item(
        title,
        summary,
        source_weight,
        event,
        sectors,
        region,
        published_at,
        points,
        comments,
    )
    categories = [event, *sectors]
    if region in {"France", "Europe"}:
        categories.append(region)
    # Preserve order while removing duplicates.
    categories = list(dict.fromkeys(categories))[:5]

    return {
        "id": item_id(url, title),
        "title": title,
        "summary": summary or "Ouvrir la source pour découvrir le projet ou l’actualité.",
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
        "domain": urlparse(url).netloc.replace("www.", ""),
        "metrics": {"points": points, "comments": comments} if points or comments else {},
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
            actual_source = source["name"]
        else:
            title = first_text(entry, ["title"])
            summary = first_text(entry, ["description", "{http://purl.org/rss/1.0/modules/content/}encoded"])
            url = first_text(entry, ["link"])
            published_raw = first_text(entry, ["pubDate", "{http://purl.org/dc/elements/1.1/}date"])
            actual_source = source_name_from_rss(entry, source["name"])
            # For curated Google News queries, the actual publication name is
            # more useful than the query bucket in the card.
            if source["name"].startswith("France ·"):
                actual_source = actual_source or source["name"]

        item = make_item(
            title=title,
            summary=summary,
            url=url,
            source=actual_source,
            published_at=parse_date(published_raw),
            source_weight=source["weight"],
            default_region=source.get("region"),
            default_event=source.get("default_event"),
        )
        if item:
            items.append(item)
    return items


def fetch_hn(name: str, endpoint: str, limit: int, weight: int) -> list[dict]:
    ids = http_json(endpoint)[:limit]
    items = []
    for story_id in ids:
        story = http_json(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json") or {}
        if story.get("type") != "story":
            continue
        title = clean_text(story.get("title"))
        url = story.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
        summary = clean_text(story.get("text"))
        published = datetime.fromtimestamp(story.get("time", 0), tz=timezone.utc).isoformat()
        points = int(story.get("score", 0) or 0)
        comments = int(story.get("descendants", 0) or 0)
        item = make_item(
            title=title,
            summary=summary,
            url=url,
            source=name,
            published_at=published,
            source_weight=weight,
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
    for item in sorted(
        items,
        key=lambda x: (x.get("score", 0), x.get("published_at", "")),
        reverse=True,
    ):
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
            "url": "https://example.com/saas",
            "source": "Maddyness",
            "published_at": now.isoformat(),
            "source_weight": 16,
            "default_region": "France",
            "default_event": "Lancement",
        },
        {
            "title": "Fintech française : une jeune pousse lève 8 M€ pour accélérer en Europe",
            "summary": "Le financement doit permettre à l'entreprise de recruter et d'étendre son produit à plusieurs marchés européens.",
            "url": "https://example.com/funding",
            "source": "FrenchWeb",
            "published_at": (now - timedelta(hours=3)).isoformat(),
            "source_weight": 15,
            "default_region": "France",
            "default_event": "Levée",
        },
        {
            "title": "Show HN: an AI agent that turns customer calls into CRM actions",
            "summary": "A founder is launching a lightweight agent for sales teams and asking the Hacker News community for feedback.",
            "url": "https://example.com/showhn",
            "source": "Show HN",
            "published_at": (now - timedelta(hours=1)).isoformat(),
            "source_weight": 15,
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
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Generate demo data without network access")
    args = parser.parse_args()

    items: list[dict] = []
    errors: list[str] = []

    if args.demo:
        items = [x for x in build_demo() if x]
    else:
        for source in RSS_SOURCES:
            try:
                items.extend(fetch_rss(source))
            except Exception as exc:
                errors.append(f"{source['name']}: {exc}")
        for spec in HN_ENDPOINTS:
            try:
                items.extend(fetch_hn(*spec))
            except Exception as exc:
                errors.append(f"{spec[0]}: {exc}")
        items = dedupe(items)

    payload = {
        "version": 2,
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
