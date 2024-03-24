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

Before running the bot, a `.env` file is expected to exist that looks like the following:

```
BOT_TOKEN=yourbottokenhere
GUILD_ID=yourguildidhere
```

Finally you can run the bot with `python main.py`
