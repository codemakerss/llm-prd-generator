from pathlib import Path

from llm_wiki_generator.archive import apply_preview, archive_source
from llm_wiki_generator.config import Settings
from llm_wiki_generator.models import SourceType


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        skill_root=tmp_path,
        wiki_root=tmp_path / "vault",
        index_db=tmp_path / "runtime" / "index.sqlite3",
        llm_provider="openai_compatible",
        llm_base_url="",
        llm_api_key="",
        llm_model="",
        llm_timeout=60,
        default_scope="stable",
    )


def test_team_history_defaults_to_draft(tmp_path: Path) -> None:
    source = tmp_path / "history.txt"
    source.write_text("历史 PRD\n用户背景\n技术方案\n", encoding="utf-8")
    settings = make_settings(tmp_path)

    preview = archive_source(source, SourceType.TEAM_HISTORY, settings)

    assert preview.updates
    assert all(update.status.value == "draft" for update in preview.updates)


def test_apply_creates_raw_and_wiki_pages(tmp_path: Path) -> None:
    source = tmp_path / "business.txt"
    source.write_text("业务目标\n用户增长\n关键指标\n", encoding="utf-8")
    settings = make_settings(tmp_path)

    preview = archive_source(source, SourceType.BUSINESS_FACT, settings)
    written = apply_preview(preview, source, settings)

    assert written
    assert (settings.wiki_root / "10-raw/business_fact/business.txt").exists()
    assert (settings.wiki_root / "20-wiki/index.md").exists()
    assert (settings.wiki_root / "20-wiki/log.md").exists()
    assert any(path.exists() for path in written)
