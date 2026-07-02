---
name: llm-wiki-generator
description: Build or query a standalone Obsidian-compatible LLM Wiki from PDF, DOCX, PPTX, XLSX, and TXT sources. Use when you need to convert files to Markdown, preview archive updates, write structured wiki pages, index the stable knowledge base, or answer questions from the wiki without depending on BA-Agent code.
---

# LLM Wiki Generator

## Overview

Use this skill when you want a fully standalone LLM Wiki workflow:

- convert common files into Markdown with `markitdown`
- preview what knowledge updates should be archived
- apply those updates into an Obsidian-compatible wiki vault
- build a local searchable index
- answer questions from stable or draft wiki knowledge

This skill does not depend on BA-Agent code, does not use `WikiUpdatePlan`, and does not require an approval step. It shows archive updates first, then writes pages directly when you run `apply`.

## Supported Inputs

The archive pipeline accepts exactly these five file types:

- `PDF`
- `DOCX`
- `PPTX`
- `XLSX`
- `TXT`

## Workflow

### 1. Initialize a standalone vault

Run:

```bash
cp skill/llm-wiki-generator/.env.example skill/llm-wiki-generator/.env
.venv/bin/python skill/llm-wiki-generator/scripts/cli.py init
```

This creates an Obsidian-compatible structure under `WIKI_ROOT`:

- `10-raw/`
- `20-wiki/sources/`
- `20-wiki/entities/`
- `20-wiki/concepts/`
- `20-wiki/synthesis/`
- `20-wiki/conflicts/`
- `20-wiki/prd-patterns/`
- `20-wiki/index.md`
- `20-wiki/log.md`

### 2. Convert a file to Markdown

Run:

```bash
.venv/bin/python skill/llm-wiki-generator/scripts/cli.py convert path/to/file.pdf
```

Use this when you only want the Markdown output from `markitdown`.

### 3. Preview archive updates

Run:

```bash
.venv/bin/python skill/llm-wiki-generator/scripts/cli.py show-updates path/to/file.docx --source-type team_history
```

This step uses:

- `markitdown` for conversion
- an OpenAI-compatible model if configured
- a deterministic fallback if no model is configured

Output is an `ArchivePreview` that shows what pages would be created or updated, their status, confidence, evidence, and why they matter.

### 4. Apply archive updates

Run:

```bash
.venv/bin/python skill/llm-wiki-generator/scripts/cli.py apply path/to/file.docx --source-type team_history
```

The writer is deterministic. It:

- copies the raw source into `10-raw/<source_type>/`
- writes or updates wiki pages under `20-wiki/`
- updates `20-wiki/index.md`
- appends to `20-wiki/log.md`

### 5. Build the local index

Run:

```bash
.venv/bin/python skill/llm-wiki-generator/scripts/cli.py index
```

This builds a local SQLite index for wiki retrieval.

### 6. Answer from the wiki

Run:

```bash
.venv/bin/python skill/llm-wiki-generator/scripts/cli.py answer "当前已知的业务约束是什么？"
```

Default scope is `stable`. You can override it:

```bash
.venv/bin/python skill/llm-wiki-generator/scripts/cli.py answer "团队历史里提到的设计思路有哪些？" --scope stable-draft
```

## Source Boundary Rules

- `business_fact`: can become factual business knowledge if evidence is strong and there is no conflict
- `industry_practice`: can become `source`, `synthesis`, or `prd_pattern`; it must not become customer fact
- `team_history`: defaults to `draft`
- `feedback`: defaults to `draft`
- conflicts never overwrite older knowledge; they become `20-wiki/conflicts/`

## Environment

Copy `.env.example` and set:

- `LLM_BASE_URL`
- `LLM_API_KEY`
- `LLM_MODEL`
- `WIKI_ROOT`
- `WIKI_INDEX_DB`

The LLM endpoint must support the OpenAI chat-completions format.

## Resources

### scripts/

Python implementation for conversion, preview, archive, indexing, and answer flows.

### references/

Prompt contracts, source-boundary rules, and vault layout notes for this skill.
