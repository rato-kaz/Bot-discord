# cogs/riddle_game.py
"""
AI Riddle Master - Minigame đoán hình ảnh bí mật
Kiến trúc: Hybrid AI (VLM Local cho mô tả + Cloud LLM cho gợi ý)

TÍNH NĂNG:
- Tạo kênh chat tạm thời riêng cho mỗi người chơi
- Lock/Unlock chat khi bot đang xử lý AI
- Tự động xóa kênh sau khi game kết thúc
"""

import asyncio
import json
import logging
import os
import random
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from utils.prompts import RIDDLE_MASTER_PROMPT, LLM_ROUTER_PROMPT

load_dotenv()

logger = logging.getLogger("discord_bot.riddle_game")

# Load config
with open("config.json", encoding="utf-8") as f:
    config = json.load(f)

LLM_CONFIG = config.get("llm", {})

# Đọc từ .env
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME")
LLM_KEY = os.getenv("LLM_KEY")
LLM_API = os.getenv("LLM_API")
LLM_VERSION = os.getenv("LLM_VERSION")

# Đường dẫn data
GAME_DATA_PATH = "data/riddle/game_data.json"
IMAGES_PATH = "assets/riddle_images"

# Prefix cho tên kênh game
CHANNEL_PREFIX = "riddle-"

# Thời gian chờ trước khi xóa kênh (giây)
CHANNEL_DELETE_DELAY = 30


class RiddleSession:
    """Lưu trữ trạng thái game của mỗi người chơi."""

    def __init__(self, riddle_data: dict, channel_id: int, user_id: int):
        self.riddle_id = riddle_data["id"]
        self.filename = riddle_data["filename"]
        self.answers = [ans.lower().strip() for ans in riddle_data["answers"]]
        self.blind_description = riddle_data["blind_description"]
        self.topic = riddle_data.get("topic", "Bí mật")  # Chủ đề gợi ý
        self.hints_asked = 0
        self.guesses = 0
        self.channel_id = channel_id
        self.user_id = user_id
        self.is_locked = False  # Trạng thái lock chat

    def check_answer(self, user_answer: str) -> bool:
        """Kiểm tra đáp án với fuzzy matching đơn giản."""
        user_answer = user_answer.lower().strip()

        # Kiểm tra chính xác
        if user_answer in self.answers:
            return True

        # Fuzzy matching: kiểm tra nếu đáp án chứa trong câu trả lời hoặc ngược lại
        for ans in self.answers:
            if ans in user_answer or user_answer in ans:
                return True
            # Bỏ dấu và so sánh (đơn giản)
            if self._remove_accents(ans) == self._remove_accents(user_answer):
                return True

        return False

    @staticmethod
    def _remove_accents(text: str) -> str:
        """Loại bỏ dấu tiếng Việt (đơn giản)."""
        accents = {
            "à": "a", "á": "a", "ả": "a", "ã": "a", "ạ": "a",
            "ă": "a", "ằ": "a", "ắ": "a", "ẳ": "a", "ẵ": "a", "ặ": "a",
            "â": "a", "ầ": "a", "ấ": "a", "ẩ": "a", "ẫ": "a", "ậ": "a",
            "è": "e", "é": "e", "ẻ": "e", "ẽ": "e", "ẹ": "e",
            "ê": "e", "ề": "e", "ế": "e", "ể": "e", "ễ": "e", "ệ": "e",
            "ì": "i", "í": "i", "ỉ": "i", "ĩ": "i", "ị": "i",
            "ò": "o", "ó": "o", "ỏ": "o", "õ": "o", "ọ": "o",
            "ô": "o", "ồ": "o", "ố": "o", "ổ": "o", "ỗ": "o", "ộ": "o",
            "ơ": "o", "ờ": "o", "ớ": "o", "ở": "o", "ỡ": "o", "ợ": "o",
            "ù": "u", "ú": "u", "ủ": "u", "ũ": "u", "ụ": "u",
            "ư": "u", "ừ": "u", "ứ": "u", "ử": "u", "ữ": "u", "ự": "u",
            "ỳ": "y", "ý": "y", "ỷ": "y", "ỹ": "y", "ỵ": "y",
            "đ": "d",
        }
        result = ""
        for char in text:
            result += accents.get(char, char)
        return result


class RiddleGame(commands.Cog):
    """Cog quản lý game đoán hình Riddle Master."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.llm_client = self._init_llm_client()
        self.game_data = self._load_game_data()
        # Dict lưu session game: {channel_id: RiddleSession}
        self.active_sessions: dict[int, RiddleSession] = {}
        # Dict mapping user_id -> channel_id (để check user đang chơi ở kênh nào)
        self.user_channels: dict[int, int] = {}

    def _init_llm_client(self):
        """Khởi tạo Azure OpenAI client."""
        if not LLM_KEY:
            logger.warning("LLM_KEY chưa được cấu hình. Riddle Game sẽ không hoạt động.")
            return None

        try:
            from openai import AzureOpenAI

            client = AzureOpenAI(
                api_key=LLM_KEY,
                api_version=LLM_VERSION,
                azure_endpoint=LLM_API,
            )
            logger.info("Riddle Game: Đã khởi tạo LLM client.")
            return client
        except Exception as e:
            logger.error("Riddle Game: Không thể khởi tạo LLM client: %s", e)
            return None

    def _load_game_data(self) -> list[dict]:
        """Load dữ liệu game từ JSON."""
        try:
            with open(GAME_DATA_PATH, encoding="utf-8") as f:
                data = json.load(f)
                logger.info("Riddle Game: Đã load %d câu đố.", len(data))
                return data
        except FileNotFoundError:
            logger.warning("Riddle Game: Không tìm thấy file %s", GAME_DATA_PATH)
            return []
        except Exception as e:
            logger.error("Riddle Game: Lỗi khi load game data: %s", e)
            return []

    def _get_random_riddle(self) -> Optional[dict]:
        """Lấy ngẫu nhiên một câu đố."""
        if not self.game_data:
            return None
        return random.choice(self.game_data)

    # ==================== PERMISSION HELPERS ====================

    async def _lock_channel(self, channel: discord.TextChannel, user: discord.Member):
        """
        LOCK: Chặn user gửi tin nhắn trong kênh.
        Gọi khi bot đang xử lý AI.
        """
        try:
            await channel.set_permissions(user, send_messages=False)
            logger.debug("Riddle: Đã LOCK kênh %s cho user %s", channel.name, user.name)
        except Exception as e:
            logger.error("Riddle: Lỗi khi lock kênh: %s", e)

    async def _unlock_channel(self, channel: discord.TextChannel, user: discord.Member):
        """
        UNLOCK: Cho phép user gửi tin nhắn trong kênh.
        Gọi sau khi bot trả lời xong.
        """
        try:
            await channel.set_permissions(user, send_messages=True, view_channel=True)
            logger.debug("Riddle: Đã UNLOCK kênh %s cho user %s", channel.name, user.name)
        except Exception as e:
            logger.error("Riddle: Lỗi khi unlock kênh: %s", e)

    async def _create_game_channel(
        self, guild: discord.Guild, user: discord.Member
    ) -> Optional[discord.TextChannel]:
        """
        Tạo kênh game tạm thời với permission overwrites:
        - @everyone: View = True, Send = False (chỉ xem, không chat)
        - User (người chơi): View = True, Send = True
        - Bot: View = True, Send = True
        """
        channel_name = f"{CHANNEL_PREFIX}{user.name.lower().replace(' ', '-')}-{user.id % 1000}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=False,
                add_reactions=False,
            ),
            user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                manage_messages=True,
            ),
        }

        try:
            channel = await guild.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                topic=f"🎭 Riddle Game - Người chơi: {user.display_name}",
                reason=f"Riddle Game cho {user.name}",
            )
            logger.info("Riddle: Đã tạo kênh game %s cho user %s", channel.name, user.name)
            return channel
        except Exception as e:
            logger.error("Riddle: Không thể tạo kênh game: %s", e)
            return None

    async def _delete_game_channel(self, channel: discord.TextChannel, delay: int = CHANNEL_DELETE_DELAY):
        """Xóa kênh game sau một khoảng thời gian."""
        try:
            await channel.send(f"⏳ Kênh này sẽ bị xóa sau **{delay} giây**...")
            await asyncio.sleep(delay)
            await channel.delete(reason="Riddle Game kết thúc")
            logger.info("Riddle: Đã xóa kênh game %s", channel.name)
        except Exception as e:
            logger.error("Riddle: Lỗi khi xóa kênh game: %s", e)

    # ==================== AI HELPER ====================

    async def _ask_riddle_master(self, session: RiddleSession, question: str) -> str:
        """Gọi LLM để lấy gợi ý."""
        if not self.llm_client:
            return "❌ Hệ thống AI chưa sẵn sàng. Vui lòng thử lại sau!"

        system_prompt = RIDDLE_MASTER_PROMPT.format(
            blind_description=session.blind_description
        )

        def _request():
            response = self.llm_client.chat.completions.create(
                model=LLM_MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question},
                ],
                max_tokens=150,
                temperature=0.8,
            )
            return response.choices[0].message.content

        try:
            return await asyncio.to_thread(_request)
        except Exception as e:
            logger.error("Riddle Game: Lỗi khi gọi LLM: %s", e)
            return "❌ Có lỗi xảy ra khi xử lý. Vui lòng thử lại!"

    # ==================== GAME LOGIC ====================

    async def _classify_message(self, user_message: str, target_word: str) -> dict:
        """
        Sử dụng LLM Router để phân loại tin nhắn người chơi.
        
        Returns:
            dict: {"type": "GUESS_CORRECT|GUESS_WRONG|QUESTION|GIVE_UP", "reason": "..."}
        """
        if not self.llm_client:
            # Fallback: phân loại đơn giản nếu không có LLM
            return self._fallback_classify(user_message, target_word)
        
        prompt = LLM_ROUTER_PROMPT.format(
            user_message=user_message,
            target_word=target_word
        )
        
        def _request():
            response = self.llm_client.chat.completions.create(
                model=LLM_MODEL_NAME,
                messages=[
                    {"role": "system", "content": prompt},
                ],
                max_tokens=100,
                temperature=0.1,  # Low temperature cho task classification
            )
            return response.choices[0].message.content
        
        try:
            result = await asyncio.to_thread(_request)
            # Parse JSON response
            result = result.strip()
            # Xử lý trường hợp LLM trả về markdown code block
            if result.startswith("```"):
                result = result.split("```")[1]
                if result.startswith("json"):
                    result = result[4:]
                result = result.strip()
            
            parsed = json.loads(result)
            logger.debug("LLM Router: %s -> %s", user_message[:30], parsed)
            return parsed
        
        except json.JSONDecodeError as e:
            logger.warning("LLM Router: Không parse được JSON: %s - %s", result, e)
            return self._fallback_classify(user_message, target_word)
        except Exception as e:
            logger.error("LLM Router: Lỗi khi gọi API: %s", e)
            return self._fallback_classify(user_message, target_word)
    
    def _fallback_classify(self, user_message: str, target_word: str) -> dict:
        """
        Phân loại đơn giản (fallback) khi LLM không khả dụng.
        """
        message = user_message.lower().strip()
        target = target_word.lower().strip()
        
        # Check give up
        give_up_keywords = ["bỏ cuộc", "đầu hàng", "thua", "give up", "!give_up", "không chơi"]
        for kw in give_up_keywords:
            if kw in message:
                return {"type": "GIVE_UP", "reason": "Phát hiện từ khóa bỏ cuộc"}
        
        # Check correct guess (đơn giản)
        if target in message or message in target:
            return {"type": "GUESS_CORRECT", "reason": "Đáp án khớp"}
        
        # Check question (có dấu ?)
        if "?" in message:
            return {"type": "QUESTION", "reason": "Có dấu hỏi"}
        
        # Default: coi là đoán sai
        return {"type": "GUESS_WRONG", "reason": "Mặc định"}

    async def _handle_guess_correct(self, message: discord.Message, session: RiddleSession):
        """Xử lý khi người chơi đoán ĐÚNG đáp án."""
        session.guesses += 1
        
        embed = discord.Embed(
            title="🎉 CHÍNH XÁC!",
            description=(
                f"**Đáp án:** {session.answers[0].upper()}\n\n"
                f"📊 **Thống kê:**\n"
                f"• Số câu hỏi gợi ý: {session.hints_asked}\n"
                f"• Số lần đoán: {session.guesses}"
            ),
            color=discord.Color.green(),
        )

        # Gửi ảnh nếu có
        image_path = os.path.join(IMAGES_PATH, session.filename)
        if os.path.exists(image_path):
            file = discord.File(image_path, filename=session.filename)
            embed.set_image(url=f"attachment://{session.filename}")
            await message.channel.send(embed=embed, file=file)
        else:
            await message.channel.send(embed=embed)

        # Cleanup session
        await self._end_game(message.channel, session)

    async def _handle_guess_wrong(self, message: discord.Message, session: RiddleSession):
        """Xử lý khi người chơi đoán SAI đáp án."""
        session.guesses += 1
        user_answer = message.content.strip()
        
        await message.channel.send(
            f"❌ **\"{user_answer}\"** không phải đáp án. Thử lại hoặc hỏi thêm gợi ý nhé!"
        )

    async def _handle_question_unlocked(self, message: discord.Message, session: RiddleSession):
        """
        Xử lý khi người chơi hỏi gợi ý.
        Lưu ý: Hàm này được gọi khi kênh đã bị LOCK từ on_message.
        """
        channel = message.channel

        try:
            # Gọi AI RiddleMaster
            session.hints_asked += 1
            hint = await self._ask_riddle_master(session, message.content)

            # Gửi câu trả lời
            embed = discord.Embed(
                title="🎭 RiddleMaster:",
                description=hint,
                color=discord.Color.blue(),
            )
            embed.set_footer(text=f"Câu hỏi #{session.hints_asked}")
            await channel.send(embed=embed)

        except Exception as e:
            logger.error("Riddle: Lỗi xử lý câu hỏi: %s", e)
            await channel.send("❌ Có lỗi xảy ra khi trả lời. Vui lòng thử lại!")

    async def _end_game(self, channel: discord.TextChannel, session: RiddleSession):
        """Kết thúc game và cleanup."""
        user_id = session.user_id
        channel_id = session.channel_id

        # Xóa session
        if channel_id in self.active_sessions:
            del self.active_sessions[channel_id]
        if user_id in self.user_channels:
            del self.user_channels[user_id]

        # Xóa kênh sau delay
        asyncio.create_task(self._delete_game_channel(channel))

    # ==================== SLASH COMMANDS ====================

    @app_commands.command(name="riddle", description="🎭 Bắt đầu game đoán hình bí mật!")
    async def riddle_start(self, interaction: discord.Interaction):
        """Bắt đầu một game mới - Tạo kênh riêng cho người chơi."""
        user = interaction.user
        guild = interaction.guild

        if not guild:
            await interaction.response.send_message(
                "❌ Lệnh này chỉ dùng được trong server!", ephemeral=True
            )
            return

        # Kiểm tra nếu user đang có game
        if user.id in self.user_channels:
            existing_channel_id = self.user_channels[user.id]
            await interaction.response.send_message(
                f"⚠️ Bạn đang có game chưa hoàn thành ở <#{existing_channel_id}>!\n"
                "Hãy hoàn thành hoặc dùng `!give_up` để bỏ cuộc.",
                ephemeral=True,
            )
            return

        # Lấy câu đố ngẫu nhiên
        riddle = self._get_random_riddle()
        if not riddle:
            await interaction.response.send_message(
                "❌ Chưa có dữ liệu câu đố. Vui lòng liên hệ admin!", ephemeral=True
            )
            return

        await interaction.response.defer()

        # Tạo kênh game
        channel = await self._create_game_channel(guild, user)
        if not channel:
            await interaction.followup.send(
                "❌ Không thể tạo kênh game. Vui lòng liên hệ admin!", ephemeral=True
            )
            return

        # Tạo session
        session = RiddleSession(riddle, channel.id, user.id)
        self.active_sessions[channel.id] = session
        self.user_channels[user.id] = channel.id

        # Gửi thông báo ở kênh gốc
        await interaction.followup.send(
            f"🎭 **Game đã bắt đầu!** Vào kênh {channel.mention} để chơi nhé!"
        )

        # Gửi welcome message trong kênh game
        embed = discord.Embed(
            title="🎭 AI RIDDLE MASTER",
            description=(
                f"**Chào mừng {user.mention} đến với trò chơi!**\n\n"
                f"🏷️ **Chủ đề gợi ý:** `{session.topic}`\n\n"
                "📌 **Cách chơi:**\n"
                "• Gõ **câu hỏi** để hỏi gợi ý (VD: `Nó có màu gì?`)\n"
                "• Gõ **đáp án** để đoán (VD: `cá heo`)\n"
                "• Gõ `!give_up` nếu muốn bỏ cuộc\n\n"
                "🎯 **Hãy bắt đầu hỏi nhé!**"
            ),
            color=discord.Color.purple(),
        )
        embed.set_footer(text="💡 Mẹo: AI sẽ tự động nhận biết bạn đang hỏi hay đoán!")
        await channel.send(embed=embed)

    @app_commands.command(name="riddle_reload", description="🔄 Reload dữ liệu câu đố (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def riddle_reload(self, interaction: discord.Interaction):
        """Reload dữ liệu game từ JSON (Admin only)."""
        self.game_data = self._load_game_data()
        await interaction.response.send_message(
            f"✅ Đã reload {len(self.game_data)} câu đố!", ephemeral=True
        )

    # ==================== EVENT LISTENER ====================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Xử lý tin nhắn trong kênh riddle.
        Check 1: Có phải kênh riddle không?
        Check 2: Có phải người chơi của kênh đó không?
        Check 3: Phân loại ý định (Hỏi hay Đoán)
        """
        # Bỏ qua tin nhắn từ bot
        if message.author.bot:
            return

        # Check 1: Có phải kênh riddle không?
        channel = message.channel
        if not isinstance(channel, discord.TextChannel):
            return
        if not channel.name.startswith(CHANNEL_PREFIX):
            return

        # Lấy session từ channel_id
        session = self.active_sessions.get(channel.id)
        if not session:
            return

        # Check 2: Có phải người chơi của kênh đó không?
        if message.author.id != session.user_id:
            await message.delete()
            return

        # Check: Session có đang bị lock không?
        if session.is_locked:
            await message.delete()
            return

        user_input = message.content.strip()
        
        # LOCK kênh trước khi xử lý (vì cần gọi LLM Router)
        session.is_locked = True
        await self._lock_channel(channel, message.author)
        
        # Gửi indicator đang xử lý
        thinking_msg = await channel.send("🤔 *Đang xử lý...*")
        
        try:
            # Gọi LLM Router để phân loại tin nhắn
            classification = await self._classify_message(
                user_message=user_input,
                target_word=session.answers[0]  # Đáp án chính
            )
            
            msg_type = classification.get("type", "QUESTION")
            
            # Xóa indicator
            await thinking_msg.delete()
            
            # Xử lý theo loại tin nhắn
            if msg_type == "GUESS_CORRECT":
                await self._handle_guess_correct(message, session)
            
            elif msg_type == "GUESS_WRONG":
                await self._handle_guess_wrong(message, session)
            
            elif msg_type == "GIVE_UP":
                await self._handle_give_up(message, session)
            
            elif msg_type == "QUESTION":
                # Hỏi gợi ý - Gọi RiddleMaster
                await self._handle_question_unlocked(message, session)
            
            else:
                # Fallback: coi như câu hỏi
                await self._handle_question_unlocked(message, session)
        
        except Exception as e:
            logger.error("Riddle: Lỗi xử lý tin nhắn: %s", e)
            await thinking_msg.edit(content="❌ Có lỗi xảy ra. Vui lòng thử lại!")
        
        finally:
            # UNLOCK kênh sau khi xử lý xong
            session.is_locked = False
            await self._unlock_channel(channel, message.author)

    async def _handle_give_up(self, message: discord.Message, session: RiddleSession):
        """Xử lý khi người chơi bỏ cuộc."""
        embed = discord.Embed(
            title="🏳️ Bạn đã bỏ cuộc!",
            description=(
                f"**Đáp án là:** {session.answers[0].upper()}\n\n"
                f"📊 **Thống kê:**\n"
                f"• Số câu hỏi đã hỏi: {session.hints_asked}\n"
                f"• Số lần đoán: {session.guesses}"
            ),
            color=discord.Color.orange(),
        )

        # Gửi ảnh nếu có
        image_path = os.path.join(IMAGES_PATH, session.filename)
        if os.path.exists(image_path):
            file = discord.File(image_path, filename=session.filename)
            embed.set_image(url=f"attachment://{session.filename}")
            await message.channel.send(embed=embed, file=file)
        else:
            await message.channel.send(embed=embed)

        # Cleanup
        await self._end_game(message.channel, session)

    # ==================== CLEANUP ON COG UNLOAD ====================

    def cog_unload(self):
        """Cleanup khi cog bị unload."""
        logger.info("Riddle Game: Cog đang được unload...")
        # Lưu ý: Không xóa kênh ở đây vì có thể gây lỗi khi bot restart


async def setup(bot: commands.Bot):
    await bot.add_cog(RiddleGame(bot))
    logger.info("Đã load cog: RiddleGame")
