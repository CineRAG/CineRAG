"""
One-shot live regression check for the recurring
"same Why this movie? on every card" bug.

Run on Nuvolos AFTER backend is up on http://127.0.0.1:8000:

    cd /files/CineRAG
    conda activate cinerag_backend
    python scripts/verify_chat_distinct.py

Exit codes:
    0 = PASS — every recommendation has a distinct explanation (bug NOT manifesting)
    1 = EMPTY recommendations (LLM-grounding issue, not deploy bug)
    2 = HTTP-level failure (signup/login/chat returned non-2xx)
    3 = REGRESSION — all explanations identical (recurring bug is back)
    4 = PARTIAL DUPE — fewer unique explanations than recommendations
"""
from __future__ import annotations

import sys
import time
import uuid

import requests

BASE = "http://127.0.0.1:8000"
QUERY = "Recommend me a mind-bending sci-fi movie like Inception"
SESSION_ID = f"verify-{uuid.uuid4().hex[:8]}"


def main() -> int:
    email = f"verify_{int(time.time())}@test.local"
    print(f"Signing up: {email}")
    r = requests.post(
        f"{BASE}/api/auth/signup",
        json={"email": email, "password": "test123"},
        timeout=30,
    )
    if r.status_code != 201:
        print(f"FAIL signup: HTTP {r.status_code}: {r.text[:300]}")
        return 2
    tok = r.json()["token"]
    print(f"Token: {tok[:30]}...\n")

    print(f"POST /api/chat: {QUERY!r}")
    r = requests.post(
        f"{BASE}/api/chat",
        json={"message": QUERY, "session_id": SESSION_ID},
        headers={"Authorization": f"Bearer {tok}"},
        timeout=180,
    )
    print(f"  HTTP: {r.status_code}")
    if r.status_code != 200:
        print(f"FAIL chat: {r.text[:400]}")
        return 2

    data = r.json()
    recs = data.get("recommendations", [])
    print(f"  recommendations returned: {len(recs)}\n")

    if not recs:
        print("EMPTY: no recommendations — LLM-grounding issue, not deploy bug.")
        return 1

    for i, m in enumerate(recs, 1):
        title = m.get("title", "???")
        expl = m.get("explanation", "<missing>")
        print(f"  [{i}] {title}")
        print(f"      explanation: {expl[:220]}\n")

    exps = [m.get("explanation", "") for m in recs]
    uniq = len(set(exps))
    print(f"count: {len(exps)}, unique explanations: {uniq}")

    if uniq == 1 and len(exps) > 1:
        print("REGRESSION: all explanations IDENTICAL — recurring bug is back.")
        return 3
    if uniq < len(exps):
        print(
            f"PARTIAL DUPE: {len(exps)} recs but only {uniq} unique explanations."
        )
        return 4

    print("PASS: all explanations distinct — recurring bug NOT manifesting.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
