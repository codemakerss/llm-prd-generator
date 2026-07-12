from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class WikiLayoutError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class WikiLayout:
    language: str
    raw_dirs: dict[str, str]
    wiki_dirs: dict[str, str]
    wiki_root_dir: str
    index_file: str
    log_file: str

    @property
    def pattern_dir(self) -> str:
        return self.wiki_dirs["prd_pattern"]

    @property
    def required_paths(self) -> list[str]:
        return [*self.raw_dirs.values(), *self.wiki_dirs.values(), self.index_file, self.log_file]


LAYOUTS = {
    "en": WikiLayout(
        language="en",
        raw_dirs={
            "business_fact": "10-raw/business_fact",
            "industry_practice": "10-raw/industry_practice",
            "team_history": "10-raw/team_history",
            "feedback": "10-raw/feedback",
        },
        wiki_dirs={
            "source": "20-wiki/sources",
            "entity": "20-wiki/entities",
            "concept": "20-wiki/concepts",
            "synthesis": "20-wiki/synthesis",
            "conflict": "20-wiki/conflicts",
            "prd_pattern": "20-wiki/prd-patterns",
        },
        wiki_root_dir="20-wiki",
        index_file="20-wiki/index.md",
        log_file="20-wiki/log.md",
    ),
    "zh": WikiLayout(
        language="zh",
        raw_dirs={
            "business_fact": "10-原始资料/业务知识",
            "industry_practice": "10-原始资料/业界实践",
            "team_history": "10-原始资料/团队历史PRD",
            "feedback": "10-原始资料/用户反馈",
        },
        wiki_dirs={
            "source": "20-知识库/来源",
            "entity": "20-知识库/实体",
            "concept": "20-知识库/概念",
            "synthesis": "20-知识库/综合",
            "conflict": "20-知识库/冲突",
            "prd_pattern": "20-知识库/PRD模式",
        },
        wiki_root_dir="20-知识库",
        index_file="20-知识库/索引.md",
        log_file="20-知识库/日志.md",
    ),
}


def normalize_layout_language(language: str | None) -> str:
    resolved = (language or "").strip().lower()
    if resolved and resolved not in LAYOUTS:
        raise WikiLayoutError("WIKI_LAYOUT_LANGUAGE must be 'zh' or 'en'.")
    return resolved


def detect_layout_language(wiki_root: Path) -> str | None:
    has_en = (wiki_root / "20-wiki").exists()
    has_zh = (wiki_root / "20-知识库").exists()
    if has_en and has_zh:
        raise WikiLayoutError(
            f"Conflicting wiki layouts under {wiki_root}: both 20-wiki and 20-知识库 exist."
        )
    if has_zh:
        return "zh"
    if has_en:
        return "en"
    return None


def resolve_layout(wiki_root: Path, preferred_language: str | None = None) -> WikiLayout:
    preferred = normalize_layout_language(preferred_language)
    detected = detect_layout_language(wiki_root)
    if preferred and detected and preferred != detected:
        raise WikiLayoutError(
            f"Configured layout language '{preferred}' does not match existing '{detected}' layout at {wiki_root}."
        )
    return LAYOUTS[detected or preferred or "en"]
