# ArchivePreview Schema

`ArchivePreview` is the shared archive contract for host-model skill mode and standalone CLI/API mode.
In host-model mode, Claude Code, Codex, or OpenCode generates this JSON from `convert --as-json`, then `apply-preview` validates and writes it.
In standalone CLI/API mode, `archive`, `show-updates`, and `apply` generate the same shape through a configured OpenAI-compatible LLM.
`team_history` may produce `prd_pattern`, but those updates are enforced as `draft`.

```json
{
  "title": "Document title",
  "source_type": "business_fact | industry_practice | team_history | feedback",
  "source_path": "relative/or/input/path",
  "summary": "Short explanation",
  "updates": [
    {
      "action": "create_or_update | conflict | deprecate",
      "page_type": "source | entity | concept | synthesis | conflict | prd_pattern",
      "title": "Page title",
      "status": "stable | draft | conflict | deprecated",
      "summary": "Short summary",
      "body": "Markdown content",
      "tags": ["tag-a"],
      "links": ["[[Other Page]]"],
      "confidence": "low | medium | high",
      "evidence": [
        {
          "snippet": "Quoted or summarized evidence",
          "reason": "Why it supports the update"
        }
      ],
      "reason": "Why this update should exist"
    }
  ]
}
```
