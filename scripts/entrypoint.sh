#!/bin/sh
set -e
if [ -z "$PUBLIC_BASE_URL" ] && [ -n "$RENDER_EXTERNAL_URL" ]; then
  export PUBLIC_BASE_URL="$RENDER_EXTERNAL_URL"
fi
if [ "$EMBED_IDP" = "1" ]; then
  export IDP_BASE_URL="${PUBLIC_BASE_URL%/}/idp"
  export IDP_INTERNAL_URL="http://127.0.0.1:${PORT:-8000}/idp"
fi
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  alembic upgrade head
fi
exec "$@"
