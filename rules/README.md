# Norma — Cross-skill rules

Shared enforcement copy that every Norma skill imports by reference. One source of truth per concern; if you edit a rule here, every skill that cites it stays in sync.

| Rule | Governs |
|------|---------|
| [`professional-disclaimer.md`](./professional-disclaimer.md) | The "Análisis indicativo, no certificación" block + `normativa:requires-disclaimer` marker contract for outputs that include zoning interpretations |
| [`envelope-contract.md`](./envelope-contract.md) | Strict types + structural rules for `selection.v1.json` and `normativa.v1.json`. Authoritative against the schema doc — diverge here at your peril |
| [`units-and-measurements.md`](./units-and-measurements.md) | SI conventions (m / m² / %), ISO-8601 dates, regimen + data_quality enums, decimal formatting (es-UY locale) |
| [`terminology.md`](./terminology.md) | Tipología codes, frente principal hierarchy, decreto citation format, locality slugs |

## How skills cite rules

A skill SKILL.md references a rule by relative path:

```markdown
See [`../../rules/professional-disclaimer.md`](../../rules/professional-disclaimer.md) for the canonical disclaimer block + marker contract.
```

The `scripts/lint.sh` walks SKILL.md files and verifies cited rule paths resolve.

## When to add a new rule

Add a new file when 2+ skills would otherwise duplicate the same enforcement copy. Don't add a rule for a concern that's load-bearing in only one skill — keep it inline.
