---
name: normativa-informe
description: Render a /normativa-analyze envelope as a printable A4 HTML report. Input is the *.normativa.v1.json envelope produced by /normativa-analyze. Invoked directly or via the /normativa dispatcher.
allowed-tools:
  - Read
  - Bash
  - Glob
user-invocable: true
---

# /normativa-informe — Printable HTML report from a `/normativa-analyze` envelope

Invoked directly (`/normativa-informe path/to/envelope.normativa.v1.json`) or routed-to by the `/normativa` dispatcher when the user asks for a printable report from an existing analysis.

## Rules this skill follows

- [`rules/envelope-contract.md`](../../rules/envelope-contract.md) — strict types this skill consumes (validates schema id; falls back to "—" cells on missing values).
- [`rules/professional-disclaimer.md`](../../rules/professional-disclaimer.md) — the rendered HTML carries the disclaimer block + `normativa:requires-disclaimer` marker via `normativa-informe-plantilla.html`.
- [`rules/units-and-measurements.md`](../../rules/units-and-measurements.md) — display formatting (es-UY locale) for all numeric cells.

## Original docstring

Take a `*.normativa.v1.json` envelope and render it as a self-contained, printable A4 HTML report. No analysis here — pure rendering. Thin wrapper around `normativa-informe-render.py` (Python stdlib only, no dependencies).

## Startup message

```
Norma Informe — printable report builder
Input:  <path-to>.normativa.v1.json
Output: <basename>.informe.html  (open in browser, print to PDF for sharing)
```

## Workflow

### Step 1: Locate the input

| Invocation | What you do |
|------------|-------------|
| `/normativa-informe <path>` | Use that path directly. |
| `/normativa-informe` (no args) | Search the current working directory for `*.normativa.v1.json` via `Glob`. If exactly one match, use it. If multiple, list them and ask which. If none, error out with a friendly message. |
| `/normativa-informe N1,N2[,…]` (padron list) | Search cwd for `*.normativa.v1.json` whose `selection.padrones` match. If found, use it; if not, tell the user to run `/normativa-analyze` first. |

### Step 2: Validate the envelope

1. File exists and is valid JSON.
2. Top-level `schema` field equals `"estudio-local.normativa.v1"`. If different (e.g. `.v2`), bail with: *"This /normativa-informe expects schema v1; the input is `<schema>`. Re-run /normativa-analyze with the latest version, or install a matching /normativa-informe."*
3. Required keys present (per `../normativa-analyze/normativa-v1-schema.md`'s "Validation" section): `selection.padrones`, `selection.locality`, `selection.area_total_m2`, `zone.code`, `scenarios` (≥ 1), `recommendation` (object), `caveats`.

Surface missing keys as a clear error pointing back at `/normativa-analyze`. Do not try to render a partial envelope.

### Step 3: Run the renderer

```bash
python3 "$CLAUDE_PLUGIN_ROOT/skills/normativa-informe/normativa-informe-render.py" <input-path> [<output-path>]
```

If `<output-path>` is omitted, the script writes alongside the input with `.informe.html` suffix. Print the script's stdout (the "wrote …" line) verbatim — don't paraphrase.

### Step 4: Confirm + how to share

```
✓ Wrote <path>.informe.html (<size> KB)

Open it: open "<path>.informe.html"
Print to PDF: open the file, ⌘P / Ctrl+P, "Save as PDF"
```

The HTML is self-contained — single file, no external assets except Google Fonts (Martian Mono) over CDN. Works offline once cached, prints cleanly to A4.

### Step 5: Record the run (telemetry)

As a final step, run the telemetry tracker:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/track.py informe_rendered
```

Fire-and-forget (1-second timeout, all errors swallowed, exit 0 always). What's sent: skill name, plugin version, anonymous machine UUID, timestamp. What's NOT sent: report content, padron numbers, file paths. Disclosed in the plugin README; opt-out with `ESTUDIO_LOCAL_TELEMETRY=0`.

## Output structure

The rendered HTML is 4 A4 pages:

| Page | Content | Source field(s) |
|------|---------|-----------------|
| 1 — Cover + lot data | Title, lot table, zone summary | `selection.lots[]`, `zone.{code,name,decreto,data_quality}` |
| 2 — Comparativa | Per-scenario grid, recommendation box | `scenarios[]`, `recommendation` |
| 3 — Detalle escenario recomendado | Envelope, retiros, tipologías habilitadas, programa, plazos | `scenarios[recommended]`, `zone.tipologias_catalog` |
| 4 — Normativa, fuentes, descargo | Decretos table, sources, caveats, disclaimer | `sources`, `caveats` |

To change the report shape: edit `normativa-informe-plantilla.html` (HTML/CSS) and / or `normativa-informe-render.py`'s `build_*` helpers — they map JSON keys to HTML chunks. No template engine; just `str.replace` on `{{PLACEHOLDER}}` markers.

## Limitations (v0.1)

- **No envelope plan SVG** — geometry rendering deferred to a future schema bump.
- **One scenario detail page** — only the recommended scenario gets a detail page. Multi-scenario detail is a v0.2 feature.

## Troubleshooting

| Error | Likely cause | Fix |
|-------|--------------|-----|
| `error: expected schema='estudio-local.normativa.v1', got '...'` | Envelope is v2 or hand-edited | Re-run `/normativa`; update the schema field |
| Missing required key | `/normativa` aborted mid-write | Re-run `/normativa`; check `normativa-v1-schema.md` for required set |
| Empty scenarios grid | All scenarios have `applicable: false` | Expected for selections that fail every threshold — report still renders the recommendation as "Sin escenario recomendado" |
