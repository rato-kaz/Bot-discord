# bot.py

import asyncio
import json
import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# Load config
with open("config.json", encoding="utf-8") as f:
    config = json.load(f)

# Thiết lập logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("discord_bot")

# Khởi tạo bot
intents = discord.Intents.all()
bot = commands.Bot(
    command_prefix=config.get("prefix", "!"),
    intents=intents,
)

# Danh sách cogs và events cần load
INITIAL_COGS = [
    "cogs.moderation",
    "cogs.music",
    "cogs.welcome",
    "cogs.stable_diffusion",
    "cogs.chatbot",
]

EVENTS = [
    "events.on_member_join",
    "events.on_message",
]

MESSAGES = config.get("messages", {})


@bot.event
async def on_ready():
    logger.info("Bot is online as %s", bot.user)

    try:
        synced = await bot.tree.sync()
        logger.info("Đã sync %d slash command(s).", len(synced))
    except Exception as e:
        logger.exception("Lỗi khi sync slash command: %s", e)


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    # Bỏ qua CommandNotFound
    if isinstance(error, commands.CommandNotFound):
        return

    # Xử lý các lỗi phổ biến
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Thiếu tham số: `{error.param.name}`")
        return

    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Bạn không có quyền sử dụng lệnh này.")
        return

    if isinstance(error, commands.BotMissingPermissions):
        await ctx.send("❌ Bot không có quyền để thực hiện lệnh này.")
        return

    if isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Tham số không hợp lệ: {error}")
        return

    # Log lỗi không xác định
    logger.exception(
        "Lỗi khi chạy command %s: %s",
        getattr(ctx.command, "qualified_name", "unknown"),
        error,
    )

    try:
        await ctx.send(MESSAGES.get("error_generic", "❌ Đã xảy ra lỗi. Thử lại sau."))
    except discord.HTTPException:
        pass


async def main():
    async with bot:
        # Load tất cả extensions
        for extension in INITIAL_COGS + EVENTS:
            try:
                await bot.load_extension(extension)
                logger.info("Loaded extension: %s", extension)
            except Exception as e:
                logger.exception("Failed to load extension %s: %s", extension, e)

        # Start bot
        token = os.getenv("BOT_TOKEN")
        if not token:
            logger.error("BOT_TOKEN chưa được cấu hình trong .env!")
            return

        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
