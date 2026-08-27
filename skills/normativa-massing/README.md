# norma-massing

Interactive 3D **building-massing configurator** built from a `/normativa-analyze` envelope.

The step after `/normativa-analyze`: where analysis resolves *what is legal* (the envelope) and
`/normativa-informe` renders it as a static report, `/normativa-massing` turns the envelope into a
**parametric massing studio**. It generates one self-contained HTML file (Three.js, CDN-only,
no build, no server) in which:

- the **legal zoning envelope is a fixed translucent container** ("ghost"), and
- the user tests **massing options** inside it — partido (barra / patio / torre+zócalo / L / U),
  programa (mezcla de tipologías → conteo de viviendas), circulación (crujía → eficiencia), y
  orientación (giro + asoleamiento sur) — with **live FOS/FOT/altura/viviendas metrics and
  green/red compliance flags** recomputed in the browser on every change.

## Usage

```
/normativa-massing path/to/padron-1881.normativa.v1.json
/normativa-massing 130,131,132 la-juanita
/normativa-massing                              # most recent *.normativa.v1.json in CWD
```

Output: `massing-<locality>-<padrones>.html`, opened in the browser.

## How it fits the pipeline

```
/normativa-analyze   →  *.normativa.v1.json   →  /normativa-informe   (printable A4 report)
                                          └→  /normativa-massing   (interactive massing studio)
```

It consumes the envelope's `FOS_pct` / `FOT_pct` / `altura_m` / `retiros` and the parcel's
`frentes` (orientation). It acquires the lot polygon from the Maldonado ArcGIS cadastral layer
(or pasted geometry), works in UTM 21S meters, and computes the buildable polygon from per-edge
setbacks. It does **not** re-run zoning analysis and does **not** draw interiors — envelope-only
volumes plus derived metrics.

See [`SKILL.md`](./SKILL.md) for the full workflow and the
[`examples/massing-la-juanita-130-132.html`](../../examples/massing-la-juanita-130-132.html)
reference implementation.

## Status

V1: partido + programa + circulación + orientación/asoleamiento, single-parcel, convex lots
exact (irregular lots degrade to a uniform inset + caveat). Output carries the canonical
professional disclaimer — exploratory massing, not a certification.
