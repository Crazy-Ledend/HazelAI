import discord
from discord.ext import commands, tasks


class Presence(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.status_index = 0
        self.statuses = [
            discord.Game("with your memory 🧠"),
            discord.Activity(type=discord.ActivityType.listening, name="Fairytale ☁️"),
            discord.Activity(type=discord.ActivityType.listening, name="Die with a smile! 💖"),
            discord.Activity(type=discord.ActivityType.listening, name="Perfect 👌🏼"),
            discord.Activity(type=discord.ActivityType.watching, name="AI Magic ✨"),
            discord.Activity(type=discord.ActivityType.watching, name="Shin-chan 🖍️")
        ]
        self.update_presence.start()

    def cog_unload(self):
        self.update_presence.cancel()

    @tasks.loop(seconds=30)
    async def update_presence(self):
        current_status = self.statuses[self.status_index % len(self.statuses)]
        await self.bot.change_presence(activity=current_status, status=discord.Status.online)
        self.status_index += 1

    @update_presence.before_loop
    async def before_presence(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Presence(bot))
