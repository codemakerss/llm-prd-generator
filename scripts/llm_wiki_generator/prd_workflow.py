from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import Settings
from .prd_quality import PRD_DIMENSIONS, PrdQualityGate
from .utils import ensure_parent, load_frontmatter, slugify, write_json


FIELD_ALIASES = {
    "goal": ["业务问题与目标", "业务问题", "目标", "goal"],
    "target_users": ["目标用户", "用户", "target_users"],
    "stakeholders": ["干系人与决策权", "干系人", "决策权", "stakeholders"],
    "success_metric": ["成功指标", "指标", "success_metric"],
    "scope": ["MVP 范围", "范围", "scope"],
    "non_goals": ["非目标", "不做", "non_goals"],
    "user_workflows": ["用户流程与异常路径", "用户流程", "异常路径", "流程", "user_workflows"],
    "business_rules": ["业务规则与权限", "业务规则", "权限", "规则", "business_rules"],
    "data_integrations": ["数据与集成", "数据", "集成", "接口", "data_integrations"],
    "non_functional_requirements": ["非功能要求", "性能", "安全", "审计", "non_functional_requirements"],
    "risks_dependencies": ["风险与依赖", "风险", "依赖", "risks_dependencies"],
    "acceptance_criteria": ["验收标准", "验收", "acceptance_criteria"],
    "rollout_plan": ["上线与反馈", "上线", "灰度", "监控", "回滚", "rollout_plan"],
    "evidence": ["业务证据", "证据", "evidence"],
    "conflict_resolution": ["冲突决策", "冲突解决", "conflict_resolution"],
}


@dataclass(slots=True)
class WikiKnowledgeItem:
    title: str
    path: str
    page_type: str
    status: str
    source_type: str
    tags: list[str]
    links: list[str]
    confidence: str
    body: str
    excerpt: str
    score: float = 0.0

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("body", None)
        return payload


@dataclass(slots=True)
class PrdSession:
    topic: str
    extracted: dict[str, Any] = field(default_factory=dict)
    answers: list[str] = field(default_factory=list)
    last_question_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "extracted": self.extracted,
            "answers": self.answers,
            "last_question_key": self.last_question_key,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PrdSession":
        return cls(
            topic=str(payload.get("topic", "")),
            extracted=dict(payload.get("extracted", {})),
            answers=list(payload.get("answers", [])),
            last_question_key=str(payload.get("last_question_key", "")),
        )


def session_path(settings: Settings, topic: str) -> Path:
    return settings.skill_root / "runtime" / "prd_sessions" / f"{slugify(topic)}.json"


def load_session(settings: Settings, topic: str) -> PrdSession:
    path = session_path(settings, topic)
    if not path.exists():
        return PrdSession(topic=topic)
    return PrdSession.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_session(settings: Settings, session: PrdSession) -> Path:
    path = session_path(settings, session.topic)
    write_json(path, session.to_dict())
    return path


def markdown_wiki_files(settings: Settings) -> list[Path]:
    wiki_root = settings.wiki_root / "20-wiki"
    if not wiki_root.exists():
        return []
    return sorted(path for path in wiki_root.rglob("*.md") if path.name not in {"index.md", "log.md"})


def read_all_wiki_knowledge(settings: Settings) -> list[WikiKnowledgeItem]:
    items: list[WikiKnowledgeItem] = []
    for path in markdown_wiki_files(settings):
        text = path.read_text(encoding="utf-8")
        frontmatter, body = load_frontmatter(text)
        title = str(frontmatter.get("title") or path.stem)
        tags = frontmatter.get("tags") or []
        links = frontmatter.get("links") or []
        if isinstance(tags, str):
            tags = [tags]
        if isinstance(links, str):
            links = [links]
        items.append(
            WikiKnowledgeItem(
                title=title,
                path=str(path.relative_to(settings.wiki_root)),
                page_type=str(frontmatter.get("page_type", "unknown")),
                status=str(frontmatter.get("status", "draft")),
                source_type=str(frontmatter.get("source_type", "unknown")),
                tags=[str(tag) for tag in tags],
                links=[str(link) for link in links],
                confidence=str(frontmatter.get("confidence", "medium")),
                body=body,
                excerpt=body.strip()[:500],
            )
        )
    return items


def tokenize(value: str) -> list[str]:
    tokens: list[str] = []
    for chunk in re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+", value.lower()):
        if re.fullmatch(r"[\u4e00-\u9fff]+", chunk) and len(chunk) > 2:
            tokens.extend(chunk[index : index + 2] for index in range(len(chunk) - 1))
        else:
            tokens.append(chunk)
    return [token for token in dict.fromkeys(tokens) if token.strip()]


def score_item(item: WikiKnowledgeItem, query: str, extracted: dict[str, Any]) -> float:
    query_text = " ".join([query, *(str(value) for value in extracted.values())])
    tokens = tokenize(query_text)
    haystack = f"{item.title} {' '.join(item.tags)} {item.body}".lower()
    score = 0.0
    for token in tokens:
        if not token:
            continue
        if token in item.title.lower():
            score += 4
        if token in [tag.lower() for tag in item.tags]:
            score += 5
        score += min(haystack.count(token), 6) * 0.5

    if item.status == "stable":
        score += 2
    if item.page_type == "prd_pattern":
        score += 3
    if item.page_type == "conflict":
        score += 8
    if item.source_type == "business_fact":
        score += 2
    if item.source_type == "team_history":
        score += 1
    return score


def build_context(topic: str, extracted: dict[str, Any], items: list[WikiKnowledgeItem], limit: int = 5) -> dict[str, Any]:
    scored = []
    for item in items:
        item.score = score_item(item, topic, extracted)
        if item.score > 0:
            scored.append(item)
    ranked = sorted(scored, key=lambda item: item.score, reverse=True)

    evidence = [
        item
        for item in ranked
        if item.source_type == "business_fact" and item.page_type != "prd_pattern"
    ][:limit]
    templates = [
        item
        for item in ranked
        if item.source_type == "industry_practice" or item.page_type == "prd_pattern"
    ][:limit]
    team = [
        item
        for item in ranked
        if item.source_type in {"team_history", "feedback"} and item.page_type != "prd_pattern"
    ][:limit]
    conflicts = [item.title for item in ranked if item.page_type == "conflict" or item.status == "conflict"]
    return {
        "evidence_pack": [item.to_payload() for item in evidence],
        "template_guidance": [item.to_payload() for item in templates],
        "team_style_pack": [item.to_payload() for item in team],
        "conflicts": conflicts,
        "all_ranked": [item.to_payload() for item in ranked[: limit * 3]],
    }


def extract_fields(text: str, expected_key: str = "") -> dict[str, Any]:
    extracted: dict[str, Any] = {}
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        match = re.match(r"^([^:：]{1,30})[:：]\s*(.+)$", line)
        if not match:
            continue
        label, value = match.group(1).strip(), match.group(2).strip()
        for key, aliases in FIELD_ALIASES.items():
            if label in aliases:
                extracted[key] = value
                break

    if expected_key and expected_key not in extracted and text.strip():
        extracted[expected_key] = text.strip()
    return extracted


def update_session_from_answer(session: PrdSession, answer: str) -> None:
    if not answer.strip():
        return
    session.answers.append(answer)
    session.extracted.update(extract_fields(answer, session.last_question_key))


def prd_chat_turn(
    settings: Settings,
    topic: str,
    answer: str = "",
    limit: int = 5,
) -> dict[str, Any]:
    session = load_session(settings, topic)
    update_session_from_answer(session, answer)
    items = read_all_wiki_knowledge(settings)
    context = build_context(topic, session.extracted, items, limit=limit)
    gate = PrdQualityGate()
    quality = gate.evaluate(session.extracted, context, context["conflicts"])
    next_question = gate.next_question(quality, session.extracted)
    session.last_question_key = next_question["key"] if next_question else ""
    save_session(settings, session)
    return {
        "topic": topic,
        "session_path": str(session_path(settings, topic)),
        "extracted": session.extracted,
        "context": {
            "evidence_pack": context["evidence_pack"],
            "template_guidance": context["template_guidance"],
            "team_style_pack": context["team_style_pack"],
            "conflicts": context["conflicts"],
        },
        "quality": quality,
        "next_question": next_question,
        "ready": quality["ready"] and quality["score"] == 100,
    }


def evidence_lines(context: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for pack_name in ("evidence_pack", "template_guidance", "team_style_pack"):
        for item in context.get(pack_name, []):
            lines.append(
                f"- {item['title']} [{item['status']}/{item['page_type']}/{item['source_type']}] `{item['path']}`"
            )
    return lines or ["- 暂无可引用证据。"]


def render_prd(topic: str, extracted: dict[str, Any], context: dict[str, Any]) -> str:
    field_label = {dimension.key: dimension.label for dimension in PRD_DIMENSIONS}
    sections = [f"# {topic} PRD", "", "## 需求追溯", *evidence_lines(context), ""]
    for dimension in PRD_DIMENSIONS:
        sections.extend([f"## {field_label[dimension.key]}", str(extracted.get(dimension.key, "")).strip(), ""])
    return "\n".join(sections).rstrip() + "\n"


def render_proposal(topic: str, extracted: dict[str, Any], context: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {topic}",
            "",
            "## Why",
            str(extracted.get("goal", "")).strip(),
            "",
            "## What Changes",
            str(extracted.get("scope", "")).strip(),
            "",
            "## Evidence",
            *evidence_lines(context),
            "",
        ]
    )


def render_design(topic: str, extracted: dict[str, Any], context: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {topic} Design",
            "",
            "## Data and Integrations",
            str(extracted.get("data_integrations", "")).strip(),
            "",
            "## Business Rules and Permissions",
            str(extracted.get("business_rules", "")).strip(),
            "",
            "## Non-functional Requirements",
            str(extracted.get("non_functional_requirements", "")).strip(),
            "",
            "## Risks and Dependencies",
            str(extracted.get("risks_dependencies", "")).strip(),
            "",
            "## Evidence",
            *evidence_lines(context),
            "",
        ]
    )


def render_tasks(extracted: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Tasks",
            "",
            "- [ ] Confirm final PRD with business owner",
            "- [ ] Implement MVP scope",
            "- [ ] Add success metric instrumentation",
            "- [ ] Validate success and failure acceptance scenarios",
            "- [ ] Prepare rollout, monitoring, rollback, and feedback loop",
            "",
            "## Acceptance",
            str(extracted.get("acceptance_criteria", "")).strip(),
            "",
        ]
    )


def render_spec(topic: str, capability: str, extracted: dict[str, Any], context: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {capability} Spec",
            "",
            f"## ADDED Requirements",
            "",
            f"### Requirement: {topic}",
            f"The system SHALL support the confirmed MVP scope: {str(extracted.get('scope', '')).strip()}",
            "",
            "#### Scenario: Successful business acceptance",
            f"- GIVEN {str(extracted.get('target_users', '')).strip()} need to complete the core workflow",
            f"- WHEN they use the delivered capability",
            f"- THEN {str(extracted.get('acceptance_criteria', '')).strip()}",
            "",
            "#### Scenario: Business rule enforcement",
            f"- GIVEN the configured rules and permissions",
            f"- WHEN a user or system action violates them",
            f"- THEN the system MUST enforce: {str(extracted.get('business_rules', '')).strip()}",
            "",
            "## Evidence",
            *evidence_lines(context),
            "",
        ]
    )


def ensure_openspec_initialized(project_root: Path) -> tuple[bool, str]:
    openspec_root = project_root / "openspec"
    if not (openspec_root / "config.yaml").exists():
        return False, "OpenSpec 未初始化。请先运行：openspec init --tools codex --profile core"
    return True, ""


def default_change_name(topic: str, now: datetime | None = None) -> str:
    resolved_now = now or datetime.now()
    return f"{topic}-{resolved_now:%m-%d}"


def generate_openspec_change(
    settings: Settings,
    topic: str,
    project_root: Path,
    change_name: str | None = None,
    capability: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    turn = prd_chat_turn(settings, topic, limit=limit)
    if not turn["ready"]:
        return {
            "written": [],
            "ready": False,
            "quality": turn["quality"],
            "next_question": turn["next_question"],
            "message": "PRD 完整度未达到 100%，不会生成 OpenSpec artifacts。",
        }

    initialized, message = ensure_openspec_initialized(project_root)
    if not initialized:
        return {
            "written": [],
            "ready": True,
            "quality": turn["quality"],
            "next_question": None,
            "message": message,
        }

    capability_name = slugify(capability or topic)
    resolved_change_name = change_name or default_change_name(topic)
    change_root = project_root / "openspec" / "changes" / slugify(resolved_change_name)
    spec_dir = change_root / "specs" / capability_name
    files = {
        change_root / "proposal.md": render_proposal(topic, turn["extracted"], turn["context"]),
        change_root / "design.md": render_design(topic, turn["extracted"], turn["context"]),
        change_root / "tasks.md": render_tasks(turn["extracted"]),
        change_root / "prd.md": render_prd(topic, turn["extracted"], turn["context"]),
        spec_dir / "spec.md": render_spec(topic, capability_name, turn["extracted"], turn["context"]),
    }
    written: list[str] = []
    for path, content in files.items():
        ensure_parent(path)
        path.write_text(content, encoding="utf-8")
        written.append(str(path))
    return {
        "written": written,
        "ready": True,
        "quality": turn["quality"],
        "next_question": None,
        "message": "OpenSpec artifacts generated.",
    }
