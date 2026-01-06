# scripts/riddle_generator.py
"""
VLM Generator - Tạo blind_description từ ảnh cho Riddle Game
Sử dụng VLM (Vision Language Model) để mô tả ảnh mà không nhắc tên vật thể.

Cách dùng:
    python scripts/riddle_generator.py

Yêu cầu:
    - Cấu hình VLM API trong file .env
    - Đặt ảnh vào thư mục assets/riddle_images/
    - Tạo file data/riddle/raw_list.txt với danh sách: tên_file|đáp_án|chủ_đề
"""

import base64
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# Thêm thư mục gốc vào path để import utils
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.prompts import VLM_BLIND_CAPTION_PROMPT

load_dotenv()

# ==================== CẤU HÌNH VLM API ====================

VLM_BASE_URL = os.getenv("OPENAI_BASE_URL")
VLM_API_KEY = os.getenv("OPENAI_API_KEY")
VLM_MODEL = os.getenv("OPENAI_MODEL")

# ==================== ĐƯỜNG DẪN ====================

IMAGES_PATH = Path("assets/riddle_images")
RAW_LIST_PATH = Path("data/riddle/raw_list.txt")
OUTPUT_PATH = Path("data/riddle/game_data.json")


def init_vlm_client() -> OpenAI:
    """Khởi tạo VLM client (OpenAI-compatible API)."""
    if not VLM_API_KEY:
        raise ValueError("❌ OPENAI_API_KEY chưa được cấu hình trong .env")
    
    client = OpenAI(
        base_url=VLM_BASE_URL if VLM_BASE_URL else None,
        api_key=VLM_API_KEY,
    )
    print(f"✅ Đã kết nối VLM API: {VLM_BASE_URL or 'OpenAI Default'}")
    print(f"   Model: {VLM_MODEL}")
    return client


def encode_image_to_base64(image_path: Path) -> str:
    """Đọc ảnh và encode thành base64."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_image_mime_type(image_path: Path) -> str:
    """Xác định MIME type của ảnh."""
    suffix = image_path.suffix.lower()
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    return mime_types.get(suffix, "image/jpeg")


def generate_blind_description(
    client: OpenAI, 
    image_path: Path, 
    object_name: str
) -> str:
    """
    Sử dụng VLM để tạo mô tả ảnh mà không nhắc tên vật thể.
    
    Args:
        client: OpenAI client
        image_path: Đường dẫn đến file ảnh
        object_name: Tên vật thể cần tránh nhắc đến
    
    Returns:
        Mô tả chi tiết về ảnh (blind description)
    """
    # Encode ảnh
    base64_image = encode_image_to_base64(image_path)
    mime_type = get_image_mime_type(image_path)
    
    # Tạo prompt
    prompt = VLM_BLIND_CAPTION_PROMPT.format(object_name=object_name)
    
    # Gọi VLM API
    response = client.chat.completions.create(
        model=VLM_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_image}",
                        },
                    },
                ],
            }
        ],
        max_tokens=500,
        temperature=0.7,
    )
    
    return response.choices[0].message.content


def load_raw_list() -> list[dict]:
    """
    Đọc file raw_list.txt và parse thành danh sách.
    
    Format mỗi dòng: tên_file|đáp_án_1,đáp_án_2|chủ_đề
    Ví dụ: ca_heo.jpg|cá heo,dolphin,con cá heo|Đại dương
    """
    if not RAW_LIST_PATH.exists():
        print(f"⚠️ Không tìm thấy file {RAW_LIST_PATH}")
        print("   Tạo file mẫu...")
        create_sample_raw_list()
        return []
    
    items = []
    with open(RAW_LIST_PATH, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            parts = line.split("|")
            if len(parts) < 2:
                print(f"⚠️ Dòng {line_num} không đúng format: {line}")
                continue
            
            filename = parts[0].strip()
            answers = [a.strip() for a in parts[1].split(",")]
            topic = parts[2].strip() if len(parts) > 2 else "Bí mật"
            
            items.append({
                "filename": filename,
                "answers": answers,
                "topic": topic,
            })
    
    return items


def create_sample_raw_list():
    """Tạo file raw_list.txt mẫu."""
    RAW_LIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    sample_content = """# Format: tên_file|đáp_án_1,đáp_án_2|chủ_đề
# Ví dụ:
ca_heo.jpg|cá heo,dolphin,con cá heo|Đại dương
con_meo.jpg|mèo,con mèo,cat|Động vật
cay_dua.jpg|cây dừa,dừa,coconut tree|Thực vật
"""
    with open(RAW_LIST_PATH, "w", encoding="utf-8") as f:
        f.write(sample_content)
    
    print(f"✅ Đã tạo file mẫu: {RAW_LIST_PATH}")


def load_existing_data() -> list[dict]:
    """Load dữ liệu game hiện có."""
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_game_data(data: list[dict]):
    """Lưu dữ liệu game ra file JSON."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Đã lưu {len(data)} câu đố vào {OUTPUT_PATH}")


def main():
    """Hàm chính - Generate blind descriptions cho tất cả ảnh."""
    print("=" * 60)
    print("🎭 RIDDLE GAME - VLM GENERATOR")
    print("=" * 60)
    
    # Khởi tạo VLM client
    try:
        client = init_vlm_client()
    except ValueError as e:
        print(e)
        return
    
    # Load raw list
    raw_items = load_raw_list()
    if not raw_items:
        print("❌ Không có dữ liệu để xử lý. Hãy thêm vào file raw_list.txt")
        return
    
    print(f"\n📋 Tìm thấy {len(raw_items)} mục cần xử lý")
    
    # Load existing data
    existing_data = load_existing_data()
    existing_files = {item["filename"] for item in existing_data}
    
    # Process từng ảnh
    new_items = []
    next_id = max((item.get("id", 0) for item in existing_data), default=0) + 1
    
    for idx, item in enumerate(raw_items, 1):
        filename = item["filename"]
        image_path = IMAGES_PATH / filename
        
        # Skip nếu đã có trong database
        if filename in existing_files:
            print(f"⏭️  [{idx}/{len(raw_items)}] {filename} - Đã có trong database")
            continue
        
        # Kiểm tra file ảnh tồn tại
        if not image_path.exists():
            print(f"❌ [{idx}/{len(raw_items)}] {filename} - File không tồn tại!")
            continue
        
        print(f"🔄 [{idx}/{len(raw_items)}] Đang xử lý: {filename}...")
        
        try:
            # Generate blind description
            blind_desc = generate_blind_description(
                client=client,
                image_path=image_path,
                object_name=item["answers"][0],  # Dùng đáp án đầu tiên
            )
            
            new_item = {
                "id": next_id,
                "filename": filename,
                "topic": item["topic"],
                "answers": item["answers"],
                "blind_description": blind_desc,
            }
            new_items.append(new_item)
            next_id += 1
            
            print(f"   ✅ Đã tạo mô tả ({len(blind_desc)} ký tự)")
            
        except Exception as e:
            print(f"   ❌ Lỗi: {e}")
    
    # Lưu kết quả
    if new_items:
        all_data = existing_data + new_items
        save_game_data(all_data)
        print(f"\n🎉 Hoàn thành! Đã thêm {len(new_items)} câu đố mới.")
    else:
        print("\n⚠️ Không có câu đố mới nào được thêm.")


if __name__ == "__main__":
    main()
