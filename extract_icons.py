#!/usr/bin/env python3
"""
Figma Icon Extractor

Extracts component keys from a published Figma library and combines them
with local SVG files to produce:

  icons.json            – full icon metadata (keys, variants, tags)
  thumbnails.json       – light-theme SVG strings keyed by icon id
  thumbnails-dark.json  – dark-theme SVG strings keyed by icon id

Usage:
  export FIGMA_TOKEN="figd_XXXXX"
  python3 extract_icons.py

Prerequisites:
  • The Figma file must be published as a library.
  • Local SVG folders must exist (LIGHT_DIR / DARK_DIR below).
"""

import json
import os
import re
import ssl
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# macOS Python often lacks root certificates
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# ─────────────────────────────────────────────
# CONFIGURATION – edit these values
# ─────────────────────────────────────────────

FIGMA_FILE_KEY = "ywUkdkkWuu1e05R7zcxUlC"  # ArcGIS Pro Icons

SVG_INPUT = Path("/Users/manuelacosta/Documents/icons-workspace/input")
LIGHT_DIR = "XAML Active Light Theme"
DARK_DIR = "XAML Active Dark Theme"

OUTPUT_DIR = Path(".")

# ─────────────────────────────────────────────
# REGEX HELPERS
# ─────────────────────────────────────────────

TOKEN_RE = re.compile(
    r"\d+[A-Z](?=\d|[A-Z][a-z]|$)"
    r"|[A-Z]{2,}(?=[A-Z][a-z]|\d|$)"
    r"|[A-Z][a-z]+"
    r"|\d+"
    r"|[A-Z]"
)

BASENAME_RE = re.compile(r"^(?P<name>.+?)(?P<size>\d+)$")

DARK_SUFFIX_RE = re.compile(r"[_\-\s]*(Dark|Light)$", re.IGNORECASE)


def to_kebab(raw):
    tokens = TOKEN_RE.findall(raw.replace("_", " ").strip())
    return "-".join(t.lower() for t in tokens)


def strip_theme_suffix(ctx):
    return DARK_SUFFIX_RE.sub("", ctx).strip()


def split_name_size(stem):
    m = BASENAME_RE.match(stem.strip())
    if not m:
        return stem.strip(), None
    return m.group("name").strip(), int(m.group("size"))


def build_tags(icon_name, context):
    tags = set()
    for t in TOKEN_RE.findall(icon_name.replace("_", " ")):
        if len(t) > 1:
            tags.add(t.lower())
    for t in TOKEN_RE.findall(context.replace("_", " ")):
        if len(t) > 1:
            tags.add(t.lower())
    return sorted(tags)


# ─────────────────────────────────────────────
# FIGMA API
# ─────────────────────────────────────────────

def figma_get(endpoint):
    token = os.environ.get("FIGMA_TOKEN", "")
    if not token:
        print("Error: FIGMA_TOKEN not set.")
        print("  export FIGMA_TOKEN='figd_...'")
        sys.exit(1)
    url = "https://api.figma.com/v1" + endpoint
    req = Request(url, headers={"X-Figma-Token": token})
    try:
        with urlopen(req, context=_ssl_ctx) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print("Figma API error: {} {} – {}".format(e.code, e.reason, body[:200]))
        sys.exit(1)


def fetch_figma_data():
    """Return (components_list, {set_node_id: set_info})."""
    print("Fetching components from Figma...")
    comp_data = figma_get("/files/{}/components".format(FIGMA_FILE_KEY))
    components = comp_data.get("meta", {}).get("components", [])

    print("Fetching component sets from Figma...")
    sets_data = figma_get("/files/{}/component_sets".format(FIGMA_FILE_KEY))
    sets_list = sets_data.get("meta", {}).get("component_sets", [])

    sets_dict = {}
    for s in sets_list:
        sets_dict[s["node_id"]] = s

    print("  {} components, {} component sets".format(len(components), len(sets_dict)))
    return components, sets_dict


# ─────────────────────────────────────────────
# VARIANT PROPERTY PARSER
# ─────────────────────────────────────────────

def parse_variant_props(name):
    """'Mode=A, Size=16' -> {'Mode': 'A', 'Size': '16'}"""
    props = {}
    for part in name.split(","):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            props[k.strip()] = v.strip()
    return props


def classify_mode(props):
    """Return 'A' (light) or 'B' (dark) based on variant properties."""
    light_vals = {"a", "light", "default"}
    dark_vals = {"b", "dark", "dart"}

    for key in props:
        val = props[key].lower()
        if val in light_vals:
            return "A"
        if val in dark_vals:
            return "B"
        if val == "variant2":
            return "B"
    return None


# ─────────────────────────────────────────────
# INDEX LOCAL SVGs
# ─────────────────────────────────────────────

def index_svgs():
    """
    Walk light/dark SVG folders.
    Returns {
      "light": { "ComponentName16": {"svg": "...", "context": "01_MapView_A"} },
      "dark":  { "ComponentName16": {"svg": "...", "context": "01_MapView_A_Dark"} }
    }
    """
    result = {"light": {}, "dark": {}}

    for dirname, mode in [(LIGHT_DIR, "light"), (DARK_DIR, "dark")]:
        theme_path = SVG_INPUT / dirname
        if not theme_path.exists():
            print("Warning: {} not found – skipping {} thumbnails".format(theme_path, mode))
            continue

        for ctx_folder in sorted(theme_path.iterdir()):
            if not ctx_folder.is_dir():
                continue
            for svg_file in ctx_folder.rglob("*.svg"):
                stem = svg_file.stem
                try:
                    svg_text = svg_file.read_text(encoding="utf-8").strip()
                except Exception:
                    continue
                result[mode][stem] = {
                    "svg": svg_text,
                    "context_raw": ctx_folder.name,
                }

    print("  Light SVGs: {}".format(len(result["light"])))
    print("  Dark SVGs:  {}".format(len(result["dark"])))
    return result


# ─────────────────────────────────────────────
# BUILD ICON RECORDS
# ─────────────────────────────────────────────

def build_icons(components, sets_dict, svg_index):
    set_node_ids = set(sets_dict.keys())

    # Group variant components by their parent component set.
    # The set info lives in containing_frame.containingComponentSet,
    # NOT in containing_frame.nodeId (which points to the parent frame).
    grouped = {}
    standalone = []

    for comp in components:
        frame = comp.get("containing_frame", {})
        cs = frame.get("containingComponentSet") or {}
        set_nid = cs.get("nodeId", "")

        if not set_nid:
            set_nid = frame.get("nodeId", "")

        if set_nid in set_node_ids:
            grouped.setdefault(set_nid, []).append(comp)
        else:
            standalone.append(comp)

    icons = []
    thumbs_light = {}
    thumbs_dark = {}

    # ── Component sets (icons with light/dark variants) ──
    for set_nid, variants in grouped.items():
        si = sets_dict[set_nid]
        set_name = si["name"]
        set_key = si["key"]

        icon_name, size = split_name_size(set_name)
        if size is None:
            size = 0

        # Context: from SVG folder (most reliable), fallback to Figma page
        ctx_raw = ""
        svg_info = svg_index["light"].get(set_name)
        if svg_info:
            ctx_raw = strip_theme_suffix(svg_info["context_raw"])
        else:
            page = (variants[0].get("containing_frame", {}).get("pageName", "")
                    if variants else "")
            ctx_raw = page or si.get("containing_frame", {}).get("pageName", "uncategorized")

        ctx_key = to_kebab(ctx_raw)
        icon_key = to_kebab(icon_name)
        icon_id = "icon/{}/{}/{}".format(ctx_key, icon_key, size)

        # Parse variant keys
        variant_keys = {}
        for v in variants:
            props = parse_variant_props(v["name"])
            mode = classify_mode(props)

            if mode == "A":
                variant_keys["A"] = v["key"]
                variant_keys["A_id"] = v["node_id"]
            elif mode == "B":
                variant_keys["B"] = v["key"]
                variant_keys["B_id"] = v["node_id"]

            # Also store raw name mapping
            variant_keys[v["name"]] = v["key"]

        # If we only found two variants and couldn't classify, assign by order
        if "A" not in variant_keys and "B" not in variant_keys and len(variants) == 2:
            variant_keys["A"] = variants[0]["key"]
            variant_keys["A_id"] = variants[0]["node_id"]
            variant_keys["B"] = variants[1]["key"]
            variant_keys["B_id"] = variants[1]["node_id"]

        record = {
            "id": icon_id,
            "context": ctx_raw,
            "context_raw": ctx_raw,
            "context_key": ctx_key,
            "icon_name": icon_name,
            "icon_key": icon_key,
            "size": size,
            "component_key": set_key,
            "component_id": set_nid,
            "component_name": set_name,
            "variant_keys": variant_keys,
            "tags": build_tags(icon_name, ctx_raw),
        }
        icons.append(record)

        # Thumbnails
        if set_name in svg_index["light"]:
            thumbs_light[icon_id] = svg_index["light"][set_name]["svg"]
        if set_name in svg_index["dark"]:
            thumbs_dark[icon_id] = svg_index["dark"][set_name]["svg"]

    # ── Standalone components (no variants) ──
    for comp in standalone:
        comp_name = comp["name"]
        comp_key = comp["key"]
        comp_id = comp["node_id"]

        icon_name, size = split_name_size(comp_name)
        if size is None:
            size = 0

        ctx_raw = ""
        svg_info = svg_index["light"].get(comp_name)
        if svg_info:
            ctx_raw = strip_theme_suffix(svg_info["context_raw"])
        else:
            ctx_raw = comp.get("containing_frame", {}).get("pageName", "uncategorized")

        ctx_key = to_kebab(ctx_raw)
        icon_key = to_kebab(icon_name)
        icon_id = "icon/{}/{}/{}".format(ctx_key, icon_key, size)

        record = {
            "id": icon_id,
            "context": ctx_raw,
            "context_raw": ctx_raw,
            "context_key": ctx_key,
            "icon_name": icon_name,
            "icon_key": icon_key,
            "size": size,
            "component_key": comp_key,
            "component_id": comp_id,
            "component_name": comp_name,
            "variant_keys": {},
            "tags": build_tags(icon_name, ctx_raw),
        }
        icons.append(record)

        if comp_name in svg_index["light"]:
            thumbs_light[icon_id] = svg_index["light"][comp_name]["svg"]
        if comp_name in svg_index["dark"]:
            thumbs_dark[icon_id] = svg_index["dark"][comp_name]["svg"]

    icons.sort(key=lambda x: x["id"])
    return icons, thumbs_light, thumbs_dark


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    if not FIGMA_FILE_KEY:
        print("Error: set FIGMA_FILE_KEY in the script (from your Figma file URL).")
        sys.exit(1)

    print("=== Figma Icon Extractor ===\n")

    # 1. Index local SVGs
    print("[1/3] Indexing local SVGs...")
    svg_index = index_svgs()

    # 2. Fetch from Figma
    print("\n[2/3] Fetching from Figma API...")
    components, sets_dict = fetch_figma_data()

    # 3. Build & write
    print("\n[3/3] Building icon records...")
    icons, thumbs_light, thumbs_dark = build_icons(components, sets_dict, svg_index)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    icons_path = OUTPUT_DIR / "icons.json"
    icons_path.write_text(
        json.dumps(icons, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    thumbs_path = OUTPUT_DIR / "thumbnails.json"
    thumbs_path.write_text(
        json.dumps(thumbs_light, ensure_ascii=False), encoding="utf-8"
    )

    dark_path = OUTPUT_DIR / "thumbnails-dark.json"
    dark_path.write_text(
        json.dumps(thumbs_dark, ensure_ascii=False), encoding="utf-8"
    )

    # ── Summary ──
    matched_light = sum(1 for i in icons if i["id"] in thumbs_light)
    matched_dark = sum(1 for i in icons if i["id"] in thumbs_dark)
    with_b = sum(1 for i in icons if "B" in i.get("variant_keys", {}))

    print("\n=== Done ===")
    print("  icons.json:            {} icons".format(len(icons)))
    print("  thumbnails.json:       {} light SVGs".format(len(thumbs_light)))
    print("  thumbnails-dark.json:  {} dark SVGs".format(len(thumbs_dark)))
    print("")
    print("  Variant B (dark) keys: {}/{}".format(with_b, len(icons)))
    print("  Light thumb match:     {}/{}".format(matched_light, len(icons)))
    print("  Dark thumb match:      {}/{}".format(matched_dark, len(icons)))

    unmatched = [i for i in icons if i["id"] not in thumbs_light]
    if unmatched:
        print("\n  Unmatched (no light SVG):")
        for i in unmatched[:10]:
            print("    - {}".format(i["component_name"]))
        if len(unmatched) > 10:
            print("    ... and {} more".format(len(unmatched) - 10))


if __name__ == "__main__":
    main()
