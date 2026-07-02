from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from markitdown import MarkItDown


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx", ".txt"}


@dataclass(slots=True)
class MarkdownDocument:
    source_path: Path
    title: str
    markdown: str
    extension: str


def assert_supported(source_path: Path) -> None:
    if source_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"Unsupported file type: {source_path.suffix}. Supported: {supported}")


def convert_to_markdown(source_path: Path) -> MarkdownDocument:
    source_path = source_path.resolve()
    assert_supported(source_path)
    if not source_path.exists():
        raise FileNotFoundError(source_path)

    if source_path.suffix.lower() == ".txt":
        markdown = source_path.read_text(encoding="utf-8")
        title = source_path.stem
    else:
        result = MarkItDown().convert(source_path)
        markdown = getattr(result, "markdown", str(result)).strip()
        title = (getattr(result, "title", None) or source_path.stem).strip()

    return MarkdownDocument(
        source_path=source_path,
        title=title or source_path.stem,
        markdown=markdown.strip() + "\n",
        extension=source_path.suffix.lower(),
    )
