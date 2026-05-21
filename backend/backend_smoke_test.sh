#!/usr/bin/env bash
set -u

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"

EMAIL="smoke_$(date +%s)@example.com"
PASSWORD="testpass123"
DISPLAY_NAME="Smoke Test User"
SESSION_ID="backend-smoke-session-$(date +%s)"

PASS=0
FAIL=0
WARN=0
TOKEN=""
MOVIE_ID=""
MOVIE_TITLE=""
MOVIE_YEAR="null"
MOVIE_GENRES_JSON="[]"

line() {
  echo "------------------------------------------------------------"
}

ok() {
  echo "[PASS] $1"
  PASS=$((PASS + 1))
}

fail() {
  echo "[FAIL] $1"
  FAIL=$((FAIL + 1))
}

warn() {
  echo "[WARN] $1"
  WARN=$((WARN + 1))
}

request() {
  local method="$1"
  local path="$2"
  local body="${3:-}"
  local auth="${4:-no}"

  local headers=(-H "Content-Type: application/json")
  if [[ "$auth" == "yes" ]]; then
    headers+=(-H "Authorization: Bearer $TOKEN")
  fi

  if [[ -n "$body" ]]; then
    curl -sS -w "\n%{http_code}" -X "$method" "${BASE_URL}${path}" "${headers[@]}" -d "$body"
  else
    curl -sS -w "\n%{http_code}" -X "$method" "${BASE_URL}${path}" "${headers[@]}"
  fi
}

check_status() {
  local name="$1"
  local status="$2"
  local expected_regex="$3"
  local body="$4"

  if [[ "$status" =~ $expected_regex ]]; then
    ok "$name returned HTTP $status"
  else
    fail "$name returned HTTP $status"
    echo "$body"
  fi
}

json_eval() {
  local body="$1"
  local expr="$2"
  python - "$expr" "$body" <<'PY'
import json
import sys

expr = sys.argv[1]
raw = sys.argv[2]
try:
    data = json.loads(raw)
except Exception:
    print("")
    sys.exit(0)

try:
    value = eval(expr, {"__builtins__": {}}, {"data": data, "len": len, "isinstance": isinstance, "str": str, "any": any})
except Exception:
    print("")
    sys.exit(0)

if isinstance(value, bool):
    print("true" if value else "false")
elif value is None:
    print("")
else:
    print(json.dumps(value) if isinstance(value, (list, dict)) else str(value))
PY
}

extract_token() {
  json_eval "$1" 'data.get("token") or data.get("access_token") or data.get("accessToken") or (data.get("data") or {}).get("token") or (data.get("data") or {}).get("access_token") or ""'
}

assert_json_true() {
  local name="$1"
  local body="$2"
  local expr="$3"
  local result
  result="$(json_eval "$body" "$expr")"
  if [[ "$result" == "true" ]]; then
    ok "$name"
  else
    fail "$name"
    echo "$body"
  fi
}

echo "Backend demo smoke test"
echo "Backend:      $BASE_URL"
echo "Project root: $PROJECT_ROOT"
line

echo "1) Health, docs, and local Ollama reachability"
RESP="$(curl -sS -w "\n%{http_code}" "${BASE_URL}/docs" || true)"
BODY="$(echo "$RESP" | sed '$d')"
STATUS="$(echo "$RESP" | tail -n1)"
check_status "Swagger /docs" "$STATUS" "^(200|3[0-9][0-9])$" "$BODY"

RESP="$(curl -sS -w "\n%{http_code}" "${BASE_URL}/api/health" || true)"
BODY="$(echo "$RESP" | sed '$d')"
STATUS="$(echo "$RESP" | tail -n1)"
check_status "GET /api/health" "$STATUS" "^200$" "$BODY"
assert_json_true "Health status is ok" "$BODY" 'data.get("status") == "ok"'
assert_json_true "Health reports LFS Chroma path" "$BODY" 'data.get("paths", {}).get("chroma_db_path") == "/space_mounts/pars/data/chroma_db"'
assert_json_true "Health reports LFS BM25 path" "$BODY" 'data.get("paths", {}).get("bm25_index_path") == "/space_mounts/pars/data/bm25_index.pkl"'

RESP="$(curl -sS -w "\n%{http_code}" "http://127.0.0.1:11434/api/tags" || true)"
BODY="$(echo "$RESP" | sed '$d')"
STATUS="$(echo "$RESP" | tail -n1)"
if [[ "$STATUS" == "200" ]]; then
  ok "Ollama API is reachable on localhost:11434"
else
  fail "Ollama API is not reachable on localhost:11434"
  echo "$BODY"
fi

line
echo "2) Auth"
SIGNUP_BODY=$(cat <<JSON
{
  "email": "$EMAIL",
  "password": "$PASSWORD",
  "display_name": "$DISPLAY_NAME"
}
JSON
)

RESP="$(request POST "/api/auth/signup" "$SIGNUP_BODY" "no")"
BODY="$(echo "$RESP" | sed '$d')"
STATUS="$(echo "$RESP" | tail -n1)"
check_status "POST /api/auth/signup" "$STATUS" "^201$" "$BODY"
TOKEN="$(extract_token "$BODY")"
if [[ -n "$TOKEN" ]]; then
  ok "Signup response contains token"
else
  fail "Signup response did not contain token"
fi

LOGIN_BODY=$(cat <<JSON
{
  "email": "$EMAIL",
  "password": "$PASSWORD"
}
JSON
)

RESP="$(request POST "/api/auth/login" "$LOGIN_BODY" "no")"
BODY="$(echo "$RESP" | sed '$d')"
STATUS="$(echo "$RESP" | tail -n1)"
check_status "POST /api/auth/login" "$STATUS" "^200$" "$BODY"
LOGIN_TOKEN="$(extract_token "$BODY")"
if [[ -n "$LOGIN_TOKEN" ]]; then
  TOKEN="$LOGIN_TOKEN"
  ok "Login response contains token"
else
  fail "Login response did not contain token"
fi

if [[ -z "$TOKEN" ]]; then
  fail "Cannot continue protected endpoint tests without a token"
  line
  echo "Passed:   $PASS"
  echo "Warnings: $WARN"
  echo "Failed:   $FAIL"
  exit 1
fi

RESP="$(request GET "/api/users/me" "" "yes")"
BODY="$(echo "$RESP" | sed '$d')"
STATUS="$(echo "$RESP" | tail -n1)"
check_status "GET /api/users/me" "$STATUS" "^200$" "$BODY"
assert_json_true "GET /api/users/me contains smoke email" "$BODY" "data.get('email') == '$EMAIL'"

SAVED_TOKEN="$TOKEN"
TOKEN=""
RESP="$(request GET "/api/users/me" "" "yes")"
BODY="$(echo "$RESP" | sed '$d')"
STATUS="$(echo "$RESP" | tail -n1)"
check_status "GET /api/users/me without token" "$STATUS" "^401$" "$BODY"
TOKEN="$SAVED_TOKEN"

line
echo "3) Movie endpoints using rebuilt retriever"
RESP="$(request GET "/api/movies/search?q=Inception" "" "yes")"
BODY="$(echo "$RESP" | sed '$d')"
STATUS="$(echo "$RESP" | tail -n1)"
check_status "GET /api/movies/search?q=Inception" "$STATUS" "^200$" "$BODY"
assert_json_true "Movie search returned at least one result" "$BODY" 'len(data.get("results", [])) > 0'
MOVIE_ID="$(json_eval "$BODY" 'data.get("results", [{}])[0].get("movie_id", "")')"
MOVIE_TITLE="$(json_eval "$BODY" 'data.get("results", [{}])[0].get("title", "")')"
MOVIE_YEAR="$(json_eval "$BODY" 'data.get("results", [{}])[0].get("year", None)')"
MOVIE_GENRES_JSON="$(json_eval "$BODY" 'data.get("results", [{}])[0].get("genres", [])')"
[[ -n "$MOVIE_YEAR" ]] || MOVIE_YEAR="null"
[[ -n "$MOVIE_GENRES_JSON" ]] || MOVIE_GENRES_JSON="[]"

if [[ -z "$MOVIE_ID" || -z "$MOVIE_TITLE" ]]; then
  fail "Could not extract first movie from search results"
else
  ok "Extracted movie_id=$MOVIE_ID from search results"
fi

RESP="$(request GET "/api/movies/${MOVIE_ID}" "" "yes")"
BODY="$(echo "$RESP" | sed '$d')"
STATUS="$(echo "$RESP" | tail -n1)"
check_status "GET /api/movies/{movie_id}" "$STATUS" "^200$" "$BODY"
assert_json_true "Movie detail contains plot_summary" "$BODY" 'len(data.get("plot_summary", "")) > 0'

RESP="$(request GET "/api/movies/not-a-real-cinerag-id" "" "yes")"
BODY="$(echo "$RESP" | sed '$d')"
STATUS="$(echo "$RESP" | tail -n1)"
check_status "GET /api/movies/{bad_id}" "$STATUS" "^404$" "$BODY"

line
echo "4) Watched list CRUD"
WATCHED_BODY="$(
MOVIE_ID="$MOVIE_ID" MOVIE_TITLE="$MOVIE_TITLE" MOVIE_YEAR="$MOVIE_YEAR" MOVIE_GENRES_JSON="$MOVIE_GENRES_JSON" python - <<'PY'
import json
import os

year_raw = os.environ.get("MOVIE_YEAR") or "null"
genres_raw = os.environ.get("MOVIE_GENRES_JSON") or "[]"

try:
    year = None if year_raw == "null" else int(year_raw)
except ValueError:
    year = None

try:
    genres = json.loads(genres_raw)
except json.JSONDecodeError:
    genres = []

print(json.dumps({
    "movie_id": os.environ["MOVIE_ID"],
    "title": os.environ["MOVIE_TITLE"],
    "year": year,
    "genres": genres if isinstance(genres, list) else [],
    "rating": 4.5,
}))
PY
)"

RESP="$(request POST "/api/watched" "$WATCHED_BODY" "yes")"
BODY="$(echo "$RESP" | sed '$d')"
STATUS="$(echo "$RESP" | tail -n1)"
check_status "POST /api/watched" "$STATUS" "^201$" "$BODY"

RESP="$(request POST "/api/watched" "$WATCHED_BODY" "yes")"
BODY="$(echo "$RESP" | sed '$d')"
STATUS="$(echo "$RESP" | tail -n1)"
check_status "Duplicate POST /api/watched" "$STATUS" "^409$" "$BODY"

RESP="$(request GET "/api/watched" "" "yes")"
BODY="$(echo "$RESP" | sed '$d')"
STATUS="$(echo "$RESP" | tail -n1)"
check_status "GET /api/watched" "$STATUS" "^200$" "$BODY"
assert_json_true "Watched list contains the smoke movie" "$BODY" "any(item.get('movie_id') == '$MOVIE_ID' for item in data.get('watched', []))"

UPDATE_BODY='{"rating": 5.0}'
RESP="$(request PUT "/api/watched/${MOVIE_ID}" "$UPDATE_BODY" "yes")"
BODY="$(echo "$RESP" | sed '$d')"
STATUS="$(echo "$RESP" | tail -n1)"
check_status "PUT /api/watched/{movie_id}" "$STATUS" "^200$" "$BODY"
assert_json_true "Watched rating updated to 5.0" "$BODY" 'data.get("rating") == 5.0'

line
echo "5) Chat endpoint and session continuity"
CHAT_BODY_ONE=$(cat <<JSON
{
  "message": "Recommend thoughtful science fiction movies with emotional depth.",
  "session_id": "$SESSION_ID"
}
JSON
)

RESP="$(request POST "/api/chat" "$CHAT_BODY_ONE" "yes")"
BODY="$(echo "$RESP" | sed '$d')"
STATUS="$(echo "$RESP" | tail -n1)"
check_status "First POST /api/chat" "$STATUS" "^200$" "$BODY"
assert_json_true "First chat response preserves session_id" "$BODY" "data.get('session_id') == '$SESSION_ID'"
assert_json_true "First chat response contains response_text" "$BODY" 'len(data.get("response_text", "")) > 0'
assert_json_true "First chat response contains debug.retrieval_method" "$BODY" 'len(data.get("debug", {}).get("retrieval_method", "")) > 0'
assert_json_true "First chat returned at least one recommendation" "$BODY" 'len(data.get("recommendations", [])) > 0'

CHAT_BODY_TWO=$(cat <<JSON
{
  "message": "Make the next suggestion a bit more emotional and character-driven.",
  "session_id": "$SESSION_ID"
}
JSON
)

RESP="$(request POST "/api/chat" "$CHAT_BODY_TWO" "yes")"
BODY="$(echo "$RESP" | sed '$d')"
STATUS="$(echo "$RESP" | tail -n1)"
check_status "Second POST /api/chat with same session_id" "$STATUS" "^200$" "$BODY"
assert_json_true "Second chat response preserves session_id" "$BODY" "data.get('session_id') == '$SESSION_ID'"
assert_json_true "Second chat response contains response_text" "$BODY" 'len(data.get("response_text", "")) > 0'

line
echo "6) Conversation DB history"
PYTHONPATH="$PROJECT_ROOT" PROJECT_ROOT="$PROJECT_ROOT" SMOKE_EMAIL="$EMAIL" SMOKE_SESSION_ID="$SESSION_ID" python - <<'PY'
import json
import os
import sys

from backend.auth.models import User
from backend.database import SessionLocal
from backend.movies.models import ConversationMessage

email = os.environ["SMOKE_EMAIL"]
session_id = os.environ["SMOKE_SESSION_ID"]

with SessionLocal() as db:
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        print(json.dumps({"ok": False, "reason": "user_not_found"}))
        sys.exit(1)

    rows = (
        db.query(ConversationMessage)
        .filter(
            ConversationMessage.user_id == user.id,
            ConversationMessage.session_id == session_id,
        )
        .order_by(ConversationMessage.created_at.asc(), ConversationMessage.id.asc())
        .all()
    )
    roles = [row.role for row in rows]
    ok = len(rows) >= 4 and roles[:4] == ["user", "assistant", "user", "assistant"]
    print(json.dumps({"ok": ok, "count": len(rows), "roles": roles}))
    sys.exit(0 if ok else 1)
PY
DB_STATUS=$?
if [[ "$DB_STATUS" -eq 0 ]]; then
  ok "Conversation history persisted at least four messages for the session"
else
  fail "Conversation history persistence check failed"
fi

line
echo "7) Cleanup watched list entry"
RESP="$(request DELETE "/api/watched/${MOVIE_ID}" "" "yes")"
BODY="$(echo "$RESP" | sed '$d')"
STATUS="$(echo "$RESP" | tail -n1)"
check_status "DELETE /api/watched/{movie_id}" "$STATUS" "^200$" "$BODY"

line
echo "Smoke test complete."
echo "Passed:   $PASS"
echo "Warnings: $WARN"
echo "Failed:   $FAIL"

if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi

exit 0
