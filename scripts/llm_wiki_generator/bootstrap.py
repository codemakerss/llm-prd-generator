from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Union

from .config import Settings, env_file_path, load_env_file_map, load_settings, write_env_values
from .layout import LAYOUTS, WikiLayoutError, normalize_layout_language, resolve_layout
from .vault import init_vault


@dataclass
class BootstrapStatus:
    skill_root: Path
    env_path: Path
    env_exists: bool
    configured: bool
    initialized: bool
    wiki_root: Optional[Path]
    index_db: Optional[Path]
    layout_language: Optional[str]
    layout_paths: list[str]
    missing_paths: list[str]
    error: Optional[str] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "skill_root": str(self.skill_root),
            "env_path": str(self.env_path),
            "env_exists": self.env_exists,
            "configured": self.configured,
            "initialized": self.initialized,
            "wiki_root": str(self.wiki_root) if self.wiki_root else None,
            "index_db": str(self.index_db) if self.index_db else None,
            "layout_language": self.layout_language,
            "layout_paths": self.layout_paths,
            "missing_paths": self.missing_paths,
            "error": self.error,
        }


def required_relative_paths(language: str = "en") -> list[str]:
    return LAYOUTS[normalize_layout_language(language) or "en"].required_paths


def derive_index_db_path(wiki_root: Path) -> Path:
    return wiki_root / "index.sqlite3"


def normalize_wiki_root(skill_root: Path, raw_path: Union[str, Path]) -> Path:
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = (skill_root / candidate).resolve()
    return candidate


def initialized_relative_gaps(wiki_root: Path, language: str = "en") -> list[str]:
    missing: list[str] = []
    for relative in required_relative_paths(language):
        if not (wiki_root / relative).exists():
            missing.append(relative)
    return missing


def inspect_bootstrap(skill_root: Path) -> BootstrapStatus:
    env_path = env_file_path(skill_root)
    env_values = load_env_file_map(skill_root)
    raw_root = env_values.get("WIKI_ROOT", "").strip()
    raw_index = env_values.get("WIKI_INDEX_DB", "").strip()
    raw_language = env_values.get("WIKI_LAYOUT_LANGUAGE", "").strip().lower()

    try:
        initial_language = normalize_layout_language(raw_language) or "en"
    except WikiLayoutError as exc:
        return BootstrapStatus(
            skill_root=skill_root,
            env_path=env_path,
            env_exists=env_path.exists(),
            configured=bool(raw_root),
            initialized=False,
            wiki_root=normalize_wiki_root(skill_root, raw_root) if raw_root else None,
            index_db=normalize_wiki_root(skill_root, raw_index) if raw_index else None,
            layout_language=raw_language or None,
            layout_paths=[],
            missing_paths=[],
            error=str(exc),
        )

    if not env_path.exists() or not raw_root:
        return BootstrapStatus(
            skill_root=skill_root,
            env_path=env_path,
            env_exists=env_path.exists(),
            configured=False,
            initialized=False,
            wiki_root=None,
            index_db=None,
            layout_language=raw_language or None,
            layout_paths=required_relative_paths(initial_language),
            missing_paths=required_relative_paths(initial_language),
        )

    wiki_root = normalize_wiki_root(skill_root, raw_root)
    index_db = normalize_wiki_root(skill_root, raw_index) if raw_index else derive_index_db_path(wiki_root)
    try:
        layout = resolve_layout(wiki_root, raw_language)
    except WikiLayoutError as exc:
        return BootstrapStatus(
            skill_root=skill_root,
            env_path=env_path,
            env_exists=True,
            configured=True,
            initialized=False,
            wiki_root=wiki_root,
            index_db=index_db,
            layout_language=raw_language or None,
            layout_paths=[],
            missing_paths=[],
            error=str(exc),
        )
    missing_paths = initialized_relative_gaps(wiki_root, layout.language)
    return BootstrapStatus(
        skill_root=skill_root,
        env_path=env_path,
        env_exists=env_path.exists(),
        configured=True,
        initialized=not missing_paths,
        wiki_root=wiki_root,
        index_db=index_db,
        layout_language=layout.language,
        layout_paths=layout.required_paths,
        missing_paths=missing_paths,
    )


def persist_wiki_location(
    skill_root: Path, wiki_root_input: Union[str, Path], language: str = "en"
) -> Tuple[Path, Path, Path]:
    wiki_root = normalize_wiki_root(skill_root, wiki_root_input)
    layout = resolve_layout(wiki_root, language)
    index_db = derive_index_db_path(wiki_root)
    env_path = write_env_values(
        skill_root,
        {
            "WIKI_ROOT": str(wiki_root),
            "WIKI_INDEX_DB": str(index_db),
            "WIKI_LAYOUT_LANGUAGE": layout.language,
        },
    )
    return env_path, wiki_root, index_db


def initialize_wiki_location(
    skill_root: Path, wiki_root_input: Union[str, Path], language: str = "en"
) -> Tuple[Settings, list[Path], Path]:
    env_path, wiki_root, index_db = persist_wiki_location(skill_root, wiki_root_input, language)
    settings = load_settings()
    settings.wiki_root = wiki_root
    settings.index_db = index_db
    settings.layout_language = resolve_layout(wiki_root, language).language
    created = init_vault(settings)
    return settings, created, env_path
