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
from difflib import SequenceMatcher
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse, urljoin

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "feed.json"
USER_AGENT = "BusinessRadar/2.9 (+personal entrepreneurship news reader; direct-source strict mode)"
MAX_ITEMS = 120

# V2.8: direct publisher feeds + official source pages only. No Google News redirector and no arbitrary
# founder website links in the trusted feed.
RSS_SOURCES = [
    {
        "name": "Bpifrance Presse",
        "url": "https://presse.bpifrance.fr/feed/",
        "weight": 22,
        "region": "France",
        "max": 24,
        "trust": "official",
        "trust_label": "Source officielle",
        "source_type": "official",
        "safe_domains": ["presse.bpifrance.fr", "bpifrance.fr"],
        "display_domain": "presse.bpifrance.fr",
        "max_age_days": 45,
        "fallback_listing_url": "https://presse.bpifrance.fr/?lang=fra",
        "fallback_link_pattern": r"^/",
        "fallback_max": 20,
    },
    {
        "name": "Maddyness",
        "url": "https://www.maddyness.com/feed/",
        "weight": 19,
        "region": "France",
        "max": 28,
        "trust": "editorial",
        "trust_label": "Média sélectionné",
        "source_type": "media",
        "safe_domains": ["maddyness.com"],
        "display_domain": "maddyness.com",
    },
    {
        "name": "FrenchWeb",
        "url": "https://www.frenchweb.fr/feed",
        "weight": 18,
        "region": "France",
        "max": 28,
        "trust": "editorial",
        "trust_label": "Média sélectionné",
        "source_type": "media",
        "safe_domains": ["frenchweb.fr"],
        "display_domain": "frenchweb.fr",
    },
    {
        "name": "Sifted",
        "url": "https://sifted.eu/feed",
        "weight": 21,
        "region": "Europe",
        "max": 28,
        "trust": "reference",
        "trust_label": "Média de référence",
        "source_type": "media",
        "safe_domains": ["sifted.eu"],
        "display_domain": "sifted.eu",
    },
    {
        "name": "EU-Startups",
        "url": "https://www.eu-startups.com/feed/",
        "weight": 18,
        "region": "Europe",
        "max": 28,
        "trust": "editorial",
        "trust_label": "Média sélectionné",
        "source_type": "media",
        "safe_domains": ["eu-startups.com"],
        "display_domain": "eu-startups.com",
    },
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "weight": 20,
        "region": "International",
        "max": 30,
        "trust": "reference",
        "trust_label": "Média de référence",
        "source_type": "media",
        "safe_domains": ["techcrunch.com"],
        "display_domain": "techcrunch.com",
    },
    {
        "name": "Product Hunt",
        "url": "https://www.producthunt.com/feed",
        "weight": 14,
        "region": "International",
        "default_event": "Lancement",
        "max": 25,
        "trust": "discovery",
        "trust_label": "Découverte · non confirmée",
        "source_type": "launch_platform",
        "safe_domains": ["producthunt.com"],
        "display_domain": "producthunt.com",
    },
]


HTML_SOURCES = [
    {
        "name": "La French Tech",
        "listing_url": "https://lafrenchtech.gouv.fr/fr/actualites/",
        "link_pattern": r"^/fr/actualites/(?!page/)[^?#]+/?$",
        "weight": 24,
        "region": "France",
        "max": 14,
        "max_age_days": 45,
        "trust": "official",
        "trust_label": "Source officielle",
        "source_type": "official",
        "safe_domains": ["lafrenchtech.gouv.fr"],
        "display_domain": "lafrenchtech.gouv.fr",
    },
    {
        "name": "European Innovation Council",
        "listing_url": "https://eic.ec.europa.eu/eic-funding-opportunities/eic-accelerator_en",
        "link_pattern": r"^/news/[^?#]+(?:_en)?$",
        "weight": 24,
        "region": "Europe",
        "max": 14,
        "max_age_days": 90,
        "trust": "official",
        "trust_label": "Source officielle UE",
        "source_type": "official",
        "safe_domains": ["eic.ec.europa.eu"],
        "display_domain": "eic.ec.europa.eu",
    },
]

HN_ENDPOINTS = [
    {
        "name": "Show HN",
        "endpoint": "https://hacker-news.firebaseio.com/v0/showstories.json",
        "limit": 30,
        "weight": 12,
        "trust": "discovery",
        "trust_label": "Découverte · non confirmée",
        "source_type": "community",
        "safe_domains": ["news.ycombinator.com"],
        "display_domain": "news.ycombinator.com",
    }
]

TRUST_RANK = {"official": 4, "reference": 3, "editorial": 2, "discovery": 1}

EVENT_PATTERNS = {
    "Levée": [
        r"\blev[ée]e de fonds\b", r"\btour de table\b", r"\bl[èe]ve\s+(?:plus de\s+)?(?:\d|\$|€|£)",
        r"\braises?\s+(?:\$|€|£|\d)", r"\braised\s+(?:\$|€|£|\d)", r"\bsecures?\s+(?:\$|€|£|\d)",
        r"\bfunding round\b", r"\bseries\s+[a-e]\b", r"\bpre[- ]seed\b", r"\bseed round\b",
        r"\binvestment from\b", r"\binvests?\s+(?:\$|€|£|\d)",
    ],
    "Acquisition": [
        r"\bacqui(?:res?|red|sition)\b", r"\btakeover\b", r"\brachat\b", r"\brach[èe]te\b",
        r"\bacquisition\b", r"\bfusion\b", r"\bmerger\b",
    ],
    "Expansion": [
        r"\bexpands? into\b", r"\binternational expansion\b", r"\benters? the .{0,35} market\b",
        r"\bopens? (?:a |its )?(?:new )?(?:office|hub|site|factory|plant)\b",
        r"\bs['’]implante\b", r"\bse d[ée]ploie\b", r"\bouvre (?:un|une) (?:bureau|site|usine)\b",
        r"\bnouveau march[ée]\b", r"\bnew market\b",
    ],
    "Partenariat": [
        r"\bstrategic partnership\b", r"\bpartners? with\b", r"\bpartnership with\b",
        r"\bpartenariat strat[ée]gique\b", r"\bs['’]associe avec\b", r"\bcollaboration with\b",
        r"\bsigns? (?:a )?(?:major |strategic )?(?:deal|agreement) with\b",
    ],
    "Lancement": [
        r"\blaunch(?:es|ed|ing)?\b", r"\bunveil(?:s|ed)?\b", r"\bintroduc(?:es|ed|ing)\b",
        r"\blanc(?:e|ent|ement)\b", r"\bd[ée]voile\b", r"\bnouveau (?:produit|service|logiciel|saas|outil)\b",
        r"\bnouvelle (?:plateforme|application|offre|solution)\b", r"\bshow hn\b",
    ],
    "Croissance": [
        r"\bprofitable\b", r"\bprofitability\b", r"\bmrr\b", r"\barr\b", r"\brevenue\b",
        r"\bchiffre d['’]affaires\b", r"\bgrowth\b", r"\bcroissance\b",
        r"\bvaluation\b", r"\bvalorisation\b", r"\bunicorn\b",
    ],
}

SECTOR_PATTERNS = {
    "IA": [r"\bai\b", r"\bia\b", r"artificial intelligence", r"intelligence artificielle", r"\bllm\b", r"agentic", r"machine learning"],
    "SaaS": [r"\bsaas\b", r"software as a service", r"b2b software", r"logiciel b2b"],
    "Fintech": [r"\bfintech\b", r"payments?", r"paiements?", r"banking", r"banque", r"insurtech"],
    "E-commerce": [r"e-?commerce", r"shopify", r"marketplace", r"retail", r"commerce en ligne"],
    "Deeptech": [r"deeptech", r"quantum", r"robotics?", r"robotique", r"semiconductor", r"chip", r"spacetech"],
    "Climat": [r"climat", r"climate", r"cleantech", r"green ?tech", r"carbon", r"d[ée]carbon"],
    "Healthtech": [r"healthtech", r"medtech", r"biotech", r"healthcare", r"sant[ée]"],
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
EXCLUDE_PATTERNS = [r"\bjob(?:s)?\b", r"\bhiring\b", r"\bcareer(?:s)?\b", r"\brecrutement\b", r"\boffre d['’]emploi\b"]
PERSONAL_BOOSTS = {
    "France": 9, "Europe": 4, "Lancement": 8, "Levée": 16, "Acquisition": 14, "Expansion": 12,
    "Partenariat": 10, "Croissance": 11, "SaaS": 5, "IA": 3, "Sales": 4, "Fintech": 4, "Deeptech": 4,
}

# V2.8: the score remains entrepreneurship-first. Product features from very large platforms
# remain visible, but they should not outrank fundraising, launches, expansion, M&A or hard traction signals.
LOW_VALUE_PATTERNS = [
    r"\bnew feature\b", r"\badds? (?:a |an )?(?:new )?feature\b", r"\bnow lets? users\b",
    r"\bplaylist\b", r"\bredesign\b", r"\binterface update\b", r"\bminor update\b",
    r"\bhow to\b", r"\bguide to\b", r"\btips? for\b", r"\breview\b", r"\bwhat is\b",
]
ESTABLISHED_PLATFORM_NAMES = {
    "spotify", "apple", "google", "microsoft", "meta", "amazon", "netflix", "tiktok", "youtube",
    "openai", "x", "twitter", "snap", "snapchat",
}
STARTUP_MARKERS = [
    r"\bstartup\b", r"\bstart-up\b", r"\bscale-?up\b", r"\bfounder\b", r"\bfounded\b",
    r"\bentrepreneur\b", r"\bjeune pousse\b", r"\bpme innovante\b",
]
HARD_BUSINESS_METRICS = {
    "Financement chiffré": [r"(?:raises?|raised|secures?|secured|investment|lev[ée]e|tour de table).{0,35}(?:[$€£]\s?\d|\d+(?:[.,]\d+)?\s?(?:million|milliard|billion|bn))"],
    "Valorisation": [r"\bvaluation\b", r"\bvalorisation\b", r"\bunicorn\b"],
    "Revenus": [r"\b(?:arr|mrr|revenue|revenues|chiffre d['’]affaires|sales)\b.{0,30}(?:[$€£]\s?\d|\d+(?:[.,]\d+)?\s?(?:million|milliard|billion|bn))"],
    "Traction clients": [r"\b\d+(?:[.,]\d+)?\s?(?:k|m|million|millions)?\s+(?:users?|customers?|clients?|subscribers?|abonn[ée]s)\b"],
    "Croissance chiffrée": [r"\b\d+(?:[.,]\d+)?%\s+(?:growth|croissance|increase|hausse)\b", r"\b(?:growth|croissance).{0,20}\d+(?:[.,]\d+)?%\b"],
}

BLOCKED_DOWNLOAD_EXTENSIONS = (".exe", ".msi", ".dmg", ".pkg", ".apk", ".zip", ".rar", ".7z", ".iso")
STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "into", "after", "before", "its", "their", "about",
    "une", "des", "dans", "pour", "avec", "sur", "les", "ses", "son", "aux", "plus", "par", "est", "qui",
    "startup", "startups", "company", "companies", "funding", "round", "raises", "raised", "raise", "launches", "launch",
    "announces", "annonce", "lance", "levee", "levée", "million", "millions", "billion", "series", "seed", "new", "nouveau",
}
METRICS = {"links_checked": 0, "links_blocked": 0}
SOURCE_HEALTH = {"expected": len(RSS_SOURCES) + len(HTML_SOURCES) + len(HN_ENDPOINTS), "success": 0, "failed": [], "empty": []}


def http_get(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/rss+xml, application/atom+xml, application/json, text/xml, */*",
    })
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def http_json(url: str):
    return json.loads(http_get(url).decode("utf-8"))


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    value = html.unescape(re.sub(r"<[^>]+>", " ", value))
    return re.sub(r"\s+", " ", value).strip()


def short_text(value: str, max_chars: int = 320) -> str:
    value = clean_text(value)
    if len(value) <= max_chars:
        return value
    cut = value[: max_chars + 1]
    pos = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
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
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
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
        if any(parsed.path.lower().endswith(ext) for ext in BLOCKED_DOWNLOAD_EXTENSIONS):
            return False
        return True
    except Exception:
        return False


def detect_event(text: str, default_event: str | None = None) -> str:
    t = text.lower()
    for event in ["Levée", "Acquisition", "Expansion", "Partenariat", "Lancement", "Croissance"]:
        if matches_any(EVENT_PATTERNS[event], t):
            return event
    return default_event or "Business"


def detect_sectors(text: str) -> list[str]:
    t = text.lower()
    sectors = [label for label, patterns in SECTOR_PATTERNS.items() if matches_any(patterns, t)]
    return sectors[:3]


def detect_region(text: str, default_region: str | None = None) -> str:
    t = text.lower()
    france_markers = ["france", "french", "français", "française", "paris", "station f", "lyon", "lille", "nantes", "bordeaux", "toulouse"]
    europe_markers = ["europe", "european", "berlin", "amsterdam", "madrid", "barcelona", "brussels", "lisbon", "london", "munich"]
    if any(marker in t for marker in france_markers):
        return "France"
    if any(marker in t for marker in europe_markers):
        return "Europe"
    return default_region or "International"


def business_relevance(title: str, summary: str, source: str, event: str) -> int:
    t = f"{title} {summary} {source}".lower()
    score = sum(2 for term in BUSINESS_TERMS if term in t)
    if event != "Business": score += 5
    if source in {"Product Hunt", "Show HN", "EU-Startups", "Maddyness", "FrenchWeb", "Sifted", "TechCrunch"}: score += 4
    return score


def should_exclude(title: str, summary: str, source: str, event: str) -> bool:
    text = f"{title} {summary}".lower()
    if matches_any(EXCLUDE_PATTERNS, text): return True
    if source in {"Product Hunt", "Show HN"}: return False
    return business_relevance(title, summary, source, event) < 4


def looks_french(text: str) -> bool:
    t = f" {clean_text(text).lower()} "
    markers = [" le ", " la ", " les ", " une ", " des ", " avec ", " dans ", " pour ", " startup française", " levée ", " entreprise "]
    return sum(marker in t for marker in markers) >= 2 or any(ch in t for ch in "éèêàùçôî")


def extract_subject(title: str) -> str:
    t = re.sub(r"^Show HN:\s*", "", clean_text(title), flags=re.I)
    separators = [
        r"\s+(?:raises?|raised|secures?|secured|closes?|closed|bags?|lands?)\s+",
        r"\s+(?:acquires?|acquired|buys?|bought)\s+",
        r"\s+(?:launches?|launched|unveils?|unveiled|introduces?)\s+",
        r"\s+(?:l[èe]ve|boucle|rach[èe]te|lance|d[ée]voile|annonce)\s+",
        r"\s+hits?\s+", r"\s+reaches?\s+", r"\s+valued at\s+",
    ]
    for sep in separators:
        parts = re.split(sep, t, maxsplit=1, flags=re.I)
        if len(parts) > 1 and 1 <= len(parts[0].split()) <= 10:
            return parts[0].strip(" :-–—")
    return " ".join(t.split()[:6]).strip(" :-–—")


COUNTRY_POSSESSIVES = {
    "france", "french", "germany", "german", "spain", "spanish", "italy", "italian",
    "norway", "norwegian", "sweden", "swedish", "finland", "finnish", "denmark", "danish",
    "uk", "britain", "british", "europe", "european", "belgium", "belgian", "netherlands", "dutch",
    "lithuania", "lithuanian", "estonia", "estonian", "latvia", "latvian", "poland", "polish",
    "switzerland", "swiss", "austria", "austrian", "portugal", "portuguese", "ireland", "irish",
    "czechia", "czech", "romania", "romanian", "bulgaria", "bulgarian", "croatia", "croatian",
}
GENERIC_ENTITY_PREFIXES = [
    r"^(?:french|german|spanish|italian|british|european|norwegian|swedish|finnish|danish|belgian|dutch|lithuanian|estonian|latvian|polish|swiss|austrian|portuguese|irish|czech|romanian|bulgarian|croatian)\s+",
    r"^(?:ai|ia|fintech|deeptech|healthtech|climate|cyber|saas|b2b)\s+",
    r"^(?:startup|start-up|scale-up|scaleup|company|entreprise|soci[ée]t[ée])\s+",
]
GENERIC_ENTITY_WORDS = {
    "the", "this", "new", "how", "why", "what", "sans", "avec", "pour", "from", "inside",
    "startup", "start-up", "company", "business", "french", "european", "europe", "france",
}


def company_identity(title: str) -> str:
    subject = clean_text(extract_subject(title)).strip(" :-–—")
    # Headlines such as “Norway’s Birdsview raises …” should track Birdsview, not the country label.
    m = re.match(r"^([A-Za-zÀ-ÿ0-9.+-]+)[’']s\s+(.+)$", subject)
    if m and m.group(1).lower() in COUNTRY_POSSESSIVES:
        subject = m.group(2).strip()
    elif m and re.match(r"^(?:new|latest|next|first)\b", m.group(2), flags=re.I):
        # “Spotify’s new feature …” still identifies Spotify as the company, even if the article is low priority.
        subject = m.group(1).strip()
    # “Vilnius-based LITILIT”, “Paris based Acme”, “AI-based Acme” -> keep only the company.
    subject = re.sub(r"^(?:[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9.'’ -]{0,36})[- ]based\s+", "", subject, count=1, flags=re.I).strip()
    # Remove common editorial descriptors while preserving the actual company name.
    changed = True
    while changed:
        changed = False
        for pattern in GENERIC_ENTITY_PREFIXES:
            cleaned = re.sub(pattern, "", subject, count=1, flags=re.I).strip()
            if cleaned != subject and cleaned:
                subject = cleaned
                changed = True
    words = subject.split()
    if not words or len(words) > 8:
        return ""
    if words[0].lower().strip(".,:;!?()[]{}") in GENERIC_ENTITY_WORDS:
        return ""
    # Do not turn a generic sentence fragment into a fake company history.
    if len(words) >= 5 and not any(ch.isupper() for ch in "".join(words[1:])):
        return ""
    return subject.strip(" :-–—")

def extract_amount(text: str) -> str | None:
    m = re.search(r"(?:[$€£]\s?\d+(?:[.,]\d+)?\s?(?:[kmb]|bn|million|billion)?|\d+(?:[.,]\d+)?\s?(?:million|millions|milliard|milliards)\s?(?:d['’]euros|euros|€|dollars?)?)", text, flags=re.I)
    return clean_text(m.group(0)) if m else None


def sector_phrase(sectors: list[str]) -> str | None:
    if not sectors:
        return None
    sector = sectors[0]
    articles = {"IA": "l’IA", "E-commerce": "l’e-commerce", "SaaS": "le SaaS", "Climat": "la climate tech"}
    return articles.get(sector, f"la {sector}" if sector in {"Fintech", "Deeptech", "Healthtech", "Legaltech", "Proptech"} else sector)


def french_digest(title: str, source_summary: str, event: str, source: str, sectors: list[str], region: str) -> str:
    source_summary = short_text(source_summary, 270)
    if source_summary and looks_french(source_summary):
        return source_summary

    subject = extract_subject(title) or "L’entreprise"
    amount = extract_amount(title)
    sector = sector_phrase(sectors)

    if event == "Levée":
        if amount:
            return f"{subject} annonce une levée de {amount}. Ce financement constitue un signal de traction à suivre" + (f" dans {sector}." if sector else ".")
        return f"{subject} annonce un nouveau financement. Le signal mérite d’être suivi pour mesurer sa traction et ses ambitions de croissance."
    if event == "Acquisition":
        return f"{subject} est au cœur d’une opération d’acquisition ou de rapprochement. Cela peut signaler une consolidation du marché" + (f" dans {sector}." if sector else ".")
    if event == "Expansion":
        return f"{subject} accélère son expansion ou son implantation sur un nouveau marché" + (f" dans {sector}." if sector else ".")
    if event == "Partenariat":
        return f"{subject} annonce un partenariat stratégique ou commercial" + (f" dans {sector}." if sector else ".")
    if event == "Lancement":
        if source == "Show HN":
            return f"Nouveau projet présenté sur Show HN : {subject}. Le lien du radar ouvre uniquement la discussion Hacker News, pas le site externe du créateur."
        if source == "Product Hunt":
            return f"Nouveau produit repéré sur Product Hunt : {subject}. Il est classé en découverte tant qu’une source éditoriale ou officielle ne le confirme pas."
        return f"{subject} lance ou dévoile une nouvelle offre" + (f" dans {sector}." if sector else ".") + " Le radar conserve le lien direct vers l’éditeur sélectionné."
    if event == "Croissance":
        return f"{subject} publie un signal de croissance, de revenus ou de traction commerciale" + (f" dans {sector}." if sector else ".")
    if region == "France":
        return f"Actualité entrepreneuriale française concernant {subject}. Le lien renvoie directement vers {source}, sans intermédiaire."
    return f"Actualité entrepreneuriale concernant {subject}. Le lien renvoie directement vers {source}, une source autorisée par le radar."


def hard_business_metric_bonus(text: str) -> tuple[int, list[str]]:
    bonus = 0
    reasons: list[str] = []
    for label, patterns in HARD_BUSINESS_METRICS.items():
        if matches_any(patterns, text.lower()):
            add = {"Financement chiffré": 8, "Valorisation": 7, "Revenus": 7, "Traction clients": 5, "Croissance chiffrée": 5}.get(label, 4)
            bonus += add
            reasons.append(f"{label} +{add}")
    return min(bonus, 14), reasons[:2]


def established_platform_subject(title: str) -> bool:
    subject = normalize_entity(extract_subject(title))
    tokens = set(subject.split())
    return bool(tokens & ESTABLISHED_PLATFORM_NAMES)


def entrepreneurship_adjustment(title: str, summary: str, event: str) -> tuple[int, list[str]]:
    text = f"{title} {summary}".lower()
    reasons: list[str] = []
    delta = 0
    metric_bonus, metric_reasons = hard_business_metric_bonus(text)
    if metric_bonus:
        delta += metric_bonus
        reasons.extend(metric_reasons)
    if matches_any(STARTUP_MARKERS, text):
        delta += 4
        reasons.append("Startup / scale-up +4")
    if event in {"Levée", "Acquisition", "Expansion", "Partenariat", "Croissance"}:
        # These events are structurally closer to the user's business-monitoring goal than a generic feature release.
        delta += 3
        reasons.append("Signal business structurant +3")
    weak_update = matches_any(LOW_VALUE_PATTERNS, text)
    hard_signal = bool(metric_bonus) or event in {"Levée", "Acquisition", "Expansion", "Partenariat", "Croissance"}
    if weak_update and not hard_signal:
        delta -= 15
        reasons.append("Simple actualité produit −15")
    if established_platform_subject(title) and event in {"Lancement", "Business"} and not hard_signal:
        delta -= 12
        reasons.append("Grande plateforme, enjeu entrepreneurial faible −12")
    return delta, reasons[:4]


def why_interesting(event: str, sectors: list[str], region: str) -> str:
    sector = sector_phrase(sectors) or "ce marché"
    if event == "Lancement": return f"Permet de repérer tôt un nouveau besoin, un positionnement ou un modèle économique dans {sector}."
    if event == "Levée": return f"Une levée peut signaler de la traction et montre où les investisseurs concentrent du capital dans {sector}."
    if event == "Acquisition": return f"Peut signaler une consolidation du marché ou une valeur stratégique croissante dans {sector}."
    if event == "Expansion": return f"Une expansion géographique ou industrielle aide à repérer les entreprises qui passent à l'échelle dans {sector}."
    if event == "Partenariat": return f"Un partenariat stratégique peut accélérer la distribution, l'accès au marché ou la crédibilité commerciale dans {sector}."
    if event == "Croissance": return "Les revenus, clients ou indicateurs de croissance aident à identifier les modèles qui commencent à fonctionner."
    if region == "France": return "Signal français utile pour suivre les entreprises et marchés qui gagnent en visibilité localement."
    return "Signal business utile pour repérer une tendance, un nouvel acteur ou un changement de marché."


def score_item(source_weight: int, trust: str, event: str, sectors: list[str], region: str, published_at: str,
               points: int = 0, comments: int = 0, title: str = "", summary: str = "") -> tuple[int, list[str]]:
    # Lower fixed base than V2.5: the score now has room to reward concrete entrepreneurial value.
    score = 20 + source_weight
    reasons = [f"Source pondérée +{source_weight}"]

    trust_bonus = {"official": 11, "reference": 7, "editorial": 4, "discovery": -2}.get(trust, 0)
    score += trust_bonus
    if trust_bonus > 0:
        trust_name = {"official": "Source officielle", "reference": "Média de référence", "editorial": "Média spécialisé"}.get(trust, "Source")
        reasons.append(trust_name + f" +{trust_bonus}")
    elif trust_bonus < 0:
        reasons.append(f"Découverte {trust_bonus}")

    event_bonus = {"Levée": 17, "Acquisition": 15, "Expansion": 12, "Partenariat": 10, "Croissance": 11, "Lancement": 8, "Business": 0}.get(event, 0)
    if event_bonus:
        score += event_bonus
        reasons.append(f"{event} +{event_bonus}")

    region_bonus = {"France": 8, "Europe": 4}.get(region, 0)
    if region_bonus:
        score += region_bonus
        reasons.append(f"{region} +{region_bonus}")

    sector_bonus_map = {"SaaS": 4, "IA": 2, "Sales": 3, "Fintech": 3, "Deeptech": 4, "Cyber": 3, "Climat": 3, "Healthtech": 3}
    sector_bonus = sum(sector_bonus_map.get(s, 0) for s in sectors[:2])
    if sector_bonus:
        score += sector_bonus
        reasons.append(f"Secteur pertinent +{sector_bonus}")

    entrepreneurship_delta, entrepreneurship_reasons = entrepreneurship_adjustment(title, summary, event)
    score += entrepreneurship_delta
    reasons.extend(entrepreneurship_reasons)

    hours = age_hours(published_at)
    if hours <= 6:
        score += 8; reasons.append("Très récent +8")
    elif hours <= 24:
        score += 5; reasons.append("Récent +5")
    elif hours <= 72:
        score += 3; reasons.append("Moins de 3 jours +3")
    elif hours > 24 * 14:
        score -= 7; reasons.append("Ancien −7")

    # Community popularity can help surface a discovery, but no longer overwhelms business value.
    if points:
        bonus = min(points // 35, 5); score += bonus
        if bonus: reasons.append(f"Traction communauté +{bonus}")
    if comments:
        bonus = min(comments // 40, 3); score += bonus
        if bonus: reasons.append(f"Discussion active +{bonus}")

    return max(1, min(score, 99)), reasons[:9]


def interest_label(score: int) -> str:
    if score >= 86: return "À ne pas manquer"
    if score >= 74: return "Très intéressant"
    if score >= 62: return "À surveiller"
    return "Signal"


def first_text(node: ET.Element, names: list[str]) -> str:
    for name in names:
        found = node.find(name)
        if found is not None and found.text:
            return found.text.strip()
    return ""


def make_item(*, title: str, summary: str, url: str, source: str, published_at: str, source_weight: int,
              trust: str, trust_label: str, source_type: str, safe_domains: list[str], display_domain: str,
              default_region: str | None = None, default_event: str | None = None, points: int = 0,
              comments: int = 0, max_age_days: int = 21) -> dict | None:
    title = clean_text(title)
    source_summary = short_text(summary, 320)
    if not title or not url:
        return None
    # Business Radar is a current-awareness tool: ignore stale feed entries.
    if age_hours(published_at) > 24 * max_age_days:
        return None
    METRICS["links_checked"] += 1
    if not is_safe_url(url, safe_domains):
        METRICS["links_blocked"] += 1
        return None

    context = f"{title} {source_summary} {source}"
    event = detect_event(context, default_event)
    sectors = detect_sectors(context)
    region = detect_region(context, default_region)
    if should_exclude(title, source_summary, source, event):
        return None

    score, score_reasons = score_item(source_weight, trust, event, sectors, region, published_at, points, comments, title, source_summary)
    categories = list(dict.fromkeys([event, *sectors, *([region] if region in {"France", "Europe"} else [])]))[:5]
    company = company_identity(title)

    return {
        "id": item_id(url, title),
        "title": title,
        "entity": extract_subject(title),
        "company": company,
        "company_key": normalize_entity(company) if company else "",
        "signal_key": signal_identity(normalize_entity(company) if company else "", event, title, source_summary, published_at),
        "summary": french_digest(title, source_summary, event, source, sectors, region),
        "source_excerpt": source_summary if source_summary and source_summary != french_digest(title, source_summary, event, source, sectors, region) else "",
        "why": why_interesting(event, sectors, region),
        "url": url,
        "source": source,
        "published_at": published_at,
        "categories": categories,
        "event": event,
        "event_amount": event_amount(f"{title} {source_summary}", event),
        "region": region,
        "sectors": sectors,
        "score": score,
        "score_reasons": score_reasons,
        "interest": interest_label(score),
        "entrepreneurship_priority": score,
        "domain": display_domain,
        "metrics": {"points": points, "comments": comments} if points or comments else {},
        "trust": trust,
        "trust_rank": TRUST_RANK.get(trust, 0),
        "trust_label": trust_label,
        "source_type": source_type,
        "safe_link": True,
        "link_label": f"Ouvrir {source}",
        "confirmation_count": 1,
        "confirmation_sources": [source],
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
        else:
            title = first_text(entry, ["title"])
            summary = first_text(entry, ["description", "{http://purl.org/rss/1.0/modules/content/}encoded"])
            url = first_text(entry, ["link"])
            published_raw = first_text(entry, ["pubDate", "{http://purl.org/dc/elements/1.1/}date"])

        item = make_item(
            title=title, summary=summary, url=url, source=source["name"], published_at=parse_date(published_raw),
            source_weight=source["weight"], trust=source["trust"], trust_label=source["trust_label"],
            source_type=source["source_type"], safe_domains=source["safe_domains"], display_domain=source["display_domain"],
            default_region=source.get("region"), default_event=source.get("default_event"),
            max_age_days=int(source.get("max_age_days", 21)),
        )
        if item: items.append(item)
    return items



def decode_html(raw: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "iso-8859-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def meta_content(doc: str, key: str) -> str:
    key_re = re.escape(key)
    patterns = [
        rf'<meta[^>]+(?:property|name)=["\']{key_re}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{key_re}["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, doc, flags=re.I | re.S)
        if match:
            return clean_text(match.group(1))
    return ""


def article_date(doc: str) -> str | None:
    for key in ("article:published_time", "date", "datePublished", "publish-date"):
        value = meta_content(doc, key)
        if value:
            return value
    match = re.search(r'<time[^>]+datetime=["\']([^"\']+)["\']', doc, flags=re.I | re.S)
    if match:
        return clean_text(match.group(1))
    match = re.search(r'"datePublished"\s*:\s*"([^"]+)"', doc, flags=re.I)
    if match:
        return clean_text(match.group(1))
    return None


def page_title(doc: str) -> str:
    value = meta_content(doc, "og:title") or meta_content(doc, "twitter:title")
    if value:
        return value
    match = re.search(r'<title[^>]*>(.*?)</title>', doc, flags=re.I | re.S)
    return clean_text(match.group(1)) if match else ""


def page_description(doc: str) -> str:
    return (
        meta_content(doc, "og:description")
        or meta_content(doc, "description")
        or meta_content(doc, "twitter:description")
    )


def listing_candidates(spec: dict) -> list[str]:
    listing = decode_html(http_get(spec["listing_url"]))
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', listing, flags=re.I)
    out: list[str] = []
    seen = set()
    pattern = spec.get("link_pattern")
    for href in hrefs:
        absolute = urljoin(spec["listing_url"], html.unescape(href)).split("#", 1)[0]
        parsed = urlparse(absolute)
        if not parsed.hostname or not any(host_matches(parsed.hostname, domain) for domain in spec["safe_domains"]):
            continue
        if pattern and not re.search(pattern, parsed.path, flags=re.I):
            continue
        if absolute.rstrip("/") == spec["listing_url"].rstrip("/"):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        out.append(absolute)
        if len(out) >= int(spec.get("max", 12)):
            break
    return out


def fetch_html_source(spec: dict) -> list[dict]:
    items = []
    for url in listing_candidates(spec):
        # Validate the destination before even requesting the article page.
        if not is_safe_url(url, spec["safe_domains"]):
            continue
        try:
            doc = decode_html(http_get(url, timeout=20))
        except Exception:
            continue
        published_raw = article_date(doc)
        # Do not guess dates for arbitrary listing/navigation pages.
        if not published_raw:
            continue
        title = page_title(doc)
        summary = page_description(doc)
        item = make_item(
            title=title, summary=summary, url=url, source=spec["name"], published_at=parse_date(published_raw),
            source_weight=spec["weight"], trust=spec["trust"], trust_label=spec["trust_label"],
            source_type=spec["source_type"], safe_domains=spec["safe_domains"], display_domain=spec["display_domain"],
            default_region=spec.get("region"), default_event=spec.get("default_event"),
            max_age_days=int(spec.get("max_age_days", 45)),
        )
        if item:
            items.append(item)
    return items


def bpifrance_fallback_spec(source: dict) -> dict:
    return {
        "name": source["name"],
        "listing_url": source["fallback_listing_url"],
        "link_pattern": source.get("fallback_link_pattern", r"^/"),
        "weight": source["weight"],
        "region": source.get("region", "France"),
        "max": source.get("fallback_max", 20),
        "max_age_days": source.get("max_age_days", 45),
        "trust": source["trust"],
        "trust_label": source["trust_label"],
        "source_type": source["source_type"],
        "safe_domains": source["safe_domains"],
        "display_domain": source["display_domain"],
    }


def fetch_hn(spec: dict) -> list[dict]:
    ids = http_json(spec["endpoint"])[: spec["limit"]]
    items = []
    for story_id in ids:
        story = http_json(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json") or {}
        if story.get("type") != "story": continue
        url = f"https://news.ycombinator.com/item?id={story_id}"
        item = make_item(
            title=clean_text(story.get("title")), summary=clean_text(story.get("text")), url=url, source=spec["name"],
            published_at=datetime.fromtimestamp(story.get("time", 0), tz=timezone.utc).isoformat(), source_weight=spec["weight"],
            trust=spec["trust"], trust_label=spec["trust_label"], source_type=spec["source_type"], safe_domains=spec["safe_domains"],
            display_domain=spec["display_domain"], default_event="Lancement", points=int(story.get("score", 0) or 0),
            comments=int(story.get("descendants", 0) or 0),
        )
        if item: items.append(item)
    return items


def normalized_tokens(title: str) -> set[str]:
    t = re.sub(r"^show hn:\s*", "", title.lower())
    tokens = re.findall(r"[a-zà-ÿ0-9][a-zà-ÿ0-9+.-]{2,}", t)
    return {tok.strip(".-") for tok in tokens if tok.strip(".-") not in STOPWORDS and len(tok.strip(".-")) >= 3}


def normalized_amounts(text: str) -> set[str]:
    vals = re.findall(r"(?:[$€£]\s?\d+(?:[.,]\d+)?\s?(?:[kmb]|bn|million|billion)?|\d+(?:[.,]\d+)?\s?(?:million|millions|milliard|milliards))", text.lower())
    return {re.sub(r"\s+", "", v) for v in vals}


def normalize_entity(value: str) -> str:
    value = re.sub(r"^show hn:\s*", "", clean_text(value), flags=re.I).lower()
    value = re.sub(r"[^a-zà-ÿ0-9+.-]+", " ", value)
    words = [w.strip(".-") for w in value.split() if w.strip(".-") and w.strip(".-") not in STOPWORDS]
    return " ".join(words[:5])


def entity_tokens(item: dict) -> set[str]:
    subject = item.get("company") or item.get("entity") or extract_subject(item.get("title", ""))
    return normalized_tokens(normalize_entity(subject))


def published_distance_hours(a: dict, b: dict) -> float:
    try:
        da = datetime.fromisoformat(a["published_at"].replace("Z", "+00:00"))
        db = datetime.fromisoformat(b["published_at"].replace("Z", "+00:00"))
        if da.tzinfo is None: da = da.replace(tzinfo=timezone.utc)
        if db.tzinfo is None: db = db.replace(tzinfo=timezone.utc)
        return abs((da - db).total_seconds()) / 3600
    except Exception:
        return 9999


def normalize_event_amount(raw: str | None) -> str | None:
    if not raw:
        return None
    t = clean_text(raw).lower().replace(" ", "").replace(",", ".")
    t = t.replace("million", "m").replace("millions", "m").replace("billion", "b").replace("milliard", "b").replace("milliards", "b").replace("bn", "b")
    return t


def event_amount(text: str, event: str) -> str | None:
    if event != "Levée":
        return None
    amount = r"([$€£]\s?\d+(?:[.,]\d+)?\s?(?:[kmb]|bn|million|millions|billion)?|\d+(?:[.,]\d+)?\s?(?:million|millions|milliard|milliards)\s?(?:d['’]euros|euros|€|dollars?)?)"
    patterns = [
        rf"(?:raises?|raised|secures?|secured|closes?|closed|funding(?: round)? of)\s+(?:about\s+|over\s+|up to\s+)?{amount}",
        rf"(?:l[èe]ve|levée de|tour de table de|financement de)\s+(?:plus de\s+|environ\s+)?{amount}",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            return normalize_event_amount(m.group(1))
    return None



def signal_identity(company_key: str, event: str, title: str, summary: str, published_at: str) -> str:
    if not company_key:
        return item_id("signal", title)
    amount = event_amount(f"{title} {summary}", event)
    try:
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        week = f"{dt.isocalendar().year}-W{dt.isocalendar().week:02d}"
    except Exception:
        week = "unknown"
    if amount:
        basis = f"{company_key}|{event}|{amount}"
    else:
        keywords = sorted(normalized_tokens(title))[:5]
        basis = f"{company_key}|{event}|{week}|{'-'.join(keywords)}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:14]

def same_signal(a: dict, b: dict) -> bool:
    if a["source"] == b["source"]:
        return False
    if published_distance_hours(a, b) > (24 * 7 if a.get("event") == "Levée" else 24 * 4):
        return False
    if a["event"] != b["event"] and "Business" not in {a["event"], b["event"]}:
        return False

    ta, tb = normalized_tokens(a["title"]), normalized_tokens(b["title"])
    ea, eb = entity_tokens(a), entity_tokens(b)
    if not ta or not tb:
        return False
    inter = ta & tb
    union = ta | tb
    jaccard = len(inter) / max(1, len(union))
    seq = SequenceMatcher(None, re.sub(r"\W+", " ", a["title"].lower()), re.sub(r"\W+", " ", b["title"].lower())).ratio()
    shared_entity = ea & eb
    company_a = a.get("company_key") or normalize_entity(a.get("company") or "")
    company_b = b.get("company_key") or normalize_entity(b.get("company") or "")
    exact_company = bool(company_a and company_b and company_a == company_b)
    amount_a = event_amount(f"{a['title']} {a.get('source_excerpt','')}", a.get("event", "Business"))
    amount_b = event_amount(f"{b['title']} {b.get('source_excerpt','')}", b.get("event", "Business"))
    same_amount = bool(amount_a and amount_b and amount_a == amount_b)
    distinctive = any(len(tok) >= 5 for tok in inter)

    # V2.8: a recognized company name is strong evidence, but a funding round still needs
    # an amount or meaningful headline overlap so two separate rounds are not merged.
    if exact_company:
        if a.get("event") == "Levée":
            return same_amount or jaccard >= 0.22 or (distinctive and len(inter) >= 2)
        return jaccard >= 0.20 or (distinctive and len(inter) >= 2) or seq >= 0.66
    if shared_entity and (jaccard >= 0.26 or same_amount or (distinctive and len(inter) >= 2)):
        return True
    if seq >= 0.76 and distinctive and len(inter) >= 2:
        return True
    if same_amount and distinctive and len(inter) >= 2:
        return True
    return False

def detect_cluster_conflict(cluster: list[dict]) -> tuple[bool, str]:
    funding_amounts = {
        amount for item in cluster
        if (amount := event_amount(f"{item.get('title','')} {item.get('source_excerpt','')}", item.get("event", "Business")))
    }
    if len(funding_amounts) > 1:
        return True, "Les sources rapprochées ne donnent pas le même montant de financement. Le radar conserve le signal mais le marque à vérifier."
    return False, ""


def confidence_for(cluster: list[dict], primary: dict, conflict: bool = False) -> tuple[str, str, str]:
    trusted = [i for i in cluster if i["trust"] in {"official", "reference", "editorial"}]
    trusted_sources = list(dict.fromkeys(i["source"] for i in trusted))
    has_official = any(i["trust"] == "official" for i in trusted)

    if conflict:
        return "conflict", "À vérifier · sources divergentes", "Plusieurs sources ont été rapprochées, mais au moins un chiffre clé diffère."
    if has_official and len(trusted_sources) >= 2:
        return "official_confirmed", f"Confirmé · officiel + {len(trusted_sources)-1} média{'s' if len(trusted_sources)-1 > 1 else ''}", "Une source officielle et au moins un média indépendant convergent sur ce signal."
    if has_official:
        return "official", "Source officielle", "Information publiée directement par une source officielle autorisée."
    if len(trusted_sources) >= 3:
        return "confirmed", f"Très bien confirmé · {len(trusted_sources)} sources", "Le même signal a été retrouvé dans au moins trois médias sélectionnés distincts."
    if len(trusted_sources) == 2:
        return "confirmed", "Confirmé · 2 sources", "Deux médias sélectionnés distincts convergent sur le même signal."
    if primary["trust"] in {"reference", "editorial"}:
        return "selected", "Source unique sélectionnée", "Le lien provient d’un média autorisé, mais aucune seconde confirmation indépendante n’a été rapprochée pour l’instant."
    return "discovery", "Découverte · non confirmée", "Signal de découverte : utile pour repérer tôt un projet, mais ce n’est pas une validation éditoriale."


def cluster_and_dedupe(items: Iterable[dict]) -> list[dict]:
    ordered = sorted(items, key=lambda x: (x.get("trust_rank", 0), x.get("score", 0), x.get("published_at", "")), reverse=True)
    clusters: list[list[dict]] = []
    exact_urls = set()
    for item in ordered:
        url_key = re.sub(r"[?#].*$", "", item["url"])
        if url_key in exact_urls:
            continue
        exact_urls.add(url_key)
        placed = False
        for cluster in clusters:
            # Compare with up to the three strongest items in a cluster, not
            # only the first one, to reduce false negatives across languages.
            if any(same_signal(item, peer) for peer in cluster[:3]):
                cluster.append(item)
                placed = True
                break
        if not placed:
            clusters.append([item])

    out = []
    for cluster in clusters:
        primary = sorted(cluster, key=lambda x: (x.get("trust_rank", 0), x.get("score", 0), x.get("published_at", "")), reverse=True)[0].copy()
        sources = list(dict.fromkeys(i["source"] for i in cluster))
        trusted_cluster = [i for i in cluster if i["trust"] in {"official", "reference", "editorial"}]
        conflict, conflict_note = detect_cluster_conflict(trusted_cluster)

        primary["confirmation_count"] = len(sources)
        primary["confirmation_sources"] = sources
        primary["confirmation_links"] = [
            {
                "source": i["source"],
                "url": i["url"],
                "domain": i["domain"],
                "trust": i["trust"],
            }
            for i in sorted(cluster, key=lambda x: (x.get("trust_rank", 0), x.get("score", 0)), reverse=True)
        ][:5]
        level, label, note = confidence_for(cluster, primary, conflict)
        primary["confidence_level"] = level
        primary["confidence_label"] = label
        primary["confidence_note"] = conflict_note or note
        primary["signal_key"] = signal_identity(primary.get("company_key", ""), primary.get("event", "Business"), primary.get("title", ""), primary.get("source_excerpt", ""), primary.get("published_at", ""))
        primary["trusted_confirmation_count"] = len({i["source"] for i in trusted_cluster})
        primary["has_official_confirmation"] = any(i.get("trust") == "official" for i in trusted_cluster)
        if not primary.get("event_amount"):
            primary["event_amount"] = next((i.get("event_amount") for i in cluster if i.get("event_amount")), None)

        if level == "confirmed":
            primary["score"] = min(99, primary["score"] + 9)
            primary["score_reasons"] = ["Confirmation multi-source +9", *primary.get("score_reasons", [])][:7]
        elif level == "official_confirmed":
            primary["score"] = min(99, primary["score"] + 11)
            primary["score_reasons"] = ["Source officielle + recoupement +11", *primary.get("score_reasons", [])][:7]
        elif level == "conflict":
            primary["score"] = max(1, primary["score"] - 12)
            primary["score_reasons"] = ["Divergence détectée −12", *primary.get("score_reasons", [])][:7]

        primary["interest"] = interest_label(primary["score"])
        primary["entrepreneurship_priority"] = primary["score"]
        out.append(primary)

    # Keep the feed focused: trusted sources first, then discovery; very old
    # or weak generic business items naturally fall to the bottom.
    out.sort(key=lambda x: (x.get("confidence_level") not in {"discovery", "conflict"}, x.get("score", 0), x.get("published_at", "")), reverse=True)
    return out[:MAX_ITEMS]

def build_demo() -> list[dict]:
    now = datetime.now(timezone.utc)
    demos = [
        dict(title="Higgsfield raises $400M Series B, quadrupling its valuation", summary="Higgsfield, founded by a former Snap executive, lets users create AI images and videos.", url="https://techcrunch.com/demo-higgsfield", source="TechCrunch", published_at=now.isoformat(), source_weight=20, trust="reference", trust_label="Média de référence", source_type="media", safe_domains=["techcrunch.com"], display_domain="techcrunch.com", default_event="Levée"),
        dict(title="Higgsfield secures $400M in Series B funding", summary="The AI video startup has raised a new funding round.", url="https://sifted.eu/articles/demo-higgsfield", source="Sifted", published_at=(now-timedelta(minutes=20)).isoformat(), source_weight=21, trust="reference", trust_label="Média de référence", source_type="media", safe_domains=["sifted.eu"], display_domain="sifted.eu", default_region="Europe", default_event="Levée"),
        dict(title="Bpifrance annonce un programme d'accompagnement pour les startups deeptech", summary="Le programme renforce l'accompagnement des entreprises innovantes vers l'industrialisation.", url="https://presse.bpifrance.fr/demo", source="Bpifrance Presse", published_at=(now-timedelta(hours=2)).isoformat(), source_weight=22, trust="official", trust_label="Source officielle", source_type="official", safe_domains=["presse.bpifrance.fr"], display_domain="presse.bpifrance.fr", default_region="France"),
        dict(title="Show HN: AI agent that turns customer calls into CRM actions", summary="", url="https://news.ycombinator.com/item?id=123456", source="Show HN", published_at=(now-timedelta(hours=1)).isoformat(), source_weight=12, trust="discovery", trust_label="Découverte · non confirmée", source_type="community", safe_domains=["news.ycombinator.com"], display_domain="news.ycombinator.com", default_event="Lancement", points=98, comments=42),
    ]
    return cluster_and_dedupe([x for d in demos if (x := make_item(**d))])


def stats_for(items: list[dict]) -> dict:
    return {
        "sources": len({i.get("source") for i in items}),
        "sources_active": SOURCE_HEALTH["success"],
        "sources_expected": SOURCE_HEALTH["expected"],
        "sources_failed": len(SOURCE_HEALTH["failed"]),
        "source_failures": SOURCE_HEALTH["failed"],
        "source_empty": SOURCE_HEALTH["empty"],
        "france": sum(1 for i in items if i.get("region") == "France"),
        "verified": sum(1 for i in items if i.get("trust") in {"official", "reference", "editorial"}),
        "confirmed": sum(1 for i in items if i.get("confidence_level") in {"confirmed", "official_confirmed"}),
        "official": sum(1 for i in items if i.get("confidence_level") in {"official", "official_confirmed"}),
        "conflicts": sum(1 for i in items if i.get("confidence_level") == "conflict"),
        "links_checked": METRICS["links_checked"],
        "links_blocked": METRICS["links_blocked"],
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Generate demo data without network access")
    args = parser.parse_args()
    items: list[dict] = []
    errors: list[str] = []

    if args.demo:
        SOURCE_HEALTH["expected"] = 4
        SOURCE_HEALTH["success"] = 4
        items = build_demo()
    else:
        for source in RSS_SOURCES:
            try:
                fetched = fetch_rss(source)
                items.extend(fetched)
                SOURCE_HEALTH["success"] += 1
                if not fetched:
                    SOURCE_HEALTH["empty"].append(source["name"])
            except Exception as exc:
                # Bpifrance's RSS endpoint is occasionally unavailable; use
                # its official press listing as a same-domain fallback.
                fallback_ok = False
                if source.get("fallback_listing_url"):
                    try:
                        fetched = fetch_html_source(bpifrance_fallback_spec(source))
                        items.extend(fetched)
                        SOURCE_HEALTH["success"] += 1
                        fallback_ok = True
                        if not fetched:
                            SOURCE_HEALTH["empty"].append(source["name"])
                    except Exception as fallback_exc:
                        errors.append(f"{source['name']} fallback: {fallback_exc}")
                if not fallback_ok:
                    message = f"{source['name']}: {exc}"
                    errors.append(message)
                    SOURCE_HEALTH["failed"].append(source["name"])

        for source in HTML_SOURCES:
            try:
                fetched = fetch_html_source(source)
                items.extend(fetched)
                SOURCE_HEALTH["success"] += 1
                if not fetched:
                    SOURCE_HEALTH["empty"].append(source["name"])
            except Exception as exc:
                message = f"{source['name']}: {exc}"
                errors.append(message)
                SOURCE_HEALTH["failed"].append(source["name"])

        for spec in HN_ENDPOINTS:
            try:
                fetched = fetch_hn(spec)
                items.extend(fetched)
                SOURCE_HEALTH["success"] += 1
                if not fetched:
                    SOURCE_HEALTH["empty"].append(spec["name"])
            except Exception as exc:
                message = f"{spec['name']}: {exc}"
                errors.append(message)
                SOURCE_HEALTH["failed"].append(spec["name"])
        items = cluster_and_dedupe(items)

    payload = {
        "version": "2.9",
        "strict_link_mode": True,
        "direct_sources_only": True,
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
