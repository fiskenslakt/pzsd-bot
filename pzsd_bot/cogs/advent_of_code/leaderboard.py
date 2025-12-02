import logging
from typing import TypedDict

import pendulum
from aiohttp import ClientSession
from ansi.color import fg
from discord import ApplicationContext, Bot, Embed
from discord.commands import SlashCommandGroup, option
from discord.ext.commands import Cog

from pzsd_bot.client import retry_middleware
from pzsd_bot.settings import AOCSettings, Colors

logger = logging.getLogger(__name__)

AOC_GENESIS = 2015


class AoCAPIError(Exception):
    """Raised when Advent of Code API responds with an error."""


class AoCInvalidEventError(Exception):
    """Raised when user provides an Advent of Code event that doesn't exist."""

    def __init__(self, current_year: int):
        super().__init__(f"Invalid year, please choose a year between {AOC_GENESIS} and {current_year}.")


class MissingLeaderboardDataError(Exception):
    """Raised when there's no leaderboard data available for the requested year."""


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

    async def fetch_leaderboard(self, year: int) -> None:
        leaderboard_url = (
            f"{AOCSettings.base_url}/{year}/{AOCSettings.private_leaderboard_path}.json"
            f"?view_key={AOCSettings.private_leaderboard_key}"
        )

        client: ClientSession = self.bot.client.session
        async with client.get(url=leaderboard_url, middlewares=(retry_middleware,)) as resp:
            if resp.ok:
                leaderboard_response = await resp.json()
                self.cached_leaderboards[year] = {
                    "leaderboard": leaderboard_response,
                    "last_fetched": pendulum.now(),
                }
            else:
                logger.warning("Failed to fetch leaderboard")
                raise AoCAPIError

    def make_aoc_leaderboard_embed(
        self,
        member_scores: list[tuple[int, int, str]],
        year: int,
        last_fetched: pendulum.DateTime,
    ) -> Embed:
        header = fg.boldgreen("Rank |  Stars  | Score | Name ")
        divider = fg.boldred("-----+---------+-------+-------- ")

        lines = [header, divider]

        for rank, (score, stars, name) in enumerate(sorted(member_scores, reverse=True), 1):
            if rank == 1:
                color = fg.boldyellow
            elif rank <= 3:
                color = fg.boldred if rank % 2 == 0 else fg.boldgreen
            else:
                color = fg.red if rank % 2 == 0 else fg.green

            stars_str = f"⭐ ({stars})"
            if stars < 10:
                stars_str += " "

            line = color(f"{rank:>3}  | {stars_str:<7}| {score:>5} | {name}")
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

    def make_aoc_star_times_embed(
        self,
        member_star_times: list[tuple[int | None, int | None, str]],
        day: int,
        year: int,
        last_fetched: pendulum.DateTime,
    ) -> Embed:
        longest_name = max((len(name) for *_, name in member_star_times), default=4)

        header = fg.green(f"Rank | {'Name'.ljust(longest_name)} | ⭐       | ⭐⭐")
        divider = fg.red(f"-----+{'-' * (longest_name + 2)}+----------+----------")

        lines = [header, divider]

        # Sort by first star time
        member_star_times.sort(key=lambda x: x[0] or float("inf"))

        def get_completion_time(timestamp: int | None) -> str:
            """Format a timestamp into HH:MM:SS, or >24h if not same day."""
            if timestamp is None:
                return "--:--:--"

            dt = pendulum.from_timestamp(timestamp, tz="America/New_York")

            if dt.day != day:
                return ">24h"

            return dt.to_time_string()

        for rank, (ts1, ts2, name) in enumerate(member_star_times, 1):
            color = fg.green if rank % 2 == 1 else fg.red

            star1_time = get_completion_time(ts1)
            star2_time = get_completion_time(ts2)

            line = color(f"{rank:>3}  | {name.ljust(longest_name)} | {star1_time:>8} | {star2_time:>8}")
            lines.append(line)

        embed = Embed(
            colour=Colors.dark_green.value,
            title=f"🎄 Advent of Code {year} ✨ Day {day} Star Times 🎄",
            description="```ansi\n" + "\n".join(lines) + "\n```",
            url=f"{AOCSettings.base_url}/{year}/day/{day}",
            timestamp=last_fetched,
        )
        embed.set_footer(text="Last updated")

        return embed

    def make_aoc_stats_embed(
        self,
        daily_stats: list[dict[str, int]],
        total_members: int,
        year: int,
        last_fetched: pendulum.DateTime,
    ) -> Embed:
        header = fg.green("Day | ⭐  | ⭐⭐ | ⭐%     | ⭐⭐%")
        divider = fg.red("----+-----+-----+---------+--------")
        lines = [header, divider]

        for day, stats in enumerate(daily_stats, 1):
            star1_count = stats["star1_count"]
            star2_count = stats["star2_count"]

            if total_members > 0:
                star1_pct = (star1_count / total_members) * 100
                star2_pct = (star2_count / total_members) * 100
            else:
                star1_pct = 0.0
                star2_pct = 0.0

            color = fg.green if day % 2 == 1 else fg.red

            line = color(f"{day:>3} | {star1_count:>3} | {star2_count:>3} | {star1_pct:>6.2f}% | {star2_pct:>6.2f}%")
            lines.append(line)

        embed = Embed(
            colour=Colors.dark_green.value,
            title=f"🎄 Advent of Code ✨ {year} Star Stats 🎄",
            description="```ansi\n" + "\n".join(lines) + "\n```",
            url=f"{AOCSettings.base_url}/{year}",
            timestamp=last_fetched,
        )
        embed.set_footer(text="Last updated")

        return embed

    async def update_leaderboard_data(self, ctx: ApplicationContext, year: int | None) -> tuple[bool, int]:
        current_year = pendulum.today().year

        deferred = False

        if year is None:
            year = current_year
        elif year < AOC_GENESIS or year > current_year:
            logger.info("Invalid year, doing nothing")
            raise AoCInvalidEventError(current_year)

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
            await ctx.defer()
            deferred = True

            try:
                await self.fetch_leaderboard(year)
            except AoCAPIError:
                if year not in self.cached_leaderboards:
                    logger.info("No %s leaderboard in cache, doing nothing", year)
                    await ctx.followup.send("Unable to fetch leaderboard, please try again later.")
                    raise MissingLeaderboardDataError
                else:
                    logger.info("Last fetch failed, falling back to leaderboard from cache")
        else:
            logger.info(
                "Last fetch <%smin ago. Returning leaderboard from cache",
                AOCSettings.leaderboard_cache_ttl_minutes,
            )

        return deferred, year

    @aoc.command(description="View aoc leaderboard.")
    @option("year", description="What year to view the leaderboard for.", default=None)
    async def leaderboard(self, ctx: ApplicationContext, year: int) -> None:
        logger.info("/aoc leaderboard invoked by %s with year=%s", ctx.author.name, year)

        try:
            deferred, year = await self.update_leaderboard_data(ctx, year)
        except AoCInvalidEventError as e:
            await ctx.respond(e, ephemeral=True)
            return
        except MissingLeaderboardDataError:
            return

        leaderboard = self.cached_leaderboards[year]["leaderboard"]
        last_fetched = self.cached_leaderboards[year]["last_fetched"]

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

        if deferred:
            await ctx.followup.send(embed=embed)
        else:
            await ctx.respond(embed=embed)

    @aoc.command(description="View aoc star times.")
    @option("day", description="What day to view the star times for.")
    @option("year", description="What year to view the star times for.", default=None)
    async def star_times(self, ctx: ApplicationContext, day: int, year: int) -> None:
        logger.info("/aoc star_times invoked by %s with day=%s, year=%s", ctx.author.name, day, year)

        try:
            deferred, year = await self.update_leaderboard_data(ctx, year)
        except AoCInvalidEventError as e:
            await ctx.respond(e, ephemeral=True)
            return
        except MissingLeaderboardDataError:
            return

        leaderboard = self.cached_leaderboards[year]["leaderboard"]
        last_fetched = self.cached_leaderboards[year]["last_fetched"]

        if day < 1 or day > leaderboard["num_days"]:
            logger.info("Invalid day '%s' given for year %s, doing nothing", day, year)
            msg = f"Invalid day for {year}, try again"
            if deferred:
                await ctx.followup.send(msg)
            else:
                await ctx.respond(msg)
            return

        member_star_times = []
        for member in leaderboard["members"].values():
            star1_timestamp = None
            star2_timestamp = None

            if str(day) in member["completion_day_level"]:
                if "1" in member["completion_day_level"][str(day)]:
                    star1_timestamp = member["completion_day_level"][str(day)]["1"]["get_star_ts"]
                if "2" in member["completion_day_level"][str(day)]:
                    star2_timestamp = member["completion_day_level"][str(day)]["2"]["get_star_ts"]

            member_star_times.append(
                (
                    star1_timestamp,
                    star2_timestamp,
                    member["name"] or str(member["id"]),
                )
            )

        embed = self.make_aoc_star_times_embed(member_star_times, day, year, last_fetched)

        if deferred:
            await ctx.followup.send(embed=embed)
        else:
            await ctx.respond(embed=embed)

    @aoc.command(description="View aoc stats.")
    @option("year", description="What year to view the stats for.", default=None)
    async def stats(self, ctx: ApplicationContext, year: int) -> None:
        logger.info("/aoc stats invoked by %s with year=%s", ctx.author.name, year)

        try:
            deferred, year = await self.update_leaderboard_data(ctx, year)
        except AoCInvalidEventError as e:
            await ctx.respond(e, ephemeral=True)
            return
        except MissingLeaderboardDataError:
            return

        leaderboard = self.cached_leaderboards[year]["leaderboard"]
        last_fetched = self.cached_leaderboards[year]["last_fetched"]

        total_members = len(leaderboard["members"])
        daily_stats = [{"star1_count": 0, "star2_count": 0} for _ in range(leaderboard["num_days"])]

        for member in leaderboard["members"].values():
            for day in member["completion_day_level"]:
                if "1" in member["completion_day_level"][day]:
                    daily_stats[int(day) - 1]["star1_count"] += 1
                if "2" in member["completion_day_level"][day]:
                    daily_stats[int(day) - 1]["star2_count"] += 1

        embed = self.make_aoc_stats_embed(daily_stats, total_members, year, last_fetched)

        if deferred:
            await ctx.followup.send(embed=embed)
        else:
            await ctx.respond(embed=embed)


def setup(bot: Bot) -> None:
    bot.add_cog(AOCLeaderboards(bot))
