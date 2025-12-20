## 🤖 My Discord Bot

Một bot Discord đa chức năng được viết bằng Python + discord.py, có thể:

Quản lý server (moderation)

Phát nhạc từ YouTube

Chào mừng thành viên mới

Tích hợp Stable Diffusion để tạo ảnh từ prompt

## 📂 Cấu trúc dự án
```
my-discord-bot/
├── bot.py # Entry point chính
├── cogs/ # Các module lệnh (command handler)
│ ├── moderation.py
│ ├── music.py
│ ├── welcome.py
│ └── stable_diffusion.py
├── events/ # Event listener
│ ├── on_ready.py
│ ├── on_member_join.py
│ └── on_message.py
├── utils/ # Helper functions, DB, checks
│ ├── database.py
│ ├── checks.py
│ └── helpers.py
├── data/ # Logs, cache
│ ├── logs/
│ └── cache.json
├── config.json # Config chung (prefix, settings)
├── .env # Chứa token/API key (không push lên git!)
├── requirements.txt # Các thư viện cần cài
└── README.md
```

## 🚀 Cài đặt
1. Clone repo
```
git clone https://github.com/rato-kaz/Bot-discord-basic.git
```

2. Tạo virtual environment
```
python -m venv venv
```
# Windows
```
venv\Scripts\activate
```
# Linux/macOS
```
source venv/bin/activate
```

3. Cài dependencies
```
pip install -r requirements.txt
```

4. **Cài đặt FFmpeg (BẮT BUỘC cho tính năng phát nhạc)**

   **Windows:**
   - Tải FFmpeg từ: https://www.gyan.dev/ffmpeg/builds/ (chọn "ffmpeg-release-essentials.zip")
   - Giải nén vào thư mục (ví dụ: `C:\ffmpeg`)
   - Thêm vào PATH:
     - Mở "Environment Variables" trong Windows Settings
     - Thêm `C:\ffmpeg\bin` vào PATH
     - Hoặc copy `ffmpeg.exe` vào thư mục bot
   - Kiểm tra: Mở CMD và chạy `ffmpeg -version`

   **Linux (Ubuntu/Debian):**
   ```bash
   sudo apt update
   sudo apt install ffmpeg
   ```

   **macOS:**
   ```bash
   brew install ffmpeg
   ```

   **Hoặc dùng conda:**
   ```bash
   conda install -c conda-forge ffmpeg
   ```

## ▶️ Chạy bot
```
python bot.py
```
## ⚙️ Các tính năng
# 1. Moderation

- !kick @user – kick user

- !ban @user – ban user

# 2. Music

-!play <youtube_url> – phát nhạc từ YouTube

-!stop – dừng phát

# 3. Welcome

Tự động gửi lời chào khi có người mới vào server

# 4. Stable Diffusion (AI Image)

- !imagine <prompt> – tạo ảnh từ văn bản

## 🐳 Chạy với Docker

### Yêu cầu
- Docker và Docker Compose đã được cài đặt
- File `.env` đã được cấu hình với các biến môi trường cần thiết

### Cách chạy

1. **Build và chạy với Docker Compose (Khuyến nghị):**
   ```bash
   docker-compose up -d
   ```

2. **Hoặc build và chạy thủ công:**
   ```bash
   # Build image
   docker build -t discord-bot .

   # Chạy container
   docker run -d \
     --name discord-bot \
     --restart unless-stopped \
     --env-file .env \
     discord-bot
   ```

3. **Xem logs:**
   ```bash
   docker-compose logs -f
   # hoặc
   docker logs -f discord-bot
   ```

4. **Dừng bot:**
   ```bash
   docker-compose down
   # hoặc
   docker stop discord-bot
   ```

### Biến môi trường cần thiết trong `.env`:

## 🌐 Triển khai

Bạn có thể deploy bot bằng:

- **Docker** (đã có sẵn Dockerfile và docker-compose.yml)
- **Railway.app** (hỗ trợ Docker)
- **Heroku** (cần thêm buildpack cho FFmpeg)
- **VPS riêng** (dùng Docker hoặc chạy trực tiếp)
- **GitHub Actions** (CI/CD với Docker)

## 📜 License

MIT License
