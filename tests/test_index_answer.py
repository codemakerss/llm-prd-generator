from pathlib import Path

from llm_wiki_generator.answer import answer_question
from llm_wiki_generator.archive import apply_preview, archive_source
from llm_wiki_generator.config import Settings
from llm_wiki_generator.indexer import build_index, search_index
from llm_wiki_generator.models import Scope, SourceType


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


def test_index_and_answer_flow(tmp_path: Path) -> None:
    source = tmp_path / "industry.txt"
    source.write_text("PRD 模板\n目标用户\n指标设计\n风险控制\n", encoding="utf-8")
    settings = make_settings(tmp_path)

    preview = archive_source(source, SourceType.INDUSTRY_PRACTICE, settings)
    apply_preview(preview, source, settings)
    count = build_index(settings)
    results = search_index(settings, "指标", Scope.STABLE, limit=3)
    answer = answer_question(settings, "有哪些指标相关知识？", Scope.STABLE, limit=3)

    assert count >= 1
    assert results
    assert "指标" in answer
