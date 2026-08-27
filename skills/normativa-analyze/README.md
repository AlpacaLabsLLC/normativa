# `/normativa-analyze` skill

Zoning envelope analyzer for lots in Maldonado, Uruguay. Paste GIS JSON from the cadastral portal — or pass a `selection.v1.json` envelope via `--input` — and get a building envelope analysis based on the TONE (Texto Ordenado de Normas de Edificación, Volumen V del Digesto Departamental).

End users typically reach this skill via the [`/normativa` dispatcher](../normativa/SKILL.md), but it's user-invocable directly too. For install instructions and the full plugin overview, see the [repo README](../../README.md).

## What this skill writes per run

| File | Format | Audience |
|------|--------|----------|
| `<basename>.md` | Markdown | Humans — full written analysis |
| `<basename>.normativa.v1.json` | JSON envelope | Machines — fed to `/normativa-informe` for the printable HTML report |

## Files in this directory

| File | Purpose |
|------|---------|
| `SKILL.md` | Instructions Claude follows when the skill runs |
| `normativa-v1-schema.md` | Spec for the `normativa.v1.json` envelope (named after the schema id — stable across skill renames) |
| `normativa-v1-validate.py` | Strict validator — `/normativa-analyze` runs this before declaring done. Same naming convention as the schema doc (script-after-schema, not script-after-skill) so renaming the skill doesn't reach in here. |
| `normativa-scenarios.py` | Pure-function engine — `applicable_tipologias(zone, area, frente)` |
| `normativa-extract-tipologias.py` | Deterministic markdown → JSON extractor (data pipeline) |
| `normativa-merge-tipologias.py` | Reviewed extractions → `tone-zones.json` merger |
| `datos/tone-zones.json` | 10 localities, 33 zones, ~91 subzones with `tipologias[]` schema (TONE-derived content; filename keeps the `tone-` prefix because the data IS TONE) |
| `datos/titulo-*.md` | Full normativa text by sector (audit trail) |
| `datos/extractions/` | Per-titulo extraction artifacts (audit trail) |
| `datos/zoning/` | Per-zone GeoJSON polygons (reference geometry, 116 files) |

## Cross-skill rules cited

- [`rules/envelope-contract.md`](../../rules/envelope-contract.md) — strict types this skill produces
- [`rules/professional-disclaimer.md`](../../rules/professional-disclaimer.md) — disclaimer + marker contract
- [`rules/units-and-measurements.md`](../../rules/units-and-measurements.md) — SI conventions
- [`rules/terminology.md`](../../rules/terminology.md) — tipología codes + frente principal hierarchy
