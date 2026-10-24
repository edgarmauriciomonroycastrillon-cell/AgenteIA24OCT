#!/usr/bin/env python3
"""Send one email through the Resend API, with an HTML body and a plain-text twin.

Usage:
  python3 enviar_resend.py --to person@example.com --subject "..." \
      --html /mnt/session/outputs/reporte.html --text /mnt/session/outputs/reporte.txt

Reads RESEND_API_KEY from the environment. In the sandbox that value is only a placeholder:
the real key is added when the request leaves the sandbox, so never print or log it.
Prints "status <code> id <id>" and exits 0 on success; exits 1 on failure.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.resend.com/emails"
SENDER = "Analista Colombia <onboarding@resend.dev>"


def send(payload: dict, key: str):
    req = urllib.request.Request(
        API,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "analista-colombia/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        return 0, str(e.reason)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", required=True)
    ap.add_argument("--subject", required=True)
    ap.add_argument("--html", required=True)
    ap.add_argument("--text", required=True)
    args = ap.parse_args()

    key = os.environ.get("RESEND_API_KEY", "")
    if not key:
        print("ERROR: RESEND_API_KEY no está definida en el entorno", file=sys.stderr)
        return 1
    payload = {
        "from": SENDER,
        "to": [args.to],
        "subject": args.subject,
        "html": Path(args.html).read_text(encoding="utf-8"),
        "text": Path(args.text).read_text(encoding="utf-8"),
    }
    status, body = send(payload, key)
    # Retry only on 429: Resend rejected the request, so nothing was sent. After a timeout or a
    # 5xx the email may already be on its way, and a retry could send it twice.
    if status == 429:
        time.sleep(5)
        status, body = send(payload, key)
    if status == 200:
        try:
            mail_id = json.loads(body).get("id", "")
        except json.JSONDecodeError:
            mail_id = ""
        print(f"status {status} id {mail_id}")
        return 0
    print(f"ERROR: Resend respondió {status}: {body[:300]}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
