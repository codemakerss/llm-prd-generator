---
name: llm-prd-generator
description: Generate evidence-backed PRDs and OpenSpec change artifacts from an Obsidian-compatible LLM Wiki. Use when you need to archive product knowledge, recall raw/wiki evidence, ask business questions until PRD completeness reaches 100%, and only then write proposal/spec/design/tasks/prd artifacts.
---

# LLM PRD Generator

## What This Skill Does

Use this skill to turn archived product knowledge into implementation-ready PRDs.

It supports two connected workflows:

- knowledge archiving: convert source files, use the host model or standalone API to produce archive previews, apply them into an Obsidian-compatible vault, index the vault, and answer from stable/draft knowledge
- PRD generation: read all wiki knowledge, retrieve evidence by tags and content, ask one business question at a time, enforce a 100% PRD completeness gate, then generate OpenSpec artifacts

The PRD workflow is mandatory. Do not generate PRD or OpenSpec artifacts directly from a vague topic. Always run the business-question loop first.

## Initialization Guard

Before archive, indexing, answer, or PRD work, check initialization:

```bash
.venv/bin/python skill/llm-prd-generator/scripts/cli.py bootstrap-status --as-json
```

If `initialized=false`, ask whether to initialize, ask for the wiki vault path, confirm it, then run:

```bash
.venv/bin/python skill/llm-prd-generator/scripts/cli.py bootstrap-init /absolute/or/relative/wiki-root
```

This writes `WIKI_ROOT` and `WIKI_INDEX_DB` into `.env` and creates the vault structure.

## Supported Source Files

The archive pipeline accepts:

- `PDF`
- `DOCX`
- `PPTX`
- `XLSX`
- `TXT`
- `MD`
- `Markdown`

Markdown files are read as-is from `.md` and `.markdown` files.

## Knowledge Workflow

Initialize a vault:

```bash
cp skill/llm-prd-generator/.env.example skill/llm-prd-generator/.env
.venv/bin/python skill/llm-prd-generator/scripts/cli.py init
```

Convert a source file:

```bash
.venv/bin/python skill/llm-prd-generator/scripts/cli.py convert path/to/file.pdf
```

For host-model archiving, use structured conversion output:

```bash
.venv/bin/python skill/llm-prd-generator/scripts/cli.py convert path/to/file.pdf --as-json
```

Then use the current host model to generate strict `ArchivePreview` JSON from the converted Markdown, write that JSON to a temporary preview file, and apply it:

```bash
.venv/bin/python skill/llm-prd-generator/scripts/cli.py apply-preview path/to/file.docx --preview-file /tmp/archive-preview.json
```

`apply-preview` validates the preview, enforces source-boundary rules, writes raw/wiki files, and rebuilds the retrieval index by default. Use `--no-index` only when batching many files.

Standalone API archive mode is available when `.env` contains an OpenAI-compatible model:

```bash
.venv/bin/python skill/llm-prd-generator/scripts/cli.py archive path/to/file.docx --source-type team_history
```

Optional preview-only mode:

```bash
.venv/bin/python skill/llm-prd-generator/scripts/cli.py show-updates path/to/file.docx --source-type team_history
```

Build the local index:

```bash
.venv/bin/python skill/llm-prd-generator/scripts/cli.py index
```

Search deterministically:

```bash
.venv/bin/python skill/llm-prd-generator/scripts/cli.py search "当前已知的业务约束是什么？" --scope stable-draft --as-json
```

Answer from the wiki:

```bash
.venv/bin/python skill/llm-prd-generator/scripts/cli.py answer "当前已知的业务约束是什么？" --scope stable-draft
```

## PRD Business-Question Loop

Start every PRD with `prd-chat`:

```bash
.venv/bin/python skill/llm-prd-generator/scripts/cli.py prd-chat "商家刷单识别系统"
```

The command:

- loads or creates a PRD session for the topic
- reads every Markdown file under `20-wiki/`
- parses `tags`, `page_type`, `status`, `source_type`, `confidence`, links, and body text
- scores relevance by tag overlap, title/body matches, page type, source type, and status
- builds three context packs:
  - `Evidence Pack`: `business_fact`; may support project facts
  - `Template Guidance`: `industry_practice` and `prd_pattern`; may shape structure and questions
  - `Team Style Pack`: `team_history` and `feedback`; may guide language, granularity, and review style
- evaluates PRD completeness using BA-Agent-style dimensions
- asks exactly one highest-priority business question if completeness is below 100%

Answer the current question with:

```bash
.venv/bin/python skill/llm-prd-generator/scripts/cli.py prd-chat "商家刷单识别系统" --answer "目标用户：风控运营、商家治理专员和风控策略负责人。"
```

After each answer, the skill updates the structured PRD state, re-reads the wiki, re-runs retrieval, and re-calculates completeness.

## PRD Completeness Gate

The loop stops only when:

- all PRD dimensions have values
- traceable business evidence exists
- all knowledge conflicts have been resolved by the business user
- score is exactly `100%`

Completeness dimensions:

- business problem and goal
- target users
- stakeholders and decision authority
- success metric
- MVP scope
- non-goals
- user workflows and exception paths
- business rules and permissions
- data and integrations
- non-functional requirements
- risks and dependencies
- acceptance criteria
- rollout and feedback
- traceable business evidence
- unresolved knowledge conflicts

Rules:

- Ask one question per turn, never a bulk questionnaire.
- Resolve knowledge conflicts before ordinary missing fields.
- If business evidence is missing, ask for interview notes, policy, metrics, reports, or owner confirmation.
- `prd-patterns/` pages may influence structure and questioning, but must not create business facts.
- `team_history` is historical style/reference unless the business user confirms it still applies.

## OpenSpec PRD Generation

Only run after `prd-chat` reports 100% completeness:

```bash
.venv/bin/python skill/llm-prd-generator/scripts/cli.py propose-prd "商家刷单识别系统" --project-root /path/to/project
```

If `--change-name` is omitted, the default change directory is `<topic>-MM-DD`, for example `商家刷单识别系统-08-09`. If `--capability` is omitted, the default capability directory is the topic, for example `specs/商家刷单识别系统/spec.md`.

Behavior:

- below 100%: write nothing and return the next required business question
- missing `openspec/config.yaml`: write nothing and tell the user to run `openspec init --tools codex --profile core`
- ready and initialized: write artifacts under `openspec/changes/<change-name>/`

Generated artifacts:

- `proposal.md`
- `design.md`
- `tasks.md`
- `prd.md`
- `specs/<capability>/spec.md`

Every key requirement, metric, rule, and acceptance criterion must cite retrieved evidence.

## Source Boundaries

- `business_fact`: can become factual product knowledge if evidence is strong and there is no conflict
- `industry_practice`: can become `source`, `synthesis`, or `prd_pattern`; never customer truth
- `team_history`: can become `source`, `concept`, `synthesis`, or `prd_pattern`; defaults to `draft`
- `feedback`: defaults to `draft`
- conflicts never overwrite older knowledge; they belong in `20-wiki/conflicts/`

## Environment

Copy `.env.example` and set:

- `LLM_BASE_URL`
- `LLM_API_KEY`
- `LLM_MODEL`
- `WIKI_ROOT`
- `WIKI_INDEX_DB`

Host-model skill usage does not require model settings such as `LLM_API_KEY`; `.env` is still needed for wiki paths. Standalone CLI archive mode can use an OpenAI-compatible API configured in `.env`.

## Resources

### scripts/

Python implementation for conversion, archive preview/application, indexing, search, answer, PRD questioning, completeness gating, and OpenSpec artifact generation.

### references/

Prompt contracts, source-boundary rules, and vault layout notes.
