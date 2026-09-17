#!/usr/bin/env python3
"""HEIC -> JPEG copies for uploading.

    python3 scripts/heic_to_jpg.py

Keeps jpg/ in step with items/: every HEIC in an item folder gets a copy at
jpg/<folder>/<name>.jpg, and copies whose HEIC has moved or gone are deleted (items/_unsorted/
is skipped). The HEIC is decoded by pillow-heif where it is installed, and otherwise by macOS's
sips into a temp folder outside the project; Pillow then bakes the EXIF orientation into the
pixels and saves a quality-92 JPEG with only the ICC profile, so the copy carries no EXIF or XMP
(no GPS). Each copy is written under a temporary name first, so an interrupted run never leaves a
half-written JPEG behind. HEIC originals are untouched.
"""
import contextlib
import os
import shutil
import subprocess
import sys
import tempfile
from multiprocessing import Pool
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("Pillow is missing: run `python3 -m pip install -r requirements.txt` or `brew install pillow`")

try:  # cross-platform HEIC decoding; without it this falls back to macOS sips
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIF_NATIVE = True
except ImportError:
    HEIF_NATIVE = False

SIPS = shutil.which("sips")
if not HEIF_NATIVE and not SIPS:
    sys.exit("No way to read HEIC on this machine: run `python3 -m pip install pillow-heif` "
             "(macOS has sips built in, which is why it needs nothing extra there).")

ROOT = Path(__file__).resolve().parent.parent
SRC, DST = ROOT / "items", ROOT / "jpg"
UNSORTED = SRC / "_unsorted"
QUALITY = 92


def copy_path(src):
    return (DST / src.relative_to(SRC)).with_suffix(".jpg")


def convert(src):
    rel, dst = src.relative_to(SRC), copy_path(src)
    if dst.exists() and dst.stat().st_size > 0 and dst.stat().st_mtime >= src.stat().st_mtime:
        return rel, "skipped: exists"
    dst.parent.mkdir(parents=True, exist_ok=True)
    part = dst.with_name(dst.name + ".part")
    with contextlib.ExitStack() as stack:
        if HEIF_NATIVE:
            source = src
        else:
            tmp = stack.enter_context(tempfile.TemporaryDirectory())
            source = Path(tmp) / "decoded.png"
            r = subprocess.run([SIPS, "-s", "format", "png", str(src), "--out", str(source)],
                               capture_output=True, text=True, check=False)
            if r.returncode != 0 or not source.exists():
                return rel, "FAILED sips: " + (r.stderr or r.stdout).strip()
        try:
            with Image.open(source) as im:
                orient = im.getexif().get(0x0112, 1)
                icc = im.info.get("icc_profile")
                out = ImageOps.exif_transpose(im)
                if out.mode != "RGB":
                    out = out.convert("RGB")
                out.info.clear()  # the decoded image carries EXIF and XMP, GPS included: keep none of it
                out.save(part, "JPEG", quality=QUALITY, subsampling=0, optimize=True, icc_profile=icc)
                size = out.size
            os.replace(part, dst)
        except Exception as e:  # noqa: BLE001
            if part.exists():
                part.unlink()
            return rel, f"FAILED pillow: {e}"
    return rel, f"ok orient={orient} {size[0]}x{size[1]}"


def prune(wanted):
    """Delete copies whose HEIC is gone, leftover .part files, then empty folders."""
    removed = 0
    if not DST.is_dir():
        return removed
    for p in sorted(DST.rglob("*"), reverse=True):
        if p.is_file() and p.name.endswith(".part"):
            p.unlink()
        elif p.is_file() and p.suffix.lower() == ".jpg" and p not in wanted:
            p.unlink()
            removed += 1
        elif p.is_dir() and not [c for c in p.iterdir() if c.name != ".DS_Store"]:
            for c in p.iterdir():
                c.unlink()
            p.rmdir()
    return removed


if __name__ == "__main__":
    files = sorted(p for p in SRC.rglob("*") if p.is_file() and p.suffix.lower() == ".heic"
                   and not p.name.startswith(".") and UNSORTED not in p.parents) if SRC.is_dir() else []
    removed = prune({copy_path(p) for p in files})
    done = failed = skipped = 0
    with Pool(6) as pool:
        for rel, status in pool.imap_unordered(convert, files):
            if status.startswith("ok"):
                done += 1
            elif status.startswith("skipped"):
                skipped += 1
            else:
                failed += 1
                print(f"{rel}: {status}")
    print(f"{len(files)} HEIC: {done} converted, {skipped} already had a JPEG, {failed} failed, "
          f"{removed} old copies removed")
