import asyncio
import json
import logging
import os
from io import BytesIO

import discord
from discord import app_commands
from discord.ext import commands

from utils.database import save_chat_history

logger = logging.getLogger("discord_bot.stable_diffusion")

# Load config
with open("config.json", encoding="utf-8") as f:
    config = json.load(f)

HF_CONFIG = config.get("huggingface", {})
HF_API_URL = HF_CONFIG.get("model_url", "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0")
HF_TIMEOUT = HF_CONFIG.get("timeout", 60)


def _get_hf_headers() -> dict:
    """Lấy headers cho HuggingFace API. Gọi runtime để đảm bảo env đã load."""
    api_key = os.getenv("HF_API_KEY")
    if not api_key:
        logger.warning("HF_API_KEY chưa được cấu hình!")
    return {"Authorization": f"Bearer {api_key or ''}"}


class StableDiffusion(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _generate_image(self, prompt: str) -> bytes | None:
        """
        Gọi HuggingFace API để generate ảnh.
        Chạy trong thread riêng để không block event loop.
        """
        import requests

        def _request():
            response = requests.post(
                HF_API_URL,
                headers=_get_hf_headers(),
                json={"inputs": prompt},
                timeout=HF_TIMEOUT,
            )
            if response.status_code != 200:
                raise Exception(f"API Error {response.status_code}: {response.text}")
            if not response.content:
                raise Exception("Không nhận được dữ liệu ảnh từ API")
            return response.content

        return await asyncio.to_thread(_request)

    async def _imagine_logic(
        self,
        prompt: str,
        user_id: int,
        guild_id: int | None,
        send_initial,
        send_result,
        edit_initial,
        delete_initial,
    ):
        """
        Logic chung cho cả prefix và slash command.
        """
        await send_initial(f"🎨 Đang tạo ảnh cho prompt: `{prompt}` ... Vui lòng chờ!")

        try:
            image_bytes = await self._generate_image(prompt)

            buffer = BytesIO(image_bytes)
            file = discord.File(fp=buffer, filename="stable_diffusion_result.png")
            msg = await send_result(f"✅ Ảnh được tạo với prompt: `{prompt}`", file=file)

            # Lưu vào DB (không crash nếu lỗi)
            save_chat_history(
                user_id=user_id,
                guild_id=guild_id,
                prompt=prompt,
                response=f"StableDiffusion image message_id={msg.id if msg else 'unknown'}",
            )

            await delete_initial()

        except asyncio.TimeoutError:
            await edit_initial("❌ Lỗi: API timeout - thời gian chờ quá lâu")
        except Exception as e:
            logger.exception("Lỗi khi generate ảnh: %s", e)
            await edit_initial(f"❌ Lỗi: {e}")

    # ===================== PREFIX COMMAND =====================

    @commands.command(name="imagine", help="Tạo ảnh từ prompt bằng Stable Diffusion XL")
    async def imagine(self, ctx: commands.Context, *, prompt: str):
        initial_msg = None

        async def send_initial(content: str):
            nonlocal initial_msg
            initial_msg = await ctx.send(content)

        async def send_result(content: str, file: discord.File):
            return await ctx.send(content, file=file)

        async def edit_initial(content: str):
            if initial_msg:
                await initial_msg.edit(content=content)

        async def delete_initial():
            if initial_msg:
                try:
                    await initial_msg.delete()
                except discord.HTTPException:
                    pass

        await self._imagine_logic(
            prompt=prompt,
            user_id=ctx.author.id,
            guild_id=ctx.guild.id if ctx.guild else None,
            send_initial=send_initial,
            send_result=send_result,
            edit_initial=edit_initial,
            delete_initial=delete_initial,
        )

    # ===================== SLASH COMMAND =====================

    @app_commands.command(name="imagine", description="Tạo ảnh từ prompt bằng Stable Diffusion XL")
    @app_commands.describe(prompt="Mô tả ảnh bạn muốn tạo")
    async def imagine_slash(self, interaction: discord.Interaction, prompt: str):
        await interaction.response.send_message(
            f"🎨 Đang tạo ảnh cho prompt: `{prompt}` ... Vui lòng chờ!"
        )

        try:
            image_bytes = await self._generate_image(prompt)

            buffer = BytesIO(image_bytes)
            file = discord.File(fp=buffer, filename="stable_diffusion_result.png")
            msg = await interaction.followup.send(f"✅ Ảnh được tạo với prompt: `{prompt}`", file=file)

            save_chat_history(
                user_id=interaction.user.id,
                guild_id=interaction.guild.id if interaction.guild else None,
                prompt=prompt,
                response=f"StableDiffusion image message_id={msg.id if msg else 'unknown'}",
            )

        except asyncio.TimeoutError:
            await interaction.followup.send("❌ Lỗi: API timeout - thời gian chờ quá lâu")
        except Exception as e:
            logger.exception("Lỗi khi generate ảnh (slash): %s", e)
            await interaction.followup.send(f"❌ Lỗi: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(StableDiffusion(bot))
