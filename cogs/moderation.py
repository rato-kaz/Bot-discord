import discord
from discord import app_commands
from discord.ext import commands


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ===================== PREFIX COMMANDS =====================

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: str = "Không có lý do"):
        """Kick một thành viên khỏi server."""
        await member.kick(reason=reason)
        await ctx.send(f"👢 Đã kick {member.mention} vì: {reason}")

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, member: discord.Member, *, reason: str = "Không có lý do"):
        """Ban một thành viên khỏi server."""
        await member.ban(reason=reason)
        await ctx.send(f"🔨 Đã ban {member.mention} vì: {reason}")

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx: commands.Context, user_id: int):
        """Unban một user bằng ID."""
        try:
            user = await self.bot.fetch_user(user_id)
            await ctx.guild.unban(user)
            await ctx.send(f"✅ Đã unban {user.mention}")
        except discord.NotFound:
            await ctx.send("❌ Không tìm thấy user với ID này.")
        except discord.Forbidden:
            await ctx.send("❌ Bot không có quyền unban.")

    # ===================== SLASH COMMANDS =====================

    @app_commands.command(name="kick", description="Kick một thành viên khỏi server")
    @app_commands.describe(member="Thành viên cần kick", reason="Lý do kick")
    @app_commands.default_permissions(kick_members=True)
    async def kick_slash(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "Không có lý do",
    ):
        await member.kick(reason=reason)
        await interaction.response.send_message(f"👢 Đã kick {member.mention} vì: {reason}")

    @app_commands.command(name="ban", description="Ban một thành viên khỏi server")
    @app_commands.describe(member="Thành viên cần ban", reason="Lý do ban")
    @app_commands.default_permissions(ban_members=True)
    async def ban_slash(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "Không có lý do",
    ):
        await member.ban(reason=reason)
        await interaction.response.send_message(f"🔨 Đã ban {member.mention} vì: {reason}")

    @app_commands.command(name="unban", description="Unban một user bằng ID")
    @app_commands.describe(user_id="ID của user cần unban")
    @app_commands.default_permissions(ban_members=True)
    async def unban_slash(self, interaction: discord.Interaction, user_id: str):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user)
            await interaction.response.send_message(f"✅ Đã unban {user.mention}")
        except ValueError:
            await interaction.response.send_message("❌ ID không hợp lệ.", ephemeral=True)
        except discord.NotFound:
            await interaction.response.send_message("❌ Không tìm thấy user với ID này.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Bot không có quyền unban.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
