from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class QualityDimension:
    key: str
    label: str
    question: str
    reason: str
    weight: int


PRD_DIMENSIONS = (
    QualityDimension(
        "goal",
        "业务问题与目标",
        "这个需求最需要解决的业务问题是什么？期望带来什么业务结果？",
        "Proposal 必须解释为什么要做，以及结果如何改善。",
        10,
    ),
    QualityDimension(
        "target_users",
        "目标用户",
        "主要用户是谁？请说明角色以及他们当前最痛苦的任务。",
        "需求和验收场景必须绑定明确用户。",
        8,
    ),
    QualityDimension(
        "stakeholders",
        "干系人与决策权",
        "谁负责决策、评审、交付和最终验收？",
        "需要明确需求所有者和跨团队责任。",
        7,
    ),
    QualityDimension(
        "success_metric",
        "成功指标",
        "首个版本用哪些可量化指标判断成功？请包含基线、目标值或观察周期。",
        "没有可量化指标就无法判断变更是否有效。",
        9,
    ),
    QualityDimension(
        "scope",
        "MVP 范围",
        "MVP 必须包含哪些能力？请同时说明边界。",
        "OpenSpec change 需要清晰、可交付的变更边界。",
        8,
    ),
    QualityDimension(
        "non_goals",
        "非目标",
        "本次明确不解决什么？哪些内容推迟到后续版本？",
        "非目标用于防止范围持续膨胀。",
        5,
    ),
    QualityDimension(
        "user_workflows",
        "用户流程与异常路径",
        "请描述用户完成核心任务的主要步骤，以及至少一个失败或异常路径。",
        "Delta specs 需要从真实流程生成可验证场景。",
        9,
    ),
    QualityDimension(
        "business_rules",
        "业务规则与权限",
        "有哪些计算规则、状态流转、审批条件、权限或合规要求？",
        "业务规则决定规范性需求和权限边界。",
        9,
    ),
    QualityDimension(
        "data_integrations",
        "数据与集成",
        "需要读取或写入哪些数据？涉及哪些上下游系统、接口或数据保留要求？",
        "数据来源与系统依赖必须在设计前确认。",
        7,
    ),
    QualityDimension(
        "non_functional_requirements",
        "非功能要求",
        "对性能、可用性、安全、隐私、审计或可访问性有什么最低要求？",
        "非功能要求是完整 PRD 的必要约束。",
        7,
    ),
    QualityDimension(
        "risks_dependencies",
        "风险与依赖",
        "有哪些外部依赖、关键假设和可能导致延期或失败的风险？",
        "风险和依赖会影响方案、任务顺序与上线决策。",
        6,
    ),
    QualityDimension(
        "acceptance_criteria",
        "验收标准",
        "业务方最终如何验收？请给出至少一个成功条件和一个失败条件。",
        "验收标准将转化为 Requirement Scenario。",
        8,
    ),
    QualityDimension(
        "rollout_plan",
        "上线与反馈",
        "计划如何灰度、监控、回滚和收集用户反馈？",
        "上线方案用于闭环验证指标并控制变更风险。",
        7,
    ),
)


class PrdQualityGate:
    def evaluate(
        self,
        extracted: dict[str, Any],
        context: dict[str, Any],
        conflicts: list[str] | None = None,
    ) -> dict[str, Any]:
        conflicts = conflicts or []
        missing = [
            dimension
            for dimension in PRD_DIMENSIONS
            if not self._has_value(extracted.get(dimension.key))
        ]
        evidence_available = bool(
            context.get("evidence_pack") or self._has_value(extracted.get("evidence"))
        )
        total = sum(item.weight for item in PRD_DIMENSIONS) + 10
        earned = sum(
            item.weight
            for item in PRD_DIMENSIONS
            if self._has_value(extracted.get(item.key))
        )
        if evidence_available:
            earned += 10

        unresolved_conflicts = conflicts if not extracted.get("conflict_resolution") else []
        blockers = [item.label for item in missing]
        if not evidence_available:
            blockers.append("业务证据")
        if unresolved_conflicts:
            blockers.append("知识冲突")

        return {
            "score": 100 if not blockers else round(earned / total * 100),
            "ready": not blockers,
            "blockers": blockers,
            "missing": [
                {
                    "key": item.key,
                    "label": item.label,
                    "reason": item.reason,
                    "question": item.question,
                    "weight": item.weight,
                }
                for item in missing
            ],
            "evidence_available": evidence_available,
            "conflicts": unresolved_conflicts,
            "dimensions": [
                {
                    **asdict(item),
                    "complete": self._has_value(extracted.get(item.key)),
                }
                for item in PRD_DIMENSIONS
            ],
        }

    def next_question(
        self,
        quality: dict[str, Any],
        extracted: dict[str, Any],
    ) -> dict[str, str] | None:
        if quality["conflicts"] and not extracted.get("conflict_resolution"):
            return {
                "key": "conflict_resolution",
                "question": "检索到相互冲突的知识："
                + "；".join(quality["conflicts"])
                + "。请确认本次需求采用哪一条规则，并说明原因。",
                "reason": "冲突必须由业务负责人确认，不能由模型自行选择。",
            }
        if quality["missing"]:
            item = sorted(quality["missing"], key=lambda value: value["weight"], reverse=True)[0]
            return {
                "key": item["key"],
                "question": item["question"],
                "reason": item["reason"],
            }
        if not quality["evidence_available"]:
            return {
                "key": "evidence",
                "question": "知识库中没有匹配的业务证据。请提供访谈结论、业务制度、数据报告或负责人确认记录。",
                "reason": "业务事实必须可追溯，不能由业界模板或历史 PRD 替代。",
            }
        return None

    @staticmethod
    def _has_value(value: Any) -> bool:
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, tuple, set, dict)):
            return bool(value)
        return value is not None
