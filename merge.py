#!/usr/bin/env python3
"""Merge a Mist CSV export (or a weigh-in) into the site data.

Usage:
  python3 merge.py logan ~/Downloads/mist_export.csv
  python3 merge.py felix --weight 148.5 [2026-09-02]

Mist exports overlap (each export can include dates from previous ones).
Merging is day-level: any date present in the new CSV completely replaces
that date's meals in the stored data, so re-uploading old dates is safe.
Dates absent from the new CSV are left alone.
"""
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PEOPLE = ("logan", "felix")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def die(msg):
    sys.exit(f"error: {msg}")


def num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return 0.0


def load(person):
    p = ROOT / "data" / f"{person}.json"
    return json.loads(p.read_text()) if p.exists() else {"days": {}}


def save(person, data):
    data["days"] = dict(sorted(data["days"].items()))
    (ROOT / "data" / f"{person}.json").write_text(json.dumps(data, indent=1))


def weight_path(person):
    return ROOT / "data" / f"{person}_weight.csv"


def load_weights(person):
    p = weight_path(person)
    out = {}
    if p.exists():
        for row in csv.DictReader(p.open()):
            if row.get("date") and row.get("weight"):
                out[row["date"].strip()] = float(row["weight"])
    return out


def save_weights(person, weights):
    with weight_path(person).open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "weight"])
        for d in sorted(weights):
            w.writerow([d, weights[d]])


def merge_csv(person, csv_file):
    days, weights, unknown = {}, {}, set()
    with open(csv_file, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            d = (row.get("date") or "").strip()
            typ = (row.get("type") or "").strip().lower()
            if not DATE_RE.fullmatch(d):
                continue
            if typ == "food":
                day = days.setdefault(
                    d, {"calories": 0, "protein": 0, "carbs": 0, "fat": 0, "meals": []}
                )
                cal, pro = num(row.get("calories")), num(row.get("protein"))
                day["calories"] += cal
                day["protein"] += pro
                day["carbs"] += num(row.get("carbs"))
                day["fat"] += num(row.get("fat"))
                day["meals"].append([(row.get("entry") or "").strip(), round(cal), round(pro)])
            elif typ in ("weight", "bodyweight", "weigh-in", "weighin"):
                # Mist hasn't shown us a weight row yet; take the first numeric
                # value we can find in the likely columns.
                v = num(row.get("calories")) or num(row.get("entry"))
                if v:
                    weights[d] = v
            else:
                unknown.add(typ or "(blank)")
    if not days and not weights:
        die(f"no usable rows found in {csv_file}")
    for day in days.values():
        for k in ("calories", "protein", "carbs", "fat"):
            day[k] = round(day[k], 1)
    data = load(person)
    data["days"].update(days)  # day-level replace: the new export wins for its dates
    save(person, data)
    if weights:
        stored = load_weights(person)
        stored.update(weights)
        save_weights(person, stored)
    print(
        f"{person}: merged {len(days)} day(s) of food"
        + (f", {len(weights)} weigh-in(s)" if weights else "")
        + f" -> {len(data['days'])} days on record"
    )
    if unknown:
        print(f"note: skipped unrecognized row type(s): {', '.join(sorted(unknown))}")


def log_weight(person, lbs, d):
    if not DATE_RE.fullmatch(d):
        die(f"bad date {d!r}, want YYYY-MM-DD")
    weights = load_weights(person)
    weights[d] = lbs
    save_weights(person, weights)
    print(f"{person}: {lbs} lb on {d} ({len(weights)} weigh-in(s) total)")


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) < 2 or args[0] not in PEOPLE:
        die(__doc__)
    person = args[0]
    if args[1] == "--weight":
        if len(args) < 3:
            die("usage: merge.py <person> --weight <lbs> [YYYY-MM-DD]")
        log_weight(
            person,
            float(args[2]),
            args[3] if len(args) > 3 else date.today().isoformat(),
        )
    else:
        merge_csv(person, args[1])
