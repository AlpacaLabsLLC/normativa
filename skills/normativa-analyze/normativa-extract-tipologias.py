#!/usr/bin/env python3
"""
Deterministic extractor — reads titulo markdown files and emits draft
tipologias[] per zone. Handles the 5 standard titulos (`## Zona` header
pattern + `### a-h)` subsections). José Ignacio (titulo-iii-cap-iii-sector-2)
does NOT follow this structure and must be handled by AI.

Outputs: norma/datos/extractions/<titulo-slug>.json
Plus:    norma/datos/extractions/<titulo-slug>-warnings.json (issues for AI review)

Usage:
  python3 extract-tipologias.py                  # process all standard titulos
  python3 extract-tipologias.py --titulo <name>  # process one
  python3 extract-tipologias.py --verify-23      # check MALDONADO 2.3 matches DRAFT_ENTRY
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
DATOS = os.path.join(HERE, "datos")
EXTRACT_DIR = os.path.join(DATOS, "extractions")

STANDARD_TITULOS = [
    "titulo-ii-cap-ii-sector-1",   # PdE Sector 1
    "titulo-ii-cap-ii-sector-2",   # Maldonado city zones 2.x (PdE titulo II sector 2 mapping)
    "titulo-iii-cap-ii-sector-1",  # Maldonado Sector 1 (northern coastal)
    "titulo-v-cap-i-sector-1",     # San Carlos Sector 1
    "titulo-v-cap-ii-sector-2",    # San Carlos Sector 2
]

# Tipología name → canonical code.
TIPOLOGIA_CODES = [
    # Order matters — more specific patterns first.
    (r"bloque\s+medio", "bloque_medio"),
    (r"bloque\s+bajo\s*\(?\s*12\s*m?\)?", "bloque_bajo_12m"),
    (r"bloque\s+bajo\s*\(?\s*9\s*m?\)?",  "bloque_bajo_9m"),
    (r"bloque\s+bajo",                    "bloque_bajo"),
    (r"bloques?\s+bajos?",                "bloque_bajo"),
    (r"edificaci[oó]n\s+baja",            "edificacion_baja"),
    (r"conjunto\s+de\s+bloques?",         "conjunto_bloques"),
    (r"conjunto\s+(de\s+)?unidades",      "conjunto_unidades"),
    (r"unidad(es)?\s+apareadas?",         "unidad_apareada"),
    (r"unidad(es)?\s+aisladas?",          "unidad_aislada"),
    (r"unidades?\s+locativas",            "unidad_aislada"),  # treated as aislada default
    (r"torre\s+alta",                     "torre_alta"),
    (r"torre\s+media",                    "torre_media"),
    (r"bloque\s+alto",                    "bloque_alto"),
    (r"hotel(ero)?",                      "hotelero"),
    (r"otra\s+estructura",                "otra"),
    (r"vivienda\s+individual",            "unidad_aislada"),
]

ZONE_HEADER_RE = re.compile(
    r"^## (?:Zona|Subzona)\s+([0-9]+(?:\.[0-9]+)*)\s*[—–-]\s*(.+?)\s*$",
    re.MULTILINE,
)

SUBSECTION_RE = re.compile(
    r"^### (?:([a-h])\)\s*)?(.+?)\s*$",
    re.MULTILINE,
)

# Cross-zone Art.D.N tables that apply to multiple zones (e.g. "2.3 y 2.5.1 | ...")
CROSS_ZONE_TABLE_ZONES_CELL_RE = re.compile(
    r"^([0-9.]+(?:\s*[yY,]\s*[0-9.]+)*(?:\.\d+)?)$"
)


def normalize_tipologia(name):
    """Map a tipología label to a canonical code."""
    s = name.strip().lower()
    for pat, code in TIPOLOGIA_CODES:
        if re.search(pat, s):
            return code
    return None


def parse_meters(s):
    """Parse '13.60 m', '13,60 m', '28 m', '— m' → float or None."""
    s = str(s).strip()
    if not s or s in ("—", "-", "N/A"):
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*m", s)
    if m:
        return float(m.group(1).replace(",", "."))
    m = re.search(r"^(\d+(?:[.,]\d+)?)$", s)
    if m:
        return float(m.group(1).replace(",", "."))
    return None  # symbolic / conditional


def parse_pct(s):
    """Parse '290%', '50 %', '25-40% (...)' → int, float, or None."""
    s = str(s).strip()
    if not s or s in ("—", "-"):
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*%", s)
    if m:
        v = float(m.group(1).replace(",", "."))
        return int(v) if v == int(v) else v
    return None


def parse_area(s):
    """Parse '1.000 m²', '2.000', '450 m²' → int or None."""
    s = str(s).strip()
    if not s or s in ("—", "-"):
        return None
    # strip thousands separator (Spanish uses '.')
    m = re.search(r"(\d+(?:[.,]\d{3})*)\s*m", s)
    if m:
        return int(m.group(1).replace(".", "").replace(",", ""))
    m = re.search(r"^(\d+(?:[.,]\d{3})*)$", s)
    if m:
        return int(m.group(1).replace(".", "").replace(",", ""))
    return None


def parse_frente(s):
    """Parse '30 m', '14 m', '— m' → int or None."""
    s = str(s).strip()
    if not s or s in ("—", "-"):
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*m", s)
    if m:
        v = float(m.group(1).replace(",", "."))
        return int(v) if v == int(v) else v
    return None


def parse_retiro(s):
    """Parse retiro value. Literal meters → float; conditional/symbolic → string."""
    s = str(s).strip()
    if not s or s in ("—", "-"):
        return None
    # Fraction like "2/7 de la altura"
    frac = re.search(r"(\d+)/(\d+)\s+de\s+la\s+altura", s, re.I)
    if frac:
        lo = re.search(r"m[ií]n\.?\s*(\d+(?:[.,]\d+)?)\s*m", s, re.I)
        lo_v = lo.group(1).replace(",", ".") if lo else "0"
        return f"{frac.group(1)}/{frac.group(2)}_altura_min_{lo_v}"
    # Simple meters
    m = re.search(r"^(\d+(?:[.,]\d+)?)\s*m?$", s)
    if m:
        return float(m.group(1).replace(",", "."))
    # Conditional prose — keep as string
    return s


def parse_markdown_table(block):
    """Parse a pipe-table block into [(header_row, data_rows)]."""
    lines = [ln for ln in block.splitlines() if ln.strip().startswith("|")]
    if len(lines) < 2:
        return None, []
    header = [c.strip() for c in lines[0].strip("|").split("|")]
    data = []
    for ln in lines[2:]:  # skip separator row
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if len(cells) == len(header):
            data.append(cells)
    return header, data


def split_into_sections(md_text):
    """Return [(level, heading, body_text)] for ##, ###. Body is text between
    this heading and the next heading at same-or-higher level."""
    lines = md_text.splitlines()
    sections = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        m2 = re.match(r"^(#{2,3}) (.+?)\s*$", ln)
        if m2:
            level = len(m2.group(1))
            heading = m2.group(2)
            # Collect body until next heading at same-or-higher level
            body = []
            j = i + 1
            while j < len(lines):
                mj = re.match(r"^(#{1,6}) ", lines[j])
                if mj and len(mj.group(1)) <= level:
                    break
                body.append(lines[j])
                j += 1
            sections.append((level, heading, "\n".join(body)))
            i = j
        else:
            i += 1
    return sections


def zone_sections(md_text):
    """Split markdown by ## Zona/Subzona AND nested ### (Art. D.N —)? Subzona.
    Returns [(zone_code, zone_name, body)] where subzones may be flattened
    alongside their parent zones."""
    out = []
    sections = split_into_sections(md_text)
    for level, heading, body in sections:
        if level != 2:
            continue
        m = re.match(r"^(?:Zona|Subzona)\s+([0-9]+(?:\.[0-9]+)*)\s*[—–-]\s*(.+?)\s*$", heading)
        if m:
            out.append((m.group(1), m.group(2), body))
            # Also extract any nested subzones inside this zone body.
            # Pattern: ### [Art. D.N — ]Subzona N.N.N — Name
            for sub_head, sub_body in walk_all_l3(body):
                # Match "Subzona 2.4.1" or "Art. D.183 — Subzona 1.1.2 Residencial"
                # Number group is greedy; name is optional trailing text.
                ms = re.match(
                    r"^(?:Art\.?\s*D\.\S+\s*[—–-]\s*)?Subzona\s+(\d+(?:\.\d+)+)\b\s*[—–-]?\s*(.*?)\s*$",
                    sub_head,
                )
                if ms:
                    out.append((ms.group(1), ms.group(2) or ms.group(1), sub_body))
    return out


# Parameter name → schema field mapping for vertical "| Parámetro | Valor |" tables.
VPARAM_MAP = [
    # (regex matching param name, field_path list, value-parser)
    (r"^\s*área\s*mín", ["thresholds.area_min_m2"], parse_area),
    (r"^\s*area\s*mín", ["thresholds.area_min_m2"], parse_area),
    (r"^\s*superficie\s*mín", ["thresholds.area_min_m2"], parse_area),
    (r"^\s*frente\s*mín", ["thresholds.frente_min_m"], parse_frente),
    (r"^\s*retiro\s*frontal", ["retiros.frontal_m"], parse_retiro),
    (r"^\s*retiro\s*de\s*fondo", ["retiros.fondo_m"], parse_retiro),
    (r"^\s*retiro\s*fondo", ["retiros.fondo_m"], parse_retiro),
    (r"^\s*retiros?\s*laterales?", ["retiros.lateral_m"], parse_retiro),
    (r"^\s*retiro\s*lateral", ["retiros.lateral_m"], parse_retiro),
    (r"^\s*retiro\s*bilateral", ["retiros.lateral_m"], parse_retiro),
    (r"^\s*altura\s*máx", ["altura_m"], parse_meters),
    (r"^\s*altura\s*mín\s*(obligatoria)?", ["altura_m"], parse_meters),
    (r"^\s*altura\b", ["altura_m"], parse_meters),
    (r"^\s*plantas|^\s*pisos\b", ["pisos_label"], lambda s: s.strip() or None),
    (r"^\s*fos\s*ss\b", ["FOS_SS_pct"], parse_pct),
    (r"^\s*fos\s*subsuelo", ["FOS_SS_pct"], parse_pct),
    (r"^\s*fos\s*v\b", ["FOS_V_pct"], parse_pct),
    (r"^\s*fos\s*verde", ["FOS_V_pct"], parse_pct),
    (r"^\s*fos\s*n\b", ["FOS_V_pct"], parse_pct),  # FOS Natural (treat as verde)
    (r"^\s*fos\s*pb\b", ["FOS_pct"], parse_pct),
    (r"^\s*fos\b", ["FOS_pct"], parse_pct),
    (r"^\s*fot\b", ["FOT_pct"], parse_pct),
]


def extract_vertical_params(body):
    """Parse `| Parámetro | Valor |` tables. Returns flat dict of field_path → value.
    Field paths use dot notation: 'thresholds.area_min_m2', 'retiros.frontal_m', etc."""
    out = {}
    tables = re.split(r"\n\n+", body)
    for tb in tables:
        if not tb.strip().startswith("|"):
            continue
        hdr, rows = parse_markdown_table(tb)
        if not hdr or len(hdr) != 2:
            continue
        lower = [h.lower() for h in hdr]
        if "parámetro" not in lower[0] and "parametro" not in lower[0] and "factor" not in lower[0]:
            continue
        for row in rows:
            name_cell = row[0]
            val_cell = row[1] if len(row) > 1 else ""
            for pat, field_path, parser in VPARAM_MAP:
                if re.search(pat, name_cell, re.I):
                    parsed = parser(val_cell)
                    if parsed is not None:
                        out[field_path[0]] = parsed
                    break
    return out


def synthesize_tipologia_from_vparams(vparams, zone_body):
    """Given flat vparams dict, produce a single-tipología list.
    Tipología codigo is inferred from 'Tipos de edificación permitidos' prose
    (or 'allowed_building_types' hints); falls back to 'otra'."""
    # Try to infer codigo from prose
    inferred = None
    lowered = zone_body.lower()
    # Search for tipología mentions near the top
    for pat, code in TIPOLOGIA_CODES:
        if re.search(pat, lowered[:2000]):
            inferred = code
            break
    codigo = inferred or "otra"

    t = {
        "codigo": codigo,
        "nombre": codigo.replace("_", " ").title(),
        "thresholds": {
            "area_min_m2": None,
            "frente_min_m": None,
            "operator": "and",
        },
        "altura_m": None,
        "pisos_label": None,
        "FOT_pct": None,
        "FOS_pct": None,
        "FOS_SS_pct": None,
        "FOS_V_pct": None,
        "retiros": {},
    }
    for path, val in vparams.items():
        if "." in path:
            parent, child = path.split(".", 1)
            t.setdefault(parent, {})
            t[parent][child] = val
        else:
            t[path] = val
    return [t]


def subsection_map(zone_body):
    """Returns dict {letter: (title, body)} for subsections within a zone body.
    Recognizes two patterns:
      1. `### a) Title` on its own line (standard)
      2. `**a) Title:**` inline bold (PdE sector 1 style)
    """
    out = OrderedDict()
    # Pattern 1 — ### a) subsections
    sections = split_into_sections(zone_body)
    for level, heading, body in sections:
        if level != 3:
            continue
        m = re.match(r"^([a-h])\)\s*(.+?)\s*$", heading)
        if m:
            out[m.group(1)] = (m.group(2), body)

    # Pattern 2 — **a) Title:** bold inline. Split on each bold-subsection and
    # take the text up to the next one.
    if not out:
        bold_re = re.compile(r"^\*\*([a-h])\)\s*([^:*]+?)(?::?)\*\*", re.MULTILINE)
        matches = list(bold_re.finditer(zone_body))
        for idx, m in enumerate(matches):
            start = m.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(zone_body)
            body = zone_body[start:end].strip()
            out[m.group(1)] = (m.group(2).strip(), body)

    return out


def walk_all_l3(md_text):
    """Return list of (heading, body) for every ### section in the file,
    regardless of L2 nesting. Body runs until the next ## or ### heading."""
    lines = md_text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        m = re.match(r"^### (.+?)\s*$", lines[i])
        if m:
            heading = m.group(1)
            body_lines = []
            j = i + 1
            while j < len(lines):
                mj = re.match(r"^(#{2,3}) ", lines[j])
                if mj:
                    break
                body_lines.append(lines[j])
                j += 1
            out.append((heading, "\n".join(body_lines)))
            i = j
        else:
            i += 1
    return out


def extract_preamble_crosszone_tables(md_text):
    """Pull Art.D.N tables that apply to multiple zones (e.g. D.192 'Superficie
    y frente mínimo' spans zones 2.2, 2.3, 2.5.1). Returns dict
    {zone_code: [(tipologia_label, frente_min, area_min)]}."""
    out = defaultdict(list)
    for heading, body in walk_all_l3(md_text):
        if "Superficie" not in heading and "mínima" not in heading and "Dimensiones" not in heading and "mínimo" not in heading:
            continue
        # Find first pipe table with columns like "Zona | Tipo | Frente ... | Área ..."
        tables = re.split(r"\n\n+", body)
        for tb in tables:
            if not tb.strip().startswith("|"):
                continue
            hdr, rows = parse_markdown_table(tb)
            if not hdr or len(hdr) < 3:
                continue
            # Accept headers like Zona|Tipo|Frente mín.|Área mín.
            lower = [h.lower() for h in hdr]
            if not any("zona" in h for h in lower):
                continue
            if not any("tipo" in h for h in lower):
                continue
            zi = next(i for i, h in enumerate(lower) if "zona" in h)
            ti = next(i for i, h in enumerate(lower) if "tipo" in h)
            fi = next((i for i, h in enumerate(lower) if "frente" in h), None)
            ai = next((i for i, h in enumerate(lower) if "área" in h or "area" in h), None)
            for row in rows:
                zone_cell = row[zi]
                # Split "2.3 y 2.5.1" → ["2.3", "2.5.1"]
                zones = [z.strip() for z in re.split(r"\s+[yY,]\s+", zone_cell)]
                tipo = row[ti]
                frente = parse_frente(row[fi]) if fi is not None else None
                area = parse_area(row[ai]) if ai is not None else None
                for z in zones:
                    out[z].append({
                        "tipologia_label": tipo,
                        "codigo": normalize_tipologia(tipo),
                        "frente_min_m": frente,
                        "area_min_m2": area,
                    })
    return dict(out)


def tipologia_rows_from_table(body, label_col_candidates, value_extractors):
    """Generic: walk the first pipe table in `body`, use first column as
    tipología label and `value_extractors` to pull per-column values.

    Returns list of dicts: [{'codigo': ..., 'label': ..., <extracted fields>}]
    """
    out = []
    tables = re.split(r"\n\n+", body)
    for tb in tables:
        if not tb.strip().startswith("|"):
            continue
        hdr, rows = parse_markdown_table(tb)
        if not hdr or not rows:
            continue
        lower = [h.lower() for h in hdr]
        # Find the "tipo" column (by name candidate match)
        label_i = None
        for c in label_col_candidates:
            for i, h in enumerate(lower):
                if c in h:
                    label_i = i
                    break
            if label_i is not None:
                break
        if label_i is None:
            continue
        # Apply value extractors
        for row in rows:
            label = row[label_i]
            codigo = normalize_tipologia(label)
            if not codigo:
                continue
            rec = {"codigo": codigo, "label": label}
            for field_name, extractor, col_candidates in value_extractors:
                col_i = None
                for cc in col_candidates:
                    for i, h in enumerate(lower):
                        if cc in h:
                            col_i = i
                            break
                    if col_i is not None:
                        break
                if col_i is not None and col_i < len(row):
                    rec[field_name] = extractor(row[col_i])
                else:
                    rec[field_name] = None
            out.append(rec)
        break  # only first matching table
    return out


def extract_altura_table(body):
    """Returns [{codigo, altura_m, pisos_label}]."""
    return tipologia_rows_from_table(
        body,
        label_col_candidates=["tipo", "edif", "estruc"],
        value_extractors=[
            ("altura_m", parse_meters, ["altura"]),
            ("pisos_label", lambda s: s.strip() or None, ["plantas", "pisos", "niveles"]),
        ],
    )


def extract_fot_table(body):
    """Factores de ocupación — FOT per tipología (column form) or per-factor (row form)."""
    # Variant A (row form): | Factor | Bloque Bajo | Bloque Medio |
    #                       | FOS    | 50%         | 30%          |
    # Variant B (col form): | Tipo         | FOT |
    #                       | Bloque Bajo  | 70% |
    #
    # Try variant A first: header row with tipologías as columns.
    out = {}
    tables = re.split(r"\n\n+", body)
    for tb in tables:
        if not tb.strip().startswith("|"):
            continue
        hdr, rows = parse_markdown_table(tb)
        if not hdr or not rows:
            continue
        lower = [h.lower() for h in hdr]
        # Variant A: first col is factor name; remaining cols are tipologías
        tipol_cols = []
        for i, h in enumerate(hdr[1:], start=1):
            c = normalize_tipologia(h)
            if c:
                tipol_cols.append((i, c))
        if tipol_cols:
            for row in rows:
                factor_name = row[0].strip().lower()
                if "fot" in factor_name:
                    field = "FOT_pct"
                elif "fos ss" in factor_name or "fos_ss" in factor_name or "subsuelo" in factor_name:
                    field = "FOS_SS_pct"
                elif "fos v" in factor_name or "fos_v" in factor_name or "verde" in factor_name:
                    field = "FOS_V_pct"
                elif "fos" == factor_name.strip() or factor_name.strip().startswith("fos"):
                    field = "FOS_pct"
                else:
                    continue
                for col_i, codigo in tipol_cols:
                    if col_i < len(row):
                        val = parse_pct(row[col_i])
                        out.setdefault(codigo, {})[field] = val
            if out:
                return out
        # Variant B: first col is tipología; per-factor columns may be present.
        label_i = 0
        fot_i = next((i for i, h in enumerate(lower) if "fot" in h and "fos" not in h), None)
        fos_i = next((i for i, h in enumerate(lower)
                      if h.strip() == "fos" or h.strip().startswith("fos ") and "ss" not in h and "v" not in h and "verde" not in h), None)
        fos_ss_i = next((i for i, h in enumerate(lower) if "fos ss" in h or "subsuelo" in h), None)
        fos_v_i = next((i for i, h in enumerate(lower) if "fos v" in h or "verde" in h), None)
        if fot_i is None and fos_i is None:
            continue
        for row in rows:
            label = row[label_i]
            codigo = normalize_tipologia(label)
            if not codigo:
                continue
            rec = out.setdefault(codigo, {})
            if fot_i is not None and fot_i < len(row):
                rec["FOT_pct"] = parse_pct(row[fot_i])
            if fos_i is not None and fos_i < len(row):
                rec["FOS_pct"] = parse_pct(row[fos_i])
            if fos_ss_i is not None and fos_ss_i < len(row):
                rec["FOS_SS_pct"] = parse_pct(row[fos_ss_i])
            if fos_v_i is not None and fos_v_i < len(row):
                rec["FOS_V_pct"] = parse_pct(row[fos_v_i])
        # Don't break — continue to find additional per-tipología tables
    return out


def extract_retiros_table(body):
    """Returns {codigo: {frontal_m, lateral_m, fondo_m}} or None."""
    out = defaultdict(dict)
    tables = re.split(r"\n\n+", body)
    for tb in tables:
        if not tb.strip().startswith("|"):
            continue
        hdr, rows = parse_markdown_table(tb)
        if not hdr or not rows:
            continue
        lower = [h.lower() for h in hdr]
        # Look for "tipo" + direction columns
        label_i = next((i for i, h in enumerate(lower) if "tipo" in h), None)
        if label_i is None:
            continue
        front_i = next((i for i, h in enumerate(lower) if "frontal" in h or "frente" in h), None)
        fondo_i = next((i for i, h in enumerate(lower) if "fondo" in h), None)
        lat_i = next((i for i, h in enumerate(lower) if "lateral" in h), None)
        if not any([front_i, fondo_i, lat_i]):
            continue
        for row in rows:
            label = row[label_i]
            codigo = normalize_tipologia(label)
            if not codigo:
                continue
            r = out[codigo]
            if front_i is not None and front_i < len(row):
                v = parse_retiro(row[front_i])
                if v is not None:
                    r["frontal_m"] = v
            if fondo_i is not None and fondo_i < len(row):
                v = parse_retiro(row[fondo_i])
                if v is not None:
                    r["fondo_m"] = v
            if lat_i is not None and lat_i < len(row):
                v = parse_retiro(row[lat_i])
                if v is not None:
                    r["lateral_m"] = v
    return dict(out)


def extract_dimensiones_table(body):
    """Subzone-scope Dimensiones mínimas (c) or d) subsection).
    Returns {codigo: {area_min_m2, frente_min_m}}."""
    out = {}
    tables = re.split(r"\n\n+", body)
    for tb in tables:
        if not tb.strip().startswith("|"):
            continue
        hdr, rows = parse_markdown_table(tb)
        if not hdr or not rows:
            continue
        lower = [h.lower() for h in hdr]
        label_i = next((i for i, h in enumerate(lower) if "tipo" in h), 0)
        frente_i = next((i for i, h in enumerate(lower) if "frente" in h), None)
        area_i = next((i for i, h in enumerate(lower) if "área" in h or "area" in h), None)
        if frente_i is None and area_i is None:
            continue
        for row in rows:
            label = row[label_i]
            codigo = normalize_tipologia(label)
            if not codigo:
                continue
            rec = {}
            if frente_i is not None and frente_i < len(row):
                rec["frente_min_m"] = parse_frente(row[frente_i])
            if area_i is not None and area_i < len(row):
                rec["area_min_m2"] = parse_area(row[area_i])
            if rec:
                out[codigo] = rec
        break
    return out


def merge_tipologias(*dicts):
    """Merge a list of {codigo: {...}} dicts, later wins for set fields."""
    out = defaultdict(dict)
    for d in dicts:
        for k, v in (d or {}).items():
            if isinstance(v, dict):
                out[k].update(v)
            else:
                out[k] = v
    return dict(out)


def build_zone_entry(zone_code, zone_name, zone_body, preamble, titulo):
    """Build the new-schema subzone entry from extracted data."""
    subs = subsection_map(zone_body)
    warnings = []
    # Locate relevant subsections by letter AND/OR title keywords
    def find_by_title(keywords):
        for ltr, (title, body) in subs.items():
            if any(k in title.lower() for k in keywords):
                return body
        return None

    altura_body = find_by_title(["altura"])
    retiros_body = find_by_title(["retiro"])
    fot_body = find_by_title(["factores", "ocupación", "ocupacion"])
    dims_body = find_by_title(["dimension", "superficie", "mínimas"])

    # Per-zone tipología data from subsection tables
    altura_data = extract_altura_table(altura_body) if altura_body else []
    fot_data = extract_fot_table(fot_body) if fot_body else {}
    retiros_data = extract_retiros_table(retiros_body) if retiros_body else {}
    dims_data = extract_dimensiones_table(dims_body) if dims_body else {}

    # From preamble cross-zone tables
    preamble_rows = preamble.get(zone_code, [])
    preamble_thresholds = {}
    for pr in preamble_rows:
        c = pr["codigo"]
        if c:
            preamble_thresholds[c] = {
                "area_min_m2": pr["area_min_m2"],
                "frente_min_m": pr["frente_min_m"],
            }

    # Build tipologias list — merge by codigo
    tipos_accum = defaultdict(dict)
    for row in altura_data:
        c = row["codigo"]
        tipos_accum[c]["altura_m"] = row.get("altura_m")
        if row.get("pisos_label"):
            tipos_accum[c]["pisos_label"] = row.get("pisos_label")
    for c, fots in fot_data.items():
        tipos_accum[c].update(fots)
    for c, ret in retiros_data.items():
        tipos_accum[c]["retiros"] = ret
    for c, dims in dims_data.items():
        tipos_accum[c]["thresholds"] = {
            "area_min_m2": dims.get("area_min_m2"),
            "frente_min_m": dims.get("frente_min_m"),
            "operator": "and",
        }
    for c, th in preamble_thresholds.items():
        existing = tipos_accum[c].get("thresholds") or {"operator": "and"}
        # Preamble wins if subsection was silent
        if existing.get("area_min_m2") is None and th.get("area_min_m2") is not None:
            existing["area_min_m2"] = th["area_min_m2"]
        if existing.get("frente_min_m") is None and th.get("frente_min_m") is not None:
            existing["frente_min_m"] = th["frente_min_m"]
        tipos_accum[c]["thresholds"] = existing

    # Finalize in canonical order
    ORDER = [
        "unidad_aislada", "unidad_apareada",
        "edificacion_baja",
        "bloque_bajo_9m", "bloque_bajo_12m", "bloque_bajo",
        "bloque_medio", "bloque_alto",
        "conjunto_unidades", "conjunto_bloques",
        "torre_media", "torre_alta",
        "hotelero", "otra",
    ]
    tipologias = []
    for c in ORDER:
        if c in tipos_accum:
            t = tipos_accum[c]
            # Fill missing shape with nulls
            t.setdefault("codigo", c)
            t.setdefault("nombre", c.replace("_", " ").title())
            t.setdefault("thresholds", {
                "area_min_m2": None, "frente_min_m": None, "operator": "and"
            })
            t.setdefault("altura_m", None)
            t.setdefault("pisos_label", None)
            t.setdefault("FOT_pct", None)
            t.setdefault("FOS_pct", None)
            t.setdefault("FOS_SS_pct", None)
            t.setdefault("FOS_V_pct", None)
            t.setdefault("retiros", {})
            tipologias.append(t)
    for c in tipos_accum:
        if c not in ORDER:
            warnings.append(f"{zone_code}: unknown tipología code '{c}' — not in ORDER")

    if not tipologias:
        # Fallback: try vertical parameter table extraction (single-tipología zones)
        vparams = extract_vertical_params(zone_body)
        if vparams:
            tipologias = synthesize_tipologia_from_vparams(vparams, zone_body)

    if not tipologias:
        warnings.append(f"{zone_code}: no tipologías extracted; AI fallback needed")

    entry = {
        "zone_code": zone_code,
        "zone_name": zone_name,
        "source_titulo": titulo,
        "tipologias": tipologias,
    }
    return entry, warnings


def process_titulo(titulo_slug):
    path = os.path.join(DATOS, f"{titulo_slug}.md")
    if not os.path.exists(path):
        return None, [f"{titulo_slug}: file missing"]
    with open(path) as f:
        md = f.read()
    preamble = extract_preamble_crosszone_tables(md)
    zones = zone_sections(md)
    entries = []
    warnings = []
    for zone_code, zone_name, body in zones:
        entry, wns = build_zone_entry(zone_code, zone_name, body, preamble, titulo_slug)
        entries.append(entry)
        warnings.extend(wns)
    return entries, warnings


def verify_23(entries):
    """Sanity check: the extracted MALDONADO 2.3 entry should match the
    canonical DRAFT_ENTRY_MALDONADO_2_3 in scenarios.py."""
    from scenarios import DRAFT_ENTRY_MALDONADO_2_3 as canon
    found = next((e for e in entries if e["zone_code"] == "2.3"), None)
    if not found:
        print("verify: Zone 2.3 not found in extracted output", file=sys.stderr)
        return False
    # Compare FOT_pct, altura_m per tipología
    canon_tips = {t["codigo"]: t for t in canon["tipologias"]}
    found_tips = {t["codigo"]: t for t in found["tipologias"]}
    ok = True
    for code in ["bloque_bajo", "bloque_medio"]:
        c = canon_tips.get(code, {})
        f = found_tips.get(code, {})
        for field in ["FOT_pct", "altura_m"]:
            cv, fv = c.get(field), f.get(field)
            status = "OK" if cv == fv else "MISMATCH"
            if cv != fv:
                ok = False
            print(f"  [{status}] 2.3.{code}.{field}: canonical={cv!r} extracted={fv!r}")
        cth = c.get("thresholds", {})
        fth = f.get("thresholds", {})
        for field in ["area_min_m2", "frente_min_m"]:
            cv, fv = cth.get(field), fth.get(field)
            status = "OK" if cv == fv else "MISMATCH"
            if cv != fv:
                ok = False
            print(f"  [{status}] 2.3.{code}.thresholds.{field}: canonical={cv!r} extracted={fv!r}")
    return ok


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--titulo", help="one titulo slug to process")
    parser.add_argument("--verify-23", action="store_true",
                        help="verify MALDONADO 2.3 extraction matches scenarios.py DRAFT")
    args = parser.parse_args()

    os.makedirs(EXTRACT_DIR, exist_ok=True)

    titulos = [args.titulo] if args.titulo else STANDARD_TITULOS

    total_zones = 0
    total_warnings = 0
    for slug in titulos:
        entries, warnings = process_titulo(slug)
        if entries is None:
            print(f"[skip] {slug}: {warnings[0] if warnings else 'unknown error'}")
            continue

        out_path = os.path.join(EXTRACT_DIR, f"{slug}.json")
        with open(out_path, "w") as f:
            json.dump({"titulo": slug, "zones": entries}, f, indent=2, ensure_ascii=False)

        warn_path = os.path.join(EXTRACT_DIR, f"{slug}-warnings.json")
        with open(warn_path, "w") as f:
            json.dump({"titulo": slug, "warnings": warnings}, f, indent=2, ensure_ascii=False)

        print(f"[ok] {slug}: {len(entries)} zones, {len(warnings)} warnings → {out_path}")
        total_zones += len(entries)
        total_warnings += len(warnings)

        if args.verify_23 and slug == "titulo-ii-cap-ii-sector-2":
            print(f"\n  Verification against canonical MALDONADO 2.3:")
            verify_23(entries)

    print(f"\nTotal: {total_zones} zones extracted, {total_warnings} warnings across {len(titulos)} titulos")


if __name__ == "__main__":
    main()
