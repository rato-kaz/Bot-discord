import json
import logging

import discord
from discord.ext import commands

logger = logging.getLogger("discord_bot.events")

# Load config
with open("config.json", encoding="utf-8") as f:
    config = json.load(f)

WELCOME_CHANNEL = config.get("welcome_channel", "general")
MESSAGES = config.get("messages", {})


class OnMemberJoin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # Tìm channel theo tên từ config
        channel = discord.utils.get(member.guild.text_channels, name=WELCOME_CHANNEL)

        if channel:
            welcome_msg = MESSAGES.get("welcome", "Chào mừng {member} đến với {server}!").format(
                member=member.mention,
                server=member.guild.name,
            )
            await channel.send(welcome_msg)
            logger.info("Đã gửi welcome message cho %s trong server %s", member, member.guild.name)
        else:
            logger.warning(
                "Không tìm thấy channel '%s' để gửi lời chào khi %s tham gia %s",
                WELCOME_CHANNEL,
                member,
                member.guild.name,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(OnMemberJoin(bot))
