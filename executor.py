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
from utils import run_default_group_if_exists
from logger import get_logger

logger = get_logger()

# Lock để tránh xung đột phím/chuột giữa các thread
key_lock = threading.Lock()

def safe_execute(func, *args, **kwargs):
    """Wrapper an toàn cho mọi hành động - trả về True/False rõ ràng"""
    try:
        result = func(*args, **kwargs)
        # Nếu function trả về True/False, dùng giá trị đó
        if isinstance(result, bool):
            return result
        # Nếu không throw exception, coi là thành công
        return True
    except Exception as e:
        logger.error(f"Lỗi trong {func.__name__}: {e}\n{traceback.format_exc()}")
        return False

def get_ldplayer_hwnd(instance_name):
    """Lấy window handle của LDPlayer instance"""
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

def send_key_to_ldplayer(instance_name, key, use_wake_up=False, max_retries=3):
    """
    Hàm unified gửi phím đến LDPlayer với hỗ trợ wake-up.
    
    Args:
        instance_name: Tên giả lập
        key: Phím cần gửi (ví dụ: 'a', 'ctrl+8', 'alt+ctrl+9')
        use_wake_up: Có dùng Ctrl+8 wake-up trước không (mặc định False)
        max_retries: Số lần retry tối đa (mặc định 3)
    
    Returns:
        True nếu thành công, False nếu thất bại
    """
    with key_lock:
        old_x, old_y = pyautogui.position()
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"[KEY] Thử gửi phím '{key}' cho {instance_name} (lần {attempt+1}/{max_retries})")

                # Lấy hwnd
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

                # Nếu yêu cầu wake-up và không phải lần 1 → thực hiện wake_up
                if use_wake_up and attempt > 0:
                    logger.info(f"[KEY] Thực hiện wake-up cho {instance_name} (lần {attempt})")
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
                time.sleep(0.2)  # ← Thêm delay nhỏ để đảm bảo phím được xử lý

                logger.info(f"[KEY] Đã gửi phím '{key}' cho {instance_name} thành công")
                return True

            except Exception as e:
                logger.warning(f"[KEY] Lỗi lần {attempt+1} khi gửi '{key}' cho {instance_name}: {e}")
                
                if attempt < max_retries - 1:
                    time.sleep(0.7)
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

def run_key_press(instance_name, key):
    """
    Gửi phím đơn giản (không wake-up).
    Wrapper để giữ compatibility với code cũ.
    """
    return send_key_to_ldplayer(instance_name, key, use_wake_up=False)

def execute_single_job(job):
    """Thực thi một job đơn lẻ (không phải nhóm)"""
    try:
        logger.info(f"[EXEC] Bắt đầu thực thi job: {job}")
        success = False

        if job.job_type == "record":
            success = safe_execute(run_record_line, job.instance, int(job.value))
            if success:
                logger.info(f"[EXEC] Job record thành công: dòng {job.value}")
            else:
                logger.error(f"[EXEC] Job record thất bại: dòng {job.value}")
                
        elif job.job_type == "key":
            success = safe_execute(send_key_to_ldplayer, job.instance, job.value, False)
            if success:
                logger.info(f"[EXEC] Job key thành công: {job.value}")
            else:
                logger.error(f"[EXEC] Job key thất bại: {job.value}")
                
        elif job.job_type == "launch":
            success = safe_execute(launch_instance, job.instance)
            if success:
                logger.info(f"[EXEC] Job launch thành công")
                time.sleep(0.5)  # Đảm bảo giả lập có thời gian khởi động
            else:
                logger.error(f"[EXEC] Job launch thất bại")
                
        elif job.job_type == "quit":
            success = safe_execute(quit_instance, job.instance)
            if success:
                logger.info(f"[EXEC] Job quit thành công")
            else:
                logger.error(f"[EXEC] Job quit thất bại")
                
        elif job.job_type == "notification":
            auto_close_messagebox("info", "Thông báo", f"Đã đến giờ {job.time_str[:-3]}")
            success = True
            logger.info(f"[EXEC] Notification thành công")
            
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
    """
    Chạy một nhóm hành động tuần tự.
    
    Args:
        instance: Tên giả lập
        actions: Danh sách hành động (từ action_groups.json)
        visited: Set để tránh vòng lặp nhóm
        group_name: Tên nhóm (cho logging)
        parent_instance: Instance cha (để debug)
    """
    if visited is None:
        visited = set()

    logger.info(f"[GROUP] Bắt đầu chạy nhóm '{group_name}' trên {instance} ({len(actions)} hành động)")

    try:
        action_success_count = 0
        
        for idx, action in enumerate(actions, 1):
            if not isinstance(action, dict):
                logger.error(f"[GROUP] Hành động không phải dict: {action}")
                continue

            action_type = action.get("type")
            value = action.get("value")
            delay = action.get("delay", 0)

            logger.debug(f"[GROUP] Hành động {idx}/{len(actions)}: {action_type} - {value} (delay {delay}s)")

            action_success = False
            try:
                if action_type == "group":
                    # Xử lý nhóm con lồng nhau
                    sub_name = value
                    if sub_name in visited:
                        logger.warning(f"[GROUP] Tránh vòng lặp nhóm: {sub_name}")
                        continue
                    visited.add(sub_name)
                    sub_group = next((g for g in ACTION_GROUPS if g["name"] == sub_name), None)
                    if sub_group:
                        logger.info(f"[GROUP] Chạy nhóm con: {sub_name}")
                        run_group_actions(instance, sub_group["actions"], visited, sub_name, instance)
                        action_success = True
                    else:
                        logger.warning(f"[GROUP] Nhóm con '{sub_name}' không tồn tại")
                    visited.remove(sub_name)

                elif action_type == "record":
                    # Chạy dòng script
                    action_success = safe_execute(run_record_line, instance, int(value))
                    if action_success:
                        logger.info(f"[GROUP] Record dòng {value} thành công")
                    else:
                        logger.error(f"[GROUP] Record dòng {value} thất bại")
                        
                elif action_type == "key":
                    # Gửi phím với wake-up
                    action_success = safe_execute(send_key_to_ldplayer, instance, value, use_wake_up=True)
                    if action_success:
                        logger.info(f"[GROUP] Gửi phím '{value}' thành công")
                    else:
                        logger.error(f"[GROUP] Gửi phím '{value}' thất bại")
                        
                elif action_type == "launch":
                    action_success = safe_execute(launch_instance, instance)
                    if action_success:
                        logger.info(f"[GROUP] Launch thành công")
                        time.sleep(0.5)
                    else:
                        logger.error(f"[GROUP] Launch thất bại")
                        
                elif action_type == "quit":
                    action_success = safe_execute(quit_instance, instance)
                    if action_success:
                        logger.info(f"[GROUP] Quit thành công")
                    else:
                        logger.error(f"[GROUP] Quit thất bại")
                        
                else:
                    logger.warning(f"[GROUP] Loại hành động không hỗ trợ: {action_type}")

                if action_success:
                    action_success_count += 1

            except Exception as e:
                logger.error(f"[GROUP] Lỗi hành động {idx} trong nhóm {group_name}: {e}\n{traceback.format_exc()}")

            # Chờ delay giữa các hành động
            if delay > 0:
                logger.debug(f"[GROUP] Chờ {delay} giây trước hành động tiếp theo...")
                remaining = delay
                while remaining > 0:
                    time.sleep(min(remaining, 1.0))
                    remaining -= 1.0

        logger.info(f"[GROUP] Hoàn thành nhóm '{group_name}' trên {instance} ({action_success_count}/{len(actions)} hành động thành công)")
        return action_success_count == len(actions)
        
    except Exception as e:
        logger.error(f"[GROUP] Lỗi toàn bộ run_group_actions cho nhóm {group_name}: {e}\n{traceback.format_exc()}")
        return False
