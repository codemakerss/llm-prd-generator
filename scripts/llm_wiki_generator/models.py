from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


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


class EvidenceItem(BaseModel):
    snippet: str
    reason: str


class UpdateItem(BaseModel):
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


class ArchivePreview(BaseModel):
    title: str
    source_type: SourceType
    source_path: str
    summary: str
    updates: list[UpdateItem] = Field(default_factory=list)


class RetrievedDocument(BaseModel):
    path: str
    title: str
    page_type: str
    status: str
    source_type: str
    score: float
    excerpt: str
