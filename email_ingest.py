#!/usr/bin/env python3
"""Poll Gmail for BULKWATCH emails and merge their contents into the site data.

Reads unread mail addressed to the +bulkwatch alias, maps the sender to a
person via senders.json, then:
  - merges any attached .csv as a Mist export (day-level replace, so
    overlapping re-sends are safe)
  - logs a weigh-in if the subject or body contains e.g. "weight 152.5"
    (dated by the email's send date)

Processed messages are marked read; nothing else in the inbox is touched.
Env: GMAIL_USER, GMAIL_APP_PASSWORD, optional BULKWATCH_ALIAS.
"""
import email
import email.utils
import imaplib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

import merge

ROOT = Path(__file__).resolve().parent
SENDERS = {k.lower(): v for k, v in json.loads((ROOT / "senders.json").read_text()).items()}
USER = os.environ["GMAIL_USER"]
PW = os.environ["GMAIL_APP_PASSWORD"]
ALIAS = os.environ.get("BULKWATCH_ALIAS", USER.replace("@", "+bulkwatch@"))
WEIGHT_RE = re.compile(r"weight\s*[:=]?\s*(\d{2,3}(?:\.\d+)?)", re.I)


def bodies(msg):
    for part in msg.walk():
        if part.get_content_type() == "text/plain" and not part.get_filename():
            try:
                yield part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
            except Exception:
                pass


def process(msg):
    addr = email.utils.parseaddr(msg.get("From", ""))[1].lower()
    person = SENDERS.get(addr)
    if not person:
        print(f"skip: unknown sender {addr}")
        return False
    changed = False
    subject = str(email.header.make_header(email.header.decode_header(msg.get("Subject", ""))))
    try:
        sent = email.utils.parsedate_to_datetime(msg["Date"]).date().isoformat()
    except Exception:
        sent = None

    m = WEIGHT_RE.search(subject) or next(
        (w for w in (WEIGHT_RE.search(b) for b in bodies(msg)) if w), None
    )
    if m and sent:
        merge.log_weight(person, float(m.group(1)), sent)
        changed = True

    for part in msg.walk():
        name = part.get_filename() or ""
        if name.lower().endswith(".csv"):
            with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
                f.write(part.get_payload(decode=True))
                tmp = f.name
            try:
                merge.merge_csv(person, tmp)
                changed = True
            except SystemExit as e:  # merge.die() on an unusable file
                print(f"skip attachment {name}: {e}")
            finally:
                os.unlink(tmp)
    return changed


def main():
    M = imaplib.IMAP4_SSL("imap.gmail.com")
    M.login(USER, PW)
    M.select("INBOX")
    typ, data = M.search(None, f'(X-GM-RAW "to:{ALIAS} is:unread")')
    ids = data[0].split() if typ == "OK" and data and data[0] else []
    print(f"{len(ids)} unread bulkwatch email(s)")
    for num in ids:
        typ, raw = M.fetch(num, "(RFC822)")
        if typ != "OK":
            continue
        msg = email.message_from_bytes(raw[0][1])
        try:
            process(msg)
            M.store(num, "+FLAGS", "\\Seen")  # processed (or rejected) — don't retry forever
        except Exception as e:
            print(f"error on message {num}: {e}", file=sys.stderr)  # left unread for retry
    M.logout()


if __name__ == "__main__":
    main()
