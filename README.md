# LLM PRD Generator

LLM PRD Generator turns archived wiki knowledge into evidence-backed PRDs and OpenSpec change artifacts.

It includes a host-model friendly wiki ingestion pipeline, but the main workflow is product-spec generation:

```text
archive knowledge -> read all wiki pages -> retrieve by tags/content -> ask business questions -> reach 100% PRD completeness -> generate OpenSpec artifacts
```

## Why This Exists

PRDs generated from a single prompt are usually incomplete. They either invent missing business facts or silently reuse stale historical assumptions.

This project takes a stricter path:

1. keep raw source files and structured wiki knowledge traceable
2. retrieve business evidence, PRD patterns, and team history separately
3. ask one business question at a time
4. block PRD generation until completeness reaches 100%
5. write OpenSpec artifacts only after evidence and conflicts are handled

## Core Workflows

### Knowledge Archiving

Use this when adding source material to the vault.

```bash
python scripts/cli.py convert path/to/file.pdf --as-json
```

Then let Claude Code, Codex, or OpenCode generate `ArchivePreview` JSON from the converted Markdown and apply it:

```bash
python scripts/cli.py apply-preview path/to/file.docx --preview-file /tmp/archive-preview.json
```

Standalone API archive mode is also available:

```bash
python scripts/cli.py archive path/to/file.docx --source-type team_history
```

Search and answer:

```bash
python scripts/cli.py index
python scripts/cli.py search "当前已知的业务约束是什么？" --scope stable-draft --as-json
python scripts/cli.py answer "当前已知的业务约束是什么？" --scope stable-draft
```

Supported source types:

- `business_fact`
- `industry_practice`
- `team_history`
- `feedback`

Supported file types:

- `PDF`
- `DOCX`
- `PPTX`
- `XLSX`
- `TXT`
- `MD`
- `Markdown`

### PRD Question Loop

Start a PRD session:

```bash
python scripts/cli.py prd-chat "商家刷单识别系统"
```

Answer the current business question:

```bash
python scripts/cli.py prd-chat "商家刷单识别系统" --answer "目标用户：风控运营、商家治理专员和风控策略负责人。"
```

Each turn:

- loads the saved session
- reads every Markdown file under `20-wiki/`
- ranks knowledge by tags, title, body, page type, source type, and status
- builds `Evidence Pack`, `Template Guidance`, and `Team Style Pack`
- uses stable PRD patterns as strong structure guidance and draft PRD patterns as weaker question/coverage hints
- evaluates PRD completeness
- returns exactly one next question if the score is below 100%

The loop stops only when every required PRD dimension is complete, business evidence exists, and all knowledge conflicts are resolved.

### OpenSpec Generation

Generate artifacts after the PRD gate reaches 100%:

```bash
python scripts/cli.py propose-prd "商家刷单识别系统"
```

By default, artifacts are written under `WIKI_ROOT/openspec/changes/`. This keeps raw sources, wiki knowledge, and generated PRDs in the same knowledge workspace.

Initialize OpenSpec in the wiki root before generation:

```bash
cd <WIKI_ROOT>
openspec init --tools codex --profile core
```

Use `--project-root` only when you intentionally want to write artifacts to another OpenSpec project.

Generated files:

```text
<WIKI_ROOT>/openspec/changes/商家刷单识别系统-MM-DD/
  proposal.md
  design.md
  tasks.md
  prd.md
  specs/商家刷单识别系统/spec.md
```

Use `--change-name` to override the default directory name, for example
`--change-name 商家刷单识别系统-08-09`.

By default, successful generation also learns a reusable PRD Pattern from the final `prd.md`, session answers, retrieved evidence, existing patterns, and related wiki pages. The learned pattern is written to:

```text
<WIKI_ROOT>/20-wiki/prd-patterns/<领域>-PRD-Pattern.md
```

Disable automatic learning when needed:

```bash
python scripts/cli.py propose-prd "商家刷单识别系统" --no-learn-pattern
```

Re-learn from an existing generated PRD:

```bash
python scripts/cli.py learn-prd-pattern "商家刷单识别系统"
```

Pattern stability is automatic:

- `stable`: enough supporting sources, no conflicts, reusable structure only
- `draft`: useful but not sufficiently proven

Draft patterns still participate in future PRD generation, but only as weak structure/question guidance. They never fill business facts or metric values.

## PRD Completeness Gate

The gate follows BA-Agent-style completeness dimensions:

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

Generation is blocked until the score is `100%`.

## Vault Structure

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

`index.sqlite3` lives inside `WIKI_ROOT` by default, so the raw sources, wiki pages, OpenSpec PRDs, learned PRD patterns, and retrieval index move together as one knowledge workspace.

## Source Boundaries

- `business_fact`: may support factual requirements when evidence is strong
- `industry_practice`: may guide patterns and structure, but not project facts
- `team_history`: may guide style and precedent, but remains draft unless confirmed
- `feedback`: draft signal by default
- `generated_prd_pattern`: learned reusable PRD structure; may be draft or stable based on automatic stability scoring
- `conflicts`: must be resolved by the business user before generation

## Quick Start

Install dependencies:

```bash
pip install -r requirements.txt
```

Create `.env`:

```bash
cp .env.example .env
```

Initialize or inspect the vault:

```bash
python scripts/cli.py bootstrap-status --as-json
python scripts/cli.py bootstrap-init path/to/wiki-vault
```

## Skill Install Name

Use the skill as:

```text
$llm-prd-generator
```

The implementation package is still named `llm_wiki_generator` internally for compatibility with the existing archive/index code.
