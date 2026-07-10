from datetime import datetime
from pathlib import Path

from typer.testing import CliRunner

import cli as cli_module
from llm_wiki_generator.config import Settings
from llm_wiki_generator.prd_workflow import (
    default_change_name,
    generate_openspec_change,
    prd_chat_turn,
    read_all_wiki_knowledge,
)
from llm_wiki_generator.utils import load_frontmatter


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
        default_scope="stable-draft",
    )


def write_wiki_page(
    settings: Settings,
    relative: str,
    *,
    title: str,
    page_type: str,
    status: str,
    source_type: str,
    tags: list[str],
    body: str,
) -> Path:
    path = settings.wiki_root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered_tags = "\n".join(f"- {tag}" for tag in tags)
    path.write_text(
        "\n".join(
            [
                "---",
                f"title: {title}",
                f"page_type: {page_type}",
                f"status: {status}",
                f"source_type: {source_type}",
                "tags:",
                rendered_tags,
                "confidence: high",
                "---",
                "",
                f"# {title}",
                "",
                body,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def complete_answer() -> str:
    return "\n".join(
        [
            "业务问题与目标: 识别商家刷单团伙，降低虚假交易对搜索排序和用户决策的影响。",
            "目标用户: 风控运营、商家治理专员和风控策略负责人。",
            "干系人与决策权: 风控负责人决策，治理运营验收，数据平台和物流平台协作交付。",
            "成功指标: 中大型刷单团伙识别召回率达到90%以上，误杀申诉推翻率低于1%。",
            "MVP 范围: 支持交易图谱团伙识别、物流异常检测、设备网络聚集告警和处罚配置。",
            "非目标: 本期不建设商家申诉工作台和跨境物流风控。",
            "用户流程与异常路径: 运营查看异常特征、确认风险、下发处罚；异常路径为证据不足时进入复核。",
            "业务规则与权限: 高风险处罚需主管审批，处罚包括降权、屏蔽评价、冻结货款和清退店铺。",
            "数据与集成: 读取交易图谱、物流轨迹、评价对象、设备指纹和支付网络数据。",
            "非功能要求: T+1离线团伙识别，实时物流异常阻断，保留审计日志并保护隐私数据。",
            "风险与依赖: 依赖物流公司API、设备指纹SDK和图计算平台，风险是误杀正常商家。",
            "验收标准: 成功条件为命中闭环资金和空包异常；失败条件为证据不足时不能自动处罚。",
            "上线与反馈: 先灰度高风险类目，监控召回率、申诉推翻率和处罚转化，支持回滚策略。",
        ]
    )


def test_prd_chat_reads_all_wiki_and_asks_one_question(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    write_wiki_page(
        settings,
        "20-wiki/concepts/设备指纹技术.md",
        title="设备指纹技术",
        page_type="concept",
        status="stable",
        source_type="business_fact",
        tags=["设备指纹", "风控", "刷单"],
        body="设备指纹用于识别同源设备和黑灰产聚集风险。",
    )
    write_wiki_page(
        settings,
        "20-wiki/prd-patterns/风控PRD模式.md",
        title="风控PRD模式",
        page_type="prd_pattern",
        status="stable",
        source_type="industry_practice",
        tags=["风控", "PRD", "验收"],
        body="风控 PRD 应覆盖指标、误杀、申诉、灰度和回滚。",
    )

    items = read_all_wiki_knowledge(settings)
    turn = prd_chat_turn(settings, "商家刷单识别系统")

    assert len(items) == 2
    assert turn["quality"]["score"] < 100
    assert turn["next_question"]["key"] == "goal"
    assert len(turn["context"]["evidence_pack"]) == 1
    assert len(turn["context"]["template_guidance"]) == 1


def test_stable_prd_pattern_boosts_next_question_priority(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    write_wiki_page(
        settings,
        "20-wiki/prd-patterns/风控类-PRD-Pattern.md",
        title="风控类 PRD Pattern",
        page_type="prd_pattern",
        status="stable",
        source_type="generated_prd_pattern",
        tags=["PRD", "风控", "灰度", "回滚"],
        body="风控 PRD 应优先确认灰度、监控、回滚和反馈闭环。",
    )

    turn = prd_chat_turn(
        settings,
        "商家刷单识别系统",
        answer="业务问题与目标: 识别商家刷单团伙，降低虚假交易影响。",
    )

    assert turn["next_question"]["key"] == "rollout_plan"
    assert turn["context"]["template_guidance"][0]["guidance_weight"] == 1.0


def test_prd_generation_is_blocked_before_100_percent(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    write_wiki_page(
        settings,
        "20-wiki/concepts/设备指纹技术.md",
        title="设备指纹技术",
        page_type="concept",
        status="stable",
        source_type="business_fact",
        tags=["设备指纹", "风控", "刷单"],
        body="设备指纹用于识别同源设备和黑灰产聚集风险。",
    )
    project_root = tmp_path / "project"
    (project_root / "openspec").mkdir(parents=True)
    (project_root / "openspec/config.yaml").write_text("project: demo\n", encoding="utf-8")

    result = generate_openspec_change(
        settings,
        "商家刷单识别系统",
        project_root,
        "add-fraud-prd",
    )

    assert result["ready"] is False
    assert result["written"] == []
    assert not (project_root / "openspec/changes/add-fraud-prd").exists()


def test_prd_generation_writes_openspec_after_100_percent(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    write_wiki_page(
        settings,
        "20-wiki/concepts/设备指纹技术.md",
        title="设备指纹技术",
        page_type="concept",
        status="stable",
        source_type="business_fact",
        tags=["设备指纹", "风控", "刷单"],
        body="设备指纹用于识别同源设备和黑灰产聚集风险。",
    )
    write_wiki_page(
        settings,
        "20-wiki/prd-patterns/风控PRD模式.md",
        title="风控PRD模式",
        page_type="prd_pattern",
        status="stable",
        source_type="industry_practice",
        tags=["风控", "PRD", "验收"],
        body="风控 PRD 应覆盖指标、误杀、申诉、灰度和回滚。",
    )
    prd_chat_turn(settings, "商家刷单识别系统", answer=complete_answer())
    project_root = tmp_path / "project"
    (project_root / "openspec").mkdir(parents=True)
    (project_root / "openspec/config.yaml").write_text("project: demo\n", encoding="utf-8")

    result = generate_openspec_change(
        settings,
        "商家刷单识别系统",
        project_root,
        "add-fraud-prd",
        capability="fraud-detection",
    )

    assert result["ready"] is True
    assert len(result["written"]) == 5
    prd = project_root / "openspec/changes/add-fraud-prd/prd.md"
    spec = project_root / "openspec/changes/add-fraud-prd/specs/fraud-detection/spec.md"
    assert prd.exists()
    assert spec.exists()
    assert "设备指纹技术" in prd.read_text(encoding="utf-8")


def test_default_change_name_uses_chinese_topic_and_mm_dd() -> None:
    assert default_change_name("商家刷单识别系统", now=datetime(2026, 8, 9)) == "商家刷单识别系统-08-09"


def test_prd_generation_defaults_to_chinese_change_and_capability(tmp_path: Path) -> None:
    topic = "商家刷单识别系统"
    settings = make_settings(tmp_path)
    write_wiki_page(
        settings,
        "20-wiki/concepts/设备指纹技术.md",
        title="设备指纹技术",
        page_type="concept",
        status="stable",
        source_type="business_fact",
        tags=["设备指纹", "风控", "刷单"],
        body="设备指纹用于识别同源设备和黑灰产聚集风险。",
    )
    prd_chat_turn(settings, topic, answer=complete_answer())
    project_root = tmp_path / "project"
    (project_root / "openspec").mkdir(parents=True)
    (project_root / "openspec/config.yaml").write_text("project: demo\n", encoding="utf-8")

    result = generate_openspec_change(
        settings,
        topic,
        project_root,
    )

    expected_change_name = default_change_name(topic)
    assert result["ready"] is True
    assert (project_root / f"openspec/changes/{expected_change_name}/prd.md").exists()
    assert (
        project_root / f"openspec/changes/{expected_change_name}/specs/商家刷单识别系统/spec.md"
    ).exists()
    pattern_path = settings.wiki_root / "20-wiki/prd-patterns/风控类-PRD-Pattern.md"
    frontmatter, body = load_frontmatter(pattern_path.read_text(encoding="utf-8"))
    assert frontmatter["page_type"] == "prd_pattern"
    assert frontmatter["source_type"] == "generated_prd_pattern"
    assert frontmatter["status"] == "draft"
    assert "90%" not in "\n".join(frontmatter.get("reusable_questions", []))
    assert "误杀成本" in body


def test_pattern_learning_auto_stable_with_multiple_sources(tmp_path: Path) -> None:
    topic = "商家刷单识别系统"
    settings = make_settings(tmp_path)
    write_wiki_page(
        settings,
        "20-wiki/concepts/设备指纹技术.md",
        title="设备指纹技术",
        page_type="concept",
        status="stable",
        source_type="business_fact",
        tags=["设备指纹", "风控", "刷单"],
        body="设备指纹用于识别同源设备和黑灰产聚集风险。",
    )
    write_wiki_page(
        settings,
        "20-wiki/prd-patterns/风控类-PRD-Pattern.md",
        title="风控类 PRD Pattern",
        page_type="prd_pattern",
        status="stable",
        source_type="industry_practice",
        tags=["PRD", "风控"],
        body="风控 PRD 应覆盖误杀、复核、灰度、回滚和审计。",
    )
    prd_chat_turn(settings, topic, answer=complete_answer())
    project_root = tmp_path / "project"
    (project_root / "openspec").mkdir(parents=True)
    (project_root / "openspec/config.yaml").write_text("project: demo\n", encoding="utf-8")

    result = generate_openspec_change(settings, topic, project_root)

    pattern = result["pattern"]
    assert pattern["learned"] is True
    assert pattern["candidate"]["status"] == "stable"
    assert pattern["candidate"]["stability_score"] >= 0.85
    frontmatter, _ = load_frontmatter(Path(pattern["written"]).read_text(encoding="utf-8"))
    assert frontmatter["status"] == "stable"
    assert len(frontmatter["supporting_sources"]) >= 2


def test_uninitialized_openspec_does_not_write(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    write_wiki_page(
        settings,
        "20-wiki/concepts/设备指纹技术.md",
        title="设备指纹技术",
        page_type="concept",
        status="stable",
        source_type="business_fact",
        tags=["设备指纹", "风控", "刷单"],
        body="设备指纹用于识别同源设备和黑灰产聚集风险。",
    )
    prd_chat_turn(settings, "商家刷单识别系统", answer=complete_answer())
    project_root = tmp_path / "project"

    result = generate_openspec_change(
        settings,
        "商家刷单识别系统",
        project_root,
        "add-fraud-prd",
    )

    assert result["ready"] is True
    assert result["written"] == []
    assert "openspec init" in result["message"]
    assert str(project_root) in result["message"]


def test_propose_prd_cli_defaults_project_root_to_wiki_root(monkeypatch, tmp_path: Path) -> None:
    topic = "商家刷单识别系统"
    settings = make_settings(tmp_path)
    write_wiki_page(
        settings,
        "20-wiki/concepts/设备指纹技术.md",
        title="设备指纹技术",
        page_type="concept",
        status="stable",
        source_type="business_fact",
        tags=["设备指纹", "风控", "刷单"],
        body="设备指纹用于识别同源设备和黑灰产聚集风险。",
    )
    prd_chat_turn(settings, topic, answer=complete_answer())
    (settings.wiki_root / "openspec").mkdir(parents=True)
    (settings.wiki_root / "openspec/config.yaml").write_text("project: wiki\n", encoding="utf-8")
    monkeypatch.setattr(cli_module, "load_settings", lambda: settings)

    result = CliRunner().invoke(cli_module.app, ["propose-prd", topic, "--as-json"])

    expected_change_name = default_change_name(topic)
    assert result.exit_code == 0, result.output
    assert (settings.wiki_root / f"openspec/changes/{expected_change_name}/prd.md").exists()
    assert (
        settings.wiki_root / f"openspec/changes/{expected_change_name}/specs/商家刷单识别系统/spec.md"
    ).exists()


def test_learn_prd_pattern_cli_relearns_from_existing_prd(monkeypatch, tmp_path: Path) -> None:
    topic = "商家刷单识别系统"
    settings = make_settings(tmp_path)
    write_wiki_page(
        settings,
        "20-wiki/concepts/设备指纹技术.md",
        title="设备指纹技术",
        page_type="concept",
        status="stable",
        source_type="business_fact",
        tags=["设备指纹", "风控", "刷单"],
        body="设备指纹用于识别同源设备和黑灰产聚集风险。",
    )
    prd_chat_turn(settings, topic, answer=complete_answer())
    (settings.wiki_root / "openspec").mkdir(parents=True)
    (settings.wiki_root / "openspec/config.yaml").write_text("project: wiki\n", encoding="utf-8")
    monkeypatch.setattr(cli_module, "load_settings", lambda: settings)
    generated = CliRunner().invoke(cli_module.app, ["propose-prd", topic, "--no-learn-pattern", "--as-json"])
    assert generated.exit_code == 0, generated.output

    result = CliRunner().invoke(cli_module.app, ["learn-prd-pattern", topic, "--as-json"])

    assert result.exit_code == 0, result.output
    assert (settings.wiki_root / "20-wiki/prd-patterns/风控类-PRD-Pattern.md").exists()
