# Terminology

Canonical names for tipologías, calles classes, decreto citations, locality slugs. Multiple skills emit these strings — drift across skills produces a fragmented user experience and breaks the validator's enum checks.

## Tipología codes

The `scenarios[].tipologia.codigo` and `zone.tipologias_catalog[].codigo` fields use these canonical codes (lowercase, snake_case):

| Code | Display name | Notes |
|---|---|---|
| `unidad_aislada` | Unidad aislada | Single isolated dwelling |
| `unidad_apareada` | Unidad apareada | Paired dwellings (party wall) |
| `edificacion_baja` | Edificación baja | 2-3 floor slab |
| `bloque_bajo` | Bloque bajo | 4-6 floor block (default; no specific height qualifier) |
| `bloque_bajo_9m` | Bloque bajo 9m | Bloque bajo with 9m altura cap |
| `bloque_bajo_12m` | Bloque bajo 12m | Bloque bajo with 12m altura cap |
| `bloque_medio` | Bloque medio | 7-12 floor block |
| `bloque_alto` | Bloque alto | 13+ floor block |
| `conjunto_unidades` | Conjunto de unidades | Cluster of aisladas/apareadas |
| `conjunto_bloques` | Conjunto de bloques | Cluster of bloques |
| `torre_media` | Torre media | Mid-rise tower |
| `torre_alta` | Torre alta | High-rise tower |
| `hotelero` | Hotelero | Hospitality use |
| `general_pb_pa` | General (PB + PA) | San Carlos default — single tipología with PB + PA |

Always cite by `codigo`. Never invent variants. If the TONE introduces a new tipología, add it here, update `extract-tipologias.py`'s code list, and update `tone-zones.json`.

## Frente principal hierarchy

When a parcel has multiple `frentes[]` (touches multiple calles), `/normativa-analyze` picks the canonical principal by ranking on `calle_tipo`:

1. `Ruta`
2. `CALLE` (within: AVENIDA / AVDA / BOULEVARD / BLVD prefix in `nombre` outranks plain CALLE)
3. `PASAJE`
4. `PASAJE INTERNO`
5. `PEATONAL`
6. `CALLE INTERNA`
7. `VIRTUAL`
8. `SENDERO`

Tiebreaker (within same tier): longest `length_m`. Cite the chosen frente by name in the analysis (`Frente principal: AVENIDA FRANCIA, 82,3 m`); list secondary frentes in `caveats`.

## Decreto citations

Format: `Dto. <number>/<year>` followed by article reference if applicable. Examples:

- `Dto. 3970/2017`
- `Dto. 3718/1997 Art. D.215`
- `Dto. 3970/2017 Art. D.266`

When listing multiple decretos in `sources.decretos`, order chronologically (oldest first).

For TONE-prefixed articles (`D.xxx` numbering), cite as `Art. D.xxx`. For non-D articles cite as written in the digesto.

## Locality slugs

Used in `selection.locality`, `sources.map_url`, and the `locality-map.md` lookup table. Lowercase, hyphenated, no accents:

| Slug | Display name |
|---|---|
| `punta-del-este` | Punta del Este |
| `maldonado` | Maldonado |
| `la-barra` | La Barra |
| `manantiales` | Manantiales |
| `san-carlos` | San Carlos (urban) |
| `san-carlos-rural` | San Carlos rural |
| `jose-ignacio` | José Ignacio |
| `la-juanita` | La Juanita (Faro) |
| `garzon` | Garzón |
| `aigua` | Aiguá |
| `pan-de-azucar` | Pan de Azúcar |
| `piriapolis` | Piriápolis |
| `punta-ballena` | Punta Ballena |
| `el-tesoro` | El Tesoro |
| `el-chorro` | El Chorro |
| `ocean-park` | Ocean Park |
| `balneario-buenos-aires` | Balneario Buenos Aires |
| `santa-monica` | Santa Mónica |

When `selection.locality_name` differs from the slug (e.g., `"José Ignacio – La Juanita"`), keep both — slug for routing, name for display.

## How to apply

- When emitting envelope JSON: use canonical codigos + slugs verbatim.
- When prose-naming a tipología in a report: use the display name from the table above.
- When a skill encounters an UNKNOWN tipología code, add it here first (with sources cited), then propagate to the data files. Don't invent inline.
