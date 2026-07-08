# LLM Prompts

## Archive Preview System Prompt

The archive preview model can be the current host model in Claude Code, Codex, or OpenCode, or the configured standalone CLI model. It should:

- read the converted Markdown source
- identify reusable wiki knowledge
- separate facts, patterns, history, and conflicts
- extract PRD patterns from `team_history` when historical PRDs or team decisions contain reusable requirement structures, review flows, templates, or repeated product judgments
- return strict JSON only
- never write files
- never emit absolute local paths or secrets
- honor source-boundary rules
- fail the archive flow rather than silently falling back when the model response is invalid

## Answer System Prompt

The answer model can be the current host model or the configured standalone CLI model. It should:

- answer only from retrieved wiki documents
- distinguish stable knowledge from draft knowledge
- cite page titles
- say when evidence is insufficient
