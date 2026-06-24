# action_groups.py
import json
import os
from datetime import datetime, timedelta

from config import GROUPS_FILE
from utils import auto_close_messagebox
from job import jobs, Job, save_jobs

ACTION_GROUPS = []  # Khởi tạo mặc định rỗng ở đầu module

def load_action_groups():
    global ACTION_GROUPS
    full_path = os.path.abspath(GROUPS_FILE)
    print(f"[LOAD] Bắt đầu load từ: {full_path}")
    
    if not os.path.exists(GROUPS_FILE):
        print("[LOAD] File không tồn tại → tạo nhóm mặc định")
        ACTION_GROUPS = [
            {
                "name": "Thí luyện 1 lần",
                "actions": [
                    {"type": "key", "value": "h", "delay": 5},
                    {"type": "key", "value": "h", "delay": 10},
                    {"type": "key", "value": "d", "delay": 20},
                    {"type": "record", "value": 1, "delay": 337},
                    {"type": "record", "value": 1, "delay": 0}
                ]
            }
        ]
        save_action_groups()
        return

    try:
        with open(GROUPS_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"[LOAD] Nội dung file (đầu 300 ký tự): {content[:300]}...")
            loaded_groups = json.loads(content)
            ACTION_GROUPS[:] = loaded_groups  # Gán lại giá trị, không reset
        print(f"[LOAD] Load thành công: {len(ACTION_GROUPS)} nhóm")
        for g in ACTION_GROUPS:
            print(f"  - Nhóm: {g.get('name', 'Không tên')}, {len(g.get('actions', []))} hành động")
    except json.JSONDecodeError as e:
        print(f"[LOAD] LỖI JSON DECODE: {e}")
        auto_close_messagebox("error", "Lỗi JSON", f"File hỏng:\n{e}\nXóa file để tạo lại?")
        ACTION_GROUPS.clear()  # Chỉ clear khi file hỏng thật
    except Exception as e:
        print(f"[LOAD] LỖI KHÁC: {type(e).__name__} - {e}")
        auto_close_messagebox("error", "Lỗi load", f"Không load được:\n{e}")
        ACTION_GROUPS.clear()

def save_action_groups():
    full_path = os.path.abspath(GROUPS_FILE)
    print(f"[SAVE] Đang lưu {len(ACTION_GROUPS)} nhóm vào {full_path}")
    print("[SAVE] Nội dung trước khi lưu:")
    for g in ACTION_GROUPS:
        print(f"  - {g.get('name')}: {len(g.get('actions', []))} hành động")
    
    try:
        with open(GROUPS_FILE, 'w', encoding='utf-8') as f:
            json.dump(ACTION_GROUPS, f, ensure_ascii=False, indent=4)
        print("[SAVE] Lưu thành công!")
        if os.path.exists(GROUPS_FILE):
            size = os.path.getsize(GROUPS_FILE)
            print(f"[SAVE] File tồn tại, kích thước: {size} bytes")
            with open(GROUPS_FILE, 'r', encoding='utf-8') as f:
                content_after = f.read()
                print(f"[SAVE] Nội dung sau khi lưu (đầu 300 ký tự): {content_after[:300]}...")
    except Exception as e:
        print(f"[SAVE] LỖI: {type(e).__name__} - {e}")
        auto_close_messagebox("error", "Lỗi lưu", f"Không lưu được:\n{e}")

def update_group_jobs():
    # ... giữ nguyên logic cũ
    pass
    
# ====================== HÀNH ĐỘNG MẶC ĐỊNH (DEFAULT GROUP) ======================
DEFAULT_GROUP_FILE = "default_group.json"

def save_default_group():
    """Lưu nhóm mặc định vào file"""
    try:
        data = {
            "default_group_name": default_group_name
        }
        with open(DEFAULT_GROUP_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"[DEFAULT] Đã lưu hành động mặc định: {default_group_name}")
    except Exception as e:
        print(f"[DEFAULT] Lỗi lưu default group: {e}")

def load_default_group():
    """Load nhóm mặc định từ file"""
    global default_group_name
    try:
        if os.path.exists(DEFAULT_GROUP_FILE):
            with open(DEFAULT_GROUP_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                default_group_name = data.get("default_group_name")
                print(f"[DEFAULT] Load mặc định thành công: {default_group_name}")
                return default_group_name
        else:
            default_group_name = None
            return None
    except Exception as e:
        print(f"[DEFAULT] Lỗi load default group: {e}")
        default_group_name = None
        return None