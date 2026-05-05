import asyncio
from discord.ext import commands
import __main__

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
        await ctx.send(round(self.bot.latency * 1000))

    @commands.command()
    async def bomb(self, ctx):
        import __main__

        sem = __main__.bomb_semaphore

        if sem.locked() and sem._value == 0:
            await ctx.send("💣 Too many bombs active right now. Try again soon.")
            return

        async with sem:
            custom_emoji = "<a:SparxieMeme:1485677074093048021>"
            await ctx.send(f"I have planted a bomb some where in this server find it {custom_emoji}")

            for i in range(5, 0, -1):
                await ctx.send(f"{i}...")
                await asyncio.sleep(4) # This pauses the bot for 1 second

            await ctx.send("💥 **BOOM!**")

async def setup(bot):
    await bot.add_cog(Fun(bot))
