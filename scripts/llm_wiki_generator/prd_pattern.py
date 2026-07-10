from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .config import Settings
from .indexer import build_index
from .utils import dump_frontmatter, ensure_parent, load_frontmatter, slugify, utc_now


SPECIFIC_FACT_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?%|\d+\s*(?:天|小时|分钟|秒|kg|KG|元|万元|次|个)|T\+\d|20\d{2}[-/年]\d{1,2})"
)


@dataclass(slots=True)
class PatternCandidate:
    title: str
    domain: str
    tags: list[str]
    reusable_questions: list[str]
    section_template: list[str]
    acceptance_patterns: list[str]
    risk_checks: list[str]
    forbidden_facts: list[str]
    supporting_sources: list[str]
    stability_score: float
    status: str
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DOMAIN_RULES = [
    (
        "风控类",
        ["风控", "风险", "反欺诈", "刷单", "虚假交易", "审核", "处罚", "误杀", "申诉", "复核"],
        {
            "questions": [
                "风险对象是什么，风险行为如何被识别？",
                "误杀成本是什么，如何控制误杀？",
                "处罚动作有哪些，是否需要分级处罚？",
                "是否需要申诉、复核或人工兜底流程？",
                "成功指标和反向约束指标分别是什么？",
                "如何灰度、监控、回滚并收集反馈？",
            ],
            "sections": [
                "背景与风险问题",
                "风险对象与业务对象",
                "识别规则/模型/策略",
                "处罚与复核流程",
                "权限与审计",
                "指标与验收",
                "上线、监控与回滚",
            ],
            "acceptance": [
                "正向命中场景",
                "异常/边界场景",
                "误杀控制场景",
                "证据不足时的降级处理",
            ],
            "risks": [
                "误杀正常用户或商家",
                "上游数据延迟或缺失",
                "策略绕过与对抗升级",
                "处罚动作缺少审计证据",
            ],
        },
    ),
    (
        "内容审核类",
        ["内容", "审核", "举报", "违规", "安全", "申诉", "复核"],
        {
            "questions": [
                "审核对象和违规类型如何定义？",
                "机器审核、人审和复核如何分工？",
                "误杀与漏放分别如何度量？",
                "申诉入口和处理时效是什么？",
                "审核证据和操作日志如何留存？",
            ],
            "sections": ["审核对象", "审核流程", "规则与策略", "申诉复核", "指标验收", "审计与合规"],
            "acceptance": ["机器命中场景", "人工复核场景", "申诉成功/失败场景", "审计追溯场景"],
            "risks": ["误杀高价值内容", "漏放违规内容", "规则解释不一致", "审核积压"],
        },
    ),
]


GENERIC_PATTERN = {
    "questions": [
        "核心用户是谁，当前最痛的任务是什么？",
        "本次 MVP 必须交付哪些能力，明确不做什么？",
        "成功指标、失败条件和观察周期是什么？",
        "关键业务规则、权限和异常路径是什么？",
        "依赖哪些数据、系统或团队？",
        "如何上线、监控、回滚并收集反馈？",
    ],
    "sections": [
        "业务背景与目标",
        "用户与场景",
        "MVP 范围与非目标",
        "核心流程与异常路径",
        "业务规则与权限",
        "指标与验收",
        "上线与反馈",
    ],
    "acceptance": ["成功路径验收", "失败/异常路径验收", "权限/规则验收", "上线监控验收"],
    "risks": ["范围膨胀", "指标不可观测", "依赖延期", "验收口径不一致"],
}


def unique(values: list[str]) -> list[str]:
    return [value for value in dict.fromkeys(value.strip() for value in values if value and value.strip())]


def infer_domain(topic: str, prd_text: str, context: dict[str, Any]) -> tuple[str, dict[str, list[str]]]:
    haystack = " ".join(
        [
            topic,
            prd_text,
            *(
                " ".join(str(item.get("title", "")) + " " + " ".join(item.get("tags", [])) for item in context.get(pack, []))
                for pack in ("evidence_pack", "template_guidance", "team_style_pack")
            ),
        ]
    )
    best_domain = "通用产品类"
    best_payload = GENERIC_PATTERN
    best_score = 0
    for domain, keywords, payload in DOMAIN_RULES:
        score = sum(1 for keyword in keywords if keyword in haystack)
        if score > best_score:
            best_domain = domain
            best_payload = payload
            best_score = score
    return best_domain, best_payload


def supporting_sources_from_context(context: dict[str, Any]) -> list[str]:
    sources: list[str] = []
    for pack in ("evidence_pack", "template_guidance", "team_style_pack"):
        for item in context.get(pack, []):
            title = str(item.get("title", "")).strip()
            status = str(item.get("status", "")).strip()
            page_type = str(item.get("page_type", "")).strip()
            source_type = str(item.get("source_type", "")).strip()
            if title:
                sources.append(f"{title} [{status}/{page_type}/{source_type}]")
    return unique(sources)


def existing_pattern_sources(settings: Settings, domain: str) -> tuple[list[str], int]:
    pattern_root = settings.wiki_root / "20-wiki" / "prd-patterns"
    if not pattern_root.exists():
        return [], 0
    sources: list[str] = []
    stable_count = 0
    for path in sorted(pattern_root.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        frontmatter, body = load_frontmatter(text)
        title = str(frontmatter.get("title") or path.stem)
        tags = [str(tag) for tag in frontmatter.get("tags", [])]
        if domain in title or domain in body or domain in tags:
            sources.append(f"{title} [{frontmatter.get('status', 'draft')}/prd_pattern/{frontmatter.get('source_type', 'unknown')}]")
            if frontmatter.get("status") == "stable":
                stable_count += 1
    return unique(sources), stable_count


def extract_forbidden_facts(prd_text: str) -> list[str]:
    return unique(match.group(0) for match in SPECIFIC_FACT_PATTERN.finditer(prd_text))[:12]


def score_candidate(
    external_sources: list[str],
    existing_stable_patterns: int,
    conflicts: list[str],
) -> tuple[float, str, list[str]]:
    score = 0.45
    reasons = ["reusable_prd_structure_extracted"]
    if external_sources:
        score += min(len(external_sources), 4) * 0.1
        reasons.append("supporting_sources_found")
    if len(external_sources) >= 2:
        score += 0.15
        reasons.append("supported_by_multiple_sources")
    if existing_stable_patterns:
        score += 0.15
        reasons.append("existing_stable_pattern_support")
    if conflicts:
        score -= 0.4
        reasons.append("conflicts_found")
    else:
        reasons.append("no_conflicts_found")

    score = max(0.0, min(0.99, round(score, 2)))
    status = "stable" if score >= 0.85 and len(external_sources) >= 2 and not conflicts else "draft"
    if status == "draft":
        reasons.append("insufficient_stability_for_auto_stable")
    return score, status, reasons


def build_pattern_candidate(
    settings: Settings,
    topic: str,
    prd_text: str,
    context: dict[str, Any],
    learned_from_change: str,
) -> PatternCandidate | None:
    domain, payload = infer_domain(topic, prd_text, context)
    context_sources = supporting_sources_from_context(context)
    existing_sources, existing_stable_count = existing_pattern_sources(settings, domain)
    supporting_sources = unique([*context_sources, *existing_sources, learned_from_change])
    conflicts = [str(item) for item in context.get("conflicts", [])]
    score, status, reasons = score_candidate(
        external_sources=unique([*context_sources, *existing_sources]),
        existing_stable_patterns=existing_stable_count,
        conflicts=conflicts,
    )
    forbidden_facts = extract_forbidden_facts(prd_text)
    if forbidden_facts:
        reasons.append("project_specific_facts_filtered")

    candidate = PatternCandidate(
        title=f"{domain} PRD Pattern",
        domain=domain,
        tags=unique(["PRD", domain, *[tag for item in context.get("template_guidance", []) for tag in item.get("tags", [])]]),
        reusable_questions=payload["questions"],
        section_template=payload["sections"],
        acceptance_patterns=payload["acceptance"],
        risk_checks=payload["risks"],
        forbidden_facts=forbidden_facts,
        supporting_sources=supporting_sources,
        stability_score=score,
        status=status,
        reasons=unique(reasons),
    )
    if not candidate.reusable_questions or not candidate.section_template:
        return None
    return candidate


def render_pattern_page(candidate: PatternCandidate, learned_from_change: str) -> str:
    forbidden_lines = [f"- {item}" for item in candidate.forbidden_facts] if candidate.forbidden_facts else ["- 暂无"]
    frontmatter = {
        "title": candidate.title,
        "page_type": "prd_pattern",
        "status": candidate.status,
        "source_type": "generated_prd_pattern",
        "confidence": "high" if candidate.status == "stable" else "medium",
        "stability_score": candidate.stability_score,
        "supporting_sources": candidate.supporting_sources,
        "learned_from_change": learned_from_change,
        "tags": candidate.tags,
        "links": [],
        "updated_at": utc_now(),
    }
    sections = [
        f"# {candidate.title}",
        "",
        f"Domain: {candidate.domain}",
        f"Status: {candidate.status}",
        f"Stability score: {candidate.stability_score}",
        "",
        "## 必问问题",
        *[f"- {item}" for item in candidate.reusable_questions],
        "",
        "## 推荐 PRD 章节",
        *[f"- {item}" for item in candidate.section_template],
        "",
        "## 验收模式",
        *[f"- {item}" for item in candidate.acceptance_patterns],
        "",
        "## 风险检查",
        *[f"- {item}" for item in candidate.risk_checks],
        "",
        "## 禁止沉淀为 Pattern 的项目事实",
        *forbidden_lines,
        "",
        "## Supporting Sources",
        *[f"- {item}" for item in candidate.supporting_sources],
        "",
        "## Stability Reasons",
        *[f"- {item}" for item in candidate.reasons],
        "",
    ]
    return dump_frontmatter(frontmatter) + "\n" + "\n".join(sections)


def merge_or_write_pattern(settings: Settings, candidate: PatternCandidate, learned_from_change: str) -> Path:
    path = settings.wiki_root / "20-wiki" / "prd-patterns" / f"{slugify(candidate.title)}.md"
    ensure_parent(path)
    if not path.exists():
        path.write_text(render_pattern_page(candidate, learned_from_change), encoding="utf-8")
        return path

    existing_text = path.read_text(encoding="utf-8")
    frontmatter, body = load_frontmatter(existing_text)
    old_sources = [str(item) for item in frontmatter.get("supporting_sources", [])]
    merged_sources = unique([*old_sources, *candidate.supporting_sources])
    old_tags = [str(item) for item in frontmatter.get("tags", [])]
    frontmatter.update(
        {
            "status": candidate.status,
            "confidence": "high" if candidate.status == "stable" else "medium",
            "stability_score": candidate.stability_score,
            "supporting_sources": merged_sources,
            "learned_from_change": learned_from_change,
            "tags": unique([*old_tags, *candidate.tags]),
            "updated_at": utc_now(),
        }
    )
    appendix = (
        f"\n## Learned Update {utc_now()}\n\n"
        f"- Learned from: {learned_from_change}\n"
        f"- Status: {candidate.status}\n"
        f"- Stability score: {candidate.stability_score}\n"
        f"- Reasons: {', '.join(candidate.reasons)}\n"
    )
    path.write_text(dump_frontmatter(frontmatter) + body.rstrip() + appendix + "\n", encoding="utf-8")
    return path


def learn_prd_pattern_from_payload(
    settings: Settings,
    topic: str,
    prd_path: Path,
    change_name: str,
    context: dict[str, Any],
    update_index: bool = True,
) -> dict[str, Any]:
    if not prd_path.exists():
        return {
            "learned": False,
            "written": None,
            "message": f"PRD file not found: {prd_path}",
        }

    prd_text = prd_path.read_text(encoding="utf-8")
    candidate = build_pattern_candidate(settings, topic, prd_text, context, change_name)
    if candidate is None:
        return {
            "learned": False,
            "written": None,
            "message": "No reusable PRD pattern could be extracted.",
        }

    written = merge_or_write_pattern(settings, candidate, change_name)
    indexed_count = build_index(settings) if update_index else None
    return {
        "learned": True,
        "written": str(written),
        "candidate": candidate.to_dict(),
        "indexed_count": indexed_count,
        "message": "PRD pattern learned.",
    }
