# Contributing

Thanks for taking a look. Small, focused pull requests are welcome.

## Ground rules

- Keep the request volume low: one request per portal per scan, no pagination loops, no
  CAPTCHA or authentication bypasses, no paid proxies.
- Every portal parser must be a pure function with a test against a fixture in `tests/fixtures/`.
  Trim fixtures to 2-3 listings and remove phones, seller names, user ids and licence plates.
- Never commit tokens, chat ids or the state database.
- Run the full check before pushing:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy carbotfinder && uv run pytest
```

## Adding a portal

1. Create `carbotfinder/portals/<name>.py` with `build_url()` / `build_body()`, `parse()` and a
   `Portal` subclass decorated with `@register`.
2. Import the module in `carbotfinder/portals/__init__.py` and add the name to `ALL_PORTALS`
   in `carbotfinder/config.py`.
3. Add a fixture and tests. Document how the portal was verified (date, endpoint, caveats) in the
   module docstring and in `docs/PLAN.md`.
