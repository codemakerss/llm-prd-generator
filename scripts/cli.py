from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from llm_wiki_generator.answer import answer_question
from llm_wiki_generator.archive import apply_preview, archive_source
from llm_wiki_generator.config import load_settings
from llm_wiki_generator.indexer import build_index
from llm_wiki_generator.markdown import convert_to_markdown
from llm_wiki_generator.models import Scope, SourceType
from llm_wiki_generator.vault import init_vault


app = typer.Typer(help="Standalone LLM Wiki Generator")
console = Console()


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


@app.command()
def convert(source: Path, output: Path | None = None) -> None:
    document = convert_to_markdown(source)
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


@app.command("show-updates")
def show_updates(
    source: Path,
    source_type: str = typer.Option(..., "--source-type"),
    as_json: bool = False,
) -> None:
    settings = load_settings()
    preview = archive_source(source, parse_source_type(source_type), settings)
    payload = preview.model_dump(mode="json")
    if as_json:
        console.print_json(json.dumps(payload, ensure_ascii=False))
        return
    render_preview(payload)


@app.command()
def apply(source: Path, source_type: str = typer.Option(..., "--source-type")) -> None:
    settings = load_settings()
    preview = archive_source(source, parse_source_type(source_type), settings)
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
def answer(question: str, scope: str | None = None, limit: int = 5) -> None:
    settings = load_settings()
    resolved_scope = parse_scope(scope or settings.default_scope)
    response = answer_question(settings, question, resolved_scope, limit=limit)
    console.print(Panel.fit(response, title="Wiki Answer"))


if __name__ == "__main__":
    app()
