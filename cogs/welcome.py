import discord
from discord import app_commands
from discord.ext import commands


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="hello")
    async def hello(self, ctx: commands.Context):
        """Chào bạn từ bot."""
        await ctx.send(f"👋 Chào {ctx.author.mention}!")

    @app_commands.command(name="hello", description="Chào bạn từ bot")
    async def hello_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"👋 Chào {interaction.user.mention}!")


async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))
