from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class CompatBaseModel(BaseModel):
    @classmethod
    def model_validate(cls, value):
        parser = getattr(super(), "model_validate", None)
        if parser is not None:
            return parser(value)
        return cls.parse_obj(value)

    def model_dump(self, *args, **kwargs):
        dumper = getattr(super(), "model_dump", None)
        if dumper is not None:
            return dumper(*args, **kwargs)
        kwargs.pop("mode", None)
        return self.dict(*args, **kwargs)


class SourceType(str, Enum):
    BUSINESS_FACT = "business_fact"
    INDUSTRY_PRACTICE = "industry_practice"
    TEAM_HISTORY = "team_history"
    FEEDBACK = "feedback"


class PageType(str, Enum):
    SOURCE = "source"
    ENTITY = "entity"
    CONCEPT = "concept"
    SYNTHESIS = "synthesis"
    CONFLICT = "conflict"
    PRD_PATTERN = "prd_pattern"


class Status(str, Enum):
    STABLE = "stable"
    DRAFT = "draft"
    CONFLICT = "conflict"
    DEPRECATED = "deprecated"


class Scope(str, Enum):
    STABLE = "stable"
    STABLE_DRAFT = "stable-draft"
    ALL = "all"


class EvidenceItem(CompatBaseModel):
    snippet: str
    reason: str


class UpdateItem(CompatBaseModel):
    action: Literal["create_or_update", "conflict", "deprecate"] = "create_or_update"
    page_type: PageType
    title: str
    status: Status
    summary: str
    body: str
    tags: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"
    evidence: list[EvidenceItem] = Field(default_factory=list)
    reason: str


class ArchivePreview(CompatBaseModel):
    title: str
    source_type: SourceType
    source_path: str
    summary: str
    updates: list[UpdateItem] = Field(default_factory=list)


class RetrievedDocument(CompatBaseModel):
    path: str
    title: str
    page_type: str
    status: str
    source_type: str
    score: float
    excerpt: str
