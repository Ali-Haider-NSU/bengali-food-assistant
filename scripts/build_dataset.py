"""Step 5: build the final dataset layout from inventory.csv + class_map.csv.

Output: data/images/{dishes,ingredients,ood}/<id>/<id>_0001.jpg   (hard links, no extra space)
        data/annotations.jsonl   one line per image (split/group/description filled later)
        data/labels.json         class list with English and Bengali names
Re-run any time after editing class_map.csv; the output is rebuilt from scratch.
"""
import csv, json, os, re, shutil, sys
from collections import Counter, defaultdict
from pathlib import Path

DATA = Path("data")
IMAGES = DATA / "images"
TASK_DIR = {"dish": "dishes", "ingredient": "ingredients", "ood": "ood"}
DATASET_TASK = {"all_recipe": "dish", "ingredients": "ingredient"}
ACTIONS = {"keep", "drop", "ood", "check"}
MIN_PHOTOS = 25


def load_class_map(errors):
    cmap, names = {}, {}
    for r in csv.DictReader(open(DATA / "class_map.csv", encoding="utf-8-sig")):
        task, src, cid = r["task"].strip(), r["source_class"], r["id"].strip()
        act = r["action"].strip().lower()
        if act not in ACTIONS:
            errors.append(f"unknown action '{act}' for '{src}'")
        if not re.fullmatch(r"[a-z0-9_]+", cid):
            errors.append(f"bad id '{cid}' for '{src}' (use a-z, 0-9, _)")
        cmap[(task, src)] = (cid, act)
        if act in ("keep", "ood"):
            target = "ood" if act == "ood" else task
            cur = (r["name_en"].strip(), r["name_bn"].strip())
            prev = names.get((target, cid))
            if prev and prev != cur:
                errors.append(f"id '{cid}' has two different names: {prev} vs {cur}")
            names[(target, cid)] = cur
    return cmap, names


def main():
    errors = []
    cmap, names = load_class_map(errors)
    rows = [r for r in csv.DictReader(open(DATA / "inventory.csv", encoding="utf-8"))
            if r["status"] == "ok"]

    classes = defaultdict(list)           # (target_task, id) -> inventory rows
    skipped = Counter()
    for r in rows:
        task = DATASET_TASK.get(r["dataset"])
        key = (task, r["source_class"])
        if key not in cmap:
            errors.append(f"folder not in class_map: {r['dataset']} / {r['source_class']}")
            continue
        cid, act = cmap[key]
        if act in ("drop", "check"):
            skipped[f"{act}: {r['source_class']}"] += 1
            continue
        target = "ood" if act == "ood" else task
        classes[(target, cid)].append(r)

    if errors:
        print("Fix these in data/class_map.csv first:")
        for e in sorted(set(errors)):
            print("  -", e)
        sys.exit(1)

    for d in TASK_DIR.values():                                    # rebuild from scratch
        shutil.rmtree(IMAGES / d, ignore_errors=True)

    annotations = []
    for (target, cid), rs in sorted(classes.items()):
        folder = IMAGES / TASK_DIR[target] / cid
        folder.mkdir(parents=True, exist_ok=True)
        name_en, name_bn = names[(target, cid)]
        for i, r in enumerate(sorted(rs, key=lambda r: r["out_path"]), 1):
            dst = folder / f"{cid}_{i:04d}.jpg"
            try:
                os.link(r["out_path"], dst)                         # hard link: no extra space
            except OSError:
                shutil.copy2(r["out_path"], dst)
            annotations.append(dict(
                image=str(dst.relative_to(IMAGES)), task=target, label=cid,
                name_en=name_en, name_bn=name_bn,
                source_class=r["source_class"], orig_file=r["src_path"],
                width=int(r["width"]), height=int(r["height"]),
                split="", group="", description_bn="", reviewed=False))

    with open(DATA / "annotations.jsonl", "w", encoding="utf-8") as f:
        for a in annotations:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")

    labels = defaultdict(dict)
    for (target, cid), (en, bn) in sorted(names.items()):
        if (target, cid) in classes:
            labels[target][cid] = {"name_en": en, "name_bn": bn, "photos": len(classes[(target, cid)])}
    json.dump(labels, open(DATA / "labels.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # report
    print(f"{len(annotations)} images written\n")
    for target in TASK_DIR:
        cs = {cid: len(rs) for (t, cid), rs in classes.items() if t == target}
        if cs:
            print(f"{target}: {len(cs)} classes, {sum(cs.values())} photos "
                  f"(min {min(cs.values())}, max {max(cs.values())})")
            for cid, n in sorted(cs.items(), key=lambda x: x[1]):
                if n < MIN_PHOTOS:
                    print(f"   ⚠ {cid}: {n} photos (under {MIN_PHOTOS})")
    if skipped:
        print("\nLeft out (drop / check):")
        for k, n in sorted(skipped.items()):
            print(f"   {k}: {n}")


if __name__ == "__main__":
    main()
