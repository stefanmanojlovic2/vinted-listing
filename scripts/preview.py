#!/usr/bin/env python3
"""Small JPEG previews, so an agent can look at photos it cannot open.

    python3 scripts/preview.py 500 inbox/*.HEIC          previews for grouping
    python3 scripts/preview.py 900 items/001-tee/*.HEIC  previews for writing

Prints one preview path per line, longest edge at most <size>. Previews go in a temp folder
outside this project and are reused, so running it twice costs nothing. macOS decodes with the
built-in sips and needs no install; everywhere else this needs Pillow, plus pillow-heif for HEIC
(`python3 -m pip install -r requirements.txt`). Originals are never touched.
"""
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SIPS = shutil.which("sips")


def preview_names(paths):
    """A preview filename per photo. Two photos called IMG_0001 in different folders would
    otherwise land on one preview and get read as the same garment, so those get the folder
    hashed into the name. Photos with a name of their own keep it."""
    by_stem = {}
    for p in paths:
        by_stem.setdefault(p.stem, []).append(p)
    names = {}
    for stem, group in by_stem.items():
        for p in group:
            tag = "" if len(group) == 1 else \
                "-" + hashlib.sha1(str(p.resolve().parent).encode()).hexdigest()[:6]
            names[p] = f"{stem}{tag}.jpg"
    return names


def out_dir(size):
    d = Path(tempfile.gettempdir()) / f"vinted-preview-{size}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def with_sips(todo, size, dest, names):
    """One sips call for everything keeping its own name: far faster than one call per photo.

    sips names its output after the input, so a photo that needs a different name (two files
    called IMG_0001 in different folders) gets its own call with an explicit --out.
    """
    plain = [p for p in todo if names[p] == f"{p.stem}.jpg"]
    calls = [([*map(str, plain)], str(dest))] if plain else []
    calls += [([str(p)], str(dest / names[p])) for p in todo if names[p] != f"{p.stem}.jpg"]
    for srcs, out in calls:
        r = subprocess.run([SIPS, "-s", "format", "jpeg", "-Z", str(size), *srcs, "--out", out],
                           capture_output=True, text=True, check=False)
        if r.returncode != 0:
            sys.exit("sips failed: " + (r.stderr or r.stdout).strip())


def with_pillow(todo, size, dest, names):
    try:
        from PIL import Image, ImageOps
    except ImportError:
        sys.exit("Pillow is missing: run `python3 -m pip install -r requirements.txt`")
    if any(p.suffix.lower() in (".heic", ".heif") for p in todo):
        try:
            import pillow_heif

            pillow_heif.register_heif_opener()
        except ImportError:
            sys.exit("These are HEIC photos and pillow-heif is missing: "
                     "run `python3 -m pip install -r requirements.txt`")
    for src in todo:
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im)
            im.thumbnail((size, size))
            if im.mode != "RGB":
                im = im.convert("RGB")
            im.save(dest / names[src], "JPEG", quality=80)


def main(argv):
    if len(argv) < 2 or not argv[0].isdigit():
        sys.exit(__doc__.strip())
    size, paths = int(argv[0]), [Path(a) for a in argv[1:]]
    missing = [p for p in paths if not p.is_file()]
    if missing:
        sys.exit("not found: " + ", ".join(str(p) for p in missing))
    dest = out_dir(size)
    names = preview_names(paths)
    previews = {p: dest / names[p] for p in paths}
    todo = [src for src, prev in previews.items()
            if not (prev.exists() and prev.stat().st_mtime >= src.stat().st_mtime)]
    if todo:
        (with_sips if SIPS else with_pillow)(todo, size, dest, names)
    for src, prev in previews.items():
        if not prev.exists():
            sys.exit(f"no preview came out for {src}")
        print(prev)


if __name__ == "__main__":
    main(sys.argv[1:])
