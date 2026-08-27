# Changelog

All notable changes to **Norma** (`Estudio-Local/normativa`) are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- `/norma-massing`: **buildable/retiro geometry** was collapsing to ~0 inset at vertices where two near-collinear edges carried different setbacks (e.g. a `lateral`+`fondo` split across an almost-straight rear). Rewrote `buildableFromSetbacks` as a **half-plane intersection** (lot ∩ each edge's inward-offset half-plane) — robust for any setback mix; retiro now respected on every edge. Edge-role classification moved to **outward-normal direction** (both rear edges → `fondo`), eliminating the discontinuity at the source.

### Added

- `/norma-massing`: **draws all constituent parcels** always (even when englobando) so the subdivision stays visible; the 3 real La Juanita lots are baked into `SITE.lots`.
- `/norma-massing`: **Individual mode** — an `Individual (N lotes)` scenario develops each parcel separately (per-lot buildable + massing, summed metrics); the engine is now lot-aware (`activeLots`, `evalConfig`). Scenario order is Individual → Apareada → Bloque. On the La Juanita demo the maximizer defaults to **Individual** (≈989 m² GFA, more than englobado bloque's 841 m²) — englobamiento here *loses* yield, which the tool now surfaces honestly.

### Changed

- `/norma-massing`: zoning caps (FOS/FOT/altura/retiros) are now **inherited down the pipeline (Mapa → /norma-analyze → /norma-massing)** instead of hand-coded — single source of truth is `tone-zones.json`. Added `skills/norma-massing/build-massing-site.py`, which runs the real pipeline (cadastre geometry + the `norma-scenarios` engine reading `tone-zones.json`) and emits the demo's `SITE` block; the reference HTML is now generated, not transcribed. `lot_area_m2` switched to the cadastral área del padrón (Σ `valaream2` = 1.428 m²), the legal FOS/FOT denominator. SKILL.md gained a "never hand-code the caps" rule.
- `/norma-massing`: massing **forma now conforms to the lot** on irregular parcels. Footprints are clipped to the buildable polygon and FOS/FOT are read off the **clipped** areas (previously the un-clipped rectangle, which overstated coverage and tripped a false "sobresale" on slanted edges). The flag is reframed to an informational **"Ajuste al lote: completo / recortado N%"**. Roofs are now built on the clipped footprint (height-field: 1-agua shear, 2-aguas ridge-split via `clipByT`, 4-aguas centroid hip) so they no longer overhang trimmed edges. GFA = Σ (clipped area × storeys).

### Added

- `/norma-massing`: **fronting street / address**. The configurator now captures the frente street (from the Mapa's `frentes[].calle_nombre`, or — when building from the cadastre — by reverse-geocoding the frente-edge midpoint via OSM Nominatim) into `SITE.info.frente_calle` / `address`, shown in the info panel and on the frente edge label. La Juanita demo resolves to "República Argentina, José Ignacio".
- `/norma-massing`: **roof (techo) option** — `flat` (azotea) · `1agua` (mono-pitch) · `2aguas` (gable) · `4aguas` (hip), with a cumbrera-height slider. The controlling altura becomes the top of the roof (`max floor height + ridge`), checked against `altura_m`; the roof void is not counted as habitable GFA. (TONE gálibo allowances for inclined roofs are not modeled — the ridge is treated as the controlling point.)

### Fixed

- `/norma-massing`: floors slider now clamps to the legal maximum (`⌊altura_m / floorH⌋`) per scenario, so the UI can't imply illegal storeys.

## [0.10.0] - 2026-05-27

### Added

- **`/norma-massing`** — interactive 3D building-massing configurator, the step after `/norma-analyze`. Generates a self-contained Three.js HTML (CDN-only, no build, no server) in which the legal zoning envelope is a fixed translucent "ghost" container and the user tests massing options with live metrics and green/red compliance flags, all client-side.
  - **Variables:** partido (barra · patio · torre+zócalo · L · U), programa (editable tipología table → automated `viviendas` count), circulación (doble/simple crujía · núcleo · galería → max plate depth + net/gross efficiency), orientación (giro + southern-hemisphere asoleamiento score).
  - **Inputs:** consumes a `*.normativa.v1.json` envelope (FOS_pct/FOT_pct/altura_m/retiros) + the parcel polygon (fetched from the Maldonado ArcGIS cadastral layer by padrón, or pasted; reprojected to UTM 21S meters). Buildable polygon computed from per-edge setbacks via variable-distance offset (exact for convex lots; uniform-inset fallback + caveat otherwise).
  - **Geometry kernel** lifted from the `/zoning-envelope` baseline, kept self-contained per generated file (no cross-repo import). Adds `buildableFromSetbacks`, `clipPolygon` (Sutherland–Hodgman), and the (s,t) frente frame.
  - Output carries the canonical professional disclaimer + `norma:requires-disclaimer` marker (it emits FOS/FOT figures).
  - Reference implementation: `examples/massing-la-juanita-130-132.html` — built on **real cadastral data** (3 La Juanita parcels, loc HG/mzna 26, ≈1.409 m², fetched from the `Padrones` FeatureServer) with the verified subzona 2-1-2-2 envelope (FOS 30–35 % / FOT 60–70 % / altura 7–9 m), not the illustrative `*.normativa.v1.json` fixture.
- Dispatcher (`/norma`) routing table + menu extended to route massing/volumetría/configurador/3D requests to `/norma-massing`.

## [0.9.0] - 2026-05-08

### Added

- Anonymous skill-invocation telemetry. `/norma-analyze` and `/norma-informe` now run `scripts/track.py` as a final step, recording `event` + `skill_version` + a stable per-machine UUID + `ts` to `https://estudio-local.com/api/telemetry`. Machine UUID lives at `~/.config/estudio-local/machine-id`. Padrón numbers, envelope content, file paths, conversation content, hostname, username, and IP are deliberately not collected.
- README "Telemetry" section disclosing exactly what's collected, where it goes, and how to opt out.
- `scripts/track.py` (~80 lines, pure stdlib).

### Opt-out

Set `ESTUDIO_LOCAL_TELEMETRY=0` in your environment. No machine-id file is created when opted out; an existing one can be removed with `rm ~/.config/estudio-local/machine-id`.

### Why

The Mapa side of the funnel (parcel clicks, JSON downloads, prompt copies) was already instrumented at `estudio-local.com/mapa`. The plugin side was a black box: we couldn't see whether anyone who exported a `selection.v1.json` actually ran `/norma-analyze` on it, or whether anyone went all the way to `/norma-informe`. Two events fix that.

## [0.8.1] - 2026-05-08

### Added

- `CHANGELOG.md` (this file). Adopts the version-bump discipline codified in `AlpacaLabsLLC/skills-for-architects/PATTERNS.md` rule #6: every shipped change moves three artifacts together — JSON `version` field, git tag (`vX.Y.Z`), GitHub release with notes.

### Notes

- This is a doc-only release (no plugin or skill behavior changed). Patch bump because `CHANGELOG.md` is a marketplace-level addition.
- Backfilled `v0.8.0` tag + GitHub release out-of-band (`9ee6132` → tagged retroactively with the original commit body as release notes).

## [0.8.0] - 2026-05-08

Adopt layered plugin pattern (rules/ + hooks/ + lint + dispatcher).

Restructures the plugin to follow the same layered architecture used across larger plugin libraries: a routing skill at the entry point, sub-skills for the actual work, externalized cross-skill rules, a marker-driven hook for disclaimer enforcement, and a structural lint.

### Changed

- `/norma` is now a **dispatcher** skill (no work, just routing). Reads the user's task and hands off to the right sub-skill.
- `/norma-analyze` (was `/norma`) — envelope analysis from padrones / GIS JSON / `selection.v1.json`. Same workflow as before; folder renamed.
- End users keep typing `/norma <args>`; routing happens transparently. Sub-skills remain user-invocable directly for power users.
- Validator renamed: `skills/norma/norma-validate-envelope.py` → `skills/norma-analyze/normativa-v1-validate.py`. Validator named after the schema id (`estudio-local.normativa.v1`), not after the skill, so future skill renames don't reach into it.

### Added

- **`/norma-informe`** sub-skill (unchanged behavior; previously inline) — printable HTML report from `*.normativa.v1.json` envelopes.
- **`rules/`** — externalized cross-skill enforcement copy. Single edit propagates to every skill that cites them. Lint verifies citations resolve. Files: `envelope-contract.md`, `professional-disclaimer.md`, `units-and-measurements.md`, `terminology.md`, `code-citations.md`, `transparency.md`.
- **Marker-driven disclaimer hook** — `hooks/post-write-disclaimer-check.sh` enforces `norma:requires-disclaimer` markers on regulatory output. Replaces keyword-sniffing; eliminates false positives on docs that mention regulated terms in passing.
- **`scripts/lint.sh`** — structural lint (~200 lines) modeled on `architecture-studio`. Validates: each plugin has `plugin.json` + at least one skill; SKILL.md frontmatter has `name`/`description`/`allowed-tools`/`user-invocable`; skill folder name matches frontmatter name; `*-schema.md` and `*-validate.py` references resolve; `rules/*.md` citations exist; `marketplace.json` plugin entry version matches `plugin.json`; hooks are executable.

### Notes

- Install command unchanged: `/plugin marketplace add Estudio-Local/normativa` then `/plugin install norma@normativa`.
- Power users who scripted `/norma <padrones>` directly now hit the dispatcher (which still routes correctly to `/norma-analyze` when it sees padrones+locality).
- Hooks aren't auto-enabled by Claude Code; opt-in is explicit via `~/.claude/settings.json`. Self-tested: marker+disclaimer→exit 0, marker-only→exit 2, no marker or non-md path→exit 0.
