# 🎮 AI RIDDLE MASTER - FLOW XỬ LÝ

## 📊 TỔNG QUAN KIẾN TRÚC

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AI RIDDLE MASTER                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   GIAI ĐOẠN A: OFFLINE (Chuẩn bị dữ liệu)                               │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                 │
│   │   Ảnh gốc   │───▶│  VLM Local  │───▶│ game_data   │                 │
│   │  (.jpg)     │    │  (Qwen VL)  │    │   .json     │                 │
│   └─────────────┘    └─────────────┘    └─────────────┘                 │
│                                                                          │
│   GIAI ĐOẠN B: RUNTIME (Chơi game)                                      │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                 │
│   │   Discord   │◀──▶│  LLM Cloud  │◀──▶│ game_data   │                 │
│   │    User     │    │  (GPT-4)    │    │   .json     │                 │
│   └─────────────┘    └─────────────┘    └─────────────┘                 │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🔧 GIAI ĐOẠN A: OFFLINE PREPROCESSING

**Mục đích**: Tạo `blind_description` từ ảnh (chạy 1 lần khi thêm câu đố mới)

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│   1. CHUẨN BỊ                                                │
│   ┌─────────────────┐     ┌─────────────────┐               │
│   │ raw_list.txt    │     │ riddle_images/  │               │
│   │ ─────────────── │     │ ─────────────── │               │
│   │ ca_heo.jpg|     │     │ ca_heo.jpg      │               │
│   │ cá heo,dolphin| │     │ con_meo.jpg     │               │
│   │ Đại dương       │     │ ...             │               │
│   └────────┬────────┘     └────────┬────────┘               │
│            │                       │                         │
│            └───────────┬───────────┘                         │
│                        ▼                                     │
│   2. XỬ LÝ VLM                                               │
│   ┌─────────────────────────────────────────┐               │
│   │      riddle_generator.py                │               │
│   │  ┌─────────────────────────────────┐    │               │
│   │  │ • Đọc ảnh + encode base64       │    │               │
│   │  │ • Gửi lên VLM API               │    │               │
│   │  │ • Prompt: "Mô tả ảnh, KHÔNG     │    │               │
│   │  │   nhắc tên [vật thể]"           │    │               │
│   │  │ • Nhận blind_description        │    │               │
│   │  └─────────────────────────────────┘    │               │
│   └────────────────────┬────────────────────┘               │
│                        ▼                                     │
│   3. LƯU DATABASE                                            │
│   ┌─────────────────────────────────────────┐               │
│   │  game_data.json                         │               │
│   │  {                                      │               │
│   │    "id": 1,                             │               │
│   │    "filename": "ca_heo.jpg",            │               │
│   │    "topic": "Đại dương",                │               │
│   │    "answers": ["cá heo", "dolphin"],    │               │
│   │    "blind_description": "Sinh vật biển │               │
│   │      da trơn màu xám, đang nhảy..."     │               │
│   │  }                                      │               │
│   └─────────────────────────────────────────┘               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Cách chạy Generator

```powershell
# Bước 1: Thêm ảnh vào assets/riddle_images/
# Bước 2: Cập nhật data/riddle/raw_list.txt
# Bước 3: Chạy script
python scripts/riddle_generator.py
```

---

## 🎯 GIAI ĐOẠN B: RUNTIME GAME LOOP

### B1. BẮT ĐẦU GAME (`/riddle`)

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│   User gọi /riddle                                           │
│         │                                                    │
│         ▼                                                    │
│   ┌─────────────────────────────────────┐                   │
│   │  1. CHECK USER ĐANG CHƠI?           │                   │
│   │     • Có → Thông báo "đang có game" │                   │
│   │     • Không → Tiếp tục              │                   │
│   └──────────────────┬──────────────────┘                   │
│                      ▼                                       │
│   ┌─────────────────────────────────────┐                   │
│   │  2. LOAD RANDOM RIDDLE              │                   │
│   │     • Đọc game_data.json            │                   │
│   │     • Random chọn 1 câu đố          │                   │
│   └──────────────────┬──────────────────┘                   │
│                      ▼                                       │
│   ┌─────────────────────────────────────┐                   │
│   │  3. TẠO KÊNH RIÊNG                  │                   │
│   │     • Tên: #riddle-username-123     │                   │
│   │     • Permission:                   │                   │
│   │       - @everyone: Xem ✓, Chat ✗    │                   │
│   │       - User: Xem ✓, Chat ✓         │                   │
│   │       - Bot: Full quyền             │                   │
│   └──────────────────┬──────────────────┘                   │
│                      ▼                                       │
│   ┌─────────────────────────────────────┐                   │
│   │  4. TẠO SESSION                     │                   │
│   │     • Lưu: channel_id, user_id      │                   │
│   │     • Lưu: answers, blind_desc      │                   │
│   │     • hints_asked = 0               │                   │
│   │     • guesses = 0                   │                   │
│   └──────────────────┬──────────────────┘                   │
│                      ▼                                       │
│   ┌─────────────────────────────────────┐                   │
│   │  5. GỬI WELCOME MESSAGE             │                   │
│   │     "Chào mừng! Chủ đề: [topic]"    │                   │
│   │     "Hãy đặt câu hỏi hoặc đoán!"    │                   │
│   └─────────────────────────────────────┘                   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

### B2. XỬ LÝ TIN NHẮN (`on_message`)

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│   User gửi tin nhắn trong #riddle-...                                │
│         │                                                            │
│         ▼                                                            │
│   ┌─────────────────────────────────────┐                           │
│   │  CHECK 1: Kênh riddle?              │──No──▶ Bỏ qua             │
│   └──────────────────┬──────────────────┘                           │
│                      │ Yes                                           │
│                      ▼                                               │
│   ┌─────────────────────────────────────┐                           │
│   │  CHECK 2: Đúng người chơi?          │──No──▶ Xóa tin nhắn       │
│   └──────────────────┬──────────────────┘                           │
│                      │ Yes                                           │
│                      ▼                                               │
│   ┌─────────────────────────────────────┐                           │
│   │  CHECK 3: Kênh đang LOCK?           │──Yes──▶ Xóa tin nhắn      │
│   └──────────────────┬──────────────────┘                           │
│                      │ No                                            │
│                      ▼                                               │
│   ╔═════════════════════════════════════╗                           │
│   ║        🔒 LOCK KÊNH                 ║                           │
│   ║   (User không chat được nữa)        ║                           │
│   ╚══════════════════╦══════════════════╝                           │
│                      ▼                                               │
│   ┌─────────────────────────────────────┐                           │
│   │        LLM ROUTER                   │                           │
│   │  ┌───────────────────────────────┐  │                           │
│   │  │ Input:                        │  │                           │
│   │  │ • Tin nhắn user               │  │                           │
│   │  │ • Đáp án bí mật               │  │                           │
│   │  │                               │  │                           │
│   │  │ Output: JSON                  │  │                           │
│   │  │ {"type": "...", "reason":""}  │  │                           │
│   │  └───────────────────────────────┘  │                           │
│   └──────────────────┬──────────────────┘                           │
│                      │                                               │
│       ┌──────────────┼──────────────┬──────────────┐                │
│       ▼              ▼              ▼              ▼                │
│   ┌────────┐    ┌────────┐    ┌────────┐    ┌────────┐             │
│   │GUESS   │    │GUESS   │    │QUESTION│    │GIVE_UP │             │
│   │CORRECT │    │WRONG   │    │        │    │        │             │
│   └───┬────┘    └───┬────┘    └───┬────┘    └───┬────┘             │
│       │             │             │             │                    │
│       ▼             ▼             ▼             ▼                    │
│   ┌────────┐    ┌────────┐    ┌────────┐    ┌────────┐             │
│   │🎉 WIN! │    │❌ Sai! │    │🤖 Gọi  │    │🏳️ Thua │             │
│   │Hiện ảnh│    │Thử lại │    │Riddle  │    │Hiện ảnh│             │
│   │+ thống │    │        │    │Master  │    │+ đáp án│             │
│   │kê      │    │        │    │trả lời │    │        │             │
│   └───┬────┘    └────────┘    └───┬────┘    └───┬────┘             │
│       │                           │             │                    │
│       ▼                           ▼             ▼                    │
│   ┌────────┐                  ┌────────┐    ┌────────┐             │
│   │Kết thúc│                  │Gửi     │    │Kết thúc│             │
│   │game    │                  │embed   │    │game    │             │
│   └───┬────┘                  └────────┘    └───┬────┘             │
│       │                                         │                    │
│       └────────────────┬────────────────────────┘                   │
│                        ▼                                             │
│   ╔═════════════════════════════════════╗                           │
│   ║        🔓 UNLOCK KÊNH               ║                           │
│   ║   (User chat được tiếp)             ║                           │
│   ╚══════════════════╦══════════════════╝                           │
│                      │                                               │
│              (Nếu game kết thúc)                                     │
│                      ▼                                               │
│   ┌─────────────────────────────────────┐                           │
│   │  XÓA KÊNH SAU 30 GIÂY              │                           │
│   │  • Cleanup session                  │                           │
│   │  • Delete channel                   │                           │
│   └─────────────────────────────────────┘                           │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

### B3. CHI TIẾT LLM ROUTER

```
┌──────────────────────────────────────────────────────────────┐
│                     LLM ROUTER                               │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  INPUT                          OUTPUT                       │
│  ─────                          ──────                       │
│  User: "Nó màu gì?"         →  {"type": "QUESTION"}         │
│  Target: "cá heo"                                            │
│                                                              │
│  User: "Cá heo"             →  {"type": "GUESS_CORRECT"}    │
│  Target: "cá heo"                                            │
│                                                              │
│  User: "Là cá mập à?"       →  {"type": "GUESS_WRONG"}      │
│  Target: "cá heo"                                            │
│                                                              │
│  User: "Tôi chịu thua"      →  {"type": "GIVE_UP"}          │
│  Target: "cá heo"                                            │
│                                                              │
│  User: "dolphin"            →  {"type": "GUESS_CORRECT"}    │
│  Target: "cá heo"               (từ đồng nghĩa)              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

### B4. CHI TIẾT RIDDLE MASTER

```
┌──────────────────────────────────────────────────────────────┐
│                   RIDDLE MASTER                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  SYSTEM PROMPT:                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Bạn là RiddleMaster. Trả lời gợi ý dựa trên mô tả.    │ │
│  │ QUY TẮC:                                               │ │
│  │ 1. KHÔNG tiết lộ tên vật thể                          │ │
│  │ 2. Trả lời ngắn gọn, hóm hỉnh                         │ │
│  │ 3. Khuyến khích người chơi                            │ │
│  │                                                        │ │
│  │ MÔ TẢ: {blind_description}                            │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  VÍ DỤ:                                                      │
│  ─────                                                       │
│  Mô tả: "Sinh vật biển da trơn màu xám, đang nhảy..."       │
│                                                              │
│  Q: "Nó sống ở đâu?"                                         │
│  A: "Nó yêu biển cả, thích bơi lội và nhảy múa! 🌊"         │
│                                                              │
│  Q: "Nó có thông minh không?"                                │
│  A: "Ồ, nó thuộc top những sinh vật thông minh nhất! 🧠"    │
│                                                              │
│  Q: "Nó là cá heo à?"                                        │
│  A: → Router xử lý là GUESS, không gọi RiddleMaster         │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 📁 CẤU TRÚC FILE

```
Bot-discord/
├── .env                          # API keys
├── config.json                   # Cấu hình bot
│
├── assets/
│   └── riddle_images/            # Ảnh gốc cho game
│       ├── ca_heo.jpg
│       └── ...
│
├── data/
│   └── riddle/
│       ├── raw_list.txt          # Input cho generator
│       └── game_data.json        # Database câu đố
│
├── docs/
│   └── riddle_game_flow.md       # Tài liệu này
│
├── scripts/
│   └── riddle_generator.py       # Script tạo blind_desc
│
├── utils/
│   └── prompts.py                # Tất cả prompts
│
└── cogs/
    └── riddle_game.py            # Logic game chính
```

---

## 🔑 CÁC THÀNH PHẦN CHÍNH

| Thành phần | Vai trò | API sử dụng |
|------------|---------|-------------|
| **VLM Generator** | Tạo mô tả ảnh (offline) | Qwen VL Local |
| **LLM Router** | Phân loại tin nhắn user | Azure OpenAI |
| **Riddle Master** | Trả lời gợi ý | Azure OpenAI |
| **Discord Bot** | Quản lý kênh, session | Discord.py |

---

## 🎮 HƯỚNG DẪN SỬ DỤNG

### Cho Admin (Thêm câu đố mới)

1. Thêm ảnh vào `assets/riddle_images/`
2. Cập nhật `data/riddle/raw_list.txt`:
   ```
   ten_file.jpg|đáp án 1,đáp án 2|Chủ đề
   ```
3. Chạy: `python scripts/riddle_generator.py`
4. Reload data: `/riddle_reload`

### Cho User (Chơi game)

1. Gọi `/riddle` để bắt đầu
2. Vào kênh `#riddle-...` được tạo
3. Hỏi gợi ý: "Nó có màu gì?", "Nó sống ở đâu?"
4. Đoán đáp án: "cá heo", "Là con mèo à?"
5. Bỏ cuộc: "tôi chịu thua" hoặc "đầu hàng"

---

*Cập nhật lần cuối: January 2026*
