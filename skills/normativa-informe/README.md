# `/normativa-informe` skill

Render a `*.normativa.v1.json` envelope (produced by `/normativa`) as a self-contained printable A4 HTML report. No analysis here — pure rendering. Pure stdlib Python, no external dependencies.

For install instructions and the full plugin overview, see the [repo README](../../README.md).

## What this skill reads & writes

| File | Format | Audience |
|------|--------|----------|
| `<basename>.normativa.v1.json` (input) | JSON envelope | Produced by `/normativa`; spec at [`../normativa-analyze/normativa-v1-schema.md`](../normativa-analyze/normativa-v1-schema.md) |
| `<basename>.informe.html` (output) | Self-contained HTML | Humans — open in browser, ⌘P / Ctrl+P → "Save as PDF" to share |

## Files in this directory

| File | Purpose |
|------|---------|
| `SKILL.md` | Instructions Claude follows when the skill runs |
| `normativa-informe-render.py` | JSON → HTML renderer (Python stdlib, no template engine — `str.replace` on `{{PLACEHOLDER}}` markers) |
| `normativa-informe-plantilla.html` | A4 report template (4 pages: cover + lots, comparativa, detalle escenario, normativa + descargo) |

## Contract guarantees

The renderer trusts that its input has been validated by `/normativa`'s `norma-validate-envelope.py`. If that didn't happen (e.g. someone hand-wrote the envelope), unexpected types may produce blank cells (`—`) but should not crash — the renderer is defensive about missing keys and casts numerics through `fmt_*` helpers that return `—` on `None`/wrong-type.

The schema id is checked at the top of `main()`: `estudio-local.normativa.v1`. Anything else aborts.

## Output filename

If invoked without an explicit output path, the renderer derives one from the input by stripping `.normativa.v1.json` and appending `.informe.html`:

```
padrones-130-132-la-juanita.normativa.v1.json
  → padrones-130-132-la-juanita.informe.html
```
