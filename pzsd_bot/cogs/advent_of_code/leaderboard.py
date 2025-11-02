import logging
from typing import TypedDict

import pendulum
from discord import ApplicationContext, Bot, Embed
from discord.commands import SlashCommandGroup, option
from discord.ext.commands import Cog

from pzsd_bot.settings import AOCSettings, Colors

logger = logging.getLogger(__name__)

CURRENT_YEAR = pendulum.today().year
AOC_GENESIS = 2015


class CompletionDay(TypedDict):
    get_star_ts: int
    star_index: int


class LeaderboardMembers(TypedDict):
    id: int
    name: str | None
    stars: int
    local_score: int
    last_star_ts: int
    completion_day_level: dict[str, dict[str, CompletionDay]]


class LeaderboardResponse(TypedDict):
    num_days: int
    event: str
    day1_ts: int
    owner_id: int
    members: dict[str, LeaderboardMembers]


class CachedLeaderboard(TypedDict):
    last_fetched: pendulum.DateTime
    leaderboard: LeaderboardResponse


class AOCLeaderboards(Cog):
    aoc = SlashCommandGroup("aoc", "Advent of Code related commands.")

    def __init__(self, bot: Bot):
        self.bot = bot
        self.cached_leaderboards: dict[int, CachedLeaderboard] = {}

    def make_aoc_leaderboard_embed(
        self,
        member_scores: list[tuple[int, int, str]],
        year: int,
        last_fetched: pendulum.DateTime,
    ) -> Embed:
        ESC = "\x1b"
        RESET = f"{ESC}[0m"
        GOLD_BOLD = f"{ESC}[1;33m"
        RED_BOLD = f"{ESC}[1;31m"
        GREEN_BOLD = f"{ESC}[1;32m"
        RED = f"{ESC}[31m"
        GREEN = f"{ESC}[32m"

        header = f"{GREEN_BOLD}Rank |  Stars  | Score | Name {RESET}"
        divider = f"{RED_BOLD}-----+---------+-------+-------- {RESET}"

        lines = [header, divider]

        for rank, (score, stars, name) in enumerate(
            sorted(member_scores, reverse=True), 1
        ):
            if rank == 1:
                color = GOLD_BOLD
            elif rank <= 3:
                color = RED_BOLD if rank % 2 == 0 else GREEN_BOLD
            else:
                color = RED if rank % 2 == 0 else GREEN

            stars_str = f"⭐ ({stars})"
            if stars < 10:
                stars_str += " "

            line = f"{color}{rank:>3}  | {stars_str:<7}| {score:>5} | {name}{RESET}"
            lines.append(line)

        embed = Embed(
            colour=Colors.dark_green.value,
            title=f"🎄 Advent of Code ✨ {year} Leaderboard 🎄",
            description="```ansi\n" + "\n".join(lines) + "\n```",
            url=f"{AOCSettings.base_url}/{year}/{AOCSettings.private_leaderboard_path}",
            timestamp=last_fetched,
        )
        embed.set_footer(text="Last updated")

        return embed

    @aoc.command(description="View aoc leaderboard.")
    @option(
        "year",
        descrption="What year to fetch the leaderboard for.",
        default=CURRENT_YEAR,
        min_value=AOC_GENESIS,
        max_value=CURRENT_YEAR,
    )
    async def leaderboard(self, ctx: ApplicationContext, year: int) -> None:
        logger.info(
            "`/aoc leaderboard` invoked by %s with year=%s", ctx.author.name, year
        )

        last_fetched = None
        if year in self.cached_leaderboards:
            last_fetched = self.cached_leaderboards[year]["last_fetched"]

        if last_fetched is None or last_fetched <= pendulum.now().subtract(
            minutes=AOCSettings.leaderboard_cache_ttl_minutes
        ):
            logger.info(
                "Last fetch >%smin ago. Fetching current leaderboard",
                AOCSettings.leaderboard_cache_ttl_minutes,
            )
            last_fetched = pendulum.now()

            client = self.bot.client.session
            async with client.get(
                f"{AOCSettings.base_url}/{year}/{AOCSettings.private_leaderboard_path}.json"
                f"?view_key={AOCSettings.private_leaderboard_key}"
            ) as r:
                lb_data = await r.json()

            self.cached_leaderboards[year] = {
                "leaderboard": lb_data,
                "last_fetched": last_fetched,
            }
        else:
            logger.info(
                "Last fetch <%smin ago. Returning leaderboard from cache",
                AOCSettings.leaderboard_cache_ttl_minutes,
            )

        leaderboard = self.cached_leaderboards[year]["leaderboard"]

        member_scores = []
        for member in leaderboard["members"].values():
            member_scores.append(
                (
                    member["local_score"],
                    member["stars"],
                    member["name"] or str(member["id"]),
                )
            )

        embed = self.make_aoc_leaderboard_embed(member_scores, year, last_fetched)

        await ctx.respond(embed=embed)


def setup(bot: Bot) -> None:
    bot.add_cog(AOCLeaderboards(bot))
