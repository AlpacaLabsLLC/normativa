#!/usr/bin/env python3
"""
Merge reviewed <titulo>-reviewed.json extractions into tone-zones.json.

For each titulo, locate target locality(ies) in tone-zones.json, match each
reviewed zone_code to the canonical subzone (consolidating pseudo-subzones
like 2.2.BB + 2.2.BM → 2.2), replace tipologias/source_article/decreto on the
canonical subzone, and delete pseudo-subzones that were consolidated.

Preserves: locality, titulo mapping, zone_name, manzanas, article (except
when reviewed has source_article), decreto, allowed_building_types (derived
from tipologias codes), prohibited_uses, special_rules, audit notes.

Usage:
  python3 merge-tipologias.py --dry-run        # show what would change
  python3 merge-tipologias.py                  # apply changes
  python3 merge-tipologias.py --backup         # write tone-zones.json.bak first
"""

import argparse
import json
import os
import re
import shutil
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATOS = os.path.join(HERE, "datos")
TONE_ZONES = os.path.join(DATOS, "tone-zones.json")
EXTRACT_DIR = os.path.join(DATOS, "extractions")

# Titulo → target locality(ies) in tone-zones.json. For titulos that span
# multiple localities (titulo-v-cap-ii-sector-2), use zone_code prefix routing.
TITULO_TO_LOCALITY = {
    "titulo-ii-cap-ii-sector-1":   ["PUNTA DEL ESTE"],
    "titulo-ii-cap-ii-sector-2":   ["MALDONADO"],
    "titulo-iii-cap-ii-sector-1":  ["LA BARRA - MANANTIALES"],
    "titulo-iii-cap-iii-sector-2": ["JOSE IGNACIO"],
    "titulo-v-cap-i-sector-1":     ["SAN CARLOS"],
    "titulo-v-cap-ii-sector-2":    None,  # routed by zone_code prefix (see below)
}

# For multi-locality titulos, route by zone_code prefix.
ZONE_CODE_LOCALITY_ROUTE = {
    "2.1": "GARZON",        # Pueblo Garzón
    "2.2": "AIGUA",          # Aiguá
    "2.3": "PAN DE AZUCAR",  # Pan de Azúcar
}


def pseudo_subzone_base(code):
    """Given a subzone code, return the canonical base if it's a pseudo-
    subzone (e.g. '2.2.BB' → '2.2', '1.1.OE' → '1.1', '1.6.UA' → '1.6'),
    else None."""
    # Pseudo-subzone suffixes we've observed: .BB, .BM, .OE, .UA
    # Plus SC's 1.4BJ.x (Barrio Jardín within 1.4)
    m = re.match(r"^(.+)\.(BB|BM|OE|UA|BA)$", code)
    if m:
        return m.group(1)
    # SC's 1.4BJ.x — kept as-is (not pseudo, but zone 1.4 with BJ subdivision)
    return None


def pick_canonical_subzone(locality_zones, zone_code):
    """Find the canonical subzone entry for `zone_code` within the locality's
    zones. Returns (parent_zone_key, subzone_key, subzone_obj, pseudo_siblings)
    where pseudo_siblings are subzone keys that should be deleted after merge
    (the .BB/.BM consolidated variants)."""
    # Walk zones to find a matching subzone entry.
    for zk, zv in locality_zones.items():
        subs = zv.get("subzones", {})
        if zone_code in subs:
            # Direct hit.
            # Check for pseudo-subzone siblings at this zone_code (e.g. 2.2.BB)
            pseudo_siblings = [
                sk for sk in subs
                if sk != zone_code and pseudo_subzone_base(sk) == zone_code
            ]
            return zk, zone_code, subs[zone_code], pseudo_siblings
        # Try matching a pseudo-subzone to the canonical zone_code
        for sk in list(subs.keys()):
            base = pseudo_subzone_base(sk)
            if base == zone_code:
                # Found a pseudo; use it as the canonical target (the first one)
                pseudo_siblings = [
                    other_sk for other_sk in subs
                    if other_sk != sk and pseudo_subzone_base(other_sk) == zone_code
                ]
                return zk, sk, subs[sk], pseudo_siblings
    return None, None, None, []


def merge_tipologias_into_subzone(subzone_obj, reviewed_entry):
    """Update subzone_obj in place with tipologias, source_article, decreto
    from reviewed_entry. Preserves all other fields.

    Sets allowed_building_types as a derived list of tipologia codes.
    Legacy scalar fields (altura_maxima, FOT, FOS, retiros, etc.) are
    retained if present (for back-compat) but take second priority — the
    new tipologias[] is the source of truth."""
    tipologias = reviewed_entry.get("tipologias", [])
    subzone_obj["tipologias"] = tipologias
    if reviewed_entry.get("source_article"):
        subzone_obj["article"] = reviewed_entry["source_article"]
    if reviewed_entry.get("decreto"):
        subzone_obj["decreto"] = reviewed_entry["decreto"]

    # Derived allowed_building_types from tipologia codes
    codes = [t["codigo"] for t in tipologias if t.get("codigo")]
    if codes:
        subzone_obj["allowed_building_types"] = codes

    # Audit trail (coerce to list if legacy entry stored as string)
    existing = subzone_obj.get("_notes", [])
    if isinstance(existing, str):
        existing = [existing] if existing else []
    marker = "Migrated to tipologias[] schema"
    if not any(marker in str(n) for n in existing):
        existing.append("Migrated to tipologias[] schema (T10-1c bulk merge 2026-04-24)")
    subzone_obj["_notes"] = existing


def promote_subzone_key(locality_zones, parent_key, old_key, new_key):
    """If pseudo-subzone key differs from desired canonical, rename."""
    if old_key == new_key:
        return False
    subs = locality_zones[parent_key]["subzones"]
    if new_key in subs:
        # Conflict — caller must handle
        return False
    subs[new_key] = subs.pop(old_key)
    return True


def merge_titulo(data, titulo, reviewed, stats):
    """Merge one titulo's reviewed extractions into the main tone-zones.json.
    Returns list of unmatched zones (couldn't find a target subzone)."""
    unmatched = []

    # Determine target locality per zone
    routes = TITULO_TO_LOCALITY.get(titulo)

    for entry in reviewed.get("zones", []):
        zone_code = entry.get("zone_code")
        if not zone_code:
            continue

        # Suffix normalization — map reviewer-picked suffixes to tone-zones
        # conventions (e.g. `-oeste` → `.O`, `-este` → `.E`).
        zone_code = re.sub(r"-oeste$", ".O", zone_code)
        zone_code = re.sub(r"-este$", ".E", zone_code)

        # Skip parent-only containers (empty tipologias, just shell entries)
        if not entry.get("tipologias"):
            continue

        # Decide locality
        if routes is None:  # Multi-locality titulo — route by prefix
            # zone_code like "2.1.1", "2.2.3"; prefix = first two parts
            parts = zone_code.split(".")
            prefix = ".".join(parts[:2]) if len(parts) >= 2 else zone_code
            # Try shorter prefixes too
            locality = None
            for pfx in [prefix, parts[0]]:
                if pfx in ZONE_CODE_LOCALITY_ROUTE:
                    locality = ZONE_CODE_LOCALITY_ROUTE[pfx]
                    break
            if not locality:
                unmatched.append(f"{titulo} {zone_code}: no locality route for prefix {prefix!r}")
                continue
            target_localities = [locality]
        else:
            target_localities = routes

        matched = False
        for loc in target_localities:
            if loc not in data["localities"]:
                continue
            loc_zones = data["localities"][loc]["zones"]
            parent_key, found_key, subzone_obj, pseudo_siblings = pick_canonical_subzone(loc_zones, zone_code)

            if subzone_obj is None:
                continue

            # Rename pseudo to canonical if needed
            if found_key != zone_code:
                if pseudo_subzone_base(found_key) == zone_code:
                    promote_subzone_key(loc_zones, parent_key, found_key, zone_code)
                    subzone_obj = loc_zones[parent_key]["subzones"][zone_code]

            merge_tipologias_into_subzone(subzone_obj, entry)

            # Delete pseudo-subzones that got consolidated
            for psib in pseudo_siblings:
                if psib in loc_zones[parent_key]["subzones"]:
                    del loc_zones[parent_key]["subzones"][psib]
                    stats["pseudo_deleted"] += 1

            stats["merged"] += 1
            matched = True
            break

        if not matched:
            # Try to create the subzone under the best-fit parent zone
            # (longest zone_code prefix match). Useful for zones where the
            # source defines a new subzone (e.g. JI 2.1.3.1 Suelo Suburbano).
            created = False
            for loc in target_localities:
                if loc not in data["localities"]:
                    continue
                loc_zones = data["localities"][loc]["zones"]
                parts = zone_code.split(".")
                # Try progressively shorter parent zone keys
                for k in range(len(parts) - 1, 0, -1):
                    parent = ".".join(parts[:k])
                    if parent in loc_zones:
                        new_sub = {
                            "zone_code": zone_code,
                            "zone_name": entry.get("zone_name", ""),
                            "locality": loc,
                            "article": entry.get("source_article", ""),
                            "decreto": entry.get("decreto", ""),
                            "allowed_building_types": [],
                            "tipologias": [],
                            "_notes": ["Created during T10-1c bulk merge 2026-04-24"],
                        }
                        loc_zones[parent]["subzones"][zone_code] = new_sub
                        merge_tipologias_into_subzone(new_sub, entry)
                        stats["created"] += 1
                        created = True
                        break
                if created:
                    break
            if not created:
                unmatched.append(f"{titulo} {zone_code}: no matching subzone in {target_localities}")

    return unmatched


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--backup", action="store_true")
    args = parser.parse_args()

    with open(TONE_ZONES) as f:
        data = json.load(f)

    stats = defaultdict(int)
    all_unmatched = []

    for titulo in TITULO_TO_LOCALITY:
        path = os.path.join(EXTRACT_DIR, f"{titulo}-reviewed.json")
        if not os.path.exists(path):
            print(f"[skip] {titulo}: no reviewed file")
            continue
        with open(path) as f:
            reviewed = json.load(f)
        unmatched = merge_titulo(data, titulo, reviewed, stats)
        n = len(reviewed.get("zones", []))
        print(f"[merged] {titulo}: {n} reviewed zones, {len(unmatched)} unmatched")
        all_unmatched.extend(unmatched)

    print(f"\nTotal: {stats['merged']} zones merged, {stats['pseudo_deleted']} pseudo-subzones deleted")

    if all_unmatched:
        print(f"\nUnmatched zones ({len(all_unmatched)}):")
        for u in all_unmatched:
            print(f"  · {u}")

    if args.dry_run:
        print("\nDRY-RUN — no changes written.")
        return 0

    if args.backup:
        shutil.copy(TONE_ZONES, TONE_ZONES + ".bak")
        print(f"\nBackup: {TONE_ZONES}.bak")

    with open(TONE_ZONES, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\nWrote: {TONE_ZONES}")


if __name__ == "__main__":
    main()
