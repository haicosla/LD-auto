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


def get_ldplayer_hwnd(instance_name):
    hwnd = win32gui.FindWindow(None, instance_name)
    if hwnd == 0:
        print(f"[FOCUS] Không tìm thấy cửa sổ {instance_name}")
        return None
    return hwnd
    
def auto_close_messagebox(msg_type, title, message, auto_close_sec=2):
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

# utils.py - thay thế toàn bộ hàm focus_emulator
# utils.py - thay thế toàn bộ hàm focus_emulator
def focus_emulator(name):
    hwnds = []
    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd).lower()
            if name.lower() in title:
                hwnds.append(hwnd)
    win32gui.EnumWindows(callback, None)
    if not hwnds:
        print(f"[LOG] Không tìm thấy cửa sổ giả lập: {name}")
        return False
    
    hwnd = hwnds[0]
    for _ in range(3):
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            print(f"[LOG] Đã focus giả lập: {name}")
            return True
        except Exception as e:
            print(f"[LOG] Lỗi focus giả lập {name}: {e}")
            time.sleep(1)
    print(f"[LOG] Không thể focus giả lập sau 3 lần thử: {name}")
    return False
    
def move_operation_recorder_window():
    hwnd = win32gui.FindWindow("LDOperationRecorderWindow", None)
    if hwnd == 0:
        return False
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, OPR_WINDOW_X, OPR_WINDOW_Y, 0, 0, win32con.SWP_NOSIZE)
    return True

def close_operation_recorder():
    hwnd = win32gui.FindWindow("LDOperationRecorderWindow", None)
    if hwnd:
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)

def validate_time_input(t_str):
    t_str = t_str.strip()
    if t_str.isdigit() and len(t_str) == 4:
        t_str = f"{t_str[:2]}:{t_str[2:]}"
    if len(t_str) != 5 or ":" not in t_str:
        return None
    try:
        datetime.strptime(t_str, "%H:%M")
        return t_str + ":00"
    except ValueError:
        return None

def validate_key_input(key_str):
    if not key_str:
        return False
    keys = key_str.lower().split('+')
    valid = set(pyautogui.KEYBOARD_KEYS)
    return all(k.strip() in valid for k in keys)
    
# ==================== NHÓM MẶC ĐỊNH ====================
def run_default_group_if_exists(instance_name, default_group=None):
    """Chạy nhóm mặc định trước khi thực hiện job chính (nếu có)"""
    if not default_group:
        return True

    from action_groups import ACTION_GROUPS
    from executor import run_group_actions
    from logger import get_logger

    logger = get_logger()

    group = next((g for g in ACTION_GROUPS if g["name"] == default_group), None)
    if not group:
        logger.warning(f"Nhóm mặc định '{default_group}' không còn tồn tại")
        return True

    logger.info(f"[DEFAULT] Bắt đầu chạy nhóm mặc định '{default_group}' cho {instance_name}")
    try:
        run_group_actions(instance_name, group["actions"], group_name=default_group)
        logger.info(f"[DEFAULT] Hoàn thành nhóm mặc định cho {instance_name}")
        return True
    except Exception as e:
        logger.error(f"[DEFAULT] Lỗi chạy nhóm mặc định cho {instance_name}: {e}")
        return False