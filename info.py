import discord
import time
from datetime import timedelta
from discord.ext import commands

class info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="servers", description="Displays the servers with Muffins!")
    async def servers(self, ctx):
        embed = discord.Embed(title=f"Muffins in!",color=discord.Colour(0x2776ea))
        embed.add_field(name=f"", value = f"Muffins is currently in `{len(ctx.bot.guilds)}` servers", inline=False)
        for guild in ctx.bot.guilds:
            embed.add_field(name=f"", value = f"<:point:1361022159656325351> **{guild.name}** - [members: `{guild.member_count}`]", inline=False)
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="info", description="Displays the basic information about Muffins")
    async def info(self, ctx):
        embed = discord.Embed(title=f"Statistics",color=discord.Colour(0x2776ea))
        embed.add_field(name=f"<:details:1361035027944701994> __Details__", value = f"<:d3:1361034825460613251> **Owner:** crazypokeking\n<:d1:1361034777171591288> \n<:d3:1361034825460613251> **Dev Team:** HazelTech 🦕\n<:d1:1361034777171591288> \n<:d3:1361034825460613251> **Developers:** crazypokeking\n<:d1:1361034777171591288> \n<:d3:1361034825460613251> **Web Developer:** crazypokeking\n<:d1:1361034777171591288> \n<:d3:1361034825460613251> **Dev. Helpers:** --\n<:d1:1361034777171591288> \n<:d3:1361034825460613251> **Server count:** `{len(ctx.bot.guilds)}`\n<:d1:1361034777171591288> \n<:d2:1361034803113230448> **Discord Version:** `{discord.__version__}`", inline=False)
        embed.add_field(name=f"<:links:1361035040250663103> __Links__", value = f"<a:dev:1361208894919282770> | crazypokeking \n\n \
<a:Discord:1361208933082988664> | https://discord.gg/WxvEhxG5Q5 \n\n \
<:website:1361208909133774919> | https://crazy-ledend.github.io/Hazelnut-web/ \n", inline=False)
        embed.add_field(name=f"<:bot:1361027932914716692> __Other Bots__ \n", value = f"\n<:hazelnut:1361041369757515898> | Hazelnut | [Invite here!](https://discord.com/api/oauth2/authorize?client_id=1295047885494292502&permissions=581566992346705&scope=bot%20applications.commands)", inline=False)
        await ctx.send(embed=embed)
    # Store the bot's start time
    start_time = time.time()

    @commands.hybrid_command(name="ping", description="Pongs the Latency!")
    async def ping(self, ctx):
        latency = round(self.bot.latency * 1000) # milliseconds
        await ctx.send(f"Pong! Latency is `{latency}`ms")

    @commands.hybrid_command(name="uptime", description="I wonder how long the bot's been online?'")
    async def uptime(self, ctx):
        uptime_duration = timedelta(seconds=int(time.time() - self.start_time))
        await ctx.send(f"I'm online for: `{uptime_duration}`")

        
async def setup(bot):
    await bot.tree.sync()
    await bot.add_cog(info(bot))
