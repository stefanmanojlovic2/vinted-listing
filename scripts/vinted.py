#!/usr/bin/env python3
"""Vinted organiser.

    python3 scripts/vinted.py organise   move and rename photos to match listings.json
    python3 scripts/vinted.py check      report problems, and photos organise would still move
    python3 scripts/vinted.py render     write listings.md from listings.json

listings.json is the source of truth. Each item lists its photos in upload order under
"source_photos" by original name: the filename without its extension, as the phone wrote it
("IMG_2302" on an iPhone, "PXL_20240115_143022" on a Pixel); append ":label" for a label shot.
organise finds every photo in inbox/ or items/ (subfolders too) by that name and moves it to
items/<id>-<slug>/<id>-<slug>-<nn>[-label]-<name>.<ext>, so a file can always be traced back
to its photo. Photos no item lists go to items/_unsorted/ under their original name. Only photos
are touched, never videos, and nothing is ever overwritten.
"""
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "inbox"
ITEMS = ROOT / "items"
UNSORTED = ITEMS / "_unsorted"
LISTINGS = ROOT / "listings.json"
MD = ROOT / "listings.md"
PHOTO_EXT = {".heic", ".jpeg", ".jpg", ".png"}

DEFAULTS = {
    "id": "", "slug": "", "folder": "", "images": [], "source_photos": [],
    "title": "", "description": "", "hashtags": [],
    "category": "", "brand": "", "size": "", "size_label": "",
    "condition": "", "colours": [], "material": "",
    "parcel_size": "",
    "status": "draft", "vinted_url": None, "notes": "",
}
STATUSES = ["draft", "written", "listed", "sold"]
WRITTEN = STATUSES[STATUSES.index("written"):]  # these need every Vinted field filled in
DONE = ("listed", "sold")  # photos of these items may already be deleted
REQUIRED = ("title", "description", "category", "brand", "size", "condition", "colours",
            "parcel_size")
CONDITIONS = ("New with tags", "New without tags", "Very good", "Good", "Satisfactory")
PARCELS = ("Small", "Medium", "Large")
ID_RE = re.compile(r"\d{3}")
SLUG_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
PHOTO_RE = re.compile(r"([^:/\\]+)(:label)?")
# A filename organise has already written: <id>-<slug>-<nn>[-label]-<original name>
ORGANISED_RE = re.compile(r"\d{3}-[a-z0-9]+(?:-[a-z0-9]+)*-\d{2}(?:-label)?-(.+)")


def die(msg):
    print(f"ERROR: {msg}")
    sys.exit(1)


def rel(path):
    return str(path.relative_to(ROOT))


def report(problems):
    for n, p in enumerate(problems, 1):
        print(f"{n}. {p}")


def load():
    if not LISTINGS.exists():
        return []
    try:
        with open(LISTINGS, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        die(f"listings.json is not valid JSON (line {e.lineno}): {e.msg}")
    if not isinstance(data, list) or not all(isinstance(i, dict) for i in data):
        die("listings.json must be a JSON array of items")
    return [normalise(i) for i in data]


def save(items):
    tmp = LISTINGS.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, LISTINGS)


def normalise(item):
    """Return the item with every schema key present, schema order first. null counts as missing."""
    out = {}
    for key, default in DEFAULTS.items():
        value = item.get(key)
        out[key] = (list(default) if isinstance(default, list) else default) if value is None else value
    for key, value in item.items():
        out.setdefault(key, value)
    return out


def parse_photo(entry):
    """'IMG_2302:label' -> ('IMG_2302', True). Anything else -> (None, False)."""
    m = PHOTO_RE.fullmatch(entry) if isinstance(entry, str) else None
    return (m.group(1), bool(m.group(2))) if m else (None, False)


def photo_names(item):
    return [parse_photo(entry)[0] for entry in item["source_photos"]]


def validate(items):
    problems, ids, seen = [], set(), {}
    for n, item in enumerate(items, 1):
        iid = item["id"]
        tag = f"item {iid}" if isinstance(iid, str) and iid else f"item #{n}"
        if not (isinstance(iid, str) and ID_RE.fullmatch(iid)):
            problems.append(f'{tag}: id must be three digits in quotes, like "001"')
        elif iid in ids:
            problems.append(f"{tag}: duplicate id")
        else:
            ids.add(iid)
        slug = item["slug"]
        if not (isinstance(slug, str) and SLUG_RE.fullmatch(slug) and len(slug) <= 40):
            problems.append(f"{tag}: slug {slug!r} must be lowercase a-z0-9 with dashes, max 40 chars")
        photos = item["source_photos"]
        if not isinstance(photos, list) or not photos:
            problems.append(f"{tag}: source_photos must list at least one photo")
            photos = []
        for entry in photos:
            name, _ = parse_photo(entry)
            if name is None:
                problems.append(f"{tag}: bad source photo {entry!r}, expected a filename "
                                "without its extension, like IMG_1234 or IMG_1234:label")
            elif name in seen:
                problems.append(f"{tag}: {name} is also in item {seen[name]}")
            else:
                seen[name] = iid
        status = item["status"]
        if status not in STATUSES:
            problems.append(f"{tag}: status must be one of {', '.join(STATUSES)}")
        elif status in WRITTEN:
            problems += [f"{tag}: {key} is empty but status is {status}" for key in REQUIRED if not item[key]]
        if len(str(item["title"])) > 100:
            problems.append(f"{tag}: title is longer than 100 characters")
        if item["condition"] and item["condition"] not in CONDITIONS:
            problems.append(f"{tag}: condition {item['condition']!r} must be one of {', '.join(CONDITIONS)}")
        if item["parcel_size"] and item["parcel_size"] not in PARCELS:
            problems.append(f"{tag}: parcel_size {item['parcel_size']!r} must be one of {', '.join(PARCELS)}")
        for key in ("colours", "hashtags", "images"):
            if not isinstance(item[key], list):
                problems.append(f"{tag}: {key} must be a list")
        if isinstance(item["colours"], list) and len(item["colours"]) > 2:
            problems.append(f"{tag}: at most 2 colours")
    return problems


def scan():
    """Find every photo in inbox/ and items/, subfolders included.

    Returns {photo name: [paths]}. A photo's name is its filename without the extension,
    whatever the phone called it. Photos organise has already placed carry that name at the
    end of a longer filename, so it is read back out of there.
    """
    found = {}
    for top in (INBOX, ITEMS):
        if not top.is_dir():
            continue
        for path in sorted(top.rglob("*")):
            if not path.is_file() or path.name.startswith(".") or path.suffix.lower() not in PHOTO_EXT:
                continue
            placed = ORGANISED_RE.fullmatch(path.stem)
            found.setdefault(placed.group(1) if placed else path.stem, []).append(path)
    return found


def plan(items, found):
    """Work out where every photo belongs. Returns ({current path: target path}, problems)."""
    problems = [f"{name} is in {len(paths)} files ({', '.join(rel(p) for p in paths)}), keep one"
                for name, paths in found.items() if len(paths) > 1]
    moves, claimed = {}, set()
    for item in items:
        stem = f"{item['id']}-{item['slug']}"
        for n, entry in enumerate(item["source_photos"], 1):
            name, label = parse_photo(entry)
            claimed.add(name)
            if name not in found:
                if item["status"] not in DONE:
                    problems.append(f"item {item['id']}: photo {name} is not in inbox/ or items/")
                continue
            src = found[name][0]
            moves[src] = ITEMS / stem / f"{stem}-{n:02d}{'-label' if label else ''}-{name}{src.suffix}"
    for name, paths in found.items():
        if name not in claimed:
            moves[paths[0]] = UNSORTED / f"{name}{paths[0].suffix}"
    return moves, problems


def move(moves):
    """Move photos to their targets. Checks every target first and moves nothing if one is taken."""
    moves = {src: dst for src, dst in moves.items() if src != dst}
    taken = [dst for src, dst in moves.items() if dst.exists() and not src.samefile(dst)]
    if taken:
        die("nothing moved, these files are in the way: " + ", ".join(rel(d) for d in taken))
    for n, (src, dst) in enumerate(moves.items()):
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
        except OSError as e:
            die(f"stopped after moving {n} of {len(moves)} photos ({e}). "
                "Nothing is lost: fix the cause and run organise again.")
    return len(moves)


def prune_empty_folders():
    if not ITEMS.exists():
        return
    for p in sorted(ITEMS.rglob("*"), reverse=True):
        if p.is_dir():
            leftovers = [c for c in p.iterdir() if c.name != ".DS_Store"]
            if not leftovers:
                for c in p.iterdir():
                    c.unlink()
                p.rmdir()


def cmd_organise():
    items = load()
    problems = validate(items)
    if problems:
        report(problems)
        die("fix listings.json first, nothing was moved")
    found = scan()
    moves, problems = plan(items, found)
    if problems:
        report(problems)
        die("fix these first, nothing was moved")
    moved = move(moves)
    prune_empty_folders()
    found = scan()
    for item in items:
        item["folder"] = rel(ITEMS / f"{item['id']}-{item['slug']}")
        item["images"] = [rel(found[name][0]) for name in photo_names(item) if name in found]
    save(items)
    print(f"organised: {len(items)} items, {moved} photos moved")
    cmd_render(items)
    return cmd_check(items)


def cmd_check(items=None):
    items = load() if items is None else items
    problems = validate(items)
    found = scan()
    if not problems:
        moves, plan_problems = plan(items, found)
        problems += plan_problems
        pending = sum(1 for src, dst in moves.items() if src != dst)
        if pending:
            problems.append(f"{pending} photos are not where listings.json puts them, run organise")
        for item in items:
            expected = [rel(moves[found[name][0]]) for name in photo_names(item) if name in found]
            folder = rel(ITEMS / f"{item['id']}-{item['slug']}")
            if not pending and (item["images"] != expected or item["folder"] != folder):
                problems.append(f"item {item['id']}: folder or images out of date, run organise")
    if problems:
        report(problems)
        return 1
    in_items = sum(1 for item in items for name in photo_names(item) if name in found)
    unsorted = sum(1 for paths in found.values() if paths[0].parent == UNSORTED)
    by_status = {}
    for item in items:
        by_status[item["status"]] = by_status.get(item["status"], 0) + 1
    print(f"OK: {len(items)} items, {in_items} photos in items, {unsorted} in _unsorted"
          + "".join(f", {v} {k}" for k, v in by_status.items()))
    return 0


def text(value):
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return "" if value is None else str(value)


def cmd_render(items=None):
    items = load() if items is None else items
    out = ["# Vinted listings", "",
           "Generated from `listings.json` by `scripts/vinted.py render`. Do not edit here.", ""]
    for i in items:
        flag = "" if i["status"] == "written" else f" · {text(i['status'])}"
        size = text(i["size"])
        if i["size_label"]:
            size = f"{size} (label: {text(i['size_label'])})".strip()
        tags = i["hashtags"]
        hashtags = " ".join(f"#{t}" for t in tags) if isinstance(tags, list) else text(tags)
        fields = [("Category", text(i["category"])), ("Brand", text(i["brand"])), ("Size", size),
                  ("Condition", text(i["condition"])), ("Colours", text(i["colours"])),
                  ("Material", text(i["material"])), ("Parcel size", text(i["parcel_size"])),
                  ("Hashtags", hashtags), ("Photos", text(i["folder"]))]
        out += [f"## {text(i['id'])} · {text(i['slug']).replace('-', ' ')}{flag}", "",
                "**Title**", "", "```", text(i["title"]) or "(not written yet)", "```", "",
                "**Description**", "", "```", text(i["description"]) or "(not written yet)", "```", ""]
        out += [f"- **{name}:** {value or '—'}" for name, value in fields]
        out.append("")
        if i["vinted_url"]:
            out += [f"Listed: {text(i['vinted_url'])}", ""]
    MD.write_text("\n".join(out), encoding="utf-8")
    print(f"rendered {rel(MD)} ({len(items)} items)")
    return 0


if __name__ == "__main__":
    cmds = {"organise": cmd_organise, "organize": cmd_organise, "render": cmd_render, "check": cmd_check}
    if len(sys.argv) != 2 or sys.argv[1] not in cmds:
        print(__doc__)
        sys.exit(2)
    sys.exit(cmds[sys.argv[1]]() or 0)
