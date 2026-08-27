# Professional Disclaimer

Outputs that include zoning interpretations, FOS/FOT calculations, retiros, tipología applicability, or any structural assumption MUST end with the canonical disclaimer block followed by the machine-readable marker. Both elements, in this order, with one blank line between them.

## Canonical block (Spanish, UY-facing)

```markdown
> **Análisis indicativo, no certificación.** Este informe se basa en datos catastrales publicados por la Intendencia de Maldonado y en la interpretación del TONE vigente al momento de la generación. No reemplaza el dictamen del cuerpo técnico de la Intendencia ni la consulta formal previa a un trámite de permiso.

<!-- normativa:requires-disclaimer -->
```

## Why a marker

The marker (`<!-- normativa:requires-disclaimer -->`) lets the disclaimer hook (`hooks/post-write-disclaimer-check.sh`) verify enforcement WITHOUT having to classify the document by content. If a skill emits the marker, the hook requires the canonical disclaimer text to also be present. If the marker is absent, the hook stays silent — the skill considered the output non-regulatory.

This means:
- Test fixtures, drafts, and notes-to-self that don't claim regulatory weight just don't carry the marker. No hook noise.
- Once a SKILL.md mandates the marker, dropping the disclaimer text by accident is a hook-failure, not a silent regression.

## Per-skill applicability

| Output | Disclaimer required | Marker emitted |
|---|---|---|
| `*.normativa.v1.json` (machine-readable envelope) | No | No (JSON, not markdown) |
| `*.md` analysis report (`/normativa-analyze` markdown sidecar) | **Yes** | Yes |
| `*.informe.html` (`/normativa-informe` printable report) | **Yes**, rendered via `tone-informe-plantilla.html` | Yes (in HTML comment in the template footer) |
| Internal notes / debug output | No | No |

## How to apply (skill author)

1. End the markdown body with the canonical block above (verbatim — the hook does substring match on the leading "Análisis indicativo, no certificación.").
2. Add a blank line.
3. Emit the marker.
4. Cite this rule from your SKILL.md so the lint script registers the cross-reference.

The rendered HTML report (`tone-informe-plantilla.html`) already carries this in the page-4 disclaimer block; no per-render action needed.
