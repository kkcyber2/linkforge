"""Link shortening with click analytics.

Slug generation uses rejection sampling over a base62 alphabet: a plain
`random.choice` per character is fine, but we must guarantee we never hand out
a slug that collides with an existing one, and never one that looks like a
reserved path.
"""
from __future__ import annotations

import re
import secrets
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import urlparse

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
RESERVED = {"api", "admin", "healthz", "static", "assets", "login", "signup"}
SLUG_LEN = 7

# Only these schemes are ever redirectable. Without this check the shortener
# becomes an open redirector for javascript: and data: URIs — a real XSS vector.
ALLOWED_SCHEMES = {"http", "https"}


@dataclass
class Click:
    ts: float
    referrer: str = ""
    user_agent: str = ""
    country: str = ""
    device: str = "unknown"


@dataclass
class Link:
    slug: str
    target: str
    created_at: float
    clicks: List[Click] = field(default_factory=list)
    active: bool = True
    title: str = ""

    @property
    def count(self) -> int:
        return len(self.clicks)

    def as_dict(self) -> dict:
        return {
            "slug": self.slug, "target": self.target, "title": self.title,
            "created_at": self.created_at, "clicks": self.count,
            "active": self.active,
        }


def validate_target(url: str) -> str:
    """Reject anything that is not a plain http(s) URL."""
    if not url or not isinstance(url, str):
        raise ValueError("target required")
    url = url.strip()
    if len(url) > 2048:
        raise ValueError("target too long")
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise ValueError(f"scheme '{parsed.scheme}' not allowed — use http or https")
    if not parsed.netloc:
        raise ValueError("target must include a host")
    return url


def detect_device(ua: str) -> str:
    ua = (ua or "").lower()
    if any(t in ua for t in ("iphone", "android", "mobile", "ipad", "tablet")):
        return "mobile"
    if any(t in ua for t in ("bot", "crawler", "spider", "curl", "wget")):
        return "bot"
    return "desktop"


def classify_referrer(ref: str) -> str:
    """Bucket a referrer into a channel — raw URLs are useless in a report."""
    if not ref:
        return "direct"
    low = ref.lower()
    for name, needles in (
        ("linkedin", ("linkedin.com",)),
        ("twitter", ("twitter.com", "x.com", "t.co")),
        ("google", ("google.",)),
        ("facebook", ("facebook.com", "fb.me")),
        ("instagram", ("instagram.com",)),
        ("email", ("mail.", "outlook.", "gmail.")),
    ):
        if any(n in low for n in needles):
            return name
    return "other"


class LinkStore:
    def __init__(self):
        self._links: Dict[str, Link] = {}

    def _new_slug(self) -> str:
        for _ in range(100):
            slug = "".join(secrets.choice(ALPHABET) for _ in range(SLUG_LEN))
            if slug not in self._links and slug.lower() not in RESERVED:
                return slug
        raise RuntimeError("slug space exhausted")

    def create(self, target: str, slug: Optional[str] = None,
               title: str = "") -> Link:
        target = validate_target(target)
        if slug:
            if not re.fullmatch(r"[A-Za-z0-9_-]{2,32}", slug):
                raise ValueError("slug must be 2-32 chars of A-Z a-z 0-9 _ -")
            if slug.lower() in RESERVED:
                raise ValueError(f"'{slug}' is reserved")
            if slug in self._links:
                raise ValueError(f"'{slug}' already taken")
        else:
            slug = self._new_slug()
        link = Link(slug=slug, target=target, created_at=time.time(), title=title)
        self._links[slug] = link
        return link

    def get(self, slug: str) -> Optional[Link]:
        return self._links.get(slug)

    def resolve(self, slug: str, referrer: str = "", user_agent: str = "",
                country: str = "") -> Optional[str]:
        link = self._links.get(slug)
        if not link or not link.active:
            return None
        link.clicks.append(Click(
            ts=time.time(),
            referrer=classify_referrer(referrer),
            user_agent=user_agent[:200],
            country=country,
            device=detect_device(user_agent),
        ))
        return link.target

    def deactivate(self, slug: str) -> bool:
        link = self._links.get(slug)
        if not link:
            return False
        link.active = False
        return True

    def all(self) -> List[Link]:
        return sorted(self._links.values(), key=lambda l: l.created_at, reverse=True)

    def stats(self, slug: str) -> Optional[dict]:
        link = self._links.get(slug)
        if not link:
            return None
        by_device: Dict[str, int] = {}
        by_ref: Dict[str, int] = {}
        by_country: Dict[str, int] = {}
        for c in link.clicks:
            by_device[c.device] = by_device.get(c.device, 0) + 1
            by_ref[c.referrer] = by_ref.get(c.referrer, 0) + 1
            if c.country:
                by_country[c.country] = by_country.get(c.country, 0) + 1
        return {
            "slug": slug, "target": link.target, "clicks": link.count,
            "by_device": by_device, "by_referrer": by_ref,
            "by_country": by_country,
            "first_click": link.clicks[0].ts if link.clicks else None,
            "last_click": link.clicks[-1].ts if link.clicks else None,
        }
