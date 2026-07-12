from __future__ import annotations

from pathlib import Path

from .config import Settings
from .layout import resolve_layout


def init_vault(settings: Settings) -> list[Path]:
    layout = resolve_layout(settings.wiki_root, settings.layout_language)
    created: list[Path] = []
    for relative in [*layout.raw_dirs.values(), *layout.wiki_dirs.values()]:
        path = settings.wiki_root / relative
        path.mkdir(parents=True, exist_ok=True)
        created.append(path)

    index_path = settings.wiki_root / layout.index_file
    if not index_path.exists():
        index_path.write_text("# LLM Wiki 索引\n\n" if layout.language == "zh" else "# LLM Wiki Index\n\n", encoding="utf-8")
    created.append(index_path)

    log_path = settings.wiki_root / layout.log_file
    if not log_path.exists():
        log_path.write_text("# LLM Wiki 日志\n\n" if layout.language == "zh" else "# LLM Wiki Log\n\n", encoding="utf-8")
    created.append(log_path)

    settings.index_db.parent.mkdir(parents=True, exist_ok=True)
    return created
