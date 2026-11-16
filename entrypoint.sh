#!/bin/sh
# Starts Garage, then idempotently configures it. Safe to run on every deploy.
#
# Railway variables:
#   GARAGE_RPC_SECRET     required, 64 hex chars   (openssl rand -hex 32)
#   GARAGE_ACCESS_KEY     required, GK + 24 hex    (echo GK$(openssl rand -hex 12))
#   GARAGE_SECRET_KEY     required, 64 hex chars   (openssl rand -hex 32)
#   GARAGE_ADMIN_TOKEN    optional, read by Garage itself for the admin API
#   GARAGE_PUBLIC_DOMAIN  public domain for the web endpoint
#                         (falls back to RAILWAY_PUBLIC_DOMAIN)
#   GARAGE_BUCKET         default: ckan
#   GARAGE_KEY_NAME       default: app-key
#   GARAGE_CAPACITY       default: 1G
set -eu

BUCKET="${GARAGE_BUCKET:-ckan}"
KEY_NAME="${GARAGE_KEY_NAME:-app-key}"
CAPACITY="${GARAGE_CAPACITY:-1G}"
PUBLIC_DOMAIN="${GARAGE_PUBLIC_DOMAIN:-${RAILWAY_PUBLIC_DOMAIN:-}}"
# Accept a full URL too: strip scheme and trailing slash
PUBLIC_DOMAIN="${PUBLIC_DOMAIN#https://}"
PUBLIC_DOMAIN="${PUBLIC_DOMAIN#http://}"
PUBLIC_DOMAIN="${PUBLIC_DOMAIN%/}"

: "${GARAGE_RPC_SECRET:?GARAGE_RPC_SECRET is not set}"
: "${GARAGE_ACCESS_KEY:?GARAGE_ACCESS_KEY is not set}"
: "${GARAGE_SECRET_KEY:?GARAGE_SECRET_KEY is not set}"

log() { echo "[setup] $*"; }

mkdir -p /var/lib/garage/meta /var/lib/garage/data

# Start the server in the background and forward stop signals to it
garage server &
GARAGE_PID=$!
trap 'kill -TERM "$GARAGE_PID" 2>/dev/null' TERM INT

log "waiting for Garage to start..."
i=0
until garage status >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -ge 60 ]; then log "Garage did not start in 60s"; exit 1; fi
  sleep 1
done

# 1. Layout (first start only)
if garage status | grep -q "NO ROLE ASSIGNED"; then
  NODE_ID="$(garage node id -q | cut -d@ -f1)"
  log "assigning layout to node $NODE_ID"
  garage layout assign -z dc1 -c "$CAPACITY" "$NODE_ID"
  garage layout apply --version 1
else
  log "layout already configured"
fi

# 2. Access key (imported, so ID and secret stay stable across redeploys)
if garage key info "$KEY_NAME" >/dev/null 2>&1; then
  log "key '$KEY_NAME' exists"
else
  log "importing key '$KEY_NAME'"
  garage key import --yes -n "$KEY_NAME" "$GARAGE_ACCESS_KEY" "$GARAGE_SECRET_KEY"
fi

# 3. Bucket
if garage bucket info "$BUCKET" >/dev/null 2>&1; then
  log "bucket '$BUCKET' exists"
else
  log "creating bucket '$BUCKET'"
  garage bucket create "$BUCKET"
fi

# 4. Permissions and public website access (both idempotent)
garage bucket allow --read --write --owner "$BUCKET" --key "$KEY_NAME"
garage bucket website --allow "$BUCKET"

# 5. Alias the bucket to the public domain so the web endpoint serves it
if [ -n "$PUBLIC_DOMAIN" ]; then
  if garage bucket info "$PUBLIC_DOMAIN" >/dev/null 2>&1; then
    log "alias '$PUBLIC_DOMAIN' exists"
  else
    log "aliasing '$BUCKET' as '$PUBLIC_DOMAIN'"
    garage bucket alias "$BUCKET" "$PUBLIC_DOMAIN"
  fi
  log "done. public URL: https://$PUBLIC_DOMAIN/"
else
  log "no public domain set, skipping alias"
  log "done."
fi

wait "$GARAGE_PID"