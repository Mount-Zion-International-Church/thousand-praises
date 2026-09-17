#!/usr/bin/env python3
"""
Thousand Praises — build script.

Reads sheets_config.json (spreadsheet IDs + per-tab gids for each language),
pulls each tab's data straight from Google Sheets (no API key needed — works
for any sheet shared as "Anyone with the link - Viewer"), and rebuilds
data.json + the final site HTML from template.html.

Run manually with:  python3 build_site.py
The GitHub Action in .github/workflows/deploy.yml runs this on a schedule.
"""
import json
import csv
import io
import urllib.request
import sys
import re

CONFIG_PATH = "sheets_config.json"
TEMPLATE_PATH = "template.html"
OUTPUT_PATH = "dist/index.html"
DATA_OUTPUT_PATH = "dist/data.json"

CSV_URL = "https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"


def fetch_tab_csv(sheet_id, gid):
    url = CSV_URL.format(sheet_id=sheet_id, gid=gid)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return raw


def parse_praise_csv(raw_csv):
    """Expects columns: SL No | Praise text | Bible reference (header row first)."""
    reader = csv.reader(io.StringIO(raw_csv))
    rows = list(reader)
    entries = []
    for row in rows:
        if len(row) < 3:
            continue
        sl, text, ref = row[0].strip(), row[1].strip(), row[2].strip()
        if not sl.isdigit():
            continue  # skips header row and any blank/merged rows
        if not text:
            continue
        entries.append({"n": int(sl), "text": text, "ref": ref})
    entries.sort(key=lambda e: e["n"])
    return entries


def build_data(config):
    languages = {}
    for lang_code, lang_cfg in config["languages"].items():
        sheet_id = lang_cfg["sheet_id"]
        sections = []
        for tab in lang_cfg["tabs"]:
            print(f"Fetching {lang_code} / {tab['label']} ...", file=sys.stderr)
            try:
                raw = fetch_tab_csv(sheet_id, tab["gid"])
                entries = parse_praise_csv(raw)
            except Exception as e:
                print(f"  WARNING: failed to fetch {lang_code}/{tab['label']}: {e}", file=sys.stderr)
                entries = None
            sections.append({
                "key": tab["key"],
                "label": tab["label"],
                "icon": tab.get("icon", "book"),
                "entries": entries,
            })
        languages[lang_code] = {
            "label": lang_cfg["label"],
            "native": lang_cfg["native"],
            "color": lang_cfg.get("color", "blue"),
            "sections": sections,
        }
    return {"languages": languages, "comingSoon": config.get("comingSoon", [])}


def main():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)

    data = build_data(config)

    import os
    os.makedirs("dist", exist_ok=True)

    with open(DATA_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        html = f.read()
    html = html.replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False))
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    total = sum(
        len(s["entries"]) for lang in data["languages"].values()
        for s in lang["sections"] if s["entries"]
    )
    print(f"Build complete. {total} praises loaded across "
          f"{len(data['languages'])} languages.", file=sys.stderr)


if __name__ == "__main__":
    main()
