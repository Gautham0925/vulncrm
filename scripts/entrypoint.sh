#!/bin/sh
set -e
if [ -z "$PUBLIC_BASE_URL" ] && [ -n "$RENDER_EXTERNAL_URL" ]; then
  export PUBLIC_BASE_URL="$RENDER_EXTERNAL_URL"
fi
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  alembic upgrade head
fi
exec "$@"
