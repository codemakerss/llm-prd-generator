# LLM Wiki Generator

An LLM-first document ingestion and retrieval workflow for building a structured, local, Obsidian-compatible LLM Wiki.

LLM Wiki Generator turns raw source files into traceable wiki knowledge through a host-model pipeline: `convert -> host LLM -> apply-preview -> search -> host LLM answer`.
When installed as a skill, Claude Code, Codex, or OpenCode uses its own model to understand documents, generate archive content, and answer questions. The Python CLI only handles deterministic operations: conversion, validation, import, indexing, and retrieval.

## Why This Exists

Most document-driven knowledge workflows break down in one of two ways:

- raw files remain unstructured and difficult to reuse
- LLM-based ingestion writes opaque knowledge that is hard to recall later

This project takes a structured path.

Instead of treating source files as a chat substrate, it treats them as inputs to an LLM-backed knowledge compiler:

1. convert source material into normalized text
2. let the host LLM extract structured archive content
3. let the CLI validate and import that content into a vault
4. let the CLI build a retrieval index
5. let the host LLM answer from retrieved wiki knowledge

The goal is not just answering questions.
The goal is building a knowledge base that can keep evolving and remain searchable.

## Quick Navigation

- [Docs Navigation](#docs-navigation)
- [Workflow](#workflow)
- [First-Time Path](#first-time-path)
- [Quick Start](#quick-start)
- [Example Commands](#example-commands)
- [Vault Structure](#vault-structure)
- [Source Types](#source-types-and-boundaries)

## Docs Navigation

- [Chinese Overview](docs/README.zh-home.md)
- [Chinese Usage Guide](docs/README.zh-usage.md)
- [English Usage Guide](docs/README.en-usage.md)
- [Docs Index](docs/index.md)

## Workflow

```mermaid
flowchart TD
    A["Invoke Skill or CLI"] --> B{"Initialized?"}

    B -- "No" --> C["Ask whether to initialize now"]
    C --> D["Ask where the wiki vault should live"]
    D --> E["Confirm the chosen path"]
    E --> F["Run bootstrap-init"]
    F --> G["Persist WIKI_ROOT and WIKI_INDEX_DB into .env"]
    G --> H["Create vault directories and bootstrap files"]
    H --> I["Ask whether to provide the first document now"]

    B -- "Yes" --> J["Provide source document"]
    I --> J

    J --> K["convert --as-json"]
    K --> L["Host LLM generates ArchivePreview JSON"]
    L --> M["apply-preview validates and imports"]
    M --> P["index"]
    P --> Q["search --as-json"]
    Q --> S["Host LLM answers from retrieved docs"]

    J -. "Standalone API path" .-> R["archive"]
```

## First-Time Path

For a first-time user, the shortest useful path is:

1. install the skill or Python dependencies
2. run `bootstrap-status`
3. run `bootstrap-init` if the workspace is not initialized
4. provide the first source document
5. run `convert --as-json`
6. let Claude Code, Codex, or OpenCode generate `ArchivePreview` JSON
7. run `apply-preview` to import and index the generated archive content
8. query with `search --as-json`, then let the host LLM answer from retrieved docs

If you already know the desired vault location, you can still configure `.env` first and call `init` directly.
Host-model skill usage does not require `.env` model settings such as `LLM_API_KEY`; `.env` is only needed for wiki paths. Standalone CLI archive mode can still use an OpenAI-compatible API configured in `.env`.

## Properties

- Supports `PDF`, `DOCX`, `PPTX`, `XLSX`, and `TXT`
- Uses Claude Code, Codex, or OpenCode as the default archive/answer model when installed as a skill
- Provides deterministic CLI tools for conversion, preview application, indexing, and search
- Rebuilds the retrieval index by default after `apply-preview` or standalone `archive`
- Writes into an Obsidian-compatible vault layout
- Keeps raw sources and structured knowledge separate
- Builds a local SQLite retrieval index
- Supports stable and draft knowledge scopes
- Provides bootstrap-style initialization for first-time setup
- Persists chosen vault paths into `.env`

## Responsibility Split

Host LLM responsibilities:

- understand converted Markdown
- generate `ArchivePreview` JSON for wiki pages
- summarize and answer from retrieved wiki documents

CLI responsibilities:

- convert files to Markdown
- validate and enforce archive rules
- copy raw files into `10-raw/`
- write wiki pages into `20-wiki/`
- build the SQLite index
- retrieve local knowledge with `search`

## Quick Start

### Option A: Skill-first workflow

If your host environment supports skill installation:

```bash
npx install skill llm-wiki-generator
```

Check whether the workspace has already been initialized:

```bash
python scripts/cli.py bootstrap-status --as-json
```

If not initialized, create the vault at the chosen path:

```bash
python scripts/cli.py bootstrap-init path/to/wiki-vault
```

Once initialized, continue directly into document ingestion.

### Option B: Manual CLI workflow

Install dependencies:

```bash
pip install -r requirements.txt
```

Create the environment file:

```bash
cp .env.example .env
```

Then either inspect bootstrap status:

```bash
python scripts/cli.py bootstrap-status --as-json
```

Or initialize directly if the vault path is already configured:

```bash
python scripts/cli.py init
```

## Example Commands

Convert a file:

```bash
python scripts/cli.py convert path/to/file.pdf
```

Host-model archive flow:

```bash
python scripts/cli.py convert path/to/file.docx --as-json
```

Then Claude Code, Codex, or OpenCode generates `ArchivePreview` JSON from the converted Markdown.

Apply and index that generated archive content:

```bash
python scripts/cli.py apply-preview path/to/file.docx --preview-file /tmp/archive-preview.json
```

Host-model recall flow:

```bash
python scripts/cli.py search "What business constraints are currently known?" --scope stable-draft --as-json
```

Standalone API archive mode, optional:

```bash
python scripts/cli.py archive path/to/file.docx --source-type team_history
```

Standalone CLI answer mode, optional:

```bash
python scripts/cli.py answer "What business constraints are currently known?"
```

Build the retrieval index:

```bash
python scripts/cli.py index
```

Search the wiki deterministically:

```bash
python scripts/cli.py search "What design ideas were mentioned in team history?" --scope stable-draft --as-json
```

Standalone CLI answer with draft knowledge:

```bash
python scripts/cli.py answer "What design ideas were mentioned in team history?" --scope stable-draft
```

## Vault Structure

A typical initialized workspace looks like this:

```text
10-raw/
  business_fact/
  industry_practice/
  team_history/
  feedback/

20-wiki/
  sources/
  entities/
  concepts/
  synthesis/
  conflicts/
  prd-patterns/
  index.md
  log.md

index.sqlite3
```

## Source Types and Boundaries

Supported `source_type` values:

- `business_fact`
- `industry_practice`
- `team_history`
- `feedback`

Behavior rules:

- `business_fact` may become stable business knowledge when evidence is strong
- `industry_practice` may become patterns or synthesis, but not customer truth
- `team_history` may also produce PRD patterns from historical PRDs and team decisions, but remains `draft`
- `feedback` defaults to `draft`
- conflicts never overwrite older knowledge; they go into `20-wiki/conflicts/`

## Design Intent

This repository prefers explicit state transitions over opaque ingestion.

Key design choices:

- host-model archive and answer by default when used as a skill
- deterministic archive application
- persistent raw source capture
- local retrieval over archived markdown
- standalone OpenAI-compatible API mode remains available for CLI-only usage

The result is closer to a small knowledge compiler than a chat wrapper around files.

## Who This Is For

- developers building agent-oriented knowledge workflows
- teams that need local, inspectable, versionable knowledge artifacts
- users who want a stricter alternative to direct document chat
- individuals maintaining a structured personal wiki knowledge base

## Tech Stack

- Python
- Typer
- Rich
- Pydantic
- SQLite FTS
- host-model skill mode plus optional OpenAI-compatible API mode
- document parsers for DOCX, PPTX, XLSX, and PDF

## Learn More

Detailed usage guides live in [`docs/`](docs/).
