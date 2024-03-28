# pzsd-bot
Discord bot for PZSD server

## Installation

Install [uv](https://github.com/astral-sh/uv) and then run the following:

```
# create virtual environment and activate it
uv venv
source .venv/bin/activate

# install dependencies
uv pip sync requirements.txt
```

### Database

Install [postgresql](https://www.postgresql.org/download/) and create a database called `pzsd`:
```
createdb -O postgres pzsd
```

Run migrations:
```
# with virtual environment active
alembic upgrade head
```

### Environment

Before running the bot, a `.env` file is expected to exist that looks like the following:

```
BOT_TOKEN=yourbottokenhere
GUILD_ID=yourguildidhere
POINTS_LOG_CHANNEL=channelidhere
```

### Run the bot
```
# with virtual environment active
python -m pzsd_bot
```

## Create migrations

If you've made a change to pzsd_bot/model.py, you can generate a new migration file:
```
alembic revision --autogenerate -m "description of your migration"
```
