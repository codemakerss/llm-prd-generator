from __future__ import annotations

import sqlite3
import re
from pathlib import Path

from .config import Settings
from .layout import resolve_layout
from .models import RetrievedDocument, Scope
from .utils import extract_wikilinks, load_frontmatter


def markdown_files(settings: Settings) -> list[Path]:
    layout = resolve_layout(settings.wiki_root, settings.layout_language)
    wiki_root = settings.wiki_root / layout.wiki_root_dir
    excluded = {Path(layout.index_file).name, Path(layout.log_file).name}
    return sorted(path for path in wiki_root.rglob("*.md") if path.name not in excluded)


def build_index(settings: Settings) -> int:
    settings.index_db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.index_db)
    try:
        conn.execute("DROP TABLE IF EXISTS docs")
        conn.execute("DROP TABLE IF EXISTS docs_fts")
        conn.execute(
            """
            CREATE TABLE docs (
                path TEXT PRIMARY KEY,
                title TEXT,
                page_type TEXT,
                status TEXT,
                source_type TEXT,
                tags TEXT,
                links TEXT,
                content TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE VIRTUAL TABLE docs_fts USING fts5(
                path, title, page_type, status, source_type, tags, content
            )
            """
        )
        count = 0
        for path in markdown_files(settings):
            text = path.read_text(encoding="utf-8")
            frontmatter, body = load_frontmatter(text)
            title = frontmatter.get("title", path.stem)
            page_type = frontmatter.get("page_type", "unknown")
            status = frontmatter.get("status", "draft")
            source_type = frontmatter.get("source_type", "unknown")
            tags = ",".join(frontmatter.get("tags", []))
            links = ",".join(frontmatter.get("links", []) or extract_wikilinks(body))
            relative_path = str(path.relative_to(settings.wiki_root))
            conn.execute(
                "INSERT INTO docs(path, title, page_type, status, source_type, tags, links, content) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (relative_path, title, page_type, status, source_type, tags, links, body),
            )
            conn.execute(
                "INSERT INTO docs_fts(path, title, page_type, status, source_type, tags, content) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (relative_path, title, page_type, status, source_type, tags, body),
            )
            count += 1
        conn.commit()
        return count
    finally:
        conn.close()


def scope_clause(scope: Scope) -> tuple[str, tuple[str, ...]]:
    if scope == Scope.STABLE:
        return "WHERE docs.status = ?", ("stable",)
    if scope == Scope.STABLE_DRAFT:
        return "WHERE docs.status IN (?, ?)", ("stable", "draft")
    return "", ()


def keyword_fragments(query: str) -> list[str]:
    tokens: list[str] = []
    for chunk in re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+", query):
        if re.fullmatch(r"[\u4e00-\u9fff]+", chunk) and len(chunk) > 2:
            tokens.extend(chunk[index : index + 2] for index in range(len(chunk) - 1))
        else:
            tokens.append(chunk)
    return [token for token in dict.fromkeys(tokens) if token.strip()]


def fallback_search(conn: sqlite3.Connection, scope: Scope, query: str, limit: int) -> list[RetrievedDocument]:
    where_sql, params = scope_clause(scope)
    sql = (
        f"SELECT path, title, page_type, status, source_type, content FROM docs {where_sql}"
        if where_sql
        else "SELECT path, title, page_type, status, source_type, content FROM docs"
    )
    rows = conn.execute(sql, params).fetchall()
    tokens = keyword_fragments(query)
    scored: list[RetrievedDocument] = []
    for row in rows:
        haystack = f"{row['title']} {row['content']}".lower()
        score = 0.0
        for token in tokens:
            score += haystack.count(token.lower())
        if score > 0:
            scored.append(
                RetrievedDocument(
                    path=row["path"],
                    title=row["title"],
                    page_type=row["page_type"],
                    status=row["status"],
                    source_type=row["source_type"],
                    score=-score,
                    excerpt=row["content"][:320],
                )
            )
    return sorted(scored, key=lambda item: item.score)[:limit]


def search_index(settings: Settings, query: str, scope: Scope, limit: int = 5) -> list[RetrievedDocument]:
    conn = sqlite3.connect(settings.index_db)
    conn.row_factory = sqlite3.Row
    try:
        where_sql, params = scope_clause(scope)
        sql = f"""
            SELECT docs.path, docs.title, docs.page_type, docs.status, docs.source_type,
                   bm25(docs_fts) AS score,
                   substr(docs.content, 1, 320) AS excerpt
            FROM docs_fts
            JOIN docs ON docs.path = docs_fts.path
            {where_sql}
            AND docs_fts MATCH ?
            ORDER BY score
            LIMIT ?
        """ if where_sql else """
            SELECT docs.path, docs.title, docs.page_type, docs.status, docs.source_type,
                   bm25(docs_fts) AS score,
                   substr(docs.content, 1, 320) AS excerpt
            FROM docs_fts
            JOIN docs ON docs.path = docs_fts.path
            WHERE docs_fts MATCH ?
            ORDER BY score
            LIMIT ?
        """
        values = [*params, query, limit] if where_sql else [query, limit]
        rows = conn.execute(sql, values).fetchall()
        results = [
            RetrievedDocument(
                path=row["path"],
                title=row["title"],
                page_type=row["page_type"],
                status=row["status"],
                source_type=row["source_type"],
                score=float(row["score"]),
                excerpt=row["excerpt"],
            )
            for row in rows
        ]
        if results:
            return results
        return fallback_search(conn, scope, query, limit)
    finally:
        conn.close()
