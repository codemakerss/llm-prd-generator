# Source Boundaries

- `business_fact`
  - may create `source`, `concept`, `entity`, `synthesis`
  - may be written as `stable` when evidence is strong and no conflict is detected

- `industry_practice`
  - may create `source`, `synthesis`, `prd_pattern`
  - must not be treated as customer truth or business rule

- `team_history`
  - may create `source`, `synthesis`, `concept`
  - defaults to `draft`
  - should be treated as historical reference until re-confirmed

- `feedback`
  - defaults to `draft`
  - should not become stable automatically

- `conflict`
  - does not overwrite existing pages
  - should be stored under `20-wiki/conflicts/`
