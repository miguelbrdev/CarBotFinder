# CarBotFinder

Watches the main Spanish used-car portals and sends you a Telegram message, within minutes,
when a new listing matches your filters (make/model, year range, max price, max mileage,
excluded provinces). Runs for free on GitHub Actions.

> Work in progress. See `docs/PLAN.md` (Spanish) for the research, design and roadmap.

## Quick start (local)

```bash
pip install uv                       # or see https://docs.astral.sh/uv/
uv sync
cp config.example.yaml config.yaml   # edit your searches
cp .env.example .env                 # add your Telegram bot token and chat id
uv run carbotfinder run --dry-run    # one pass, prints matches, sends nothing
uv run carbotfinder run --seed       # first real run: marks current listings as seen
uv run carbotfinder run              # one pass, notifies new matches
```

## Development

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy carbotfinder
```
