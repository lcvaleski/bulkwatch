#!/usr/bin/env python3
"""Poll Resend inbound email for BULKWATCH uploads.

Lists received emails addressed to BULKWATCH_ADDRESS, maps the sender to a
person via senders.json, then:
  - merges any attached .csv as a Mist export (day-level replace, so
    overlapping re-sends are safe)
  - logs a weigh-in if the subject or body contains e.g. "weight 152.5"
    (dated by the email's received date)

Processed email ids are remembered in data/.processed_emails.json (committed),
so each email is handled once. Env: RESEND_API_KEY, optional BULKWATCH_ADDRESS.
"""
import json
import os
import re
import sys
import tempfile
import urllib.request
from pathlib import Path

import merge

ROOT = Path(__file__).resolve().parent
API = "https://api.resend.com"
KEY = os.environ["RESEND_API_KEY"]
ADDRESS = os.environ.get("BULKWATCH_ADDRESS", "bulkwatch@in.river.page").lower()
SENDERS = {k.lower(): v for k, v in json.loads((ROOT / "senders.json").read_text()).items()}
STATE = ROOT / "data" / ".processed_emails.json"
WEIGHT_RE = re.compile(r"weight\s*[:=]?\s*(\d{2,3}(?:\.\d+)?)", re.I)


def api(path):
    req = urllib.request.Request(API + path, headers={"Authorization": f"Bearer {KEY}"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def addr(s):
    """'Name <a@b>' or 'a@b' -> 'a@b'"""
    m = re.search(r"<([^>]+)>", s or "")
    return (m.group(1) if m else (s or "")).strip().lower()


def process(row):
    person = SENDERS.get(addr(row.get("from", "")))
    if not person:
        print(f"skip {row['id']}: unknown sender {addr(row.get('from', ''))}")
        return
    e = api(f"/emails/receiving/{row['id']}")
    received = (row.get("created_at") or "")[:10]

    m = WEIGHT_RE.search(e.get("subject") or "") or WEIGHT_RE.search(e.get("text") or "")
    if m and received:
        merge.log_weight(person, float(m.group(1)), received)

    for a in e.get("attachments") or []:
        if not (a.get("filename") or "").lower().endswith(".csv"):
            continue
        meta = api(f"/emails/receiving/{row['id']}/attachments/{a['id']}")
        with urllib.request.urlopen(meta["download_url"]) as r, tempfile.NamedTemporaryFile(
            suffix=".csv", delete=False
        ) as f:
            f.write(r.read())
            tmp = f.name
        try:
            merge.merge_csv(person, tmp)
        except SystemExit as ex:  # merge.die() on an unusable file
            print(f"skip attachment {a.get('filename')}: {ex}")
        finally:
            os.unlink(tmp)


def main():
    done = set(json.loads(STATE.read_text())) if STATE.exists() else set()
    rows = api("/emails/receiving?limit=100").get("data") or []
    mine = [
        r for r in rows
        if r["id"] not in done and any(addr(t) == ADDRESS for t in r.get("to") or [])
    ]
    print(f"{len(mine)} new bulkwatch email(s)")
    for row in reversed(mine):  # oldest first
        try:
            process(row)
            done.add(row["id"])
        except Exception as e:
            print(f"error on {row['id']}: {e}", file=sys.stderr)  # retried next poll
    STATE.write_text(json.dumps(sorted(done)[-1000:]))


if __name__ == "__main__":
    main()
