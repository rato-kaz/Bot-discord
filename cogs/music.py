import asyncio
import json
import logging
import os
import shutil

import discord
import yt_dlp
from discord import app_commands
from discord.ext import commands

# Optional: Spotify support
try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
    SPOTIPY_AVAILABLE = True
except ImportError:
    SPOTIPY_AVAILABLE = False

logger = logging.getLogger("discord_bot.music")

# Load config
with open("config.json", encoding="utf-8") as f:
    config = json.load(f)
MESSAGES = config.get("messages", {})


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.spotify = self._init_spotify()
        self._check_ffmpeg()

    def _check_ffmpeg(self):
        """Kiểm tra xem ffmpeg có được cài đặt không."""
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            logger.info("FFmpeg found tại: %s", ffmpeg_path)
        else:
            logger.error(
                "FFmpeg không được tìm thấy! Bot sẽ không thể phát nhạc. "
                "Vui lòng cài đặt FFmpeg và thêm vào PATH."
            )

    def _init_spotify(self):
        """Khởi tạo Spotify client nếu có credentials."""
        if not SPOTIPY_AVAILABLE:
            return None

        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

        if not client_id or not client_secret:
            logger.info("Spotify credentials không được cấu hình. Tính năng Spotify bị tắt.")
            return None

        try:
            return spotipy.Spotify(
                auth_manager=SpotifyClientCredentials(
                    client_id=client_id,
                    client_secret=client_secret,
                )
            )
        except Exception as e:
            logger.warning("Không thể khởi tạo Spotify client: %s", e)
            return None

    async def _search_ytdlp(self, query: str) -> dict:
        """
        Tìm nguồn audio bằng yt-dlp (hỗ trợ nhiều site).
        Chạy trong thread riêng để không block event loop.
        """
        ytdl_opts = {
            "format": "bestaudio/best",
            "noplaylist": True,
            "quiet": True,
            "default_search": "ytsearch",
            "no_warnings": True,
            # Postprocessors (chỉ chạy khi download=True, nhưng giữ lại để tương thích)
            # Với download=False, FFmpegOpusAudio.from_probe() sẽ tự động xử lý conversion
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
            # Giả lập browser để tránh bị YouTube chặn
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "web"],  # Dùng Android client để bypass
                    "player_skip": ["webpage", "configs"],
                }
            },
            # Headers giả lập browser
            "http_headers": {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-us,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.7",
                "Keep-Alive": "300",
                "Connection": "keep-alive",
            },
            # Retry khi gặp lỗi
            "retries": 3,
            "fragment_retries": 3,
            "ignoreerrors": False,
        }

        def _extract():
            try:
                with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
                    info = ydl.extract_info(query, download=False)
                    return info["entries"][0] if "entries" in info else info
            except Exception as e:
                # Nếu vẫn bị lỗi, thử với options đơn giản hơn
                logger.warning("Lỗi với yt-dlp options đầy đủ, thử với options đơn giản: %s", e)
                simple_opts = {
                    "format": "bestaudio/best",
                    "noplaylist": True,
                    "quiet": True,
                    "default_search": "ytsearch",
                    "extractor_args": {"youtube": {"player_client": ["android"]}},
                }
                with yt_dlp.YoutubeDL(simple_opts) as ydl:
                    info = ydl.extract_info(query, download=False)
                    return info["entries"][0] if "entries" in info else info

        return await asyncio.to_thread(_extract)

    def _resolve_spotify(self, url: str) -> str | None:
        """
        Lấy tên bài + artist từ link Spotify track để search trên YouTube.
        """
        if not self.spotify:
            return None

        try:
            if "open.spotify.com/track" in url:
                track = self.spotify.track(url)
                name = track["name"]
                artists = ", ".join(a["name"] for a in track["artists"])
                return f"{name} - {artists}"
        except Exception as e:
            logger.warning("Lỗi khi resolve Spotify: %s", e)
            return None

        return None

    async def _play_music(
        self,
        voice_channel: discord.VoiceChannel,
        voice_client: discord.VoiceClient | None,
        query: str,
        send_message,
        stop_cmd: str = "!stop",
    ):
        """
        Logic chung cho cả prefix và slash command.
        send_message: callable async để gửi tin nhắn.
        """
        # Kiểm tra quyền của bot trong voice channel
        if voice_channel.guild.me.guild_permissions.connect is False:
            await send_message("❌ Bot không có quyền kết nối vào voice channel!")
            return

        if voice_channel.guild.me.guild_permissions.speak is False:
            await send_message("❌ Bot không có quyền phát âm thanh trong voice channel!")
            return

        # Kiểm tra xem voice channel có đầy không
        if voice_channel.user_limit and len(voice_channel.members) >= voice_channel.user_limit:
            await send_message("❌ Voice channel đã đầy!")
            return

        # Kết nối voice nếu chưa
        # Workaround cho bug IndexError trong discord.py khi Discord API không trả về đúng format
        vc = None
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if voice_client is None:
                    # Thử với các tham số khác nhau để tránh bug
                    vc = await voice_channel.connect(
                        timeout=15.0,
                        reconnect=True,
                        self_deaf=True,  # Bot tự deaf để tránh echo
                        self_mute=False,
                    )
                else:
                    vc = voice_client
                    # Nếu đã kết nối nhưng ở channel khác, di chuyển
                    if vc.channel != voice_channel:
                        await vc.move_to(voice_channel)
                break  # Thành công, thoát loop
            except (IndexError, KeyError) as e:
                # Bug đã biết trong discord.py khi Discord API trả về format sai
                logger.warning("Lỗi IndexError/KeyError khi kết nối voice (attempt %d/%d): %s", attempt + 1, max_retries, e)
                if attempt < max_retries - 1:
                    # Đợi một chút trước khi retry
                    await asyncio.sleep(1.0)
                    # Disconnect nếu đã kết nối một phần
                    if voice_client:
                        try:
                            await voice_client.disconnect(force=True)
                        except:
                            pass
                else:
                    await send_message(
                        "❌ Không thể kết nối vào voice channel do lỗi từ Discord API. "
                        "Vui lòng thử lại sau hoặc kiểm tra voice channel region."
                    )
                    return
            except discord.ClientException as e:
                logger.error("Lỗi khi kết nối voice: %s", e)
                await send_message(f"❌ Không thể kết nối vào voice channel: {e}")
                return
            except asyncio.TimeoutError:
                if attempt < max_retries - 1:
                    logger.warning("Timeout khi kết nối voice (attempt %d/%d), retrying...", attempt + 1, max_retries)
                    await asyncio.sleep(1.0)
                else:
                    await send_message("❌ Timeout khi kết nối vào voice channel sau nhiều lần thử. Vui lòng thử lại sau.")
                    return
            except Exception as e:
                logger.exception("Lỗi không xác định khi kết nối voice: %s", e)
                if attempt < max_retries - 1:
                    await asyncio.sleep(1.0)
                else:
                    await send_message(
                        "❌ Đã xảy ra lỗi khi kết nối vào voice channel. "
                        "Có thể do Discord API tạm thời không ổn định. Vui lòng thử lại sau."
                    )
                    return

        if vc is None:
            await send_message("❌ Không thể kết nối vào voice channel sau nhiều lần thử.")
            return

        if vc.is_playing():
            msg = MESSAGES.get("bot_already_playing", "Bot đang phát nhạc rồi.").format(stop_cmd=stop_cmd)
            await send_message(msg)
            return

        # Xử lý Spotify link
        search_query = query
        if "open.spotify.com/track" in query:
            resolved = self._resolve_spotify(query)
            if not resolved:
                await send_message(MESSAGES.get("spotify_error", "Lỗi Spotify."))
                return
            search_query = resolved

        await send_message(MESSAGES.get("searching", "Đang tìm...").format(query=search_query))

        try:
            info = await self._search_ytdlp(search_query)
            url = info["url"]
            title = info.get("title", "Unknown")
        except Exception as e:
            logger.error("Lỗi khi search với yt-dlp: %s", e)
            await send_message(f"❌ Không tìm thấy bài hát: {e}")
            return

        await send_message(MESSAGES.get("now_playing", "Đang phát: {title}").format(title=title))

        # Kiểm tra ffmpeg trước khi phát
        if not shutil.which("ffmpeg"):
            await send_message(
                "❌ **FFmpeg chưa được cài đặt!**\n"
                "Bot cần FFmpeg để phát nhạc. Vui lòng:\n"
                "1. Tải FFmpeg từ: https://ffmpeg.org/download.html\n"
                "2. Giải nén và thêm vào PATH\n"
                "3. Hoặc đặt file `ffmpeg.exe` trong thư mục bot\n"
                "4. Restart bot sau khi cài đặt"
            )
            return

        # Phát nhạc
        # Dùng FFmpegOpusAudio.from_probe() thay vì FFmpegPCMAudio để tự động detect codec và convert sang Opus
        # Opus là format Discord ưa thích, chất lượng tốt hơn và ít lỗi hơn
        try:
            source = await discord.FFmpegOpusAudio.from_probe(
                url,
                method="fallback",  # Fallback nếu probe không thành công
            )
            vc.play(
                source,
                after=lambda e: logger.info("Kết thúc phát: %s", e) if e else logger.info("Phát xong."),
            )
        except discord.ClientException as e:
            if "ffmpeg" in str(e).lower() or "was not found" in str(e).lower():
                logger.error("FFmpeg không tìm thấy: %s", e)
                await send_message(
                    "❌ **FFmpeg không tìm thấy!**\n"
                    "Bot cần FFmpeg để phát nhạc. Vui lòng cài đặt FFmpeg và thêm vào PATH."
                )
            else:
                logger.error("Lỗi khi phát nhạc: %s", e)
                await send_message(f"❌ Lỗi khi phát nhạc: {e}")
        except Exception as e:
            logger.exception("Lỗi không xác định khi phát nhạc: %s", e)
            # Fallback: thử dùng FFmpegPCMAudio nếu OpusAudio không hoạt động
            try:
                logger.info("Thử fallback sang FFmpegPCMAudio...")
                vc.play(
                    discord.FFmpegPCMAudio(
                        url,
                        before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                    ),
                    after=lambda e: logger.info("Kết thúc phát: %s", e) if e else logger.info("Phát xong."),
                )
            except Exception as fallback_error:
                logger.exception("Fallback cũng thất bại: %s", fallback_error)
                await send_message(f"❌ Không thể phát nhạc: {fallback_error}")

    # ===================== PREFIX COMMANDS =====================

    @commands.command(name="play")
    async def play(self, ctx: commands.Context, *, query: str):
        """Phát nhạc từ YouTube hoặc các nguồn khác (hỗ trợ Spotify link)."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send(MESSAGES.get("need_voice_channel", "Bạn cần vào voice channel!"))

        try:
            await self._play_music(
                voice_channel=ctx.author.voice.channel,
                voice_client=ctx.voice_client,
                query=query,
                send_message=ctx.send,
                stop_cmd="!stop",
            )
        except Exception as e:
            logger.exception("Lỗi trong lệnh play: %s", e)
            await ctx.send("❌ Đã xảy ra lỗi khi phát nhạc. Vui lòng thử lại sau.")

    @commands.command(name="stop")
    async def stop(self, ctx: commands.Context):
        """Dừng nhạc và rời voice channel."""
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send(MESSAGES.get("stopped", "Đã dừng."))
        else:
            await ctx.send(MESSAGES.get("bot_not_in_voice", "Bot không ở trong voice."))

    # ===================== SLASH COMMANDS =====================

    @app_commands.command(name="play", description="Phát nhạc (YouTube, Spotify, SoundCloud, ...)")
    @app_commands.describe(query="Tên bài hát, URL YouTube, hoặc link Spotify track")
    async def play_slash(self, interaction: discord.Interaction, query: str):
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                MESSAGES.get("need_voice_channel", "Bạn cần vào voice channel!"),
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        async def send_msg(content: str):
            await interaction.followup.send(content)

        try:
            await self._play_music(
                voice_channel=interaction.user.voice.channel,
                voice_client=interaction.guild.voice_client if interaction.guild else None,
                query=query,
                send_message=send_msg,
                stop_cmd="/stop",
            )
        except Exception as e:
            logger.exception("Lỗi trong lệnh play (slash): %s", e)
            await interaction.followup.send(
                "❌ Đã xảy ra lỗi khi phát nhạc. Vui lòng thử lại sau.",
                ephemeral=True,
            )

    @app_commands.command(name="stop", description="Dừng nhạc và rời voice channel")
    async def stop_slash(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client if interaction.guild else None
        if vc:
            await vc.disconnect()
            await interaction.response.send_message(MESSAGES.get("stopped", "Đã dừng."))
        else:
            await interaction.response.send_message(
                MESSAGES.get("bot_not_in_voice", "Bot không ở trong voice."),
                ephemeral=True,
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
