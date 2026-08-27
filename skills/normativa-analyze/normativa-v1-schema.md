# `normativa.v1.json` — schema spec

Machine-readable envelope produced by `/normativa-analyze` alongside the markdown report. Consumed by `/normativa-informe` (HTML report renderer). End users typically invoke both via the `/normativa` dispatcher.

The schema id (`estudio-local.normativa.v1`) and filename suffix (`.normativa.v1.json`) intentionally preserve the historical `normativa` token — they are versioned data contracts, decoupled from the skill name. Renaming the skill (`/normativa` → `/TONE` → `/normativa` → `/normativa-analyze`, etc.) does not bump the schema.

## Conventions

- **`schema` field** is `estudio-local.normativa.v1`. Bump to `.v2` only on breaking changes; additive fields stay v1.
- **Numbers** are SI units (m, m², %). Integers where natural; floats where decimals matter (e.g. `altura_m: 13.6`).
- **`null` vs missing**: prefer `null` for "known-unknown" (data exists but value not applicable); omit the key only when the concept doesn't apply.
- **Spanish-language strings** for headlines, programa, plazos, rationale, caveats — the report is Spanish-facing.
- **`generated_at`** is ISO-8601 UTC.

## Top-level shape

```json
{
  "schema": "estudio-local.normativa.v1",
  "generated_at": "2026-04-26T23:45:00Z",
  "skill_version": "0.1.0",

  "selection":      { ... },     // what was analyzed
  "zone":           { ... },     // resolved TONE zone + per-zone tipologias catalog
  "scenarios":      [ ... ],     // applicable scenarios in evaluation order
  "recommendation": { ... },     // pick one scenario + rationale
  "caveats":        [ ... ],     // free-form warnings (data quality, assumptions)
  "sources":        { ... }      // provenance for the analysis
}
```

## `selection`

```json
{
  "padrones":           ["130", "131", "132"],
  "locality":           "la-juanita",
  "locality_name":      "José Ignacio – La Juanita",
  "regimen":            "comun",     // "comun" | "ph" | "otro" | "mixed"
  "area_total_m2":      13050,
  "frente_estimado_m":  90,          // longest contiguous edge if multi-lot
  "adjacent":           true,        // false = non-contiguous selection
  "lots": [
    { "padron": "130", "manzana": "045", "area_m2": 4350, "frente_m": 30, "regimen": "comun" },
    { "padron": "131", "manzana": "045", "area_m2": 4350, "frente_m": 30, "regimen": "comun" },
    { "padron": "132", "manzana": "045", "area_m2": 4350, "frente_m": 30, "regimen": "comun" }
  ]
}
```

## `zone`

```json
{
  "code":         "2.1",
  "name":         "Amanzanado",
  "decreto":      "Dto. 3970/2017",
  "data_quality": "verified",      // "verified"|"partial"|"estimated"|"pending"|"conditional"
  "tipologias_catalog": [
    {
      "codigo":     "vivienda_unifamiliar",
      "nombre":     "Vivienda unifamiliar",
      "altura_m":   7,
      "FOS_pct":    50,
      "FOT_pct":    80,
      "thresholds": { "area_min_m2": 300, "frente_min_m": 12 },
      "retiros":    { "frontal_m": 4, "lateral_m": 3, "fondo_m": 5, "entre_volumenes_m": null }
    }
    // ... bloque_bajo, bloque_medio, etc.
  ],
  "retiros_zone":   { "frontal_m": 4, "lateral_m": 3, "fondo_m": 5 },
  "special_rules": [
    "Frente sobre rambla: gálibo de 4 m sobre el plano de fachada"
  ]
}
```

`tipologias_catalog` is the FULL list of tipologías defined for the zone — applicability per scenario lives in `scenarios[]`.

## `scenarios`

Array of evaluated scenarios. Conventional ordering: A (individual lots) → B (apareadas / party-wall) → C (englobamiento — unified). Each scenario is self-contained:

```json
{
  "id":             "C1",
  "label":          "Englobamiento — Bloque Medio",
  "headline":       "13.050 m² edificables, +480% sobre desarrollo individual",
  "applicable":     true,
  "tipologia": {
    "codigo":  "bloque_medio",
    "nombre":  "Bloque Medio"
  },
  "envelope": {
    "FOS_pct":              50,
    "FOT_pct":              290,
    "altura_m":             28,
    "viviendas_estimadas":  96,
    "area_edificable_m2":   13050,
    "area_ocupacion_m2":    6525
  },
  "retiros": {
    "frontal_m":          4,
    "lateral_m":          3,
    "fondo_m":            5,
    "entre_volumenes_m":  6
  },
  "tipologias_habilitadas": ["bloque_bajo", "bloque_medio"],
  "programa":  "Aprox. 96 unidades de 80 m² (3 dorm) o 120 unidades de 60 m² (2 dorm)…",
  "plazos":    "Permiso de construcción ~6–9 meses; englobamiento previo ~3 meses…",
  "notes":     "Frente union de 90 m supera el mínimo de 30 m. FOS 50% × 13.050 = 6.525 m² ocupación.",
  "sketch":    "       ┌──────────────────────────────┐\n       │      Fondo · 5 m              │\n  L 3  │   ┌────────────────────────┐   │  L 3\n       │   │   ZONA EDIFICABLE      │   │\n       │   │   FOS 50% · 6.525 m²   │   │\n       │   │   FOT 290% · 13.050 m² │   │\n       │   └────────────────────────┘   │\n       │      Frente · 4 m              │\n       └──────────────────────────────┘\n                       ↑ frente"
}
```

`sketch` is an OPTIONAL string carrying an ASCII envelope diagram for this scenario. When present, `/normativa-informe` renders it inside a `<pre>` block on page 3 (Detalle del escenario recomendado). Conventions:

- **Orient with frente at the bottom** so the page reader sees what they'd see standing on the street.
- Use box-drawing characters (`┌─┐│└┘`) — Geist Mono renders them correctly.
- Show retiros labeled by side (Frente, Fondo, Lateral 1/2 with their meters).
- Inside the inner rectangle: name the buildable zone and headline FOS / FOT figures.
- Keep total width ≤ 60 columns so it fits the print page without wrapping.
- Use `\n` to separate lines — JSON requires escaped newlines.
- Include sketches for every `applicable: true` scenario; the report only displays the recommended one but downstream readers may want the full set.

When a tipología does NOT apply (lot too small, etc.), still include the scenario with `applicable: false` and a `reason` field — `/normativa-informe` shows it greyed out. Omit `sketch` for non-applicable scenarios.

## `recommendation`

```json
{
  "scenario_id":              "C1",
  "rationale":                "El englobamiento de los 3 padrones desbloquea Bloque Medio (área mín 1.000 m², frente mín 30 m), maximizando m² edificables.",
  "uplift_vs_individual_pct": 480,
  "tradeoffs": [
    "Englobamiento requiere fusión catastral (~3 meses)",
    "Pérdida de 3 padrones independientes — menos flexibilidad de venta por etapas"
  ]
}
```

Bias by **m² yield** by default. Override only when explicit constraints kill the high-yield path (régimen PH, special_rule overrides, etc.) — explain in `rationale`.

## `caveats`

Free-form Spanish strings, one per line. Keep ≤ 200 chars each.

```json
[
  "Frente estimado a partir de la unión geométrica — verificar con plano de obra.",
  "data_quality=verified para zona 2.1; revisar special_rules manualmente."
]
```

## `sources`

```json
{
  "tone_zones":    "skills/normativa-analyze/datos/tone-zones.json",
  "decretos":      ["Dto. 3970/2017"],
  "last_updated":  "2026-03-15",
  "map_url":       "https://estudio-local.com/mapa?padron=130,131,132&loc=la-juanita"
}
```

- `last_updated` — date of the most recent decreto incorporated into `tone-zones.json` (not the date of *this* analysis — that's `generated_at`).
- **`map_url`** — REQUIRED string pointing to the parcel(s) on the Mapa app. Always include it. The Mapa is the canonical visual back-reference for the lot under analysis; without this link the report leaves the reader with no way to inspect geometry or neighbors. URL pattern: `https://estudio-local.com/mapa?padron={comma-joined-padrones}&loc={locality-slug}`. Use the same locality slug that goes into `selection.locality`. For multi-padrón selections, comma-join the padrones in the same order as `selection.padrones[]`.

## Validation

`/normativa-analyze` MUST write a valid envelope on every run AND MUST run `normativa-v1-validate.py` against the output before declaring done. The validator (pure stdlib, ships next to this schema) refuses malformed envelopes with concrete per-field errors so you can fix them deterministically instead of trial-and-error against `/normativa-informe`.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/normativa-analyze/normativa-v1-validate.py <output-path>
```

Minimum required keys:

- `schema`, `generated_at`, `skill_version`
- `selection.padrones`, `selection.locality`, `selection.area_total_m2`
- `zone.code`, `zone.data_quality`
- `scenarios` (at least one entry, even if just `applicable: false`)
- `recommendation.scenario_id` (or `null` if no applicable scenario)
- `caveats` (empty array OK)
- `sources.map_url` (string — link to the parcel on the Mapa app, see `sources` section above)

`/normativa-informe` refuses to render if any required key is missing.

## Strict types & common pitfalls

These mistakes silently produce broken output (the renderer crashes or shows `—` instead of real values). The validator catches them all — but knowing them up front saves a round trip:

| Field | Type | Wrong | Right |
|---|---|---|---|
| `selection.padrones` | array of **strings** | `[130, 131, 132]` | `["130", "131", "132"]` |
| `selection.lots[].padron` | **string** (must match an entry in `selection.padrones`) | `130` | `"130"` |
| `selection.area_total_m2`, `selection.lots[].area_m2`, `selection.lots[].frente_m` | **number** | `"13050"` | `13050` |
| `selection.adjacent` | **boolean** | `"true"` | `true` |
| `selection.regimen` and `selection.lots[].regimen` | one of `comun \| ph \| otro \| mixed` | `"common"`, `"PH"` | `"comun"`, `"ph"` |
| `zone.data_quality` | one of `verified \| partial \| estimated \| pending \| conditional` | `"good"`, `"high"` | `"verified"` |
| `scenarios[].applicable` | **boolean** | `"true"`, `1` | `true` |
| `scenarios[].envelope.{FOS_pct, FOT_pct, altura_m, area_edificable_m2, area_ocupacion_m2, viviendas_estimadas}` | **number** (no units, no `%` suffix) | `"50%"`, `"13.6 m"` | `50`, `13.6` |
| `scenarios[].retiros.{frontal_m, lateral_m, fondo_m, entre_volumenes_m}` | **number** or `null` | `"3 m"` | `3` |
| `recommendation.scenario_id` | **string from `scenarios[].id`** or `null` | `"recommended"`, `0` | `"C1"` |
| `generated_at` | ISO-8601 UTC string | `"April 26, 2026"` | `"2026-04-26T23:45:00Z"` |

**Structural pitfalls** (shape, not type):

- Each scenario MUST nest envelope fields under `envelope: { ... }`, NOT flatten them at the scenario level. The renderer reads `scenario.envelope.FOS_pct`, not `scenario.FOS_pct`.
- Same for `tipologia: { codigo, nombre }` and `retiros: { ... }` — keep them nested.
- When `applicable: false`, include `reason` (string), not an empty `envelope`.
- `recommendation.scenario_id` must equal an existing `scenarios[].id` exactly. Use `null` when no scenario applies (rural lots, all thresholds fail).
- `scenarios[].sketch`, when present, must be a string (multi-line via `\n`). Do not emit an array of lines or a markdown code block — the renderer wraps the raw string in `<pre>` and renders verbatim.

## Versioning

- **v1**: this document.
- **Additive changes** (new optional fields): stay v1, document under "Changelog".
- **Breaking changes** (removed/renamed fields, changed types): bump to v2, ship side-by-side support in `/normativa-informe` for one minor release, then drop v1.

## Sister envelope: `selection.v1.json` (optional input)

When `/normativa-analyze` is invoked with `--input <path>`, the file is a `selection.v1.json` envelope that pre-resolves the parcel selection. Shape:

```json
{
  "schema":         "estudio-local.selection.v1",
  "generated_at":   "2026-04-26T22:30:00Z",
  "padrones":       ["130", "131", "132"],
  "locality":       "la-juanita",
  "locality_name":  "José Ignacio – La Juanita",
  "regimen":        "comun",
  "area_total_m2":  13050,
  "frente_estimado_m": 90,
  "adjacent":       true,
  "lots": [
    {
      "padron":   "130",
      "manzana":  "045",
      "area_m2":  4350,
      "regimen":  "comun",
      "frentes": [
        {
          "edges":         [4, 5],
          "length_m":      82.3,
          "distance_m":    3.1,
          "calle_idcalle": 22549,
          "calle_nombre":  "AVENIDA FRANCIA",
          "calle_tipo":    "CALLE",
          "calle_fuente":  "INTENDENCIA_DE_MALDONADO"
        },
        {
          "edges":         [7],
          "length_m":      30.0,
          "distance_m":    11.4,
          "calle_idcalle": 22612,
          "calle_nombre":  "CALLE 1",
          "calle_tipo":    "CALLE",
          "calle_fuente":  "OSM"
        }
      ]
    }
  ],
  "zone_hint":      { "code": "2.1", "data_quality": "verified" }
}
```

**Authority rules for `/normativa` when consuming this:**
- `padrones`, `locality`, `area_total_m2`, `regimen`, `lots[]` are **authoritative** — copy verbatim into the output's `selection.*`.
- `zone_hint.code` is a **suggestion** — `/normativa` should still resolve the zone independently from `tone-zones.json` and only use the hint if its own resolution is ambiguous.
- **`lots[].frentes[]` is authoritative** when present — pre-computed by the Mapa app via parcel-polygon × IDE-calles intersection in UTM 21S meters. Do NOT re-derive frente from polygon dimensions if this field is present. When multiple frentes are listed, apply the TONE "frente principal" rule:
  1. **Rank by `calle_tipo` hierarchy:** `Ruta > CALLE > PASAJE > PASAJE INTERNO > PEATONAL > CALLE INTERNA > VIRTUAL > SENDERO`. Higher tier = higher priority for the principal frente.
  2. **Within `CALLE`:** parse `calle_nombre` for `"AVENIDA"`/`"AVDA"`/`"BOULEVARD"`/`"BLVD"` prefixes — these outrank plain calles per the TONE jerarquía vial.
  3. **Tiebreaker:** longest `length_m`.
  4. Cite the chosen calle by name in the analysis (`"Frente principal: AVENIDA FRANCIA, 82,3 m sobre la cara N del padrón"`); list secondary frentes in caveats so the reader can verify.
- **`selection.frente_estimado_m`** (top-level) is best-effort — superseded by `lots[].frentes[].length_m` when present.
- When `lots[].frentes` is empty `[]`, the parcel didn't intersect any cataloged calle within 15m. This typically means: (a) area=0 placeholder cadastral record, (b) interior parcel of a manzana with no street access, or (c) IDE catalog gap for that subdivision. Flag in caveats and fall back to polygon-dimension heuristic only as a last resort.

This input mode is optional. `/normativa` works equally well with padron lists or pasted GIS JSON (see SKILL.md).

## Changelog

- **v1.0** (2026-04): initial schema.
