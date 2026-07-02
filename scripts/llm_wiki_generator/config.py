from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(slots=True)
class Settings:
    skill_root: Path
    wiki_root: Path
    index_db: Path
    llm_provider: str
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_timeout: int
    default_scope: str


def load_settings() -> Settings:
    skill_root = Path(__file__).resolve().parents[2]
    dotenv_path = skill_root / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path)
    else:
        load_dotenv()

    wiki_root = Path(os.getenv("WIKI_ROOT", str(skill_root / "runtime" / "vault"))).expanduser()
    index_db = Path(os.getenv("WIKI_INDEX_DB", str(skill_root / "runtime" / "index.sqlite3"))).expanduser()
    if not wiki_root.is_absolute():
        wiki_root = (skill_root / wiki_root).resolve()
    if not index_db.is_absolute():
        index_db = (skill_root / index_db).resolve()

    return Settings(
        skill_root=skill_root,
        wiki_root=wiki_root,
        index_db=index_db,
        llm_provider=os.getenv("LLM_PROVIDER", "openai_compatible"),
        llm_base_url=os.getenv("LLM_BASE_URL", "").strip(),
        llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
        llm_model=os.getenv("LLM_MODEL", "").strip(),
        llm_timeout=int(os.getenv("LLM_TIMEOUT", "60")),
        default_scope=os.getenv("WIKI_SCOPE", "stable").strip() or "stable",
    )
