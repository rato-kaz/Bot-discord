import asyncio
import json
import logging
import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from utils.database import check_and_use_daily_limit, save_chat_history
from utils.prompts import CHATBOT_SYSTEM_PROMPT

load_dotenv()

logger = logging.getLogger("discord_bot.chatbot")

# Load config
with open("config.json", encoding="utf-8") as f:
    config = json.load(f)

LLM_CONFIG = config.get("llm", {})

# Đọc từ .env
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME")
LLM_KEY = os.getenv("LLM_KEY")
LLM_API = os.getenv("LLM_API")
LLM_VERSION = os.getenv("LLM_VERSION")

# Đọc từ config.json (fallback to prompts.py)
SYSTEM_PROMPT = LLM_CONFIG.get("system_prompt", CHATBOT_SYSTEM_PROMPT)
MAX_TOKENS = LLM_CONFIG.get("max_tokens", 500)
TEMPERATURE = LLM_CONFIG.get("temperature", 0.7)
DAILY_LIMIT = LLM_CONFIG.get("daily_limit", 10)


class ChatBot(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.llm_client = self._init_llm_client()

    def _init_llm_client(self):
        """Khởi tạo Azure OpenAI client từ biến môi trường."""
        if not LLM_KEY:
            logger.warning("LLM_KEY chưa được cấu hình trong .env. Tính năng ChatBot sẽ không hoạt động.")
            return None

        try:
            from openai import AzureOpenAI

            client = AzureOpenAI(
                api_key=LLM_KEY,
                api_version=LLM_VERSION,
                azure_endpoint=LLM_API,
            )
            logger.info(
                "Đã khởi tạo Azure OpenAI client (model: %s, endpoint: %s)",
                LLM_MODEL_NAME,
                LLM_API,
            )
            return client

        except Exception as e:
            logger.error("Không thể khởi tạo LLM client: %s", e)
            return None

    def _check_rate_limit(self, user_id: int) -> tuple[bool, str]:
        """
        Kiểm tra rate limit của user.
        Trả về (allowed, message).
        """
        allowed, current, limit = check_and_use_daily_limit(user_id, DAILY_LIMIT)

        if not allowed:
            return False, f"⚠️ Bạn đã hết giới hạn {limit} câu hỏi/ngày. Vui lòng quay lại vào ngày mai!"

        remaining = limit - current
        return True, f"📊 Còn lại: {remaining}/{limit} câu hỏi hôm nay"

    async def _ask_llm(self, prompt: str) -> str:
        """
        Gọi Azure OpenAI API.
        Chạy trong thread riêng để không block event loop.
        """
        if not self.llm_client:
            raise Exception("LLM client chưa được khởi tạo. Kiểm tra LLM_KEY trong .env.")

        def _request():
            response = self.llm_client.chat.completions.create(
                model=LLM_MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
            )
            return response.choices[0].message.content

        return await asyncio.to_thread(_request)

    # ===================== SLASH COMMAND =====================

    @app_commands.command(name="ask", description="Gửi câu hỏi cho trợ lý AI")
    @app_commands.describe(prompt="Câu hỏi hoặc yêu cầu của bạn")
    async def ask(self, interaction: discord.Interaction, prompt: str):
        # Kiểm tra rate limit
        allowed, limit_msg = self._check_rate_limit(interaction.user.id)
        if not allowed:
            await interaction.response.send_message(limit_msg, ephemeral=True)
            return

        await interaction.response.defer(thinking=True)

        try:
            reply = await self._ask_llm(prompt)

            # Lưu lịch sử vào DB
            save_chat_history(
                user_id=interaction.user.id,
                guild_id=interaction.guild.id if interaction.guild else None,
                prompt=prompt,
                response=reply,
            )

            # Thêm thông tin còn lại vào cuối reply
            full_reply = f"{reply}\n\n─────────────────\n{limit_msg}"

            # Nếu reply quá dài, chia nhỏ
            if len(full_reply) > 2000:
                # Gửi reply trước
                for i in range(0, len(reply), 2000):
                    if i == 0:
                        await interaction.followup.send(reply[i:i+2000])
                    else:
                        await interaction.channel.send(reply[i:i+2000])
                # Gửi limit info riêng
                await interaction.channel.send(f"─────────────────\n{limit_msg}")
            else:
                await interaction.followup.send(full_reply)

        except Exception as e:
            logger.exception("Lỗi khi gọi LLM API: %s", e)
            await interaction.followup.send(f"❌ Lỗi khi gọi LLM API: `{e}`")

    # ===================== PREFIX COMMAND =====================

    @commands.command(name="ask", help="Gửi câu hỏi cho trợ lý AI")
    async def ask_prefix(self, ctx: commands.Context, *, prompt: str):
        # Kiểm tra rate limit
        allowed, limit_msg = self._check_rate_limit(ctx.author.id)
        if not allowed:
            await ctx.send(limit_msg)
            return

        async with ctx.typing():
            try:
                reply = await self._ask_llm(prompt)

                save_chat_history(
                    user_id=ctx.author.id,
                    guild_id=ctx.guild.id if ctx.guild else None,
                    prompt=prompt,
                    response=reply,
                )

                full_reply = f"{reply}\n\n─────────────────\n{limit_msg}"

                if len(full_reply) > 2000:
                    for i in range(0, len(reply), 2000):
                        await ctx.send(reply[i:i+2000])
                    await ctx.send(f"─────────────────\n{limit_msg}")
                else:
                    await ctx.send(full_reply)

            except Exception as e:
                logger.exception("Lỗi khi gọi LLM API: %s", e)
                await ctx.send(f"❌ Lỗi khi gọi LLM API: `{e}`")

    # ===================== CHECK USAGE COMMAND =====================

    @app_commands.command(name="usage", description="Xem số lượt hỏi còn lại hôm nay")
    async def usage_slash(self, interaction: discord.Interaction):
        from utils.database import get_daily_usage
        current = get_daily_usage(interaction.user.id)
        remaining = max(0, DAILY_LIMIT - current)
        await interaction.response.send_message(
            f"📊 **Thống kê sử dụng AI hôm nay**\n"
            f"• Đã dùng: {current}/{DAILY_LIMIT}\n"
            f"• Còn lại: {remaining} câu hỏi",
            ephemeral=True,
        )

    @commands.command(name="usage", help="Xem số lượt hỏi còn lại hôm nay")
    async def usage_prefix(self, ctx: commands.Context):
        from utils.database import get_daily_usage
        current = get_daily_usage(ctx.author.id)
        remaining = max(0, DAILY_LIMIT - current)
        await ctx.send(
            f"📊 **Thống kê sử dụng AI hôm nay**\n"
            f"• Đã dùng: {current}/{DAILY_LIMIT}\n"
            f"• Còn lại: {remaining} câu hỏi"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ChatBot(bot))
