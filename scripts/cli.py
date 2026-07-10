from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from llm_wiki_generator.answer import answer_question
from llm_wiki_generator.archive import ArchiveLLMRequiredError, apply_preview, archive_source, enforce_rules
from llm_wiki_generator.bootstrap import initialize_wiki_location, inspect_bootstrap
from llm_wiki_generator.config import load_settings
from llm_wiki_generator.indexer import build_index, search_index
from llm_wiki_generator.markdown import convert_to_markdown
from llm_wiki_generator.models import ArchivePreview, Scope, SourceType
from llm_wiki_generator.prd_pattern import learn_prd_pattern_from_payload
from llm_wiki_generator.prd_workflow import default_change_name, generate_openspec_change, prd_chat_turn
from llm_wiki_generator.utils import slugify
from llm_wiki_generator.vault import init_vault


app = typer.Typer(help="Standalone LLM PRD Generator")
console = Console()


def print_archive_error(error: ArchiveLLMRequiredError) -> None:
    console.print(f"[red]error[/red] {error}")


def parse_source_type(source_type: str) -> SourceType:
    try:
        return SourceType(source_type)
    except ValueError as exc:
        raise typer.BadParameter(f"Invalid source type: {source_type}") from exc


def parse_scope(scope: str) -> Scope:
    try:
        return Scope(scope)
    except ValueError as exc:
        raise typer.BadParameter(f"Invalid scope: {scope}") from exc


@app.command()
def init() -> None:
    settings = load_settings()
    created = init_vault(settings)
    for path in created:
        console.print(f"[green]ready[/green] {path}")


@app.command("bootstrap-status")
def bootstrap_status(as_json: bool = False) -> None:
    skill_root = Path(__file__).resolve().parents[1]
    status = inspect_bootstrap(skill_root)
    payload = status.to_dict()
    if as_json:
        console.print_json(json.dumps(payload, ensure_ascii=False))
        return

    console.print(
        Panel.fit(
            "\n".join(
                [
                    f"Configured: {status.configured}",
                    f"Initialized: {status.initialized}",
                    f"Env file: {status.env_path}",
                    f"Wiki root: {status.wiki_root or '(unset)'}",
                    f"Index DB: {status.index_db or '(unset)'}",
                    f"Missing paths: {', '.join(status.missing_paths) or '(none)'}",
                ]
            ),
            title="Bootstrap Status",
        )
    )


@app.command("bootstrap-init")
def bootstrap_init(wiki_root: Path) -> None:
    skill_root = Path(__file__).resolve().parents[1]
    settings, created, env_path = initialize_wiki_location(skill_root, wiki_root)
    console.print(f"[green]configured[/green] {env_path}")
    console.print(f"[green]wiki-root[/green] {settings.wiki_root}")
    console.print(f"[green]index-db[/green] {settings.index_db}")
    for path in created:
        console.print(f"[green]ready[/green] {path}")


@app.command()
def convert(source: Path, output: Optional[Path] = None, as_json: bool = False) -> None:
    document = convert_to_markdown(source)
    if as_json:
        payload = {
            "source_path": str(document.source_path),
            "title": document.title,
            "extension": document.extension,
            "markdown": document.markdown,
        }
        console.print_json(json.dumps(payload, ensure_ascii=False))
        return
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(document.markdown, encoding="utf-8")
        console.print(f"[green]written[/green] {output}")
        return
    console.print(Panel.fit(document.markdown, title=document.title))


def render_preview(preview: dict) -> None:
    table = Table(title=preview["title"])
    table.add_column("Title")
    table.add_column("Page Type")
    table.add_column("Status")
    table.add_column("Confidence")
    table.add_column("Reason")
    for update in preview["updates"]:
        table.add_row(
            update["title"],
            update["page_type"],
            update["status"],
            update["confidence"],
            update["reason"],
        )
    console.print(table)


def load_archive_preview(source: Path, source_type: str):
    settings = load_settings()
    try:
        preview = archive_source(source, parse_source_type(source_type), settings)
    except ArchiveLLMRequiredError as exc:
        print_archive_error(exc)
        raise typer.Exit(code=1) from exc
    return settings, preview


def load_host_preview(preview_file: Path) -> ArchivePreview:
    try:
        payload = json.loads(preview_file.read_text(encoding="utf-8"))
        return enforce_rules(ArchivePreview.model_validate(payload))
    except Exception as exc:
        console.print(f"[red]error[/red] Invalid ArchivePreview JSON: {exc}")
        raise typer.Exit(code=1) from exc


@app.command("show-updates")
def show_updates(
    source: Path,
    source_type: str = typer.Option(..., "--source-type"),
    as_json: bool = False,
) -> None:
    _, preview = load_archive_preview(source, source_type)
    payload = preview.model_dump(mode="json")
    if as_json:
        console.print_json(json.dumps(payload, ensure_ascii=False))
        return
    render_preview(payload)


@app.command("apply-preview")
def apply_preview_file(
    source: Path,
    preview_file: Path = typer.Option(..., "--preview-file"),
    reindex: bool = typer.Option(True, "--index/--no-index", help="Rebuild the retrieval index after archiving."),
    as_json: bool = False,
) -> None:
    settings = load_settings()
    preview = load_host_preview(preview_file)
    written = apply_preview(preview, source.resolve(), settings)
    if reindex:
        indexed_count = build_index(settings)
    else:
        indexed_count = None

    payload = {
        "preview": preview.model_dump(mode="json"),
        "written": [str(path) for path in written],
        "indexed_count": indexed_count,
        "index_db": str(settings.index_db),
    }
    if as_json:
        console.print_json(json.dumps(payload, ensure_ascii=False))
        return

    render_preview(payload["preview"])
    for path in written:
        console.print(f"[green]archived[/green] {path}")
    if indexed_count is not None:
        console.print(f"[green]indexed[/green] {indexed_count} documents into {settings.index_db}")


@app.command("archive")
def archive(
    source: Path,
    source_type: str = typer.Option(..., "--source-type"),
    reindex: bool = typer.Option(True, "--index/--no-index", help="Rebuild the retrieval index after archiving."),
) -> None:
    settings, preview = load_archive_preview(source, source_type)
    written = apply_preview(preview, source.resolve(), settings)
    payload = preview.model_dump(mode="json")
    render_preview(payload)
    for path in written:
        console.print(f"[green]archived[/green] {path}")
    if reindex:
        count = build_index(settings)
        console.print(f"[green]indexed[/green] {count} documents into {settings.index_db}")


@app.command()
def apply(source: Path, source_type: str = typer.Option(..., "--source-type")) -> None:
    settings, preview = load_archive_preview(source, source_type)
    written = apply_preview(preview, source.resolve(), settings)
    payload = preview.model_dump(mode="json")
    render_preview(payload)
    for path in written:
        console.print(f"[green]archived[/green] {path}")


@app.command()
def index() -> None:
    settings = load_settings()
    count = build_index(settings)
    console.print(f"[green]indexed[/green] {count} documents into {settings.index_db}")


@app.command()
def search(question: str, scope: Optional[str] = None, limit: int = 5, as_json: bool = False) -> None:
    settings = load_settings()
    resolved_scope = parse_scope(scope or settings.default_scope)
    results = search_index(settings, question, resolved_scope, limit=limit)
    payload = [result.model_dump(mode="json") for result in results]
    if as_json:
        console.print_json(json.dumps(payload, ensure_ascii=False))
        return

    table = Table(title=f"Wiki Search: {question}")
    table.add_column("Title")
    table.add_column("Status")
    table.add_column("Page Type")
    table.add_column("Source Type")
    table.add_column("Excerpt")
    for result in payload:
        table.add_row(
            result["title"],
            result["status"],
            result["page_type"],
            result["source_type"],
            result["excerpt"],
        )
    console.print(table)


@app.command()
def answer(question: str, scope: Optional[str] = None, limit: int = 5) -> None:
    settings = load_settings()
    resolved_scope = parse_scope(scope or settings.default_scope)
    response = answer_question(settings, question, resolved_scope, limit=limit)
    console.print(Panel.fit(response, title="Wiki Answer"))


@app.command("prd-chat")
def prd_chat(
    topic: str,
    answer: str = typer.Option("", "--answer", "-a"),
    limit: int = 5,
    as_json: bool = False,
) -> None:
    settings = load_settings()
    payload = prd_chat_turn(settings, topic, answer=answer, limit=limit)
    if as_json:
        console.print_json(json.dumps(payload, ensure_ascii=False))
        return

    quality = payload["quality"]
    console.print(
        Panel.fit(
            "\n".join(
                [
                    f"Topic: {topic}",
                    f"Completeness: {quality['score']}%",
                    f"Ready: {payload['ready']}",
                    f"Blockers: {', '.join(quality['blockers']) or '(none)'}",
                ]
            ),
            title="PRD Quality Gate",
        )
    )
    if payload["next_question"]:
        question = payload["next_question"]
        console.print(Panel.fit(question["question"], title=f"Next Question: {question['key']}"))
        console.print(f"[dim]{question['reason']}[/dim]")
    else:
        console.print("[green]PRD completeness reached 100%. You can generate OpenSpec artifacts.[/green]")


@app.command("propose-prd")
def propose_prd(
    topic: str,
    project_root: Optional[Path] = typer.Option(None, "--project-root"),
    change_name: Optional[str] = typer.Option(None, "--change-name"),
    capability: Optional[str] = typer.Option(None, "--capability"),
    limit: int = 5,
    learn_pattern: bool = typer.Option(True, "--learn-pattern/--no-learn-pattern"),
    as_json: bool = False,
) -> None:
    settings = load_settings()
    resolved_project_root = project_root or settings.wiki_root
    payload = generate_openspec_change(
        settings,
        topic,
        project_root=resolved_project_root,
        change_name=change_name,
        capability=capability,
        limit=limit,
        learn_pattern=learn_pattern,
    )
    if as_json:
        console.print_json(json.dumps(payload, ensure_ascii=False))
        return

    console.print(Panel.fit(payload["message"], title="OpenSpec PRD"))
    if payload["next_question"]:
        question = payload["next_question"]
        console.print(Panel.fit(question["question"], title=f"Next Question: {question['key']}"))
    for path in payload["written"]:
        console.print(f"[green]written[/green] {path}")
    if payload.get("pattern") and payload["pattern"].get("learned"):
        console.print(f"[green]pattern[/green] {payload['pattern']['written']}")


@app.command("learn-prd-pattern")
def learn_prd_pattern(
    topic: str,
    project_root: Optional[Path] = typer.Option(None, "--project-root"),
    change_name: Optional[str] = typer.Option(None, "--change-name"),
    limit: int = 5,
    as_json: bool = False,
) -> None:
    settings = load_settings()
    resolved_project_root = project_root or settings.wiki_root
    resolved_change_name = change_name or default_change_name(topic)
    prd_path = resolved_project_root / "openspec" / "changes" / slugify(resolved_change_name) / "prd.md"
    turn = prd_chat_turn(settings, topic, limit=limit)
    payload = learn_prd_pattern_from_payload(
        settings=settings,
        topic=topic,
        prd_path=prd_path,
        change_name=slugify(resolved_change_name),
        context=turn["context"],
        update_index=True,
    )
    if as_json:
        console.print_json(json.dumps(payload, ensure_ascii=False))
        return

    console.print(Panel.fit(payload["message"], title="PRD Pattern Learning"))
    if payload.get("written"):
        console.print(f"[green]pattern[/green] {payload['written']}")


if __name__ == "__main__":
    app()
