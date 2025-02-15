import discord
from discord.ext.pages import Paginator as PycordPaginator


class Paginator(PycordPaginator):
    async def channel_send(
        self,
        channel: discord.abc.Messageable,
        delete_after: float | None = None,
    ) -> discord.Message:
        """Sends a paginator to a specified channel without requiring a user
        interaction.

        The default Pycord Paginator requires a command invocation context to
        respond to, which isn't available in cases where the paginator is sent
        automatically.
        """
        if not isinstance(channel, discord.abc.Messageable):
            raise TypeError(f"expected abc.Messageable not {channel.__class__!r}")

        self.update_buttons()
        page = self.pages[self.current_page]
        page_content = self.get_page_content(page)

        if page_content.custom_view:
            self.update_custom_view(page_content.custom_view)

        self.message = await channel.send(
            content=page_content.content,
            embeds=page_content.embeds,
            files=page_content.files,
            view=self,
            delete_after=delete_after,
        )

        return self.message
