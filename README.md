# pzsd-bot
Discord bot for PZSD server

## Installation

Install [uv](https://github.com/astral-sh/uv) and then run the following:

```
# Create virtual environment and install dependencies
uv sync
# Optionally omit dev dependencies
uv sync --no-dev
```

### Database

Install [postgresql](https://www.postgresql.org/download/) and create a database called `pzsd`:
```
createdb -O postgres pzsd
```

Run migrations:
```
uv run alembic upgrade head
```

### Environment

Before running the bot, a `.env` file is expected to exist that looks like the following:

```
BOT_TOKEN=yourbottokenhere
POINTS_LOG_CHANNEL=channelidhere
```

### Run the bot
```
uv run python -m pzsd_bot
```

### Run tests
```
uv run pytest -v --disable-warnings
```

## Create migrations

If you've made a change to pzsd_bot/model.py, you can generate a new migration file:
```
uv run alembic revision --autogenerate -m "description of your migration"
```
