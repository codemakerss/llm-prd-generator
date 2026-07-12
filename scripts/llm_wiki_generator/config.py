from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ENV_FILENAME = ".env"


@dataclass
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
    layout_language: str = "en"


def env_file_path(skill_root: Path) -> Path:
    return skill_root / ENV_FILENAME


def load_env_file_map(skill_root: Path) -> dict[str, str]:
    env_path = env_file_path(skill_root)
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def write_env_values(skill_root: Path, updates: dict[str, str]) -> Path:
    env_path = env_file_path(skill_root)
    existing_lines: list[str] = []
    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()

    pending = dict(updates)
    rendered: list[str] = []
    for line in existing_lines:
        if "=" not in line or line.lstrip().startswith("#"):
            rendered.append(line)
            continue
        key, _ = line.split("=", 1)
        stripped_key = key.strip()
        if stripped_key in pending:
            rendered.append(f"{stripped_key}={pending.pop(stripped_key)}")
        else:
            rendered.append(line)

    for key, value in pending.items():
        rendered.append(f"{key}={value}")

    payload = "\n".join(rendered).rstrip() + "\n"
    env_path.write_text(payload, encoding="utf-8")
    return env_path


def load_settings() -> Settings:
    skill_root = Path(__file__).resolve().parents[2]
    dotenv_path = env_file_path(skill_root)
    if dotenv_path.exists():
        load_dotenv(dotenv_path, override=True)
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
        layout_language=os.getenv("WIKI_LAYOUT_LANGUAGE", "").strip().lower(),
    )
