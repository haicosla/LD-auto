# gui_defaults.py - Quản lý nhóm hành động mặc định
import tkinter as tk
from utils import auto_close_messagebox
from action_groups import save_default_group, load_default_group
from logger import get_logger

logger = get_logger()

# Biến toàn cục
default_group_name = None
default_status_label = None

def set_default_group(group_var):
    """Đặt nhóm hiện tại làm mặc định"""
    global default_group_name, default_status_label
    group_name = group_var.get()
    if not group_name:
        auto_close_messagebox("error", "Lỗi", "Vui lòng chọn một nhóm trước!")
        return
    
    default_group_name = group_name
    save_default_group()
    if default_status_label:
        default_status_label.config(text=f"Mặc định hiện tại: {group_name}")
    auto_close_messagebox("info", "Thành công", f"Đã đặt nhóm '{group_name}' làm hành động mặc định.")
    print(f"[DEFAULT] Đã lưu nhóm mặc định: {default_group_name}")

def clear_default_group():
    """Xóa nhóm mặc định"""
    global default_group_name, default_status_label
    default_group_name = None
    save_default_group()
    if default_status_label:
        default_status_label.config(text="Chưa có nhóm mặc định")
    auto_close_messagebox("info", "Thành công", "Đã xóa nhóm mặc định.")
    print("[DEFAULT] Đã xóa và lưu nhóm mặc định")

def update_default_label():
    """Cập nhật hiển thị trạng thái nhóm mặc định"""
    global default_group_name, default_status_label
    if default_status_label:
        text = f"Mặc định hiện tại: {default_group_name}" if default_group_name else "Chưa có nhóm mặc định"
        default_status_label.config(text=text)

def init_defaults():
    """Khởi tạo nhóm mặc định từ file"""
    global default_group_name
    load_default_group()
    update_default_label()
