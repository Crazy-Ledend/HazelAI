import discord
from discord.ext import commands
from discord.ext.commands import Context, HybridCommand

class LogView(discord.ui.View):
    def __init__(self, pages, author):
        super().__init__(timeout=60)
        self.pages = pages
        self.current = 0
        self.author = author

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("Only the command user can use these buttons.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.blurple)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current > 0:
            self.current -= 1
            await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.blurple)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current < len(self.pages) - 1:
            self.current += 1
            await interaction.response.edit_message(embed=self.pages[self.current], view=self)


class LogCog(commands.Cog):
    def __init__(self, bot: commands.Bot, cursor):
        self.bot = bot
        self.cursor = cursor

    @commands.hybrid_command(name="logs", description="View chat logs. Use without arguments to view all.")
    @commands.is_owner()
    async def logs(self, ctx: Context, user_id: str = None):
        if user_id:
            self.cursor.execute("SELECT role, content FROM history WHERE user_id = ?", (user_id,))
        else:
            self.cursor.execute("SELECT user_id, role, content FROM history")

        rows = self.cursor.fetchall()
        if not rows:
            await ctx.send("No logs found.")
            return

        entries = []
        if user_id:
            for role, content in rows:
                entries.append(f"**{role.capitalize()}**: {content}")
        else:
            for uid, role, content in rows:
                entries.append(f"**{uid}** | **{role.capitalize()}**: {content}")

        # Paginate entries
        pages = []
        chunk = ""
        for entry in entries:
            if len(chunk) + len(entry) > 4000:  # Embed limit buffer
                embed = discord.Embed(
                    title="User Logs" if user_id else "All Logs",
                    description=chunk,
                    color=discord.Color.blurple()
                )
                pages.append(embed)
                chunk = ""
            chunk += entry + "\n\n"

        if chunk:
            embed = discord.Embed(
                title="User Logs" if user_id else "All Logs",
                description=chunk,
                color=discord.Color.blurple()
            )
            pages.append(embed)

        if len(pages) == 1:
            await ctx.send(embed=pages[0])
        else:
            view = LogView(pages, ctx.author)
            send_method = (
                ctx.respond if ctx.interaction else ctx.send  # Slash vs prefix
            )
            await send_method(embed=pages[0], view=view)
            self.bot.last_log_view = view  # Prevent garbage collection


async def setup(bot: commands.Bot):
    await bot.add_cog(LogCog(bot, bot.cursor))
