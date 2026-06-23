import pyautogui
import time
import win32gui
import win32con
import threading
import traceback
from datetime import datetime

from ldconsole import launch_instance, quit_instance
from recorder import run_record_line
from action_groups import ACTION_GROUPS
from utils import auto_close_messagebox, focus_emulator, move_operation_recorder_window, close_operation_recorder
from utils import run_default_group_if_exists   # ← Sửa thành import từ utils
from logger import get_logger

logger = get_logger()

# Lock để tránh xung đột phím/chuột giữa các thread
key_lock = threading.Lock()

def safe_execute(func, *args, **kwargs):
    """Wrapper an toàn cho mọi hành động"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Lỗi trong {func.__name__}: {e}\n{traceback.format_exc()}")
        return False

def get_ldplayer_hwnd(instance_name):
    try:
        hwnd = win32gui.FindWindow(None, instance_name)
        if hwnd == 0:
            logger.warning(f"Không tìm thấy hwnd cho instance '{instance_name}'")
            return None
        return hwnd
    except Exception as e:
        logger.error(f"Lỗi lấy hwnd {instance_name}: {e}")
        return None

def wake_up_ldplayer(instance_name):
    """Trick Ctrl+8 mở-đóng Recorder để đánh thức giả lập"""
    try:
        logger.debug(f"[WAKE] Bắt đầu trick Ctrl+8 cho {instance_name}")
        pyautogui.hotkey('ctrl', '8')
        time.sleep(0.6)

        if not safe_execute(move_operation_recorder_window):
            logger.warning(f"Không di chuyển được Operation Recorder cho {instance_name}")

        time.sleep(0.5)
        safe_execute(close_operation_recorder)
        time.sleep(0.5)

        logger.info(f"[WAKE] Hoàn thành trick Ctrl+8 cho {instance_name}")
        return True
    except Exception as e:
        logger.error(f"[WAKE] Lỗi trick cho {instance_name}: {e}")
        return False

def run_key_press(instance_name, key):
    """Gửi phím với retry và wake_up khi lỗi focus"""
    with key_lock:
        old_x, old_y = pyautogui.position()
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.debug(f"[KEY] Thử gửi phím '{key}' cho {instance_name} (lần {attempt+1}/{max_retries})")

                hwnd = get_ldplayer_hwnd(instance_name)
                if not hwnd:
                    logger.warning(f"[KEY] Không tìm thấy hwnd cho {instance_name}")
                    if attempt < max_retries - 1:
                        time.sleep(0.5)
                        continue
                    return False

                # Focus cửa sổ
                for _ in range(2):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(hwnd)
                    time.sleep(0.25)

                # Nếu là lần thử sau lần 1 → thực hiện wake_up
                if attempt > 0:
                    logger.info(f"[KEY] Thử wake_up_ldplayer lần {attempt}")
                    wake_up_ldplayer(instance_name)
                    time.sleep(0.6)

                # Focus lại sau wake_up
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.4)

                # Gửi phím
                if '+' in key:
                    keys = [k.strip() for k in key.split('+')]
                    pyautogui.hotkey(*keys)
                else:
                    pyautogui.press(key)

                # Restore chuột ngay lập tức
                pyautogui.moveTo(old_x, old_y, duration=0)

                logger.info(f"[KEY] Đã gửi phím '{key}' cho {instance_name} thành công")
                return True

            except Exception as e:
                logger.warning(f"[KEY] Lỗi lần {attempt+1} khi gửi '{key}' cho {instance_name}: {e}")
                
                if attempt < max_retries - 1:
                    time.sleep(0.7)   # chờ một chút trước khi thử lại
                    continue
                else:
                    logger.error(f"[KEY] Không gửi được phím '{key}' cho {instance_name} sau {max_retries} lần thử")
                    return False

        # Nếu thoát vòng lặp mà không return
        try:
            pyautogui.moveTo(old_x, old_y, duration=0)
        except:
            pass
        return False

def execute_single_job(job):
    try:
        logger.info(f"[EXEC] Bắt đầu thực thi job: {job}")

        # === KHÔNG chạy nhóm mặc định ở đây nữa (đã chạy ở mức group) ===

        if job.job_type == "record":
            success = safe_execute(run_record_line, job.instance, int(job.value))
        elif job.job_type == "key":
            success = safe_execute(run_key_press, job.instance, job.value)
        elif job.job_type == "launch":
            success = safe_execute(launch_instance, job.instance)
        elif job.job_type == "quit":
            success = safe_execute(quit_instance, job.instance)
        elif job.job_type == "notification":
            auto_close_messagebox("info", "Thông báo", f"Đã đến giờ {job.time_str[:-3]}")
            success = True
        else:
            logger.warning(f"Loại job không hỗ trợ: {job.job_type}")
            success = False

        job.status = "Đã chạy" if success else "Lỗi"
        logger.info(f"[EXEC] Kết thúc job {job.job_type} trên {job.instance} → {job.status}")
        return success

    except Exception as e:
        logger.error(f"[EXEC] Lỗi nghiêm trọng khi chạy job {job}: {e}\n{traceback.format_exc()}")
        job.status = "Lỗi"
        return False

def run_group_actions(instance, actions, visited=None, group_name="", parent_instance=""):
    if visited is None:
        visited = set()

    logger.info(f"[GROUP] Bắt đầu chạy nhóm '{group_name}' trên {instance} ({len(actions)} hành động)")

    try:
        for idx, action in enumerate(actions, 1):
            if not isinstance(action, dict):
                logger.error(f"Hành động không phải dict: {action}")
                continue

            action_type = action.get("type")
            value = action.get("value")
            delay = action.get("delay", 0)

            logger.debug(f"[GROUP] Hành động {idx}: {action_type} - {value} (delay {delay}s)")

            try:
                if action_type == "group":
                    sub_name = value
                    if sub_name in visited:
                        logger.warning(f"Tránh vòng lặp nhóm: {sub_name}")
                        continue
                    visited.add(sub_name)
                    sub_group = next((g for g in ACTION_GROUPS if g["name"] == sub_name), None)
                    if sub_group:
                        run_group_actions(instance, sub_group["actions"], visited, sub_name, instance)
                    visited.remove(sub_name)

                elif action_type == "record":
                    safe_execute(run_record_line, instance, int(value))
                elif action_type == "key":
                    wake_up_ldplayer(instance)
                    safe_execute(run_key_press, instance, value)
                elif action_type == "launch":
                    safe_execute(launch_instance, instance)
                elif action_type == "quit":
                    safe_execute(quit_instance, instance)
                else:
                    logger.warning(f"Loại hành động không hỗ trợ: {action_type}")

            except Exception as e:
                logger.error(f"Lỗi hành động {idx} trong nhóm {group_name}: {e}")

            if delay > 0:
                logger.debug(f"Chờ {delay} giây...")
                time.sleep(delay)

        logger.info(f"[GROUP] Hoàn thành nhóm '{group_name}' trên {instance}")
    except Exception as e:
        logger.error(f"Lỗi toàn bộ run_group_actions cho nhóm {group_name}: {e}")