import discord
from discord.ext.pages import PaginatorButton


def get_page_buttons() -> list[PaginatorButton]:
    return [
        PaginatorButton("first", label="<<", style=discord.ButtonStyle.blurple),
        PaginatorButton("prev", label="←", style=discord.ButtonStyle.blurple),
        PaginatorButton(
            "page_indicator", style=discord.ButtonStyle.gray, disabled=True
        ),
        PaginatorButton("next", label="→", style=discord.ButtonStyle.blurple),
        PaginatorButton("last", label=">>", style=discord.ButtonStyle.blurple),
    ]
