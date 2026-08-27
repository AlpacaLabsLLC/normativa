# `/normativa` — dispatcher skill

Smart router for the Norma plugin. Reads the user's task description and forwards to the correct sub-skill (`/normativa-analyze` for envelope analysis, `/normativa-informe` for the printable report). The dispatcher itself doesn't do the work; sub-skills own the algorithms.

For install instructions and the full plugin overview, see the [repo README](../../README.md). For the routing table + rules, see [`SKILL.md`](./SKILL.md).

## Why a dispatcher?

End users don't always know which sub-skill they need. The most common ergonomic — typing `/normativa <padron> en <locality>` and getting an analysis — used to be the only behavior. Now Norma has two surfaces (analyze + render) and will grow more (proforma, 3D viewer, market intel), and routing through a thin entry point keeps the interface stable as the catalog grows.

Pattern modeled on `/studio` from the architecture-studio plugin family — a routing skill that reads task intent and hands off, never carrying its own orchestration logic.

## Sub-skills currently routed

| Skill | When |
|---|---|
| [`/normativa-analyze`](../normativa-analyze/SKILL.md) | Padrón + locality, ArcGIS JSON, `selection.v1.json` from the Mapa, or any verb-shaped analysis request |
| [`/normativa-informe`](../normativa-informe/SKILL.md) | Existing `*.normativa.v1.json` envelope + a verb like "report", "informe", "PDF", "render" |

## Files in this directory

| File | Purpose |
|------|---------|
| `SKILL.md` | The dispatcher logic Claude follows when routed `/normativa` |
| `README.md` | This file |

The dispatcher itself has no Python helpers, no schema, no validator — it's pure routing copy.
