# LLM Prompts

## Archive Preview System Prompt

The archive preview model should:

- read the converted Markdown source
- identify reusable wiki knowledge
- separate facts, patterns, history, and conflicts
- return strict JSON only
- never write files
- never emit absolute local paths or secrets
- honor source-boundary rules

## Answer System Prompt

The answer model should:

- answer only from retrieved wiki documents
- distinguish stable knowledge from draft knowledge
- cite page titles
- say when evidence is insufficient
