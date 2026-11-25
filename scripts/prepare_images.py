"""Clean, shrink and deduplicate the raw image datasets (local, CPU only).

Input : data/raw/<dataset>/.../<class>/<image>     (class = folder that contains the image)
Output: data/images/_by_source/<dataset>/<class>/<id>.jpg   (max 512 px, JPEG, no EXIF)
        data/images/_duplicates/...                         (removed copies, for review)
        data/inventory.csv                                  (one row per source image)
        data/dedup_review.html                              (duplicate groups with thumbnails)
data/raw is never modified, so this script can be re-run at any time.
"""
import argparse, csv, hashlib, html, io, os, shutil
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import imagehash
import numpy as np
from PIL import Image, ImageOps
from tqdm import tqdm

DATA = Path("data")
RAW = DATA / "raw"
OUT = DATA / "images" / "_by_source"
DUP = DATA / "images" / "_duplicates"
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def process(job):
    src, max_side, min_side, quality = job
    raw_bytes = src.read_bytes()
    row = dict(dataset=src.relative_to(RAW).parts[0], source_class=src.parent.name,
               src_path=str(src), out_path="", status="ok", group="", kept="",
               width=0, height=0, phash="", bytes_in=len(raw_bytes), bytes_out=0)
    try:
        img = Image.open(io.BytesIO(raw_bytes))
        img = ImageOps.exif_transpose(img).convert("RGB")   # fix phone rotation
    except Exception:
        row["status"] = "corrupt"
        return row
    if min(img.size) < min_side:
        row["status"] = "too_small"
        return row
    img.thumbnail((max_side, max_side), Image.LANCZOS)      # only shrinks, never enlarges
    row["width"], row["height"] = img.size
    row["phash"] = str(imagehash.phash(img))
    out = OUT / row["dataset"] / row["source_class"] / f"{hashlib.sha1(raw_bytes).hexdigest()[:12]}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "JPEG", quality=quality, optimize=True)   # saved without EXIF
    row["out_path"], row["bytes_out"] = str(out), out.stat().st_size
    return row


def group_near_duplicates(ok_rows, threshold):
    """Union-find over all pairs whose perceptual hashes differ by <= threshold bits."""
    hashes = np.array([int(r["phash"], 16) for r in ok_rows], dtype=np.uint64)
    parent = list(range(len(ok_rows)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for start in range(0, len(hashes), 1024):
        dist = np.bitwise_count(hashes[start:start + 1024, None] ^ hashes[None, :])
        for i, j in zip(*np.nonzero(dist <= threshold)):
            i += start
            if i < j:
                parent[find(i)] = find(j)

    groups = defaultdict(list)
    for i in range(len(ok_rows)):
        groups[find(i)].append(ok_rows[i])
    return [g for g in groups.values() if len(g) > 1]


def write_review_page(groups, path):
    parts = ["<html><meta charset='utf-8'><body style='font-family:sans-serif'>",
             f"<h2>{len(groups)} duplicate groups</h2>",
             "<p>Green = kept. Red = moved to _duplicates. "
             "'classes differ' = check the label is right.</p>"]
    for n, g in enumerate(groups, 1):
        classes = {r["source_class"].lower() for r in g}
        warn = " <b style='color:#c00'>classes differ</b>" if len(classes) > 1 else ""
        parts.append(f"<h4>Group {n}{warn}</h4><div style='display:flex;gap:8px;flex-wrap:wrap'>")
        for r in g:
            colour = "#2a2" if r["status"] == "ok" else "#c22"
            rel = os.path.relpath(r["out_path"], path.parent)
            parts.append(f"<figure style='margin:0;border:3px solid {colour}'>"
                         f"<img src='{html.escape(rel)}' height='150'>"
                         f"<figcaption style='font-size:11px'>{html.escape(r['dataset'])}<br>"
                         f"{html.escape(r['source_class'])}</figcaption></figure>")
        parts.append("</div>")
    path.write_text("\n".join(parts + ["</body></html>"]), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-side", type=int, default=512)
    ap.add_argument("--min-side", type=int, default=128)
    ap.add_argument("--quality", type=int, default=90)
    ap.add_argument("--threshold", type=int, default=6, help="max differing hash bits for a duplicate")
    args = ap.parse_args()

    for d in (OUT, DUP):                                    # rebuild from raw every run
        shutil.rmtree(d, ignore_errors=True)
    files = sorted(p for p in RAW.rglob("*") if p.suffix.lower() in EXTS)
    print(f"{len(files)} images found under {RAW}")

    jobs = [(f, args.max_side, args.min_side, args.quality) for f in files]
    with ProcessPoolExecutor() as pool:
        rows = list(tqdm(pool.map(process, jobs, chunksize=32), total=len(jobs), desc="processing"))

    # identical source files in the same class share one output file
    seen = {}
    for r in rows:
        if r["status"] == "ok":
            if r["out_path"] in seen:
                r["status"], r["kept"] = "exact_duplicate", r["out_path"]
            else:
                seen[r["out_path"]] = r

    ok_rows = [r for r in rows if r["status"] == "ok"]
    groups = group_near_duplicates(ok_rows, args.threshold)
    for n, g in enumerate(groups, 1):
        g.sort(key=lambda r: (r["width"] * r["height"], r["bytes_in"]), reverse=True)
        keep = g[0]
        for r in g:
            r["group"] = n
        for r in g[1:]:                                     # move copies out of the clean set
            new = DUP / Path(r["out_path"]).relative_to(OUT)
            new.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(r["out_path"], new)
            r["out_path"], r["status"], r["kept"] = str(new), "near_duplicate", keep["out_path"]

    with open(DATA / "inventory.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    write_review_page(groups, DATA / "dedup_review.html")

    # report
    print("\nStatus:", dict(Counter(r["status"] for r in rows)))
    mb_in = sum(r["bytes_in"] for r in rows) / 2**20
    mb_out = sum(r["bytes_out"] for r in rows if r["status"] == "ok") / 2**20
    print(f"Size: {mb_in:.0f} MB raw -> {mb_out:.0f} MB clean")
    counts = Counter((r["dataset"], r["source_class"]) for r in rows if r["status"] == "ok")
    print(f"\n{len(counts)} source classes (dataset / class: clean photos)")
    for (ds, cls), n in sorted(counts.items()):
        print(f"  {'⚠' if n < 30 else ' '} {ds} / {cls}: {n}")
    print("\nReview duplicates in data/dedup_review.html")


if __name__ == "__main__":
    main()
