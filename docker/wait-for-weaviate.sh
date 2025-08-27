#!/bin/sh
set -e

WEAVIATE_URL=${WEAVIATE_URL:-http://weaviate:8080}
MAX_RETRIES=30
SLEEP=2

echo "Waiting for Weaviate at $WEAVIATE_URL..."
count=0
while [ $count -lt $MAX_RETRIES ]; do
  # Use HTTP status check for readiness (curl returns non-zero on HTTP errors with -f)
  if curl -fs --connect-timeout 3 "$WEAVIATE_URL/v1/.well-known/ready" >/dev/null 2>&1; then
    echo "Weaviate is ready"
    break
  fi
  count=$((count+1))
  echo "Not ready yet ($count/$MAX_RETRIES). Sleeping $SLEEP s..."
  sleep $SLEEP
done

if [ $count -ge $MAX_RETRIES ]; then
    echo "Timed out waiting for Weaviate" >&2
    exit 1
fi

echo "Starting: $@"
exec "$@"
