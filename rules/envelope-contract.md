# Envelope contract — strict types

The `*.normativa.v1.json` envelope is the contract between `/normativa-analyze` (producer) and `/normativa-informe` (consumer). It also flows through any LLM that the user pastes the envelope into. The full schema spec is `skills/normativa-analyze/normativa-v1-schema.md`; this rule is the **enforcement summary** that every skill cites when emitting or consuming envelopes.

The validator (`skills/normativa-analyze/normativa-v1-validate.py`) is the executable form of this rule. If you change strict types here, change the validator + schema doc + canonical example in lockstep.

## Top-level shape

```
schema (string, == "estudio-local.normativa.v1")
generated_at (string, ISO-8601 UTC)
skill_version (string)
selection (object)
zone (object)
scenarios (array of objects)
recommendation (object)
caveats (array of strings)
sources (object, includes required map_url)
```

## Strict types — the renderer crashes if these are wrong

| Field | Type | Wrong | Right |
|---|---|---|---|
| `selection.padrones` | array of **strings** | `[130, 131, 132]` | `["130", "131", "132"]` |
| `selection.lots[].padron` | **string** (matches `selection.padrones`) | `130` | `"130"` |
| `selection.area_total_m2`, `lots[].area_m2`, `lots[].frente_m` | **number** | `"13050"` | `13050` |
| `selection.adjacent` | **boolean** | `"true"` | `true` |
| `selection.regimen`, `lots[].regimen` | one of `comun \| ph \| otro \| mixed` | `"common"`, `"PH"` | `"comun"`, `"ph"` |
| `zone.data_quality` | one of `verified \| partial \| estimated \| pending \| conditional` | `"good"` | `"verified"` |
| `scenarios[].applicable` | **boolean** | `"true"`, `1` | `true` |
| `scenarios[].envelope.{FOS_pct, FOT_pct, altura_m, area_edificable_m2, area_ocupacion_m2, viviendas_estimadas}` | **number** (no units, no `%`) | `"50%"`, `"13.6 m"` | `50`, `13.6` |
| `scenarios[].retiros.{frontal_m, lateral_m, fondo_m, entre_volumenes_m}` | **number** or `null` | `"3 m"` | `3` |
| `scenarios[].sketch` | **string** with `\n` line breaks (or omitted when not applicable) | array of lines | `"┌──┐\n│ZE│\n└──┘"` |
| `recommendation.scenario_id` | **string from `scenarios[].id`** or `null` | `"recommended"`, `0` | `"C1"` |
| `generated_at` | ISO-8601 UTC string | `"April 26, 2026"` | `"2026-04-26T23:45:00Z"` |
| `sources.map_url` | **required string** — link to parcel(s) on the Mapa | omitted | `"https://estudio-local.com/mapa?padron=130,131,132&loc=la-juanita"` |

## Structural rules

- Each scenario nests envelope fields under `envelope: { ... }` — do NOT flatten them onto the scenario. Same for `tipologia: { codigo, nombre }` and `retiros`.
- When `applicable: false`, include `reason` (string) — omit `envelope`/`tipologia`/`retiros`/`sketch`.
- For rural lots: one scenario, `applicable: false`, `reason: "Rural — 50.000 m²/vivienda mínimo"`, and `recommendation.scenario_id: null`.
- When invoked with `--input selection.v1.json`, **echo the input's `selection.*` values verbatim** into the output. Do not re-derive padrones/locality/area/régimen.
- `zone.tipologias_catalog` is the FULL list of tipologías for the zone. Per-scenario `applicable`/`tipologias_habilitadas` say which are reachable for *this* selection.
- `sources.map_url` is required. Pattern: `https://estudio-local.com/mapa?padron=<comma-joined>&loc=<locality-slug>`. Use the same locality slug that goes into `selection.locality`, same padron order as `selection.padrones[]`.
- Bias `recommendation` by **m² edificable yield** unless an explicit constraint kills the high-yield path (régimen PH blocking englobamiento, special_rule overrides, etc.).

## Validation is mandatory

Before declaring an analysis complete, run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/normativa-analyze/normativa-v1-validate.py <output-path>
```

Exit code 0 + `ok ...` line on stdout = pass. Anything else = fix and re-run. The validator prints concrete per-field errors (e.g. `selection.padrones[0]: expected string, got int (130)`); read each one before patching.
