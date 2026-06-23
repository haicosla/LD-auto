# ldconsole.py
import subprocess
import os
from config import LD_CONSOLE_PATH
from utils import auto_close_messagebox

def get_instances():
    if not os.path.exists(LD_CONSOLE_PATH):
        auto_close_messagebox("error", "Lỗi", f"Không tìm thấy ldconsole.exe\n{LD_CONSOLE_PATH}")
        return []
    try:
        out = subprocess.check_output([LD_CONSOLE_PATH, "list2"], stderr=subprocess.STDOUT)
        lines = out.decode('utf-8', errors='ignore').splitlines()
        names = [p.split(',')[1].strip() for p in lines if len(p.split(',')) >= 2 and p.split(',')[1].strip()]
        return names
    except Exception as e:
        auto_close_messagebox("error", "Lỗi", f"Không lấy được danh sách giả lập:\n{e}")
        return []

def launch_instance(name):
    try:
        subprocess.Popen([LD_CONSOLE_PATH, "launch", "--name", name])
        return True
    except Exception as e:
        print(f"[LD] Lỗi launch {name}: {e}")
        return False

def quit_instance(name):
    try:
        subprocess.Popen([LD_CONSOLE_PATH, "quit", "--name", name])
        return True
    except Exception as e:
        print(f"[LD] Lỗi quit {name}: {e}")
        return False