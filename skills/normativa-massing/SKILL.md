---
name: normativa-massing
description: Build an interactive 3D building-massing configurator from a /normativa-analyze envelope. Generates a self-contained HTML where the legal zoning envelope is the fixed container and the user tests massing options (parti, program, circulation, orientation) with live FOS/FOT/height/unit metrics and live compliance flags. Invoked directly or via the /normativa dispatcher.
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Grep
  - WebFetch
  - AskUserQuestion
user-invocable: true
---

# /normativa-massing — 3D massing configurator from a `/normativa-analyze` envelope

Invoked directly (`/normativa-massing path/to/envelope.normativa.v1.json`) or routed-to by the
`/normativa` dispatcher when the user wants to *explore building forms inside* the zoning envelope
— the step **after** `/normativa-analyze` resolves what's legal.

Where `/normativa-informe` renders the envelope as a static report, this skill turns it into a
**parametric massing studio**: one self-contained interactive HTML file (Three.js, CDN-only,
no build, no server). The legal envelope is a frozen translucent "ghost" container; the user
drives sliders/toggles and the massing regenerates with live metrics and green/red legality
flags, all client-side.

**Reference implementation:** [`examples/massing-la-juanita-130-132.html`](../../examples/massing-la-juanita-130-132.html)
is the code baseline. Build new files by adapting it — same kernel, same panels, same engine.
Its `SITE` is **real cadastral data**: the 3 La Juanita parcels (loc `HG`, mzna 26) fetched live
from `gis.maldonado.gub.uy/.../Padrones/FeatureServer`, unioned (≈1.409 m²), with the verified
subzona **2-1-2-2** envelope (FOS 30–35 % / FOT 60–70 % / altura 7–9 m). Note the repo fixture
`examples/padrones-130-132-la-juanita.normativa.v1.json` is an illustrative teaching envelope
(13.050 m², zone "2.1") and does **not** match these real parcels — don't bake its numbers into a demo.

## Rules this skill follows

- [`rules/envelope-contract.md`](../../rules/envelope-contract.md) — the strict-typed `normativa.v1.json` fields this skill consumes (scenarios[].envelope FOS_pct/FOT_pct/altura_m, retiros, selection.lots[].frentes).
- [`rules/professional-disclaimer.md`](../../rules/professional-disclaimer.md) — the generated HTML carries the canonical disclaimer block + `normativa:requires-disclaimer` marker (it emits FOS/FOT figures, so it is regulatory output).
- [`rules/units-and-measurements.md`](../../rules/units-and-measurements.md) — everything is metric (m, m², %), es-UY locale; the working CRS is UTM 21S meters.

## What this skill does NOT do

- It does **not** perform zoning lookups, resolve the zone, or compute the legal envelope — that is `/normativa-analyze`'s job. This skill consumes its `*.normativa.v1.json` output.
- It does **not** draw interiors or floor plans. "Envelope only": it generates **volumes**. Program/circulation are parameters that shape the volumes and their derived metrics, not drawn rooms.
- It does **not** certify anything. The output is exploratory massing; the disclaimer says so.

## Usage

```
/normativa-massing path/to/padron-1881.normativa.v1.json
/normativa-massing 130,131,132 la-juanita      # finds the matching *.normativa.v1.json in CWD
/normativa-massing                              # uses the most recent *.normativa.v1.json
```

## Step 1 — Load the envelope

Resolve the `*.normativa.v1.json` input (explicit path → search by padrón/locality → most
recent in CWD). If none found, tell the user to run `/normativa-analyze` first. Validate the
`schema` is `estudio-local.normativa.v1`.

Pick the **recommended scenario** (`recommendation.scenario_id` → its `scenarios[]` entry) as
the active default; bake **all** `applicable` scenarios so the user can switch in-app. From the
active scenario take `envelope.FOS_pct`, `envelope.FOT_pct`, `envelope.altura_m`, and `retiros`
(`frontal_m`/`lateral_m`/`fondo_m`/`entre_volumenes_m`).

> **Single source of truth — never hand-code the caps.** FOS/FOT/altura/retiros are *inherited*
> down the pipeline **Mapa → `/normativa-analyze` → `/normativa-massing`**: `/normativa-analyze` resolves the
> parcel's `zone_code` and reads the coefficients from `tone-zones.json` (the SOT), emitting them
> in `normativa.v1.json`; this skill copies them verbatim into `SITE.scenarios`. The Mapa relays
> the same `tone-zones.json` data but does not expose FOS/FOT as JSON, so the envelope (or the
> engine) is the source — transcribing zoning numbers by hand creates a second SOT and is wrong.
> `lot_area_m2` is the **cadastral área del padrón** (Σ `valaream2`), the legal FOS/FOT denominator.
>
> For the reference demo, the `SITE` block is produced by
> [`build-massing-site.py`](./build-massing-site.py), which runs the real pipeline (cadastre
> geometry + `norma-analyze/normativa-scenarios.py` reading `tone-zones.json`) and emits the scenarios.
> Regenerate it; do not edit `SITE` by hand.

## Step 2 — Acquire the parcel polygon

`normativa.v1.json` carries constraints but **not** the lot geometry. Get the ring:

1. **Preferred — ArcGIS by padrón.** Query the **`Padrones` FeatureServer** (layer 0
   `Padrones_Urbanos`):
   `gis.maldonado.gub.uy/arcgis/rest/services/Servicios_AGOL/Padrones/FeatureServer/0/query`
   with `where=codloccat='<HG…>' AND padron IN (…)`, `outSR=32721`, `returnGeometry=true`,
   descriptive User-Agent (CF Bot Fight 403s `Python-urllib`). Fields: `padron`, `nomloccat`
   /`codloccat` (locality — **padrón numbers repeat across localities, so always filter by
   locality**), `nummancat` (manzana), `valaream2` (authoritative cadastral area). The zoning
   subzone polygons are a *different* service (`ORDENANZA_CONSTRUCCION`, synced by
   [`../normativa-analyze/datos/normativa-sync-zoning.py`](../normativa-analyze/datos/normativa-sync-zoning.py)).
   For multi-padrón englobamiento, union the rings (convex hull is a fine approximation when the
   lots form a block).
2. **Fallback — pasted geometry.** Accept ArcGIS JSON (`geometry.rings`) or GeoJSON the user pastes.
3. **Last resort — synthesize.** If geometry is genuinely unavailable, build a rectangle from
   `area_total_m2` and `frente_estimado_m` and add a caveat that the shape is nominal.

**Reproject** the ring to **UTM 21S (EPSG:32721) meters**, recenter its centroid to the origin,
and fix winding to CCW (`signedArea`). This is `lot_poly_m`.

**Classify edges by frente + capture the street.** Use `selection.lots[].frentes[]` from the Mapa
(authoritative — it intersected parcel edges with IDE street centerlines): `frentes[].edges` marks
each polygon edge as `frente` / `fondo` (opposite) / `lateral`, and `frentes[].calle_nombre` is the
**fronting street** — carry it into `SITE.info.frente_calle` + `SITE.info.address` and surface it
(the info panel shows the address; the frente edge label shows the calle). When the envelope lacks
`frentes` (e.g. building straight from the cadastre), resolve the street by reverse-geocoding a
point just outside the frente-edge midpoint via OSM Nominatim — `build-massing-site.py` does this.
Derive `north_vec` from the frente azimuth or grid north; Maldonado is southern hemisphere, so
**north = good sun**.

## Step 3 — Bake the `SITE` const

Emit an in-HTML `SITE` object (the configurator's frozen site contract):

```js
const SITE = {
  info: { title, sub, lot_area_m2 },
  lot_poly_m,            // CCW ring, meters, origin at centroid
  edge_role: [...],      // per-edge "frente"|"fondo"|"lateral", index = edge i (vertex i→i+1)
  north_vec: [x, z],     // unit vector toward geographic North
  scenarios: [ { id, label, FOS_pct, FOT_pct, altura_m, retiros:{...} }, ... ],  // verbatim from normativa.v1.json
  recommended: "C1"
};
```

The buildable polygon is computed **per active scenario** at runtime (Step 4) from `retiros`,
so it updates when the user switches scenarios.

## Step 4 — Generate the HTML (adapt the reference)

Copy the reference file and replace its `SITE` const. The reference already contains the full
engine; keep it intact. Its architecture:

### Geometry kernel (self-contained, lifted from the `/zoning-envelope` baseline)
`signedArea` · `area` · `ccw` · `centroid` · `triangulate` (ear-clip) · `extrudePolygon` ·
`groundPolygon` · `createTextSprite`. Plus massing-specific geometry:
- **`buildableFromSetbacks(poly, roles, retiros)`** — buildable = lot ∩ (every edge's
  inward-offset **half-plane**), via `clipHalfplane`. Robust for any setback mix; never collapses
  at near-collinear vertices (the earlier offset-line-intersection did, zeroing the retiro where a
  `lateral` and `fondo` edge met on a near-straight rear). Edge roles come from **outward-normal
  direction** (rear-facing → `fondo`, sideways → `lateral`) so near-collinear rear edges share a
  setback. `exact:false` only for genuinely concave lots (conservative under-approx).
- **`clipPolygon(subject, clip)`** — Sutherland–Hodgman clip of each massing footprint to the
  buildable polygon (keeps geometry inside the legal envelope).

### Lot-aware engine (englobado vs individual)
`activeLots(sc)` returns the unified hull for `mode:"englobado"` scenarios, or `SITE.lots` (the
individual parcels) for `mode:"individual"`. `evalConfig(st, sc, lotsB, sink)` generates massing
across all active lots, sums pieces, and computes aggregate metrics — so an Individual scenario
renders one building per parcel and sums GFA/units. The 3 real parcels are always drawn (even when
englobando). `SITE.lots[]` carries each parcel's `poly` + `edge_role`.

### Building frame
`frenteFrame(buildable, orientDeg)` builds a local (s = along-frente width, t = depth-into-lot)
frame, anchored at the buildable centroid, with an orientation offset. Generators work in (s,t)
and map back to world; `rectST` converts an (s,t) rectangle to a world polygon.

### Massing generators — `genMassing(frame, state, scenario)`
Each returns pieces `[{poly (clipped world), hBottom, hTop, footIntent, worldArea, clipArea}]`:
- **bar** — one bar of `depth` along the frente, full buildable width, `floors × floorH`.
- **court (patio)** — 4-bar perimeter ring of `depth` around a central void.
- **tower + podium** — full-base podium for `podiumFloors`, smaller centered tower plate to the
  height cap. *(Note: a full-base podium intentionally trips the FOS flag red until the user
  shrinks it — surfacing the violation is the point. A podium-coverage slider is a clean future add.)*
- **L** — front bar + one lateral bar. **U** — front + two laterals.

Footprints **conform to the lot**: each band is clipped to the buildable polygon, and FOS/FOT
are read off the **clipped** areas (the bands are disjoint, so summing is exact). On an
irregular lot the requested rectangle gets trimmed at slanted edges — reported as an
informational **"Ajuste al lote: completo / recortado N%"**, not a hard violation (the massing
is always within retiros because it's clipped). GFA = Σ (clipped area × storeys-in-that-volume),
so a tower podium + tower sum correctly.

### Roof — `buildRoof(frame, poly, yBase, type, ridgeH)`
A **techo** option sits on the topmost piece(s), built on the piece's **clipped footprint
polygon** (so it conforms to the real lot — no overhang past trimmed edges) as a frame-space
height field: `flat` (azotea, default), `1agua` (mono-pitch shed — exact on any convex
footprint), `2aguas` (gable — the footprint is split at mid-depth with `clipByT` so the ridge is
sharp on any shape), `4aguas` (hip, approximated as a centroid-apex pavilion; a true ridged hip
is a refinement). A `ridgeH` slider (shown only when pitched) sets cumbrera height above the eave.
- **Zoning rule applied:** the **controlling altura is the top of the roof** (`max hTop + ridgeH`),
  checked against `altura_m`. So adding a pitched roof when floors are near the cap pushes the
  height flag red — intended (conservative; TONE gálibo allowances for inclined roofs are not
  modeled in V1, so we treat the ridge as the controlling point and say so).
- The roof void is **not** counted as habitable GFA — FOT is unchanged by the roof.

### Live engine + metrics — `compute(pieces, state, scenario)`
- **FOS used** = footprint / lot_area; **FOT used** = GFA / lot_area; both vs the scenario's allowed %.
- **height** vs `altura_m` cap.
- **circulation** (`CIRC` presets) → max plate depth + net/gross efficiency → **net area**.
- **program** → editable unit-type table (m²/unit + mix %) → `units = net / weighted_avg_size`,
  split by mix. (This automates the hand-estimated `viviendas_estimadas`.)
- **solar** = share of vertical facade area whose outward normal faces within ±60° of `north_vec`.
- **spacing** = inner court / U gap vs `entre_volumenes_m`.
- **headroom** = remaining FOT m².

`rebuild()` regenerates the massing group and repaints metrics on every control change; it also
**clamps the floors slider to the legal max** (`⌊altura_m / floorH⌋`) so the UI can't imply
illegal storeys. `rebuildBuildable()` recomputes the buildable polygon + ghost envelope on
scenario change.
Snapshot bar saves up to 3 param sets (A/B/C) for comparison.

### Design system (match `/zoning-envelope`)
Background `#f5f3ef` · lot ground `#dcd7cd` · setback zone `#c85a50` · **massing `#4a7a9b`** ·
**ghost envelope / height cap `#e8a849`** (low opacity — it must read as a container, not a
solid) · labels `#333` · Helvetica Neue 11px panels · all volume materials `transparent`,
`depthWrite:false`, `side:DoubleSide`. CDN import map: `three@0.170.0`.

### V1 design constants
| Circulation | max plate depth | net/gross |
|---|---|---|
| Doble crujía (double-loaded) | 14 m | 0.82 |
| Simple crujía (single-loaded) | 10 m | 0.70 |
| Núcleo (point-access) | 22 m | 0.86 |
| Galería (exterior) | 12 m | 0.80 |

Program defaults (editable in-app; sourced from EL/UY norms): 1D 45 m² · 2D 65 m² · 3D 90 m².
Floor height default 3.0 m. Solar half-angle ±60° from north.

### Disclaimer (required)
The HTML must carry, near the end of `<body>`, the canonical disclaimer comment + the
`<!-- normativa:requires-disclaimer -->` marker + a small visible disclaimer panel (see the
reference). The output emits FOS/FOT figures, so this is mandatory per `rules/professional-disclaimer.md`.

## Step 5 — Save + open

Save next to the source envelope as `massing-<locality>-<padrones>.html`
(e.g. `massing-la-juanita-130-132.html`). Open it in the browser.

## Notes

- **Jurisdiction-agnostic core.** The engine only needs `lot_poly_m`, `edge_role`, `retiros`,
  `FOS_pct`/`FOT_pct`/`altura_m`, `frentes`/`north_vec`. A non-Maldonado adapter (e.g. a
  `/zoning-analysis-nyc` report in feet) can feed the same `SITE` shape later.
- **Convex assumption.** Half-plane buildable + Sutherland–Hodgman footprint clipping are exact for
  convex lots. Genuinely concave lots get a conservative under-approximation (`exact:false`, shown
  as a caveat) — don't silently present approximate retiros as exact.
- **Verify before declaring done:** open the HTML; sweep parti/floors/orientation and confirm
  FOS/FOT/height flags never go green while the massing visibly exceeds the ghost; confirm
  `GFA ≈ lot_area × FOT_pct/100` at full build matches the report's `area_edificable_m2`.

> **Análisis indicativo, no certificación.** Este informe se basa en datos catastrales publicados por la Intendencia de Maldonado y en la interpretación del TONE vigente al momento de la generación. No reemplaza el dictamen del cuerpo técnico de la Intendencia ni la consulta formal previa a un trámite de permiso.

<!-- normativa:requires-disclaimer -->
