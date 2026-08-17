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
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "feed.json"
USER_AGENT = "BusinessRadar/1.0 (+personal business news reader)"

RSS_SOURCES = [
    {"name": "Product Hunt", "url": "https://www.producthunt.com/feed?category=undefined", "weight": 12},
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "weight": 7},
]

HN_ENDPOINTS = [
    ("Show HN", "https://hacker-news.firebaseio.com/v0/showstories.json", 35, 12),
    ("Hacker News", "https://hacker-news.firebaseio.com/v0/beststories.json", 35, 8),
]

KEYWORDS = {
    "IA": ["ai", "artificial intelligence", "llm", "agent", "machine learning", "openai", "anthropic"],
    "SaaS": ["saas", "software as a service", "subscription", "b2b software"],
    "Startup": ["startup", "founder", "launch", "launched", "product hunt", "show hn"],
    "Levée": ["funding", "fundraise", "raised", "series a", "series b", "seed round", "venture capital", "levée"],
    "Fintech": ["fintech", "banking", "payments", "payment", "finance"],
    "E-commerce": ["ecommerce", "e-commerce", "shopify", "marketplace", "retail"],
    "France": ["france", "french", "paris", "mistral", "station f"],
}

POSITIVE = {
    "launch": 10, "launched": 10, "startup": 8, "founder": 7, "revenue": 7,
    "mrr": 9, "funding": 8, "raised": 8, "customers": 5, "growth": 6,
    "profitable": 8, "saas": 7, "agent": 5, "ai": 4,
}


def http_get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def http_json(url: str):
    return json.loads(http_get(url).decode("utf-8"))


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    value = html.unescape(re.sub(r"<[^>]+>", " ", value))
    return re.sub(r"\s+", " ", value).strip()


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


def categories_for(text: str) -> list[str]:
    t = text.lower()
    tags = [label for label, terms in KEYWORDS.items() if any(term in t for term in terms)]
    return tags[:4] or ["Business"]


def score_item(title: str, summary: str, source_weight: int = 0, points: int = 0, comments: int = 0) -> int:
    t = f"{title} {summary}".lower()
    score = 35 + source_weight
    for term, value in POSITIVE.items():
        if re.search(rf"\b{re.escape(term)}\b", t):
            score += value
    score += min(points // 10, 16)
    score += min(comments // 8, 10)
    return max(1, min(score, 99))


def first_text(node: ET.Element, names: list[str]) -> str:
    for name in names:
        found = node.find(name)
        if found is not None and found.text:
            return found.text.strip()
    return ""


def fetch_rss(source: dict) -> list[dict]:
    root = ET.fromstring(http_get(source["url"]))
    entries = root.findall(".//item")
    is_atom = False
    if not entries:
        ns = {"a": "http://www.w3.org/2005/Atom"}
        entries = root.findall(".//a:entry", ns)
        is_atom = True

    items = []
    for entry in entries[:35]:
        if is_atom:
            ns = {"a": "http://www.w3.org/2005/Atom"}
            title = clean_text(first_text(entry, ["{http://www.w3.org/2005/Atom}title"]))
            summary = clean_text(first_text(entry, ["{http://www.w3.org/2005/Atom}content", "{http://www.w3.org/2005/Atom}summary"]))
            link_node = entry.find("a:link[@rel='alternate']", ns) or entry.find("a:link", ns)
            url = link_node.attrib.get("href", "") if link_node is not None else ""
            published_raw = first_text(entry, ["{http://www.w3.org/2005/Atom}published", "{http://www.w3.org/2005/Atom}updated"])
        else:
            title = clean_text(first_text(entry, ["title"]))
            summary = clean_text(first_text(entry, ["description", "{http://purl.org/rss/1.0/modules/content/}encoded"]))
            url = first_text(entry, ["link"])
            published_raw = first_text(entry, ["pubDate", "{http://purl.org/dc/elements/1.1/}date"])
        if not title or not url:
            continue
        items.append({
            "id": item_id(url, title),
            "title": title,
            "summary": summary[:420],
            "url": url,
            "source": source["name"],
            "published_at": parse_date(published_raw),
            "categories": categories_for(f"{title} {summary} {source['name']}"),
            "score": score_item(title, summary, source["weight"]),
            "domain": urlparse(url).netloc.replace("www.", ""),
        })
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
        items.append({
            "id": item_id(url, title),
            "title": title,
            "summary": summary[:420],
            "url": url,
            "source": name,
            "published_at": published,
            "categories": categories_for(f"{title} {summary} {name}"),
            "score": score_item(title, summary, weight, points, comments),
            "domain": urlparse(url).netloc.replace("www.", ""),
            "metrics": {"points": points, "comments": comments},
        })
    return items


def dedupe(items: Iterable[dict]) -> list[dict]:
    seen = set()
    out = []
    for item in sorted(items, key=lambda x: (x.get("score", 0), x.get("published_at", "")), reverse=True):
        key = re.sub(r"\W+", "", item["title"].lower())[:120]
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out[:120]


def build_demo() -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    demos = [
        ("Un nouveau SaaS B2B automatise la prospection commerciale", "Carte de démonstration pour valider l'interface du Business Radar.", "Démo", "https://example.com/saas", ["SaaS", "Startup"], 86),
        ("Show HN: un fondateur lance un outil IA pour analyser des marchés", "Projet fictif utilisé uniquement en mode démo.", "Show HN", "https://example.com/ai", ["IA", "Startup"], 79),
        ("Une fintech française prépare un nouveau produit pour les PME", "Exemple de contenu France / Fintech.", "Démo", "https://example.com/fintech", ["France", "Fintech"], 72),
    ]
    return [{"id": item_id(u, t), "title": t, "summary": s, "url": u, "source": src, "published_at": now, "categories": cats, "score": score, "domain": urlparse(u).netloc} for t, s, src, u, cats, score in demos]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Generate demo data without network access")
    args = parser.parse_args()

    items, errors = [], []
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
                items.extend(fetch_hn(*spec))
            except Exception as exc:
                errors.append(f"{spec[0]}: {exc}")
        items = dedupe(items)

    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "count": len(items), "errors": errors, "items": items}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(items)} items to {OUT}")
    if errors:
        print("Warnings:", *errors, sep="\n- ", file=sys.stderr)
    return 0 if items else 1


if __name__ == "__main__":
    raise SystemExit(main())
