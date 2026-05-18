#!/bin/bash
# Usage: bash setup_render_env.sh <RENDER_API_KEY>
# Get your Render API key from: https://dashboard.render.com/u/settings (API Keys tab)

RENDER_KEY="${1}"
if [ -z "$RENDER_KEY" ]; then
  echo "Usage: bash setup_render_env.sh <YOUR_RENDER_API_KEY>"
  echo "Get your API key from: https://dashboard.render.com/u/settings"
  exit 1
fi

API="https://api.render.com/v1"
AUTH="Authorization: Bearer $RENDER_KEY"

echo "==> Finding your Render services..."
SERVICES=$(curl -s "$API/services?limit=20" -H "$AUTH")

BACKEND_ID=$(echo "$SERVICES" | python3 -c "
import sys, json
services = json.load(sys.stdin).get('services', []) if isinstance(json.load(open('/dev/stdin')), dict) else json.loads(sys.stdin.read())
for s in services:
    svc = s.get('service', s)
    if 'portfolio-ai-backend' in svc.get('name',''):
        print(svc['id'])
        break
" 2>/dev/null)

# Retry with correct parsing
BACKEND_ID=$(echo "$SERVICES" | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data if isinstance(data, list) else data.get('services', [])
for item in items:
    s = item.get('service', item)
    if 'portfolio-ai-backend' in s.get('name',''):
        print(s['id'])
        break
")

FRONTEND_ID=$(echo "$SERVICES" | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data if isinstance(data, list) else data.get('services', [])
for item in items:
    s = item.get('service', item)
    if 'portfolio-ai-frontend' in s.get('name',''):
        print(s['id'])
        break
")

if [ -z "$BACKEND_ID" ]; then
  echo "ERROR: Could not find portfolio-ai-backend service."
  echo "Make sure you've deployed via Blueprint first at render.com"
  echo "Services found:"
  echo "$SERVICES" | python3 -c "import sys,json; d=json.load(sys.stdin); [print(' -', i.get('service',i).get('name','?')) for i in (d if isinstance(d,list) else d.get('services',[]))]"
  exit 1
fi

echo "Backend ID:  $BACKEND_ID"
echo "Frontend ID: $FRONTEND_ID"

# ── Set backend environment variables ────────────────────────────────────────
echo ""
echo "==> Setting backend environment variables..."

set_env() {
  local service_id="$1"
  local key="$2"
  local value="$3"
  curl -s -X PUT "$API/services/$service_id/env-vars" \
    -H "$AUTH" \
    -H "Content-Type: application/json" \
    -d "{\"envVars\":[{\"key\":\"$key\",\"value\":\"$value\"}]}" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print('  ✓' if isinstance(d,list) else '  ✗ ' + str(d))" 2>/dev/null || echo "  done"
}

# We use the bulk update endpoint instead
update_envs() {
  local service_id="$1"
  shift
  local payload="$1"
  curl -s -X PUT "$API/services/$service_id/env-vars" \
    -H "$AUTH" \
    -H "Content-Type: application/json" \
    -d "$payload" \
    > /dev/null
}

# Keys are read from environment variables — never hardcode secrets in files
# Set these before running the script:
#   export ANTHROPIC_API_KEY=sk-ant-...
#   export ZERODHA_API_KEY=...
#   export ZERODHA_API_SECRET=...

BACKEND_VARS=$(cat <<EOF
{
  "envVars": [
    {"key": "ANTHROPIC_API_KEY",   "value": "${ANTHROPIC_API_KEY}"},
    {"key": "ZERODHA_API_KEY",     "value": "${ZERODHA_API_KEY}"},
    {"key": "ZERODHA_API_SECRET",  "value": "${ZERODHA_API_SECRET}"},
    {"key": "DATA_DIR",            "value": "/data"},
    {"key": "FRONTEND_URL",        "value": "https://portfolio-ai-frontend.onrender.com"}
  ]
}
EOF
)

RESULT=$(curl -s -X PUT "$API/services/$BACKEND_ID/env-vars" \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d "$BACKEND_VARS")

echo "  Backend vars: $RESULT" | python3 -c "
import sys
line = sys.stdin.read()
if 'envVars' in line or '\"key\"' in line:
    print('  ✓ Backend environment variables set successfully')
else:
    print('  Response:', line[:200])
"

# ── Set frontend environment variables ───────────────────────────────────────
if [ -n "$FRONTEND_ID" ]; then
  echo ""
  echo "==> Setting frontend environment variables..."
  FRONTEND_VARS=$(cat <<'EOF'
{
  "envVars": [
    {"key": "NEXT_PUBLIC_API_URL", "value": "https://portfolio-ai-backend.onrender.com"},
    {"key": "NODE_ENV",            "value": "production"},
    {"key": "HOSTNAME",            "value": "0.0.0.0"}
  ]
}
EOF
)
  RESULT=$(curl -s -X PUT "$API/services/$FRONTEND_ID/env-vars" \
    -H "$AUTH" \
    -H "Content-Type: application/json" \
    -d "$FRONTEND_VARS")
  echo "  $RESULT" | python3 -c "
import sys
line = sys.stdin.read()
if 'envVars' in line or '\"key\"' in line:
    print('  ✓ Frontend environment variables set successfully')
else:
    print('  Response:', line[:200])
"
fi

# ── Trigger redeploy ──────────────────────────────────────────────────────────
echo ""
echo "==> Triggering redeployment..."
curl -s -X POST "$API/services/$BACKEND_ID/deploys" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('  ✓ Backend deploy triggered:', d.get('id','?')[:16])" 2>/dev/null

if [ -n "$FRONTEND_ID" ]; then
  curl -s -X POST "$API/services/$FRONTEND_ID/deploys" \
    -H "$AUTH" -H "Content-Type: application/json" \
    -d '{}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('  ✓ Frontend deploy triggered:', d.get('id','?')[:16])" 2>/dev/null
fi

echo ""
echo "==> Done! Both services redeploying with your credentials."
echo "    Check status at: https://dashboard.render.com"
echo ""
echo "    Your app (phone link): https://portfolio-ai-frontend.onrender.com"
