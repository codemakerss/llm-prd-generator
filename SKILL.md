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

If `initialized=false`, do not silently choose defaults. Ask these questions in order, one at a time:

1. Ask whether the user wants to initialize now. Stop if they decline.
2. Ask whether Wiki folders should use Chinese (`zh`) or English (`en`) names.
3. Ask for the local Wiki Root path.
4. Show the selected language, normalized absolute path, and directory layout; ask for final confirmation.
5. Run one of:

```bash
.venv/bin/python skill/llm-prd-generator/scripts/cli.py bootstrap-init /absolute/or/relative/wiki-root --language zh
.venv/bin/python skill/llm-prd-generator/scripts/cli.py bootstrap-init /absolute/or/relative/wiki-root --language en
```

This writes `WIKI_ROOT`, `WIKI_INDEX_DB`, and `WIKI_LAYOUT_LANGUAGE` into `.env` and creates the vault structure.
By default, `WIKI_INDEX_DB` is stored inside `WIKI_ROOT` as `index.sqlite3`.

The language is fixed for an initialized Wiki. Never rename or migrate an existing layout automatically. If both `20-wiki` and `20-知识库` exist, stop and report the conflict.

Immediately after successful initialization, ask:

> 是否有文档或知识需要导入？请提供文件或目录路径。

Before importing, ask the user to classify the files as `business_fact`（业务知识）, `team_history`（团队历史 PRD）, `industry_practice`（业界 PRD）, or `feedback`（用户反馈）. Do not infer the category silently from a filename. A batch may share one category; ask per file when the user says it contains mixed sources.

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

After every import, report the input and source type, raw copy path, every created/updated wiki page with type/status/tags/summary/evidence, Pattern result and path, index location/count, and any skipped or failed files. Use `--as-json` when a structured receipt is needed.

For `team_history` and `industry_practice`, preserve the normal source/concept/synthesis extraction and also extract a reusable PRD Pattern when the document contains reusable questions, section structure, acceptance approaches, review rules, or risk checks. Team-history patterns remain `draft`; industry patterns may be `stable` or `draft`. If no reusable method exists, explicitly report that no Pattern was found. Never manufacture an empty Pattern. `business_fact` must not produce a Pattern.

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
- reads every Markdown file under the configured wiki directory (`20-wiki/` or `20-知识库/`)
- parses `tags`, `page_type`, `status`, `source_type`, `confidence`, links, and body text
- scores relevance by tag overlap, title/body matches, page type, source type, and status
- builds three context packs:
  - `Evidence Pack`: `business_fact`; may support project facts
  - `Template Guidance`: `industry_practice` and `prd_pattern`; may shape structure and questions. Stable patterns are strong guidance; draft patterns are weak guidance and require business confirmation.
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
- pages in the configured PRD Pattern directory may influence structure and questioning, but must not create business facts.
- `team_history` is historical style/reference unless the business user confirms it still applies.

## OpenSpec PRD Generation

Only run after `prd-chat` reports 100% completeness:

```bash
.venv/bin/python skill/llm-prd-generator/scripts/cli.py propose-prd "商家刷单识别系统"
```

By default, `propose-prd` uses `WIKI_ROOT` as the OpenSpec project root. Initialize OpenSpec in the wiki root first:

```bash
cd <WIKI_ROOT>
openspec init --tools codex --profile core
```

Use `--project-root` only when you intentionally want the artifacts written to a separate OpenSpec project.

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

By default, successful generation automatically learns or updates a reusable PRD Pattern from the final `prd.md`, session answers, evidence, existing patterns, and related wiki pages. The pattern is written to:

```text
<WIKI_ROOT>/20-wiki/prd-patterns/<领域>-PRD-Pattern.md
# or, for the Chinese layout:
<WIKI_ROOT>/20-知识库/PRD模式/<领域>-PRD-Pattern.md
```

Use `--no-learn-pattern` to disable this behavior for a specific generation.

To re-learn from an existing generated PRD, run:

```bash
.venv/bin/python skill/llm-prd-generator/scripts/cli.py learn-prd-pattern "商家刷单识别系统"
```

Pattern stability is automatic:

- `stable`: score is high, multiple sources support the structure, and no conflicts are found
- `draft`: useful but not sufficiently proven

Draft patterns still participate in future PRD generation, but only as structure/question hints. They must never fill business facts, rules, or metric values.

## Source Boundaries

- `business_fact`: can become factual product knowledge if evidence is strong and there is no conflict
- `industry_practice`: can become `source`, `synthesis`, or `prd_pattern`; never customer truth
- `team_history`: can become `source`, `concept`, `synthesis`, or `prd_pattern`; defaults to `draft`
- `feedback`: defaults to `draft`
- `generated_prd_pattern`: learned reusable PRD structure; may be draft or stable based on automatic stability scoring
- conflicts never overwrite older knowledge; they belong in the configured conflict directory

## Environment

Copy `.env.example` and set:

- `LLM_BASE_URL`
- `LLM_API_KEY`
- `LLM_MODEL`
- `WIKI_ROOT`
- `WIKI_INDEX_DB`
- `WIKI_LAYOUT_LANGUAGE` (`zh` or `en`)

Host-model skill usage does not require model settings such as `LLM_API_KEY`; `.env` is still needed for wiki paths. Standalone CLI archive mode can use an OpenAI-compatible API configured in `.env`.

## Resources

### scripts/

Python implementation for conversion, archive preview/application, indexing, search, answer, PRD questioning, completeness gating, and OpenSpec artifact generation.

### references/

Prompt contracts, source-boundary rules, and vault layout notes.
