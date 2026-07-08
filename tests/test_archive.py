import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import cli as cli_module
from llm_wiki_generator import archive as archive_module
from llm_wiki_generator.archive import ArchiveLLMRequiredError, apply_preview, archive_source
from llm_wiki_generator.config import Settings
from llm_wiki_generator.indexer import search_index
from llm_wiki_generator.models import Scope
from llm_wiki_generator.models import SourceType


def make_settings(tmp_path: Path, *, with_llm: bool = True) -> Settings:
    return Settings(
        skill_root=tmp_path,
        wiki_root=tmp_path / "vault",
        index_db=tmp_path / "runtime" / "index.sqlite3",
        llm_provider="openai_compatible",
        llm_base_url="https://example.test/v1" if with_llm else "",
        llm_api_key="test-key" if with_llm else "",
        llm_model="test-model" if with_llm else "",
        llm_timeout=60,
        default_scope="stable",
    )


class FakeLLM:
    available = True

    def __init__(self, settings: Settings):
        self.settings = settings

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        return {
            "title": "Team PRD History",
            "source_type": "team_history",
            "source_path": "history.txt",
            "summary": "Historical PRD notes.",
            "updates": [
                {
                    "action": "create_or_update",
                    "page_type": "source",
                    "title": "Source - Team PRD History",
                    "status": "stable",
                    "summary": "Normalized source snapshot.",
                    "body": "历史 PRD\n用户背景\n技术方案",
                    "tags": ["team_history", "prd"],
                    "links": [],
                    "confidence": "high",
                    "evidence": [{"snippet": "历史 PRD", "reason": "Source heading"}],
                    "reason": "Keep the source visible.",
                },
                {
                    "action": "create_or_update",
                    "page_type": "prd_pattern",
                    "title": "PRD Review Pattern",
                    "status": "stable",
                    "summary": "Reusable PRD review structure from team history.",
                    "body": "## Pattern\n\n- Align background\n- Review metrics\n- Track risks",
                    "tags": ["team_history", "prd", "workflow"],
                    "links": [],
                    "confidence": "high",
                    "evidence": [{"snippet": "用户背景\n技术方案", "reason": "Repeated PRD structure"}],
                    "reason": "Capture a reusable PRD pattern from historical work.",
                },
            ],
        }


class FakeBusinessLLM(FakeLLM):
    def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        return {
            "title": "Business Metrics",
            "source_type": "business_fact",
            "source_path": "business.txt",
            "summary": "Confirmed business metrics.",
            "updates": [
                {
                    "action": "create_or_update",
                    "page_type": "concept",
                    "title": "User Growth Metric",
                    "status": "stable",
                    "summary": "User growth is a tracked metric.",
                    "body": "业务目标\n用户增长\n关键指标",
                    "tags": ["business_fact", "metric"],
                    "links": [],
                    "confidence": "high",
                    "evidence": [{"snippet": "用户增长", "reason": "Metric in source"}],
                    "reason": "Preserve confirmed business knowledge.",
                }
            ],
        }


class BrokenLLM(FakeLLM):
    def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        return {"title": "missing required fields"}


def test_archive_preview_requires_llm_configuration(tmp_path: Path) -> None:
    source = tmp_path / "history.txt"
    source.write_text("历史 PRD\n用户背景\n技术方案\n", encoding="utf-8")
    settings = make_settings(tmp_path, with_llm=False)

    with pytest.raises(ArchiveLLMRequiredError, match="LLM is required for archive preview"):
        archive_source(source, SourceType.TEAM_HISTORY, settings)


def test_team_history_prd_pattern_is_allowed_and_forced_to_draft(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / "history.txt"
    source.write_text("历史 PRD\n用户背景\n技术方案\n", encoding="utf-8")
    settings = make_settings(tmp_path)
    monkeypatch.setattr(archive_module, "OpenAICompatibleLLM", FakeLLM)

    preview = archive_source(source, SourceType.TEAM_HISTORY, settings)

    assert preview.updates
    assert any(update.page_type.value == "prd_pattern" for update in preview.updates)
    assert all(update.status.value == "draft" for update in preview.updates)


def test_llm_schema_failure_raises_instead_of_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / "history.txt"
    source.write_text("历史 PRD\n用户背景\n技术方案\n", encoding="utf-8")
    settings = make_settings(tmp_path)
    monkeypatch.setattr(archive_module, "OpenAICompatibleLLM", BrokenLLM)

    with pytest.raises(ArchiveLLMRequiredError, match="LLM archive preview failed"):
        archive_source(source, SourceType.TEAM_HISTORY, settings)


def test_apply_does_not_write_when_preview_fails(tmp_path: Path) -> None:
    source = tmp_path / "business.txt"
    source.write_text("业务目标\n用户增长\n关键指标\n", encoding="utf-8")
    settings = make_settings(tmp_path, with_llm=False)

    with pytest.raises(ArchiveLLMRequiredError):
        archive_source(source, SourceType.BUSINESS_FACT, settings)

    assert not (settings.wiki_root / "10-raw/business_fact/business.txt").exists()
    assert not (settings.wiki_root / "20-wiki/index.md").exists()


def test_apply_creates_raw_and_wiki_pages_after_llm_preview(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / "business.txt"
    source.write_text("业务目标\n用户增长\n关键指标\n", encoding="utf-8")
    settings = make_settings(tmp_path)
    monkeypatch.setattr(archive_module, "OpenAICompatibleLLM", FakeBusinessLLM)

    preview = archive_source(source, SourceType.BUSINESS_FACT, settings)
    written = apply_preview(preview, source, settings)

    assert written
    assert (settings.wiki_root / "10-raw/business_fact/business.txt").exists()
    assert (settings.wiki_root / "20-wiki/index.md").exists()
    assert (settings.wiki_root / "20-wiki/log.md").exists()
    assert any(path.exists() for path in written)


def test_archive_command_writes_and_reindexes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / "business.txt"
    source.write_text("业务目标\n用户增长\n关键指标\n", encoding="utf-8")
    settings = make_settings(tmp_path)
    runner = CliRunner()
    monkeypatch.setattr(cli_module, "load_settings", lambda: settings)
    monkeypatch.setattr(archive_module, "OpenAICompatibleLLM", FakeBusinessLLM)

    result = runner.invoke(cli_module.app, ["archive", str(source), "--source-type", "business_fact"])

    assert result.exit_code == 0, result.output
    assert (settings.wiki_root / "10-raw/business_fact/business.txt").exists()
    assert settings.index_db.exists()
    assert search_index(settings, "用户增长", Scope.STABLE, limit=3)


def test_apply_preview_command_writes_host_generated_preview_without_llm(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "history.txt"
    source.write_text("历史 PRD\n用户背景\n技术方案\n", encoding="utf-8")
    preview_file = tmp_path / "preview.json"
    preview_file.write_text(json.dumps(FakeLLM(make_settings(tmp_path)).complete_json("", "")), encoding="utf-8")
    settings = make_settings(tmp_path, with_llm=False)
    runner = CliRunner()
    monkeypatch.setattr(cli_module, "load_settings", lambda: settings)

    result = runner.invoke(
        cli_module.app,
        ["apply-preview", str(source), "--preview-file", str(preview_file), "--as-json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["indexed_count"] >= 1
    assert (settings.wiki_root / "10-raw/team_history/history.txt").exists()
    assert settings.index_db.exists()
    assert search_index(settings, "PRD", Scope.STABLE_DRAFT, limit=3)


def test_apply_preview_command_rejects_invalid_preview_before_writing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "history.txt"
    source.write_text("历史 PRD\n用户背景\n技术方案\n", encoding="utf-8")
    preview_file = tmp_path / "broken.json"
    preview_file.write_text('{"title": "missing fields"}', encoding="utf-8")
    settings = make_settings(tmp_path, with_llm=False)
    runner = CliRunner()
    monkeypatch.setattr(cli_module, "load_settings", lambda: settings)

    result = runner.invoke(cli_module.app, ["apply-preview", str(source), "--preview-file", str(preview_file)])

    assert result.exit_code == 1
    assert "Invalid ArchivePreview JSON" in result.output
    assert not (settings.wiki_root / "10-raw/team_history/history.txt").exists()
    assert not (settings.wiki_root / "20-wiki/index.md").exists()
