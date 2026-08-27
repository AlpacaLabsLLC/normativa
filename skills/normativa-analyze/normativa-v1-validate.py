#!/usr/bin/env python3
"""
normativa-v1-validate.py — strict validator for `*.normativa.v1.json` envelopes.

Named after the schema id (`estudio-local.normativa.v1`) rather than after a
specific skill, so the script survives skill renames intact. Runs after
/normativa-analyze writes its output, before /normativa-informe consumes it. Refuses
malformed envelopes with concrete error messages so the LLM author can fix
them without guesswork.

Usage:
  python3 normativa-v1-validate.py <path-to-envelope.normativa.v1.json>

Exit codes:
  0  envelope is valid (also prints "ok ..." to stdout)
  1  envelope is invalid (prints concrete error list to stderr)
  2  bad invocation
"""

import json
import re
import sys
from pathlib import Path

REQUIRED_SCHEMA = "estudio-local.normativa.v1"
ALLOWED_REGIMEN = {"comun", "ph", "otro", "mixed"}
ALLOWED_DATA_QUALITY = {"verified", "partial", "estimated", "pending", "conditional"}
ISO8601_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)


def is_str(x): return isinstance(x, str)
def is_num(x): return isinstance(x, (int, float)) and not isinstance(x, bool)
def is_bool(x): return isinstance(x, bool)


def err(errors, path, msg):
    errors.append(f"  • {path}: {msg}")


def validate_selection(sel, errors):
    if not isinstance(sel, dict):
        err(errors, "selection", f"expected object, got {type(sel).__name__}")
        return

    padrones = sel.get("padrones")
    if not isinstance(padrones, list) or len(padrones) == 0:
        err(errors, "selection.padrones", "expected non-empty array")
    else:
        for i, p in enumerate(padrones):
            if not is_str(p):
                err(errors, f"selection.padrones[{i}]",
                    f"expected string, got {type(p).__name__} ({p!r}) — "
                    "the renderer joins padrones as strings; ints will crash")
            elif not p.strip():
                err(errors, f"selection.padrones[{i}]", "expected non-empty string")

    if not is_str(sel.get("locality")) or not sel.get("locality"):
        err(errors, "selection.locality", "expected non-empty string")

    area = sel.get("area_total_m2")
    if not is_num(area) or area <= 0:
        err(errors, "selection.area_total_m2",
            f"expected positive number, got {type(area).__name__} ({area!r})")

    regimen = sel.get("regimen")
    if regimen is not None and regimen not in ALLOWED_REGIMEN:
        err(errors, "selection.regimen",
            f"expected one of {sorted(ALLOWED_REGIMEN)}, got {regimen!r}")

    if "frente_estimado_m" in sel and sel["frente_estimado_m"] is not None:
        if not is_num(sel["frente_estimado_m"]):
            err(errors, "selection.frente_estimado_m", "expected number or null")

    if "adjacent" in sel and not is_bool(sel["adjacent"]):
        err(errors, "selection.adjacent",
            f"expected boolean, got {type(sel['adjacent']).__name__}")

    lots = sel.get("lots")
    if lots is not None:
        if not isinstance(lots, list):
            err(errors, "selection.lots", f"expected array, got {type(lots).__name__}")
        else:
            padron_set = set(p for p in (padrones or []) if is_str(p))
            for i, lot in enumerate(lots):
                lp = f"selection.lots[{i}]"
                if not isinstance(lot, dict):
                    err(errors, lp, "expected object")
                    continue
                if not is_str(lot.get("padron")):
                    err(errors, f"{lp}.padron",
                        f"expected string, got {type(lot.get('padron')).__name__}")
                elif padron_set and lot["padron"] not in padron_set:
                    err(errors, f"{lp}.padron",
                        f"{lot['padron']!r} not in selection.padrones")
                if "area_m2" in lot and (not is_num(lot["area_m2"]) or lot["area_m2"] <= 0):
                    err(errors, f"{lp}.area_m2", "expected positive number")
                if "frente_m" in lot and lot["frente_m"] is not None and not is_num(lot["frente_m"]):
                    err(errors, f"{lp}.frente_m", "expected number or null")
                if "regimen" in lot and lot["regimen"] not in ALLOWED_REGIMEN:
                    err(errors, f"{lp}.regimen",
                        f"expected one of {sorted(ALLOWED_REGIMEN)}, got {lot['regimen']!r}")


def validate_zone(zone, errors):
    if not isinstance(zone, dict):
        err(errors, "zone", f"expected object, got {type(zone).__name__}")
        return
    if not is_str(zone.get("code")) or not zone.get("code"):
        err(errors, "zone.code", "expected non-empty string")
    dq = zone.get("data_quality")
    if dq not in ALLOWED_DATA_QUALITY:
        err(errors, "zone.data_quality",
            f"expected one of {sorted(ALLOWED_DATA_QUALITY)}, got {dq!r}")
    cat = zone.get("tipologias_catalog")
    if cat is not None and not isinstance(cat, list):
        err(errors, "zone.tipologias_catalog", "expected array or omitted")
    elif isinstance(cat, list):
        for i, t in enumerate(cat):
            if not isinstance(t, dict):
                err(errors, f"zone.tipologias_catalog[{i}]", "expected object")
                continue
            if not is_str(t.get("codigo")):
                err(errors, f"zone.tipologias_catalog[{i}].codigo", "expected string")


def validate_scenarios(scenarios, errors):
    if not isinstance(scenarios, list):
        err(errors, "scenarios",
            f"expected array, got {type(scenarios).__name__}")
        return []
    if len(scenarios) == 0:
        err(errors, "scenarios",
            "expected at least one entry (use applicable: false if none apply)")
        return []

    ids = []
    for i, s in enumerate(scenarios):
        sp = f"scenarios[{i}]"
        if not isinstance(s, dict):
            err(errors, sp, "expected object")
            continue
        sid = s.get("id")
        if not is_str(sid) or not sid:
            err(errors, f"{sp}.id", "expected non-empty string")
        else:
            if sid in ids:
                err(errors, f"{sp}.id", f"duplicate id {sid!r}")
            ids.append(sid)
        if not is_str(s.get("label")):
            err(errors, f"{sp}.label", "expected string")
        applicable = s.get("applicable")
        if not is_bool(applicable):
            err(errors, f"{sp}.applicable",
                f"expected boolean, got {type(applicable).__name__}")
            continue
        if applicable:
            tip = s.get("tipologia")
            if not isinstance(tip, dict) or not is_str(tip.get("codigo")):
                err(errors, f"{sp}.tipologia.codigo",
                    "expected non-empty string when applicable=true")
            envelope = s.get("envelope")
            if not isinstance(envelope, dict):
                err(errors, f"{sp}.envelope", "expected object when applicable=true")
            else:
                for key in ("FOS_pct", "FOT_pct", "altura_m",
                            "area_edificable_m2", "area_ocupacion_m2",
                            "viviendas_estimadas"):
                    if key in envelope and envelope[key] is not None and not is_num(envelope[key]):
                        err(errors, f"{sp}.envelope.{key}",
                            f"expected number or null, got {type(envelope[key]).__name__} ({envelope[key]!r})")
            retiros = s.get("retiros")
            if retiros is not None and not isinstance(retiros, dict):
                err(errors, f"{sp}.retiros", "expected object or omitted")
            elif isinstance(retiros, dict):
                for key in ("frontal_m", "lateral_m", "fondo_m", "entre_volumenes_m"):
                    if key in retiros and retiros[key] is not None and not is_num(retiros[key]):
                        err(errors, f"{sp}.retiros.{key}",
                            f"expected number or null, got {type(retiros[key]).__name__}")
            if "tipologias_habilitadas" in s:
                th = s["tipologias_habilitadas"]
                if not isinstance(th, list):
                    err(errors, f"{sp}.tipologias_habilitadas", "expected array")
                else:
                    for j, code in enumerate(th):
                        if not is_str(code):
                            err(errors, f"{sp}.tipologias_habilitadas[{j}]",
                                "expected string")
            if "sketch" in s and s["sketch"] is not None and not is_str(s["sketch"]):
                err(errors, f"{sp}.sketch",
                    "expected string (ASCII envelope diagram with \\n line breaks) or null")
        else:
            if not is_str(s.get("reason")):
                err(errors, f"{sp}.reason",
                    "expected string when applicable=false")
    return ids


def validate_recommendation(rec, scenario_ids, errors):
    if not isinstance(rec, dict):
        err(errors, "recommendation",
            f"expected object, got {type(rec).__name__}")
        return
    sid = rec.get("scenario_id")
    if sid is not None:
        if not is_str(sid):
            err(errors, "recommendation.scenario_id",
                f"expected string or null, got {type(sid).__name__}")
        elif sid not in scenario_ids:
            err(errors, "recommendation.scenario_id",
                f"references non-existent scenario {sid!r} (known ids: {scenario_ids})")
    if "tradeoffs" in rec:
        tr = rec["tradeoffs"]
        if not isinstance(tr, list):
            err(errors, "recommendation.tradeoffs", "expected array")
        else:
            for i, t in enumerate(tr):
                if not is_str(t):
                    err(errors, f"recommendation.tradeoffs[{i}]", "expected string")


def validate_envelope(envelope):
    errors = []

    if not isinstance(envelope, dict):
        return [f"top-level: expected object, got {type(envelope).__name__}"]

    schema = envelope.get("schema")
    if schema != REQUIRED_SCHEMA:
        err(errors, "schema", f"expected {REQUIRED_SCHEMA!r}, got {schema!r}")

    gen_at = envelope.get("generated_at")
    if not is_str(gen_at) or not ISO8601_RE.match(gen_at):
        err(errors, "generated_at",
            f"expected ISO-8601 UTC string (e.g. 2026-05-07T13:45:00Z), got {gen_at!r}")

    if not is_str(envelope.get("skill_version")):
        err(errors, "skill_version", "expected string")

    validate_selection(envelope.get("selection"), errors)
    validate_zone(envelope.get("zone"), errors)
    scenario_ids = validate_scenarios(envelope.get("scenarios"), errors)
    validate_recommendation(envelope.get("recommendation"), scenario_ids, errors)

    caveats = envelope.get("caveats")
    if caveats is None:
        err(errors, "caveats", "required (use [] if none)")
    elif not isinstance(caveats, list):
        err(errors, "caveats", "expected array")
    else:
        for i, c in enumerate(caveats):
            if not is_str(c):
                err(errors, f"caveats[{i}]", "expected string")

    sources = envelope.get("sources")
    if not isinstance(sources, dict):
        err(errors, "sources", "expected object (sources.map_url is required)")
    else:
        if "decretos" in sources and not isinstance(sources["decretos"], list):
            err(errors, "sources.decretos", "expected array")
        map_url = sources.get("map_url")
        if not is_str(map_url) or not map_url.strip():
            err(errors, "sources.map_url",
                "required non-empty string — link to the parcel(s) on the Mapa app. "
                "Pattern: https://estudio-local.com/mapa?padron=<comma-joined>&loc=<locality-slug>")
        elif not (map_url.startswith("http://") or map_url.startswith("https://")):
            err(errors, "sources.map_url",
                f"expected http(s) URL, got {map_url!r}")

    return errors


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip(), file=sys.stderr)
        sys.exit(2)

    path = Path(sys.argv[1]).expanduser().resolve()
    if not path.is_file():
        print(f"error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    try:
        with path.open() as f:
            envelope = json.load(f)
    except json.JSONDecodeError as e:
        print(f"error: invalid JSON in {path}: {e}", file=sys.stderr)
        sys.exit(1)

    errors = validate_envelope(envelope)
    if errors:
        print(f"✗ {path.name}: {len(errors)} validation error(s):", file=sys.stderr)
        for line in errors:
            print(line, file=sys.stderr)
        print(file=sys.stderr)
        print("Fix the envelope and re-run. Reference: skills/normativa-analyze/normativa-v1-schema.md",
              file=sys.stderr)
        sys.exit(1)

    print(f"ok {path.name}: envelope conforms to {REQUIRED_SCHEMA}")


if __name__ == "__main__":
    main()
