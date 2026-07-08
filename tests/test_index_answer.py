import json
from pathlib import Path

from typer.testing import CliRunner

import cli as cli_module
from llm_wiki_generator import archive as archive_module
from llm_wiki_generator.answer import answer_question
from llm_wiki_generator.archive import apply_preview, archive_source
from llm_wiki_generator.config import Settings
from llm_wiki_generator.indexer import build_index, search_index
from llm_wiki_generator.models import Scope, SourceType


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


class FakeIndustryLLM:
    available = True

    def __init__(self, settings: Settings):
        self.settings = settings

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        return {
            "title": "Industry PRD Practice",
            "source_type": "industry_practice",
            "source_path": "industry.txt",
            "summary": "Industry PRD template and metric practice.",
            "updates": [
                {
                    "action": "create_or_update",
                    "page_type": "prd_pattern",
                    "title": "Metric Review Pattern",
                    "status": "stable",
                    "summary": "PRD templates should include metric and risk review.",
                    "body": "PRD 模板\n目标用户\n指标设计\n风险控制",
                    "tags": ["industry_practice", "prd", "metric"],
                    "links": [],
                    "confidence": "high",
                    "evidence": [{"snippet": "指标设计", "reason": "Metric design guidance"}],
                    "reason": "Capture reusable industry PRD practice.",
                }
            ],
        }


def test_index_and_answer_flow(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "industry.txt"
    source.write_text("PRD 模板\n目标用户\n指标设计\n风险控制\n", encoding="utf-8")
    settings = make_settings(tmp_path)
    monkeypatch.setattr(archive_module, "OpenAICompatibleLLM", FakeIndustryLLM)

    preview = archive_source(source, SourceType.INDUSTRY_PRACTICE, settings)
    apply_preview(preview, source, settings)
    count = build_index(settings)
    results = search_index(settings, "指标", Scope.STABLE, limit=3)
    answer_settings = make_settings(tmp_path, with_llm=False)
    answer = answer_question(answer_settings, "有哪些指标相关知识？", Scope.STABLE, limit=3)

    assert count >= 1
    assert results
    assert "指标" in answer
    assert "无模型模式" in answer


def test_search_command_emits_json_without_llm(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "industry.txt"
    source.write_text("PRD 模板\n目标用户\n指标设计\n风险控制\n", encoding="utf-8")
    settings = make_settings(tmp_path)
    monkeypatch.setattr(archive_module, "OpenAICompatibleLLM", FakeIndustryLLM)

    preview = archive_source(source, SourceType.INDUSTRY_PRACTICE, settings)
    apply_preview(preview, source, settings)
    build_index(settings)
    search_settings = make_settings(tmp_path, with_llm=False)
    runner = CliRunner()
    monkeypatch.setattr(cli_module, "load_settings", lambda: search_settings)

    result = runner.invoke(cli_module.app, ["search", "指标", "--scope", "stable", "--as-json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload
    assert payload[0]["title"] == "Metric Review Pattern"
