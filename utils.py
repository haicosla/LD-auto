# utils.py
import tkinter as tk
from tkinter import ttk, messagebox
import pyautogui
import time
import threading
import win32gui
import win32con
import win32api

from datetime import datetime
from config import OPR_WINDOW_X, OPR_WINDOW_Y
from logger import get_logger

logger = get_logger()

def get_ldplayer_hwnd(instance_name):
    """Lấy window handle của LDPlayer instance"""
    hwnd = win32gui.FindWindow(None, instance_name)
    if hwnd == 0:
        logger.warning(f"[FOCUS] Không tìm thấy cửa sổ {instance_name}")
        return None
    return hwnd
    
def auto_close_messagebox(msg_type, title, message, auto_close_sec=2):
    """Hiển thị messagebox tự động đóng sau thời gian"""
    def show_and_close():
        win = tk.Toplevel()
        win.title(title)
        win.geometry("400x180")
        win.resizable(False, False)
        win.attributes('-topmost', True)
        
        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)
        
        ttk.Label(frm, text=message, wraplength=360, justify="left").pack(anchor="w", pady=(0,12))
        ttk.Button(frm, text="Đóng", command=win.destroy).pack(side="right")
        
        win.after(auto_close_sec * 1000, win.destroy)
        win.grab_set()
        win.wait_window()
    
    threading.Thread(target=show_and_close, daemon=True).start()

def focus_emulator(name):
    """Focus + Bring to Front bình thường (không dùng TopMost)"""
    hwnds = []
    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd).lower()
            if name.lower() in title:
                hwnds.append(hwnd)
    
    try:
        win32gui.EnumWindows(callback, None)
    except Exception as e:
        logger.error(f"[FOCUS] Lỗi enum windows: {e}")
        return False
    
    if not hwnds:
        logger.warning(f"[FOCUS] Không tìm thấy cửa sổ giả lập: {name}")
        return False
    
    hwnd = hwnds[0]
    
    for attempt in range(3):
        try:
            # Bring to front + Wake up cửa sổ
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)      # Restore nếu bị minimize
            time.sleep(0.1)
            
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)         # Wake up
            time.sleep(0.1)
            
            # Đưa lên trên cùng (cách thông thường)
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.25)
            
            logger.info(f"[FOCUS] ✅ Đã bring to front giả lập: {name} (lần {attempt+1})")
            return True
            
        except Exception as e:
            logger.warning(f"[FOCUS] Lỗi focus lần {attempt+1} cho {name}: {e}")
            time.sleep(0.3)
    
    logger.error(f"[FOCUS] ❌ Không thể focus giả lập sau 3 lần thử: {name}")
    return False
    
def move_operation_recorder_window():
    """Di chuyển Operation Recorder window đến vị trí định sẵn"""
    try:
        hwnd = win32gui.FindWindow("LDOperationRecorderWindow", None)
        if hwnd == 0:
            logger.warning("[MOVE] Không tìm thấy Operation Recorder window")
            return False
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, OPR_WINDOW_X, OPR_WINDOW_Y, 0, 0, win32con.SWP_NOSIZE)
        logger.debug(f"[MOVE] Di chuyển Recorder window đến ({OPR_WINDOW_X}, {OPR_WINDOW_Y})")
        return True
    except Exception as e:
        logger.error(f"[MOVE] Lỗi di chuyển Recorder window: {e}")
        return False

def close_operation_recorder():
    """Đóng Operation Recorder"""
    try:
        hwnd = win32gui.FindWindow("LDOperationRecorderWindow", None)
        if hwnd:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            logger.debug("[CLOSE] Gửi lệnh đóng Operation Recorder")
            time.sleep(0.2)
            return True
        return False
    except Exception as e:
        logger.error(f"[CLOSE] Lỗi đóng Recorder: {e}")
        return False

def validate_time_input(t_str):
    """Validate input thời gian (HH:MM hoặc HHMM) và trả về HH:MM:SS"""
    t_str = t_str.strip()
    if t_str.isdigit() and len(t_str) == 4:
        t_str = f"{t_str[:2]}:{t_str[2:]}"
    if len(t_str) != 5 or ":" not in t_str:
        logger.warning(f"[VALIDATE] Định dạng thời gian không hợp lệ: {t_str}")
        return None
    try:
        datetime.strptime(t_str, "%H:%M")
        result = t_str + ":00"
        logger.debug(f"[VALIDATE] Validate thời gian thành công: {t_str} -> {result}")
        return result
    except ValueError:
        logger.warning(f"[VALIDATE] Giá trị thời gian không hợp lệ: {t_str}")
        return None

def validate_key_input(key_str):
    """Validate phím input"""
    if not key_str:
        return False
    keys = key_str.lower().split('+')
    valid = set(pyautogui.KEYBOARD_KEYS)
    is_valid = all(k.strip() in valid for k in keys)
    if not is_valid:
        logger.warning(f"[VALIDATE] Phím không hợp lệ: {key_str}")
    return is_valid
    
# ==================== NHÓM MẶC ĐỊNH ====================
def run_default_group_if_exists(instance_name, default_group=None):
    """Chạy nhóm mặc định trước khi thực hiện job chính (nếu có)"""
    if not default_group:
        logger.debug(f"[DEFAULT] Không có nhóm mặc định để chạy")
        return True

    try:
        from action_groups import ACTION_GROUPS
        from executor import run_group_actions
    except ImportError as e:
        logger.error(f"[DEFAULT] Lỗi import: {e}")
        return False

    group = next((g for g in ACTION_GROUPS if g["name"] == default_group), None)
    if not group:
        logger.warning(f"[DEFAULT] Nhóm mặc định '{default_group}' không còn tồn tại")
        return True

    logger.info(f"[DEFAULT] Bắt đầu chạy nhóm mặc định '{default_group}' cho {instance_name}")
    try:
        success = run_group_actions(instance_name, group["actions"], group_name=default_group)
        if success:
            logger.info(f"[DEFAULT] Hoàn thành nhóm mặc định '{default_group}' thành công")
        else:
            logger.warning(f"[DEFAULT] Nhóm mặc định '{default_group}' gặp lỗi nhưng vẫn tiếp tục")
        return True
    except Exception as e:
        logger.error(f"[DEFAULT] Lỗi chạy nhóm mặc định '{default_group}' cho {instance_name}: {e}")
        return False
