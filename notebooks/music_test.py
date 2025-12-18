import discord
from discord.ext import commands
import yt_dlp
import asyncio

# Tạo đối tượng intents
intents = discord.Intents.default()
intents.message_content = True

# Đặt tiền tố cho bot, ví dụ "!"
bot = commands.Bot(command_prefix="!", intents=intents)

# Sự kiện khi bot kết nối với Discord
@bot.event
async def on_ready():
    print(f'Bot đã đăng nhập với tên: {bot.user}')

# Lệnh để bot tham gia vào kênh thoại
@bot.command()
async def join(ctx):
    if ctx.author.voice:  # Kiểm tra xem người dùng có đang ở kênh thoại không
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send("Tớ đã tham gia kênh thoại!")
    else:
        await ctx.send("Cậu phải tham gia kênh thoại trước!")

# Lệnh để bot rời khỏi kênh thoại
@bot.command()
async def leave(ctx):
    if ctx.voice_client:  # Kiểm tra xem bot có đang ở kênh thoại không
        await ctx.voice_client.disconnect()
        await ctx.send("Tớ đi nghỉ đây!")
    else:
        await ctx.send("Tớ không ở trong kênh thoại.")

# Lệnh để phát nhạc từ YouTube
@bot.command()
async def play(ctx, url):
    if not ctx.voice_client:
        await ctx.send("Gọi tớ tham gia kênh thoại trước! Dùng lệnh !join để thêm mình vào kênh.")
        return

    # Cài đặt yt_dlp để lấy dữ liệu video
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            url2 = info['url']
            source = await discord.FFmpegOpusAudio.from_probe(url2)
            ctx.voice_client.play(source)
            await ctx.send(f"Đang phát: {info['title']}")
    except Exception as e:
        await ctx.send(f"Đã xảy ra lỗi khi phát nhạc: {str(e)}")

# Lệnh để dừng nhạc
@bot.command()
async def stop(ctx):
    if ctx.voice_client:
        ctx.voice_client.stop()
        await ctx.send("Đã dừng phát nhạc.")
    else:
        await ctx.send("Mình không đang phát nhạc.")

# Xử lý khi bot bị ngắt kết nối bất ngờ hoặc xảy ra lỗi
@bot.event
async def on_voice_state_update(member, before, after):
    if member == bot.user and before.channel is not None and after.channel is None:
        await member.guild.voice_client.disconnect()

# Chạy bot với token của bạn
async def main():
    await bot.start('')

if __name__ == "__main__":
    # Nếu vòng lặp sự kiện đã chạy, sử dụng cách khác để khởi động bot
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # Dành cho môi trường đang chạy vòng lặp sự kiện (ví dụ: Jupyter)
        loop.create_task(main())
    else:
        asyncio.run(main())
