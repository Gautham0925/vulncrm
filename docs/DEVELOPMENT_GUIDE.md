# Development guide

## Layout

`backend/` FastAPI app, models, routers, tests, Alembic · `frontend/` React app · `idp/` synthetic identity provider · `node-service/` connector · `e2e/` Playwright · `tools/gen_docs.py` generates API, schema, toggle and role references.

## Commands

```bash
cd backend && pip install -r requirements.txt && pytest -q
cd node-service && npm test
cd frontend && npm ci && npm run test -- --run && npm run build
cd e2e && npm ci && npx playwright test        # needs both configurations running
python tools/gen_docs.py                         # regenerate generated docs
```

## Conventions

- Add a new route with `require(permission)`, `scoped()` and `get_or_404()`; write secure behavior first.
- Add a weakness only as a toggle: register it in `app/mode.py`, guard the branch with `vuln("name")`, reference it from at least one test case in `testcases_seed.py`, and add a secure-mode test asserting rejection.
- Schema changes need a new Alembic revision; run `gen_docs.py` afterwards.
- Never add flags, scoring or in-UI exploit hints.
- Keep seed data synthetic.
