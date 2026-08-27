#!/usr/bin/env python3
"""
build-massing-site.py — derive a /normativa-massing SITE block from the pipeline,
so the configurator NEVER hand-maintains a second source of truth for zoning.

Pipeline (Mapa → norma zoning skill → massing):
  1. Mapa / cadastre   → parcel geometry (per lot + unified), locality, manzana.
  2. norma (UY zoning) → zone_code resolved, then `applicable_tipologias()`
     (norma-analyze/normativa-scenarios.py) reads the zone's tipologías straight
     from tone-zones.json — the SINGLE SOT for FOS/FOT/altura/retiros.
  3. massing           → this script emits the SITE block.

FOS/FOT/altura/retiros come from tone-zones.json via the engine — not typed here.

Usage:
  python3 build-massing-site.py --padrones 130,131,132 --loc HG \\
      --locality "JOSE IGNACIO" --zone 2.1.2.2 --manzana 26
Prints the SITE const to stdout. Re-run to regenerate; do not hand-edit SITE.
"""
import argparse, importlib.util, json, math, os, sys, urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYZE = os.path.join(HERE, "..", "norma-analyze")
_spec = importlib.util.spec_from_file_location("norma_scenarios",
                                               os.path.join(ANALYZE, "normativa-scenarios.py"))
_eng = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_eng)
applicable_tipologias = _eng.applicable_tipologias

TONE = os.path.join(ANALYZE, "datos", "tone-zones.json")
PADRONES_API = ("https://gis.maldonado.gub.uy/arcgis/rest/services/"
                "Servicios_AGOL/Padrones/FeatureServer/0/query")
UA = "estudio-local/1.0 (norma-massing; f@alpacalabs.co)"
# TONE special rule (Art. D.283): in these La Juanita manzanas, unifamiliar
# (unidad_aislada) is prohibited on englobado lots > 1.000 m².
JUANITA_NO_UNIFAMILIAR = {3,4,26,27,40,41,48,49,50,51,52,54,55,56,57,58,59,60,61,62,68,69,70,71}
CODE2ID = {"unidad_aislada": "AIS", "unidad_apareada": "APA",
           "bloque_bajo": "BLO", "bloque_bajo_9m": "BLO", "bloque_medio": "BME"}


def fetch_parcels(padrones, loc):
    where = f"codloccat='{loc}' AND padron IN ({','.join(padrones)})"
    qs = urllib.parse.urlencode({"where": where, "outFields": "padron,valaream2,nummancat",
                                 "returnGeometry": "true", "outSR": "4326", "f": "json"})
    req = urllib.request.Request(f"{PADRONES_API}?{qs}", headers={"User-Agent": UA})
    return json.load(urllib.request.urlopen(req, timeout=60))["features"]


def reverse_calle(lat, lng):
    qs = urllib.parse.urlencode({"lat": f"{lat:.6f}", "lon": f"{lng:.6f}",
                                 "format": "jsonv2", "zoom": "17", "addressdetails": "1"})
    try:
        req = urllib.request.Request(f"https://nominatim.openstreetmap.org/reverse?{qs}",
                                     headers={"User-Agent": UA})
        a = json.load(urllib.request.urlopen(req, timeout=30)).get("address", {})
        return a.get("road") or a.get("pedestrian") or a.get("residential")
    except Exception:
        return None


def parea(poly):
    a = 0
    for i in range(len(poly)):
        j = (i+1) % len(poly); a += poly[i][0]*poly[j][1] - poly[j][0]*poly[i][1]
    return a/2


def ccw(poly):
    return poly if parea(poly) >= 0 else poly[::-1]


def hull(points):
    pts = sorted(set(map(tuple, points)))
    cr = lambda o, a, b: (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lo = []
    for p in pts:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    up = []
    for p in reversed(pts):
        while len(up) >= 2 and cr(up[-2], up[-1], p) <= 0: up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def classify(poly):
    """Per-edge role by OUTWARD-NORMAL direction relative to the frente (longest edge).
    Edges facing roughly opposite the street → fondo; sideways → lateral. This keeps
    near-collinear rear edges on the SAME setback, so the offset doesn't break."""
    poly = ccw(poly); n = len(poly)
    def outn(i):
        a, b = poly[i], poly[(i+1) % n]
        dx, dy = b[0]-a[0], b[1]-a[1]; L = math.hypot(dx, dy) or 1
        return (dy/L, -dx/L)                       # CCW → right of direction = outward
    elen = lambda i: math.hypot(poly[(i+1) % n][0]-poly[i][0], poly[(i+1) % n][1]-poly[i][1])
    fi = max(range(n), key=elen)
    fon = outn(fi)
    roles = []
    for i in range(n):
        if i == fi:
            roles.append("frente")
        else:
            d = outn(i)[0]*fon[0] + outn(i)[1]*fon[1]
            roles.append("fondo" if d < -0.3 else "lateral")   # faces away from street = rear
    return roles, fi, elen(fi)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--padrones", required=True)
    ap.add_argument("--loc", required=True)
    ap.add_argument("--locality", required=True)
    ap.add_argument("--zone", required=True)
    ap.add_argument("--manzana", type=int, default=None)
    a = ap.parse_args()
    padrones = a.padrones.split(",")

    # ── 1. cadastre geometry (WGS84) → local-metre equirectangular frame ──
    feats = fetch_parcels(padrones, a.loc)
    cad_area = sum(f["attributes"]["valaream2"] for f in feats)
    rings_ll = [[(xy[0], xy[1]) for xy in f["geometry"]["rings"][0]] for f in feats]
    allp = [p for r in rings_ll for p in r]
    lng0 = sum(p[0] for p in allp)/len(allp); lat0 = sum(p[1] for p in allp)/len(allp)
    kx = math.cos(math.radians(lat0))*111320.0; ky = 110540.0
    proj = lambda lng, lat: ((lng-lng0)*kx, (lat-lat0)*ky)
    unproj = lambda X, Y: (lng0 + X/kx, lat0 + Y/ky)

    uni = hull([proj(*p) for p in allp])
    uni = ccw(uni)
    cx = sum(p[0] for p in uni)/len(uni); cy = sum(p[1] for p in uni)/len(uni)
    rc = lambda poly: [[round(p[0]-cx, 2), round(p[1]-cy, 2)] for p in poly]
    uni_poly = rc(uni)
    uni_roles, fi, frente = classify(uni_poly)

    # individual lots (each parcel ring, same recentred frame)
    lots = []
    for r in rings_ll:
        lp = rc(ccw([proj(*p) for p in r]))
        if len(lp) > 1 and lp[0] == lp[-1]:
            lp = lp[:-1]                         # drop closing-ring duplicate vertex
        lr, _, _ = classify(lp)
        lots.append({"poly": lp, "edge_role": lr})

    # frente street via reverse-geocode of a point just outside the unified frente midpoint
    fa, fb = uni_poly[fi], uni_poly[(fi+1) % len(uni_poly)]
    dx, dy = fb[0]-fa[0], fb[1]-fa[1]; L = math.hypot(dx, dy); nx, ny = dy/L, -dx/L
    mx, my = (fa[0]+fb[0])/2 + cx, (fa[1]+fb[1])/2 + cy
    onx, ony = (nx, ny) if (mx-cx)*nx + (my-cy)*ny > 0 else (-nx, -ny)
    frente_calle = reverse_calle(*reversed(unproj(mx + onx*6, my + ony*6)))  # (lat,lng)

    # ── 2. zoning from tone-zones.json (SOT) + engine ──
    tone = json.load(open(TONE))
    zkey = ".".join(a.zone.split(".")[:2])
    zone_entry = tone["localities"][a.locality]["zones"][zkey]["subzones"][a.zone]
    per_lot_area = cad_area/len(feats)

    def scen(t, mode, sid=None):
        r = t["retiros"]
        return {"id": sid or CODE2ID.get(t["codigo"], t["codigo"][:3].upper()),
                "label": t["nombre"], "mode": mode,
                "FOS_pct": t["FOS_pct"], "FOT_pct": t["FOT_pct"], "altura_m": t["altura_m"],
                "retiros": {"frontal_m": r["frontal_m"], "lateral_m": r["lateral_m"],
                            "fondo_m": r["fondo_m"], "entre_volumenes_m": r.get("entre_volumenes_m")}}

    tdict = {t["codigo"]: t for t in zone_entry["tipologias"]}
    scenarios = []
    # Individual: each lot developed separately → per-lot tipología (aislada applies, <1000 m²/lot)
    indiv = applicable_tipologias(zone_entry, per_lot_area, frente/len(feats))
    if indiv:
        s = scen(indiv[0], "individual", sid="IND")
        s["label"] = f"Individual ({len(feats)} lotes)"; scenarios.append(s)
    # Englobado: tipologías for the unified lot; drop unifamiliar per the mzna rule (>1000 m²)
    eng = applicable_tipologias(zone_entry, cad_area, frente)
    if a.manzana in JUANITA_NO_UNIFAMILIAR and cad_area > 1000:
        eng = [t for t in eng if t["codigo"] != "unidad_aislada"]
    scenarios += [scen(t, "englobado") for t in eng]      # apareada → bloque order (source order)

    # recommended = max buildable GFA (individual sums per-lot; englobado on unified area)
    def gfa(s):
        return (per_lot_area*len(feats) if s["mode"] == "individual" else cad_area)*s["FOT_pct"]/100
    rec = max(scenarios, key=gfa)["id"]

    site = {
        "_provenance": (f"GENERATED by build-massing-site.py — do not hand-edit. "
                        f"Geometry: Maldonado Padrones FeatureServer (loc {a.loc}). "
                        f"Zoning: tone-zones.json {a.zone} ({zone_entry.get('article')}, "
                        f"{zone_entry.get('decreto')}) via norma-scenarios engine."),
        "info": {
            "title": f"Padrones {a.padrones} · {zone_entry['zone_name'].split('—')[-1].strip()}",
            "address": (f"{frente_calle}, {a.locality.title()}" if frente_calle else a.locality.title()),
            "frente_calle": frente_calle,
            "sub": (f"{a.locality.title()} · Subzona {a.zone.replace('.', '-')} · "
                    f"{len(feats)} padrones ≈ {round(cad_area)} m² (catastral) · mzna {a.manzana} · "
                    f"{zone_entry.get('decreto')}"),
            "lot_area_m2": round(cad_area)},
        "lot_poly_m": uni_poly, "edge_role": uni_roles, "lots": lots,
        "north_vec": [0, 1], "scenarios": scenarios, "recommended": rec}
    print("const SITE = " + json.dumps(site, ensure_ascii=False, indent=2) + ";")
    sys.stderr.write(f"[ok] lots={len(lots)} uni_roles={uni_roles} cad_area={round(cad_area)} "
                     f"frente={round(frente,1)}m '{frente_calle}' scenarios="
                     f"{[s['id'] for s in scenarios]} rec={rec}\n")


if __name__ == "__main__":
    main()
