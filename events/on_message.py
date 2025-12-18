import json
import logging

from discord.ext import commands

logger = logging.getLogger("discord_bot.events")

# Load config
with open("config.json", encoding="utf-8") as f:
    config = json.load(f)

MESSAGES = config.get("messages", {})


class OnMessage(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        # Bỏ qua tin nhắn từ bot
        if message.author.bot:
            return

        # Easter egg: phản hồi "ping"
        if message.content.lower() == "ping":
            await message.channel.send(MESSAGES.get("ping_response", "🏓 Pong!"))

        # Quan trọng: để bot xử lý các command khác
        await self.bot.process_commands(message)


async def setup(bot: commands.Bot):
    await bot.add_cog(OnMessage(bot))
