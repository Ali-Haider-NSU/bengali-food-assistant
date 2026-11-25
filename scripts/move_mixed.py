"""Move files of a wrongly labelled class that duplicate photos of another class."""
import argparse, csv, shutil
from collections import defaultdict
from pathlib import Path

REJECT = Path("/mnt/d/Computer Vision/Project/rejected_images")

ap = argparse.ArgumentParser()
ap.add_argument("--wrong", required=True, help="source class whose copies are wrong")
ap.add_argument("--other", required=True, help="source class the photos really belong to")
ap.add_argument("--apply", action="store_true", help="actually move (default: dry run)")
a = ap.parse_args()

rows = list(csv.DictReader(open("data/inventory.csv", encoding="utf-8")))
groups = defaultdict(list)
for r in rows:
    if r["group"]:
        groups[r["group"]].append(r)

to_move = []
for rs in groups.values():
    classes = {r["source_class"] for r in rs}
    if a.wrong in classes and a.other in classes:
        to_move += [r["src_path"] for r in rs if r["source_class"] == a.wrong]

dest = REJECT / a.wrong
print(f"{len(to_move)} files of '{a.wrong}' duplicate photos of '{a.other}'")
for p in to_move[:5]:
    print("  ", p)
if a.apply:
    dest.mkdir(parents=True, exist_ok=True)
    for p in to_move:
        shutil.move(p, dest / Path(p).name)
    print(f"moved to {dest}")
else:
    print("dry run: add --apply to move them")
