"""Facebook view-count parsing helpers."""

from __future__ import annotations

import re
from html.parser import HTMLParser

_VIEW_COUNT = re.compile(
    r"(?:조회(?:수)?\s*)?(\d+(?:\.\d+)?)\s*(천|만|억|K|M|B)?\s*(?:회|views?)",
    re.IGNORECASE,
)
_ABBREVIATED_NUMBER = re.compile(r"\s*(\d+(?:\.\d+)?)\s*(천|만|억|K|M|B)?\s*", re.IGNORECASE)
_MULTIPLIERS = {"천": 1_000, "만": 10_000, "억": 100_000_000, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}


def parse_view_count(value: object) -> int | None:
    """Return a view count, preserving 0 and leaving absent/invalid values as None."""
    if value is None:
        return None
    normalized = str(value).replace(",", "")
    match = _VIEW_COUNT.search(normalized) or _ABBREVIATED_NUMBER.fullmatch(normalized)
    if not match:
        return None
    number, suffix = match.groups()
    return int(float(number) * _MULTIPLIERS.get((suffix or "").upper(), _MULTIPLIERS.get(suffix or "", 1)))


class _OgTitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "meta":
            return
        attributes = dict(attrs)
        if attributes.get("property") == "og:title" or attributes.get("name") == "og:title":
            self.title = attributes.get("content")


def extract_og_view_count(document: str) -> int | None:
    """Read a view count from Facebook's og:title metadata without treating absence as zero."""
    parser = _OgTitleParser()
    parser.feed(document)
    return parse_view_count(parser.title)


def extract_provider_view_count(post: dict) -> int | None:
    """Use Bright Data's explicit fields first, including an actual numeric zero."""
    for field in ("play_count", "video_view_count"):
        count = parse_view_count(post.get(field))
        if count is not None:
            return count
    return None


def is_facebook_video(url: str, attachments: list[dict] | None = None) -> bool:
    """Limit metadata fallback to Reels and video posts."""
    if "/reel/" in url or "/videos/" in url:
        return True
    return any(attachment.get("type") == "video" for attachment in attachments or [])
