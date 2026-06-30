
from __future__ import annotations

import sys

if __name__ == "__main__" and any(arg in {"-h", "--help", "help"} for arg in sys.argv[1:]):
    print(__doc__)
    print("This is an internal helper module used by image_search.py and the four web image providers.")
    raise SystemExit(0)

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional



USER_AGENT = "PPTMaster/1.0 (https://github.com/hugohe3/ppt-master)"



LICENSE_TIER_NO_ATTRIBUTION = "no-attribution"
LICENSE_TIER_ATTRIBUTION_REQUIRED = "attribution-required"

NO_ATTRIBUTION_TOKENS: tuple[str, ...] = (
    "cc0",
    "public domain",
    "publicdomain",
    "creativecommons.org/publicdomain/",
    "pexels license",
    "pixabay content license",
    "pixabay license",
)

ATTRIBUTION_REQUIRED_TOKENS: tuple[str, ...] = (
    "cc by",
    "cc-by",
    "by-sa",
    "by sa",
    "creativecommons.org/licenses/by/",
    "creativecommons.org/licenses/by-sa/",
)

REJECTED_TOKENS: tuple[str, ...] = (
    "by-nc",
    "by nc",
    "noncommercial",
    "non-commercial",
    "by-nd",
    "by nd",
    "no derivatives",
    "noderivatives",
    "all rights reserved",
)


_LICENSE_NAME_CANON: dict[str, str] = {
    "cc0": "CC0",
    "cc 0": "CC0",
    "public domain": "Public Domain",
    "publicdomain": "Public Domain",
    "pdm": "Public Domain",
    "pexels license": "Pexels License",
    "pixabay content license": "Pixabay Content License",
    "pixabay license": "Pixabay Content License",
}

_CC_PATTERN = re.compile(
    r"^\s*cc[\s-]+(by(?:[\s-]+(?:sa|nc|nd))*)\s*([0-9.]*)\s*$",
    re.IGNORECASE,
)


def normalize_license_name(name: str) -> str:
    if not name:
        return ""
    key = name.strip().lower()
    if not key:
        return ""

    if key in _LICENSE_NAME_CANON:
        return _LICENSE_NAME_CANON[key]

    cc_match = _CC_PATTERN.match(key)
    if cc_match:
        suffix_raw, version = cc_match.group(1), cc_match.group(2)
        suffix = suffix_raw.replace(" ", "-").upper()
        return f"CC {suffix} {version}".strip()

    return name.strip()


def classify_license(
    license_name: str,
    license_url: str = "",
    provider: str = "",
) -> Optional[str]:
    text = " ".join(
        part.strip().lower()
        for part in (license_name or "", license_url or "")
        if part
    )
    provider_key = (provider or "").strip().lower()

    if not text and not provider_key:
        return None

    if any(token in text for token in REJECTED_TOKENS):
        return None

    if any(token in text for token in NO_ATTRIBUTION_TOKENS):
        return LICENSE_TIER_NO_ATTRIBUTION

    if (
        provider_key in {"pexels", "pixabay"}
        and provider_key in text
        and not any(token in text for token in ATTRIBUTION_REQUIRED_TOKENS)
    ):
        return LICENSE_TIER_NO_ATTRIBUTION

    if any(token in text for token in ATTRIBUTION_REQUIRED_TOKENS):
        return LICENSE_TIER_ATTRIBUTION_REQUIRED

    return None  # unknown license -> reject




@dataclass
class ImageSearchRequest:

    query: str
    purpose: str = ""
    orientation: str = ""  # "landscape" / "portrait" / "square" / ""
    min_width: int = 0
    min_height: int = 0
    filename: str = ""
    slide: str = ""


@dataclass
class AssetCandidate:

    provider: str
    title: str
    asset_id: str = ""
    source_page_url: str = ""
    license_name: str = ""
    license_url: str = ""
    license_tier: str = ""  # one of LICENSE_TIER_* constants
    width: int = 0
    height: int = 0
    download_url: str = ""
    author: str = ""
    raw: Any = field(default=None)



_NOISE_WORDS = frozenset({
    "claude", "openai", "gpt", "gemini", "copilot", "chatgpt", "midjourney",
    "stable", "diffusion", "dall-e", "cursor", "anthropic", "microsoft",
    "google", "apple", "meta", "nvidia", "tesla",
    "using", "with", "from", "that", "this", "have", "been", "will",
    "into", "more", "also", "very", "some", "than", "them", "other",
})

_SOFT_NOISE_WORDS = frozenset({
    "ai", "code", "software", "system", "digital", "platform", "solution",
    "application", "interface", "framework", "algorithm", "api", "sdk",
    "assistant", "tool", "service", "technology", "tech", "program",
    "professional", "editorial", "commercial", "premium", "stock",
    "photo", "photograph", "photography", "image", "picture", "visual",
    "background", "hero", "cover", "banner", "wallpaper",
    "high", "quality", "resolution", "sharp", "clean", "cinematic",
    "dramatic", "lighting", "light", "modern", "natural", "visible",
})

_TOKEN_STRIP_CHARS = ".,;:!?\"'()[]{}，。；：！？、"


def simplify_query(query: str, max_words: int = 4) -> str:
    cleaned = re.sub(r"#[0-9a-fA-F]{3,8}", "", query)
    cleaned = re.sub(r"\([^)]*\)", "", cleaned)
    words = [w.strip(_TOKEN_STRIP_CHARS) for w in cleaned.split()]
    words = [w for w in words if len(w) > 2]

    after_hard = [w for w in words if w.lower() not in _NOISE_WORDS]
    after_soft = [w for w in after_hard if w.lower() not in _SOFT_NOISE_WORDS]

    filtered = after_soft if after_soft else after_hard

    if not filtered:
        return query.strip()

    return " ".join(filtered[:max_words])


def build_query_progression(query: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for candidate in (
        query,
        simplify_query(query, max_words=4),
        simplify_query(query, max_words=3),
        simplify_query(query, max_words=2),
        simplify_query(query, max_words=1),
    ):
        candidate = candidate.strip()
        if candidate and candidate not in seen:
            seen.add(candidate)
            out.append(candidate)
    return out




def normalize_orientation(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        return "unknown"
    if width > height:
        return "landscape"
    if height > width:
        return "portrait"
    return "square"


def _query_tokens(query: str) -> list[str]:
    cleaned = re.sub(r"#[0-9a-fA-F]{3,8}", "", query.lower())
    cleaned = re.sub(r"\([^)]*\)", "", cleaned)
    words = [w.strip(_TOKEN_STRIP_CHARS) for w in cleaned.split()]
    words = [w for w in words if len(w) > 2 and w.isascii()]
    if not words:
        return []
    after_hard = [w for w in words if w not in _NOISE_WORDS]
    after_soft = [w for w in after_hard if w not in _SOFT_NOISE_WORDS]
    return after_soft if after_soft else after_hard


def _candidate_text(candidate: AssetCandidate) -> str:
    return " ".join(filter(None, (candidate.title, candidate.author))).lower()


def compute_relevance(candidate: AssetCandidate, query: str) -> float:
    tokens = _query_tokens(query)
    if not tokens:
        return 1.0
    text = _candidate_text(candidate)
    if not text:
        return 0.0
    hits = sum(1 for t in tokens if t in text)
    return hits / len(tokens)


def score_candidate(candidate: AssetCandidate, request: ImageSearchRequest) -> float:
    if not candidate.license_tier:
        return float("-inf")

    relevance = compute_relevance(candidate, request.query)
    if relevance == 0.0:
        return float("-inf")

    score = relevance * 10000.0

    text = _candidate_text(candidate)
    query_lower = request.query.lower()
    infra_terms = ["station", "subway", "metro", "rail", "transit", "airport", "bus", "地铁", "站", "轨道"]
    
    if not any(t in query_lower for t in infra_terms):
        if any(t in text for t in infra_terms):
            score -= 5000.0

    candidate_orientation = normalize_orientation(candidate.width, candidate.height)
    requested = (request.orientation or "").strip().lower()
    if requested:
        if candidate_orientation == requested:
            score += 1000.0
        else:
            score -= 250.0

    if request.min_width and candidate.width < request.min_width:
        score -= 500.0
    if request.min_height and candidate.height < request.min_height:
        score -= 500.0

    pixel_score = max(candidate.width, 0) * max(candidate.height, 0) / 1000.0
    score += min(pixel_score, 5000.0)
    return score




PROVIDER_DISPLAY_NAMES: dict[str, str] = {
    "openverse": "Openverse",
    "wikimedia": "Wikimedia Commons",
    "pexels": "Pexels",
    "pixabay": "Pixabay",
}


def build_attribution_text(filename: str, candidate: AssetCandidate) -> str:
    provider_name = PROVIDER_DISPLAY_NAMES.get(
        candidate.provider, candidate.provider or "unknown"
    )

    parts: list[str] = [filename or candidate.download_url or "image"]
    middle: list[str] = []
    if candidate.title:
        middle.append(f'"{candidate.title}"')
    if candidate.author:
        middle.append(f"by {candidate.author}")
    middle.append(f"via {provider_name}")
    parts.append(" ".join(middle))

    license_part = candidate.license_name or candidate.license_url
    if license_part:
        if candidate.license_url and candidate.license_name:
            license_part = f"{candidate.license_name} ({candidate.license_url})"
        parts.append(f"license: {license_part}")

    return " — ".join(parts)




def ensure_json_parent(path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p
