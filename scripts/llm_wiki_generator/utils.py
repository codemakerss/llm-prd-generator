from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


INVALID_FILE_CHARS = r'[\\/:*?"<>|]'
WIKILINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")
FRONTMATTER_PATTERN = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def slugify(value: str) -> str:
    text = re.sub(INVALID_FILE_CHARS, "-", value.strip())
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-") or "untitled"


def dump_frontmatter(data: dict[str, Any]) -> str:
    return "---\n" + yaml.safe_dump(data, allow_unicode=True, sort_keys=False).strip() + "\n---\n"


def load_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    match = FRONTMATTER_PATTERN.match(text)
    if not match:
        return {}, text
    raw = match.group(1)
    body = text[match.end() :]
    data = yaml.safe_load(raw) or {}
    return data, body


def extract_wikilinks(text: str) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for match in WIKILINK_PATTERN.findall(text):
        if match not in seen:
            seen.add(match)
            results.append(match)
    return results


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
