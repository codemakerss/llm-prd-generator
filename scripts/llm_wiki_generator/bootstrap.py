from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Union

from .config import Settings, env_file_path, load_env_file_map, load_settings, write_env_values
from .vault import RAW_DIRS, WIKI_DIRS, init_vault


REQUIRED_FILES = ("20-wiki/index.md", "20-wiki/log.md")


@dataclass
class BootstrapStatus:
    skill_root: Path
    env_path: Path
    env_exists: bool
    configured: bool
    initialized: bool
    wiki_root: Optional[Path]
    index_db: Optional[Path]
    missing_paths: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "skill_root": str(self.skill_root),
            "env_path": str(self.env_path),
            "env_exists": self.env_exists,
            "configured": self.configured,
            "initialized": self.initialized,
            "wiki_root": str(self.wiki_root) if self.wiki_root else None,
            "index_db": str(self.index_db) if self.index_db else None,
            "missing_paths": self.missing_paths,
        }


def required_relative_paths() -> list[str]:
    return [*RAW_DIRS.values(), *WIKI_DIRS.values(), *REQUIRED_FILES]


def derive_index_db_path(wiki_root: Path) -> Path:
    return wiki_root / "index.sqlite3"


def normalize_wiki_root(skill_root: Path, raw_path: Union[str, Path]) -> Path:
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = (skill_root / candidate).resolve()
    return candidate


def initialized_relative_gaps(wiki_root: Path) -> list[str]:
    missing: list[str] = []
    for relative in required_relative_paths():
        if not (wiki_root / relative).exists():
            missing.append(relative)
    return missing


def inspect_bootstrap(skill_root: Path) -> BootstrapStatus:
    env_path = env_file_path(skill_root)
    env_values = load_env_file_map(skill_root)
    raw_root = env_values.get("WIKI_ROOT", "").strip()
    raw_index = env_values.get("WIKI_INDEX_DB", "").strip()

    if not env_path.exists() or not raw_root:
        return BootstrapStatus(
            skill_root=skill_root,
            env_path=env_path,
            env_exists=env_path.exists(),
            configured=False,
            initialized=False,
            wiki_root=None,
            index_db=None,
            missing_paths=required_relative_paths(),
        )

    wiki_root = normalize_wiki_root(skill_root, raw_root)
    index_db = normalize_wiki_root(skill_root, raw_index) if raw_index else derive_index_db_path(wiki_root)
    missing_paths = initialized_relative_gaps(wiki_root)
    return BootstrapStatus(
        skill_root=skill_root,
        env_path=env_path,
        env_exists=env_path.exists(),
        configured=True,
        initialized=not missing_paths,
        wiki_root=wiki_root,
        index_db=index_db,
        missing_paths=missing_paths,
    )


def persist_wiki_location(skill_root: Path, wiki_root_input: Union[str, Path]) -> Tuple[Path, Path, Path]:
    wiki_root = normalize_wiki_root(skill_root, wiki_root_input)
    index_db = derive_index_db_path(wiki_root)
    env_path = write_env_values(
        skill_root,
        {
            "WIKI_ROOT": str(wiki_root),
            "WIKI_INDEX_DB": str(index_db),
        },
    )
    return env_path, wiki_root, index_db


def initialize_wiki_location(skill_root: Path, wiki_root_input: Union[str, Path]) -> Tuple[Settings, list[Path], Path]:
    env_path, wiki_root, index_db = persist_wiki_location(skill_root, wiki_root_input)
    settings = load_settings()
    settings.wiki_root = wiki_root
    settings.index_db = index_db
    created = init_vault(settings)
    return settings, created, env_path
