from __future__ import annotations

from pathlib import Path

from .config import Settings


RAW_DIRS = {
    "business_fact": "10-raw/business_fact",
    "industry_practice": "10-raw/industry_practice",
    "team_history": "10-raw/team_history",
    "feedback": "10-raw/feedback",
}

WIKI_DIRS = {
    "source": "20-wiki/sources",
    "entity": "20-wiki/entities",
    "concept": "20-wiki/concepts",
    "synthesis": "20-wiki/synthesis",
    "conflict": "20-wiki/conflicts",
    "prd_pattern": "20-wiki/prd-patterns",
}


def init_vault(settings: Settings) -> list[Path]:
    created: list[Path] = []
    for relative in [*RAW_DIRS.values(), *WIKI_DIRS.values()]:
        path = settings.wiki_root / relative
        path.mkdir(parents=True, exist_ok=True)
        created.append(path)

    index_path = settings.wiki_root / "20-wiki/index.md"
    if not index_path.exists():
        index_path.write_text("# LLM Wiki Index\n\n", encoding="utf-8")
    created.append(index_path)

    log_path = settings.wiki_root / "20-wiki/log.md"
    if not log_path.exists():
        log_path.write_text("# LLM Wiki Log\n\n", encoding="utf-8")
    created.append(log_path)

    settings.index_db.parent.mkdir(parents=True, exist_ok=True)
    return created
