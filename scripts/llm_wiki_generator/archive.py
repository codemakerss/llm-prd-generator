from __future__ import annotations

import shutil
from pathlib import Path

from pydantic import ValidationError

from .config import Settings
from .llm import OpenAICompatibleLLM
from .markdown import MarkdownDocument, convert_to_markdown
from .models import ArchivePreview, EvidenceItem, PageType, SourceType, Status, UpdateItem
from .utils import dump_frontmatter, ensure_parent, extract_wikilinks, load_frontmatter, slugify, utc_now
from .layout import resolve_layout
from .vault import init_vault


class ArchiveLLMRequiredError(RuntimeError):
    pass


PREVIEW_SYSTEM_PROMPT = """You are an LLM Wiki archivist.
Return JSON only.
Do not write files.
Do not output absolute paths or secrets.
Identify reusable wiki knowledge from the converted Markdown source.
Respect source boundaries:
- business_fact may become factual business knowledge when evidence is strong
- industry_practice may become source, synthesis, or prd_pattern but not business fact
- team_history may become source, concept, synthesis, or prd_pattern and always stays draft
- for industry_practice and team_history, extract a prd_pattern whenever the source contains reusable PRD
  questions, section structure, acceptance approaches, review rules, or risk checks
- prd_pattern must exclude project names, concrete metrics/thresholds, interface names, dates, and source-specific facts
- if no reusable PRD method exists, do not emit an empty prd_pattern
- team_history PRD patterns may come from historical PRDs, team decisions, requirement structures, review flows, reusable templates, and repeated product judgments
- feedback defaults to draft
- contradictions must become conflict
Output this shape:
{
  "title": "string",
  "source_type": "business_fact|industry_practice|team_history|feedback",
  "source_path": "string",
  "summary": "string",
  "updates": [
    {
      "action": "create_or_update|conflict|deprecate",
      "page_type": "source|entity|concept|synthesis|conflict|prd_pattern",
      "title": "string",
      "status": "stable|draft|conflict|deprecated",
      "summary": "string",
      "body": "markdown body",
      "tags": ["string"],
      "links": ["[[Page]]"],
      "confidence": "low|medium|high",
      "evidence": [{"snippet":"string","reason":"string"}],
      "reason": "string"
    }
  ]
}"""


def default_status(source_type: SourceType, page_type: PageType) -> Status:
    if page_type == PageType.CONFLICT:
        return Status.CONFLICT
    if source_type in {SourceType.TEAM_HISTORY, SourceType.FEEDBACK}:
        return Status.DRAFT
    return Status.STABLE


def infer_tags(source_type: SourceType, text: str) -> list[str]:
    tags = [source_type.value]
    lowered = text.lower()
    keywords = [
        "prd",
        "workflow",
        "metric",
        "risk",
        "stakeholder",
        "requirement",
        "architecture",
        "business",
        "用户",
        "指标",
        "流程",
        "风险",
        "需求",
    ]
    for keyword in keywords:
        if keyword in lowered or keyword in text:
            tags.append(keyword)
    return sorted(set(tags))


def split_lines(text: str, limit: int = 8) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[:limit]


def deterministic_preview(document: MarkdownDocument, source_type: SourceType) -> ArchivePreview:
    lines = split_lines(document.markdown, limit=12)
    summary = lines[0] if lines else f"Imported {document.title}"
    shared_tags = infer_tags(source_type, document.markdown)
    source_update = UpdateItem(
        page_type=PageType.SOURCE,
        title=f"Source - {document.title}",
        status=default_status(source_type, PageType.SOURCE),
        summary=f"Normalized source snapshot for {document.title}.",
        body=document.markdown[:5000],
        tags=shared_tags,
        links=[],
        confidence="medium",
        evidence=[EvidenceItem(snippet=line, reason="Directly extracted from source") for line in lines[:3]],
        reason="Keep a normalized Markdown source page in the wiki.",
    )

    updates = [source_update]
    second_page_type = PageType.CONCEPT
    if source_type == SourceType.INDUSTRY_PRACTICE:
        second_page_type = PageType.PRD_PATTERN
    elif source_type == SourceType.TEAM_HISTORY:
        second_page_type = PageType.SYNTHESIS

    synthesized_body = "## Key Points\n\n" + "\n".join(f"- {line}" for line in lines[:8])
    updates.append(
        UpdateItem(
            page_type=second_page_type,
            title=f"{document.title} - {'Pattern' if second_page_type == PageType.PRD_PATTERN else 'Summary'}",
            status=default_status(source_type, second_page_type),
            summary=f"Condensed reusable knowledge from {document.title}.",
            body=synthesized_body,
            tags=shared_tags,
            links=[],
            confidence="medium",
            evidence=[EvidenceItem(snippet=line, reason="Selected as a high-signal point") for line in lines[:5]],
            reason="Preserve reusable knowledge in a structured wiki page.",
        )
    )

    return ArchivePreview(
        title=document.title,
        source_type=source_type,
        source_path=str(document.source_path),
        summary=summary,
        updates=updates,
    )


def build_preview(document: MarkdownDocument, source_type: SourceType, settings: Settings) -> ArchivePreview:
    llm = OpenAICompatibleLLM(settings)
    if not llm.available:
        raise ArchiveLLMRequiredError(
            "LLM is required for archive preview. Set LLM_PROVIDER, LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL in .env."
        )

    prompt = f"""Source type: {source_type.value}
Source path: {document.source_path.name}
Document title: {document.title}

Converted Markdown:
{document.markdown[:20000]}
"""
    try:
        payload = llm.complete_json(PREVIEW_SYSTEM_PROMPT, prompt)
        preview = ArchivePreview.model_validate(payload)
    except (ValidationError, ValueError, RuntimeError, KeyError) as exc:
        raise ArchiveLLMRequiredError(
            "LLM archive preview failed. Fix the LLM response or configuration before archiving."
        ) from exc
    return enforce_rules(preview)


def enforce_rules(preview: ArchivePreview) -> ArchivePreview:
    fixed: list[UpdateItem] = []
    for update in preview.updates:
        if preview.source_type == SourceType.BUSINESS_FACT and update.page_type == PageType.PRD_PATTERN:
            continue
        status = update.status
        if update.page_type == PageType.CONFLICT:
            status = Status.CONFLICT
        elif preview.source_type in {SourceType.TEAM_HISTORY, SourceType.FEEDBACK}:
            status = Status.DRAFT
        elif preview.source_type == SourceType.INDUSTRY_PRACTICE and update.page_type == PageType.CONCEPT:
            update.page_type = PageType.PRD_PATTERN
            status = Status.STABLE
        update.status = status
        fixed.append(update)
    if preview.source_type in {SourceType.TEAM_HISTORY, SourceType.INDUSTRY_PRACTICE}:
        fixed = ensure_reusable_prd_pattern(preview, fixed)
    preview.updates = fixed
    return preview


def ensure_reusable_prd_pattern(preview: ArchivePreview, updates: list[UpdateItem]) -> list[UpdateItem]:
    if any(update.page_type == PageType.PRD_PATTERN for update in updates):
        return updates

    source_text = "\n".join(f"{item.title}\n{item.summary}\n{item.body}" for item in updates)
    markers = [
        "prd", "需求", "背景", "目标", "用户", "范围", "流程", "指标", "验收", "风险", "上线", "评审"
    ]
    matched = [marker for marker in markers if marker.lower() in source_text.lower()]
    if len(matched) < 3:
        return updates

    reusable_lines = [
        line.strip(" #-*")
        for line in source_text.splitlines()
        if line.strip() and any(marker.lower() in line.lower() for marker in matched)
    ][:10]
    if len(reusable_lines) < 2:
        return updates

    has_conflict = any(update.page_type == PageType.CONFLICT for update in updates)
    status = (
        Status.DRAFT
        if preview.source_type == SourceType.TEAM_HISTORY or has_conflict
        else Status.STABLE
    )
    updates.append(
        UpdateItem(
            page_type=PageType.PRD_PATTERN,
            title=f"{preview.title} - PRD Pattern",
            status=status,
            summary=f"Reusable PRD structure extracted from {preview.title}.",
            body="## Reusable Structure\n\n" + "\n".join(f"- {line}" for line in reusable_lines),
            tags=sorted({preview.source_type.value, "prd", "pattern", *matched}),
            links=[],
            confidence="medium",
            evidence=[
                EvidenceItem(snippet=line, reason="Supports a reusable PRD method")
                for line in reusable_lines[:5]
            ],
            reason="The source contains reusable PRD sections, questions, acceptance methods, or risk checks.",
        )
    )
    return updates


def page_path(settings: Settings, update: UpdateItem) -> Path:
    layout = resolve_layout(settings.wiki_root, settings.layout_language)
    relative = layout.wiki_dirs[update.page_type.value]
    filename = f"{slugify(update.title)}.md"
    return settings.wiki_root / relative / filename


def render_page(preview: ArchivePreview, update: UpdateItem) -> str:
    frontmatter = {
        "title": update.title,
        "page_type": update.page_type.value,
        "status": update.status.value,
        "source_type": preview.source_type.value,
        "confidence": update.confidence,
        "tags": update.tags,
        "links": update.links or extract_wikilinks(update.body),
        "updated_at": utc_now(),
        "source_path": preview.source_path,
    }
    evidence_block = ""
    if update.evidence:
        lines = "\n".join(f"- {item.snippet} ({item.reason})" for item in update.evidence)
        evidence_block = f"\n## Evidence\n\n{lines}\n"
    return dump_frontmatter(frontmatter) + f"\n# {update.title}\n\n{update.summary}\n\n{update.body.strip()}\n{evidence_block}"


def merge_or_write(path: Path, preview: ArchivePreview, update: UpdateItem) -> None:
    ensure_parent(path)
    if not path.exists():
        path.write_text(render_page(preview, update), encoding="utf-8")
        return

    existing_text = path.read_text(encoding="utf-8")
    frontmatter, body = load_frontmatter(existing_text)
    frontmatter["status"] = update.status.value
    frontmatter["confidence"] = update.confidence
    frontmatter["updated_at"] = utc_now()
    old_tags = set(frontmatter.get("tags", []))
    old_tags.update(update.tags)
    frontmatter["tags"] = sorted(old_tags)
    old_links = set(frontmatter.get("links", []))
    old_links.update(update.links)
    old_links.update(extract_wikilinks(update.body))
    frontmatter["links"] = sorted(old_links)
    appendix = (
        f"\n## Update {utc_now()}\n\n"
        f"**Summary:** {update.summary}\n\n"
        f"{update.body.strip()}\n"
    )
    if update.evidence:
        appendix += "\n### Evidence\n\n" + "\n".join(
            f"- {item.snippet} ({item.reason})" for item in update.evidence
        )
        appendix += "\n"
    path.write_text(dump_frontmatter(frontmatter) + body.rstrip() + appendix + "\n", encoding="utf-8")


def update_index_and_log(settings: Settings, preview: ArchivePreview, written_paths: list[Path]) -> None:
    layout = resolve_layout(settings.wiki_root, settings.layout_language)
    index_path = settings.wiki_root / layout.index_file
    log_path = settings.wiki_root / layout.log_file

    relative_links = [
        f"- [[{path.stem}]] -> `{path.relative_to(settings.wiki_root)}`"
        for path in written_paths
    ]
    entry = (
        f"\n## {preview.title} ({utc_now()})\n\n"
        f"- Source type: `{preview.source_type.value}`\n"
        f"- Source path: `{preview.source_path}`\n"
        + "\n".join(relative_links)
        + "\n"
    )
    index_path.write_text(index_path.read_text(encoding="utf-8") + entry, encoding="utf-8")
    log_path.write_text(log_path.read_text(encoding="utf-8") + entry, encoding="utf-8")


def archive_source(source_path: Path, source_type: SourceType, settings: Settings) -> ArchivePreview:
    document = convert_to_markdown(source_path)
    return build_preview(document, source_type, settings)


def apply_preview(preview: ArchivePreview, source_path: Path, settings: Settings) -> list[Path]:
    init_vault(settings)
    layout = resolve_layout(settings.wiki_root, settings.layout_language)
    raw_target = settings.wiki_root / layout.raw_dirs[preview.source_type.value] / source_path.name
    ensure_parent(raw_target)
    shutil.copy2(source_path, raw_target)

    written_paths: list[Path] = []
    for update in preview.updates:
        target_path = page_path(settings, update)
        merge_or_write(target_path, preview, update)
        written_paths.append(target_path)

    update_index_and_log(settings, preview, written_paths)
    return written_paths


def archive_receipt(
    preview: ArchivePreview,
    source_path: Path,
    settings: Settings,
    written_paths: list[Path],
    indexed_count: int | None,
) -> dict:
    layout = resolve_layout(settings.wiki_root, settings.layout_language)
    raw_target = settings.wiki_root / layout.raw_dirs[preview.source_type.value] / source_path.name
    updates = []
    for update, path in zip(preview.updates, written_paths):
        updates.append(
            {
                "title": update.title,
                "page_type": update.page_type.value,
                "status": update.status.value,
                "tags": update.tags,
                "summary": update.summary,
                "evidence": [item.model_dump() for item in update.evidence],
                "path": str(path),
            }
        )
    patterns = [item for item in updates if item["page_type"] == "prd_pattern"]
    return {
        "source_file": str(source_path),
        "source_type": preview.source_type.value,
        "summary": preview.summary,
        "raw_path": str(raw_target),
        "written": [str(path) for path in written_paths],
        "wiki_updates": updates,
        "pattern": {
            "learned": bool(patterns),
            "items": patterns,
            "message": "PRD pattern archived." if patterns else "No reusable PRD pattern was identified.",
        },
        "layout_language": layout.language,
        "indexed_count": indexed_count,
        "index_db": str(settings.index_db),
        "skipped": [],
        "failed": [],
    }
