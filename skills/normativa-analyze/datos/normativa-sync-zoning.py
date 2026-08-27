#!/usr/bin/env python3
"""
Sync TONE zoning subzone geometries from the Maldonado ArcGIS ORDENANZA_CONSTRUCCION MapServer.

Authoritative source for all normativa polygon data (Punta del Este, Maldonado city,
San Carlos, La Barra / Balnearios, José Ignacio, Aiguá, Garzón, Solís).

Usage:
  python3 sync_zoning.py              # sync all layers
  python3 sync_zoning.py --list       # list layers without fetching
  python3 sync_zoning.py --layer 30   # sync one layer by ID
"""
import urllib.request, urllib.parse, json, os, sys, re, time

API = "https://gis.maldonado.gub.uy/arcgis/rest/services/Servicios_AGOL/ORDENANZA_CONSTRUCCION/MapServer"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zoning")
MANIFEST = os.path.join(OUT_DIR, "manifest.json")
PAGE = 1000

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "estudio-local/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def slugify(name):
    s = re.sub(r"[^\w\s-]", "", name).strip().lower()
    s = re.sub(r"[\s_-]+", "-", s)
    return s or "unnamed"

def list_layers():
    svc = fetch(f"{API}?f=json")
    return [l for l in svc.get("layers", []) if l.get("type") == "Feature Layer"]

def fetch_layer_features(layer_id, offset=0):
    params = urllib.parse.urlencode({
        "where": "1=1", "outFields": "*", "returnGeometry": "true",
        "outSR": "4326", "f": "geojson",
        "resultOffset": offset, "resultRecordCount": PAGE,
    })
    url = f"{API}/{layer_id}/query?{params}"
    return fetch(url)

def sync_layer(layer):
    lid = layer["id"]
    name = layer["name"]
    slug = slugify(name)
    out_path = os.path.join(OUT_DIR, f"{lid:03d}-{slug}.geojson")

    features = []
    offset = 0
    while True:
        data = fetch_layer_features(lid, offset)
        batch = data.get("features", [])
        if not batch:
            break
        features.extend(batch)
        if len(batch) < PAGE:
            break
        offset += PAGE
        time.sleep(0.3)

    if not features:
        return None, out_path, 0

    geojson = {"type": "FeatureCollection", "features": features}
    with open(out_path, "w") as f:
        json.dump(geojson, f)
    return layer, out_path, len(features)

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    args = sys.argv[1:]
    if "--list" in args:
        layers = list_layers()
        print(f"{'ID':>4}  {'Type':<10}  {'Name'}")
        print("-" * 80)
        for l in layers:
            print(f"{l['id']:>4}  {l.get('geometryType','?').replace('esriGeometry',''):<10}  {l['name']}")
        print(f"\nTotal feature layers: {len(layers)}")
        return

    target_layer_id = None
    if "--layer" in args:
        target_layer_id = int(args[args.index("--layer") + 1])

    layers = list_layers()
    if target_layer_id is not None:
        layers = [l for l in layers if l["id"] == target_layer_id]

    print(f"Syncing {len(layers)} zoning layers from {API}")
    manifest = {"api": API, "layers": []}
    ok = 0
    empty = 0
    errors = []
    for l in layers:
        try:
            result, path, count = sync_layer(l)
            if count:
                ok += 1
                manifest["layers"].append({
                    "id": l["id"], "name": l["name"],
                    "geometry": l.get("geometryType", ""),
                    "file": os.path.basename(path), "features": count,
                })
                print(f"  ✓ {l['id']:>3} {l['name'][:60]:<60} {count:>4} features")
            else:
                empty += 1
                print(f"  · {l['id']:>3} {l['name'][:60]:<60} EMPTY")
        except Exception as e:
            errors.append((l["id"], l["name"], str(e)))
            print(f"  ✗ {l['id']:>3} {l['name'][:60]:<60} ERROR: {e}")

    with open(MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n{ok} layers saved · {empty} empty · {len(errors)} errors")
    print(f"Manifest: {MANIFEST}")

if __name__ == "__main__":
    main()
