#!/usr/bin/env bash
set -u

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
EMAIL="smoke_$(date +%s)@example.com"
PASSWORD="testpass123"
DISPLAY_NAME="Smoke Test User"
MOVIE_ID="wiki_smoke_test_12345"

PASS=0
FAIL=0
WARN=0
TOKEN=""

line() {
  echo "------------------------------------------------------------"
}

ok() {
  echo "✅ PASS: $1"
  PASS=$((PASS + 1))
}

fail() {
  echo "❌ FAIL: $1"
  FAIL=$((FAIL + 1))
}

warn() {
  echo "⚠️  WARN: $1"
  WARN=$((WARN + 1))
}

extract_token() {
  python - "$1" <<'PY'
import json, sys
raw = sys.argv[1]
try:
    data = json.loads(raw)
except Exception:
    print("")
    sys.exit(0)

candidates = [
    data.get("access_token"),
    data.get("token"),
    data.get("accessToken"),
]

if isinstance(data.get("data"), dict):
    candidates.extend([
        data["data"].get("access_token"),
        data["data"].get("token"),
        data["data"].get("accessToken"),
    ])

for value in candidates:
    if isinstance(value, str) and value:
        print(value)
        sys.exit(0)

print("")
PY
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
    echo "Response:"
    echo "$body"
  fi
}

echo "Testing backend at: $BASE_URL"
line

echo "1) Checking server/docs..."
RESP="$(curl -sS -w "\n%{http_code}" "${BASE_URL}/docs" || true)"
BODY="$(echo "$RESP" | sed '$d')"
STATUS="$(echo "$RESP" | tail -n1)"

if [[ "$STATUS" =~ ^2|3 ]]; then
  ok "Swagger docs reachable at /docs"
else
  fail "Swagger docs not reachable. Is uvicorn running?"
  echo "Status: $STATUS"
  echo "$BODY"
  exit 1
fi

line
echo "2) Testing signup..."

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
check_status "Signup" "$STATUS" "^(200|201)$" "$BODY"

SIGNUP_TOKEN="$(extract_token "$BODY")"
if [[ -n "$SIGNUP_TOKEN" ]]; then
  TOKEN="$SIGNUP_TOKEN"
  ok "Signup response contained access token"
else
  warn "Signup response did not contain access token; will try login"
fi

line
echo "3) Testing login..."

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

if [[ "$STATUS" =~ ^(200|201)$ ]]; then
  ok "Login with JSON returned HTTP $STATUS"
  LOGIN_TOKEN="$(extract_token "$BODY")"
  if [[ -n "$LOGIN_TOKEN" ]]; then
    TOKEN="$LOGIN_TOKEN"
    ok "Login response contained access token"
  else
    fail "Login response did not contain access token"
    echo "$BODY"
  fi
else
  warn "JSON login failed with HTTP $STATUS; trying OAuth2 form login"

  RESP="$(curl -sS -w "\n%{http_code}" \
    -X POST "${BASE_URL}/api/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=${EMAIL}&password=${PASSWORD}")"

  BODY="$(echo "$RESP" | sed '$d')"
  STATUS="$(echo "$RESP" | tail -n1)"

  if [[ "$STATUS" =~ ^(200|201)$ ]]; then
    ok "Login with form data returned HTTP $STATUS"
    LOGIN_TOKEN="$(extract_token "$BODY")"
    if [[ -n "$LOGIN_TOKEN" ]]; then
      TOKEN="$LOGIN_TOKEN"
      ok "Form login response contained access token"
    else
      fail "Form login response did not contain access token"
      echo "$BODY"
    fi
  else
    fail "Login failed with both JSON and form data"
    echo "$BODY"
  fi
fi

if [[ -z "$TOKEN" ]]; then
  fail "Cannot continue protected endpoint tests without token"
  line
  echo "Summary: $PASS passed, $WARN warnings, $FAIL failed"
  exit 1
fi

line
echo "4) Testing protected user endpoint..."

RESP="$(request GET "/api/users/me" "" "yes")"
BODY="$(echo "$RESP" | sed '$d')"
STATUS="$(echo "$RESP" | tail -n1)"
check_status "GET /api/users/me" "$STATUS" "^200$" "$BODY"

line
echo "5) Testing watched movie CRUD..."

WATCHED_BODY=$(cat <<JSON
{
  "movie_id": "$MOVIE_ID",
  "title": "Smoke Test Movie",
  "year": 1999,
  "rating": 4.5
}
JSON
)

RESP="$(request POST "/api/watched" "$WATCHED_BODY" "yes")"
BODY="$(echo "$RESP" | sed '$d')"
STATUS="$(echo "$RESP" | tail -n1)"
check_status "POST /api/watched" "$STATUS" "^(200|201)$" "$BODY"

RESP="$(request GET "/api/watched" "" "yes")"
BODY="$(echo "$RESP" | sed '$d')"
STATUS="$(echo "$RESP" | tail -n1)"
check_status "GET /api/watched" "$STATUS" "^200$" "$BODY"

UPDATE_BODY=$(cat <<JSON
{
  "rating": 5.0
}
JSON
)

RESP="$(request PUT "/api/watched/${MOVIE_ID}" "$UPDATE_BODY" "yes")"
BODY="$(echo "$RESP" | sed '$d')"
STATUS="$(echo "$RESP" | tail -n1)"
check_status "PUT /api/watched/{movie_id}" "$STATUS" "^200$" "$BODY"

RESP="$(request DELETE "/api/watched/${MOVIE_ID}" "" "yes")"
BODY="$(echo "$RESP" | sed '$d')"
STATUS="$(echo "$RESP" | tail -n1)"
check_status "DELETE /api/watched/{movie_id}" "$STATUS" "^(200|204)$" "$BODY"

line
echo "6) Testing movie endpoints, expected to possibly be unavailable until Person A integration..."

RESP="$(request GET "/api/movies/search?q=inception" "" "yes")"
BODY="$(echo "$RESP" | sed '$d')"
STATUS="$(echo "$RESP" | tail -n1)"

if [[ "$STATUS" =~ ^200$ ]]; then
  ok "GET /api/movies/search works"
elif [[ "$STATUS" =~ ^(404|501|503)$ ]]; then
  warn "GET /api/movies/search returned HTTP $STATUS; acceptable if retrieval is not integrated yet"
else
  fail "GET /api/movies/search returned unexpected HTTP $STATUS"
  echo "$BODY"
fi

RESP="$(request GET "/api/movies/wiki_12345" "" "yes")"
BODY="$(echo "$RESP" | sed '$d')"
STATUS="$(echo "$RESP" | tail -n1)"

if [[ "$STATUS" =~ ^200$ ]]; then
  ok "GET /api/movies/{movie_id} works"
elif [[ "$STATUS" =~ ^(404|501|503)$ ]]; then
  warn "GET /api/movies/{movie_id} returned HTTP $STATUS; acceptable if retrieval is not integrated yet"
else
  fail "GET /api/movies/{movie_id} returned unexpected HTTP $STATUS"
  echo "$BODY"
fi

line
echo "7) Testing chat endpoint, expected to possibly be unavailable until Person B integration..."

CHAT_BODY=$(cat <<JSON
{
  "message": "Recommend me a thoughtful sci-fi movie",
  "session_id": "smoke-session-$(date +%s)"
}
JSON
)

RESP="$(request POST "/api/chat" "$CHAT_BODY" "yes")"
BODY="$(echo "$RESP" | sed '$d')"
STATUS="$(echo "$RESP" | tail -n1)"

if [[ "$STATUS" =~ ^200$ ]]; then
  ok "POST /api/chat works"
elif [[ "$STATUS" =~ ^(404|501|503)$ ]]; then
  warn "POST /api/chat returned HTTP $STATUS; acceptable if RAG/chat service is not integrated yet"
else
  fail "POST /api/chat returned unexpected HTTP $STATUS"
  echo "$BODY"
fi

line
echo "Smoke test complete."
echo "Passed:   $PASS"
echo "Warnings: $WARN"
echo "Failed:   $FAIL"

if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi

exit 0