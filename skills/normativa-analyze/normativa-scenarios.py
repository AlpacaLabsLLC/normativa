#!/usr/bin/env python3
"""
Scenario engine — Phase 2 T10-0 validation.

Given a zone entry (tone-zones.json subzone with `tipologias[]`), plus the
parcel/union area and frente, emit the applicable tipologías with outcomes.

This is the pure function that feeds the drawer's 4-column scenarios grid.

Usage:
  python3 scenarios.py                    # runs the built-in test cases
  python3 scenarios.py --zone 2.3 --area 1200 --frente 35
"""

import argparse
import json
import os
import sys

DRAFT_ENTRY_MALDONADO_2_3 = {
    "zone_code": "2.3",
    "zone_name": "Barrio Jardín",
    "locality": "MALDONADO",
    "article": "Art. D.201",
    "decreto": "3885/2011",
    "tipologias": [
        {
            "codigo": "unidad_aislada",
            "nombre": "Unidad aislada",
            "thresholds": {"area_min_m2": None, "frente_min_m": None, "operator": "and"},
            "altura_m": 7,
            "pisos_label": "PB + PA",
            "FOT_pct": 50,
            "retiros": {"frontal_m": 4, "lateral_m": 3, "fondo_m": 3},
        },
        {
            "codigo": "unidad_apareada",
            "nombre": "Unidad apareada",
            "thresholds": {"area_min_m2": None, "frente_min_m": None, "operator": "and"},
            "altura_m": 7,
            "pisos_label": "PB + PA",
            "FOT_pct": 50,
            "retiros": {"frontal_m": 4, "lateral_m": 3, "fondo_m": 3},
        },
        {
            "codigo": "bloque_bajo",
            "nombre": "Bloque Bajo",
            "thresholds": {
                "area_min_m2": 450,
                "frente_min_m": 14,
                "operator": "and",
                "manzana_entera_override": False,
            },
            "altura_m": 13.60,
            "pisos_label": "PB + 4PA",
            "FOS_pct": 50,
            "FOT_pct": 180,
            "retiros": {"frontal_m": 4, "lateral_m": "2/7_altura_min_3", "fondo_m": 5},
        },
        {
            "codigo": "bloque_medio",
            "nombre": "Bloque Medio",
            "thresholds": {
                "area_min_m2": 1000,
                "frente_min_m": 30,
                "operator": "and",
                "manzana_entera_override": False,
            },
            "altura_m": 28,
            "pisos_label": "PB + 9PA",
            "FOS_pct": 30,
            "FOT_pct": 290,
            "retiros": {"frontal_m": 4, "lateral_m": "2/7_altura_min_3", "fondo_m": 9},
        },
    ],
}


def applicable_tipologias(zone_entry, area_m2, frente_m, es_manzana_entera=False):
    """Filter zone.tipologias to those whose thresholds are met by (area, frente).

    Returns the list of tipologia dicts. Order is preserved (source order — first
    to last yields aislada → apareada → bloque_bajo → bloque_medio).
    """
    out = []
    for t in zone_entry.get("tipologias", []):
        th = t.get("thresholds", {})
        op = th.get("operator", "and")

        area_min = th.get("area_min_m2")
        area_max = th.get("area_max_m2")
        frente_min = th.get("frente_min_m")

        ok_area = area_min is None or area_m2 >= area_min
        if th.get("manzana_entera_override") and es_manzana_entera:
            ok_area = True
        ok_area_max = area_max is None or area_m2 <= area_max
        ok_frente = frente_min is None or frente_m >= frente_min

        if op == "or":
            ok = (ok_area or ok_frente) and ok_area_max
        else:
            ok = ok_area and ok_frente and ok_area_max

        if ok:
            out.append(t)
    return out


def describe(tipologia, area_m2):
    """One-line summary for test output."""
    fot = tipologia.get("FOT_pct")
    fot_m2 = int(round(area_m2 * fot / 100)) if fot else None
    return (
        f"{tipologia['codigo']:<18} "
        f"altura {tipologia['altura_m']:>5} m · "
        f"{tipologia['pisos_label']:<12} · "
        f"FOT {fot:>3}% = {fot_m2:>5} m²"
        if fot_m2 is not None
        else f"{tipologia['codigo']:<18} altura {tipologia['altura_m']} m"
    )


def run_tests():
    """Canonical test cases for MALDONADO 2.3."""
    zone = DRAFT_ENTRY_MALDONADO_2_3
    cases = [
        # (area, frente, expected_codigos, label)
        (300, 10, ["unidad_aislada", "unidad_apareada"],
         "Tiny lot (300 m² × 10 m) — only aislada/apareada"),
        (500, 14, ["unidad_aislada", "unidad_apareada", "bloque_bajo"],
         "450 m² + 14 m threshold met — unlocks bloque_bajo"),
        (1200, 35, ["unidad_aislada", "unidad_apareada", "bloque_bajo", "bloque_medio"],
         "Large lot (1200 m² × 35 m) — all 4 tipologías available"),
        (1200, 25, ["unidad_aislada", "unidad_apareada", "bloque_bajo"],
         "1200 m² but only 25 m frente — bloque_medio frente gate fails"),
        (900, 30, ["unidad_aislada", "unidad_apareada", "bloque_bajo"],
         "900 m² with 30 m frente — bloque_medio area gate fails"),
        (450, 14, ["unidad_aislada", "unidad_apareada", "bloque_bajo"],
         "Exact minimum threshold — bloque_bajo just unlocks"),
        (449, 14, ["unidad_aislada", "unidad_apareada"],
         "One m² below threshold — bloque_bajo does NOT unlock"),
    ]

    print("\n=== MALDONADO Zone 2.3 Barrio Jardín — scenario engine tests ===")
    all_pass = True
    for area, frente, expected, label in cases:
        got = [t["codigo"] for t in applicable_tipologias(zone, area, frente)]
        status = "PASS" if got == expected else "FAIL"
        if got != expected:
            all_pass = False
        print(f"\n[{status}] {label}")
        print(f"       area={area} m², frente={frente} m")
        print(f"       expected: {expected}")
        print(f"       got:      {got}")
        if status == "PASS":
            print("       outcomes:")
            for t in applicable_tipologias(zone, area, frente):
                fot_m2 = int(round(area * t['FOT_pct'] / 100)) if t.get('FOT_pct') else None
                print(f"         · {t['nombre']:<20} · altura {t['altura_m']} m · "
                      f"FOT {t['FOT_pct']}% = {fot_m2} m² built")

    print("\n" + ("All tests PASS" if all_pass else "SOME TESTS FAILED"))
    return 0 if all_pass else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zone", help="zone_code to resolve (e.g. 2.3)")
    parser.add_argument("--area", type=float, help="parcel/union area in m²")
    parser.add_argument("--frente", type=float, help="parcel frente in m")
    parser.add_argument("--manzana-entera", action="store_true",
                        help="treat as manzana-entera (overrides area_min)")
    parser.add_argument("--tone-zones",
                        default=os.path.join(os.path.dirname(__file__),
                                             "datos", "tone-zones.json"),
                        help="path to tone-zones.json (unused until T10-1 lands)")
    args = parser.parse_args()

    if args.zone and args.area and args.frente:
        # Use the draft entry if zone matches; else try loading from JSON.
        # Until T10-1 migrates tone-zones.json, the JSON path will have pseudo-subzones
        # without `tipologias[]` and return an empty list.
        zone = DRAFT_ENTRY_MALDONADO_2_3 if args.zone == "2.3" else None
        if zone is None:
            print(f"Only the hand-crafted 2.3 draft is available until T10-1 ships. "
                  f"Passed --zone={args.zone} is not in the draft.",
                  file=sys.stderr)
            return 2
        for t in applicable_tipologias(zone, args.area, args.frente, args.manzana_entera):
            print(json.dumps(t, ensure_ascii=False, indent=2))
        return 0

    return run_tests()


if __name__ == "__main__":
    sys.exit(main())
