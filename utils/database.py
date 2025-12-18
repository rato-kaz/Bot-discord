# utils/database.py
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("discord_bot.database")

# Lazy connection - chỉ kết nối khi thực sự cần
_client = None
_db = None
_history_collection = None
_usage_collection = None

# In-memory fallback khi không có MongoDB
# Format: {user_id: {"date": "YYYY-MM-DD", "count": int}}
_memory_usage: dict[int, dict] = defaultdict(lambda: {"date": "", "count": 0})


def _get_db():
    """Lazy init MongoDB connection. Trả về db hoặc None."""
    global _client, _db

    if _db is not None:
        return _db

    mongo_url = os.getenv("MONGO_URL")
    if not mongo_url:
        logger.warning("MONGO_URL chưa được cấu hình. Database sẽ không hoạt động.")
        return None

    try:
        from pymongo import MongoClient
        _client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
        _client.admin.command("ping")
        _db = _client["discord_bot"]
        logger.info("Đã kết nối MongoDB thành công.")
        return _db
    except Exception as e:
        logger.error("Không thể kết nối MongoDB: %s", e)
        return None


def _get_collection():
    """Trả về chat_history collection."""
    global _history_collection
    if _history_collection is not None:
        return _history_collection

    db = _get_db()
    if db is None:
        return None

    _history_collection = db["chat_history"]
    return _history_collection


def _get_usage_collection():
    """Trả về usage collection cho rate limiting."""
    global _usage_collection
    if _usage_collection is not None:
        return _usage_collection

    db = _get_db()
    if db is None:
        return None

    _usage_collection = db["daily_usage"]
    return _usage_collection


def save_chat_history(
    user_id: int,
    guild_id: Optional[int],
    prompt: str,
    response: str
) -> bool:
    """
    Lưu lịch sử chat vào MongoDB.
    Trả về True nếu thành công, False nếu thất bại.
    """
    collection = _get_collection()
    if collection is None:
        return False

    try:
        collection.insert_one({
            "user_id": str(user_id),
            "guild_id": str(guild_id) if guild_id else None,
            "prompt": prompt,
            "response": response,
            "timestamp": datetime.now(timezone.utc),
        })
        return True
    except Exception as e:
        logger.error("Lỗi khi lưu chat history: %s", e)
        return False


def get_daily_usage(user_id: int) -> int:
    """
    Lấy số lần user đã sử dụng hôm nay.
    Dùng MongoDB nếu có, fallback sang memory.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Thử dùng MongoDB
    collection = _get_usage_collection()
    if collection is not None:
        try:
            doc = collection.find_one({"user_id": str(user_id), "date": today})
            return doc["count"] if doc else 0
        except Exception as e:
            logger.error("Lỗi khi lấy daily usage từ DB: %s", e)

    # Fallback: dùng memory
    user_data = _memory_usage[user_id]
    if user_data["date"] != today:
        # Reset nếu sang ngày mới
        user_data["date"] = today
        user_data["count"] = 0
    return user_data["count"]


def increment_daily_usage(user_id: int) -> int:
    """
    Tăng số lần sử dụng của user hôm nay lên 1.
    Trả về số lần sau khi tăng.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Thử dùng MongoDB
    collection = _get_usage_collection()
    if collection is not None:
        try:
            result = collection.find_one_and_update(
                {"user_id": str(user_id), "date": today},
                {"$inc": {"count": 1}},
                upsert=True,
                return_document=True,
            )
            return result["count"] if result else 1
        except Exception as e:
            logger.error("Lỗi khi cập nhật daily usage: %s", e)

    # Fallback: dùng memory
    user_data = _memory_usage[user_id]
    if user_data["date"] != today:
        user_data["date"] = today
        user_data["count"] = 0
    user_data["count"] += 1
    return user_data["count"]


def check_and_use_daily_limit(user_id: int, limit: int) -> tuple[bool, int, int]:
    """
    Kiểm tra và sử dụng quota hàng ngày.

    Args:
        user_id: ID của user
        limit: Giới hạn số lần/ngày

    Returns:
        (allowed, current_count, limit)
        - allowed: True nếu còn quota, False nếu hết
        - current_count: Số lần đã dùng (sau khi tăng nếu allowed)
        - limit: Giới hạn
    """
    current = get_daily_usage(user_id)

    if current >= limit:
        return False, current, limit

    new_count = increment_daily_usage(user_id)
    return True, new_count, limit
