from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_PARAMS_PREFIXES = ("utm_",)
TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "msclkid",
    "ref",
    "source",
    "mc_cid",
    "mc_eid",
}


def normalize_text(value: Any) -> str:
    text = str(value or "").casefold()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-z0-9à-ÿ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_url(url: str | None) -> str:
    if not url:
        return ""

    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower() or "https"
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]

    query_items = []
    for key, value in parse_qsl(parts.query, keep_blank_values=False):
        key_lower = key.lower()
        if key_lower in TRACKING_PARAMS:
            continue
        if any(key_lower.startswith(prefix) for prefix in TRACKING_PARAMS_PREFIXES):
            continue
        query_items.append((key, value))

    path = re.sub(r"/+", "/", parts.path).rstrip("/")
    return urlunsplit((scheme, netloc, path, "", urlencode(query_items, doseq=True)))


def title_similarity(left: str | None, right: str | None) -> float:
    left_norm = normalize_text(left)
    right_norm = normalize_text(right)
    if not left_norm or not right_norm:
        return 0.0
    return SequenceMatcher(None, left_norm, right_norm).ratio()


def company_program_key(item: dict[str, Any]) -> str:
    company = item.get("company") or item.get("institution") or ""
    program = item.get("opportunity") or item.get("program") or item.get("title") or ""
    return normalize_text(f"{company} {program}")


def item_url(item: dict[str, Any]) -> str:
    return (
        item.get("applyUrl")
        or item.get("companyUrl")
        or item.get("url")
        or item.get("link")
        or ""
    )


class Deduplicador:
    def __init__(self, items: list[dict[str, Any]], title_threshold: float = 0.82) -> None:
        self.title_threshold = title_threshold
        self.items = items
        self.urls = {normalize_url(item_url(item)) for item in items if normalize_url(item_url(item))}
        self.keys = {company_program_key(item) for item in items if company_program_key(item)}

    def find_match(self, candidate: dict[str, Any]) -> tuple[str, dict[str, Any] | None, float]:
        candidate_url = normalize_url(item_url(candidate))
        if candidate_url and candidate_url in self.urls:
            return "url", None, 1.0

        candidate_key = company_program_key(candidate)
        if candidate_key and candidate_key in self.keys:
            return "empresa_programa", None, 1.0

        candidate_title = candidate.get("opportunity") or candidate.get("program") or candidate.get("title")
        best_item: dict[str, Any] | None = None
        best_score = 0.0
        for item in self.items:
            item_title = item.get("opportunity") or item.get("program") or item.get("title")
            score = title_similarity(candidate_title, item_title)
            if score > best_score:
                best_item = item
                best_score = score

        if best_score >= self.title_threshold:
            return "titulo_parecido", best_item, best_score
        return "novo", None, best_score

