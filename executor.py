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

def prepare_ldplayer_for_key(instance_name):
    """
    Chuẩn bị giả lập để nhận phím:
    1. Focus instance
    2. Gửi Ctrl+8 (mở Operation Recorder)
    3. Đóng Recorder
    4. Focus lại instance
    
    Điều này đảm bảo instance luôn sẵn sàng, đặc biệt khi chạy nhiều instances cùng lúc
    """
    try:
        logger.debug(f"[PREP] Chuẩn bị instance '{instance_name}' để nhận phím")
        
        # Bước 1: Focus instance
        hwnd = get_ldplayer_hwnd(instance_name)
        if not hwnd:
            logger.warning(f"[PREP] Không tìm thấy hwnd cho {instance_name}")
            return False
        
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)
        logger.debug(f"[PREP] Đã focus instance {instance_name}")
        
        # Bước 2: Gửi Ctrl+8 (mở Operation Recorder)
        logger.debug(f"[PREP] Gửi Ctrl+8 cho {instance_name}")
        pyautogui.hotkey('ctrl', '8')
        time.sleep(0.8)
        
        # Bước 3: Di chuyển Recorder window
        try:
            safe_execute(move_operation_recorder_window)
        except:
            pass
        
        time.sleep(0.3)
        
        # Bước 4: Đóng Recorder
        logger.debug(f"[PREP] Đóng Operation Recorder")
        safe_execute(close_operation_recorder)
        time.sleep(0.5)
        
        # Bước 5: Focus lại instance
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)
        
        logger.info(f"[PREP] Instance '{instance_name}' đã chuẩn bị sẵn sàng nhận phím")
        return True
        
    except Exception as e:
        logger.error(f"[PREP] Lỗi chuẩn bị instance {instance_name}: {e}")
        return False

def send_key_to_ldplayer(instance_name, key, max_retries=3):
    """
    Hàm unified gửi phím đến LDPlayer.
    
    **MỚI: Luôn làm Ctrl+8 chuẩn bị trước khi gửi phím**
    
    Args:
        instance_name: Tên giả lập
        key: Phím cần gửi (ví dụ: 'a', 'ctrl+8', 'alt+ctrl+9')
        max_retries: Số lần retry tối đa (mặc định 3)
    
    Flow:
    1. Chuẩn bị instance (Ctrl+8 → Close → Focus)
    2. Focus instance
    3. Gửi phím
    4. Restore chuột
    
    Returns:
        True nếu thành công, False nếu thất bại
    """
    with key_lock:
        old_x, old_y = pyautogui.position()
        
        try:
            logger.info(f"[KEY] Bắt đầu gửi phím '{key}' cho {instance_name}")
            
            # === BƯỚC 1: CHUẨN BỊ INSTANCE (Ctrl+8) ===
            if not prepare_ldplayer_for_key(instance_name):
                logger.error(f"[KEY] Không thể chuẩn bị instance '{instance_name}'")
                return False
            
            # === BƯỚC 2: GỬI PHÍM VỚI RETRY ===
            for attempt in range(max_retries):
                try:
                    logger.debug(f"[KEY] Thử gửi phím '{key}' cho {instance_name} (lần {attempt+1}/{max_retries})")

                    # Focus lại trước mỗi lần gửi
                    hwnd = get_ldplayer_hwnd(instance_name)
                    if not hwnd:
                        logger.warning(f"[KEY] Không tìm thấy hwnd cho {instance_name} (lần {attempt+1})")
                        if attempt < max_retries - 1:
                            time.sleep(0.5)
                            continue
                        return False

                    # Focus cửa sổ
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(hwnd)
                    time.sleep(0.3)

                    # Gửi phím
                    if '+' in key:
                        keys = [k.strip() for k in key.split('+')]
                        logger.debug(f"[KEY] Gửi hotkey: {'+'.join(keys)}")
                        pyautogui.hotkey(*keys)
                    else:
                        logger.debug(f"[KEY] Gửi phím: {key}")
                        pyautogui.press(key)

                    time.sleep(0.2)  # Đợi phím được xử lý

                    # Restore chuột ngay lập tức
                    pyautogui.moveTo(old_x, old_y, duration=0)

                    logger.info(f"[KEY] ✅ Đã gửi phím '{key}' cho {instance_name} thành công (lần {attempt+1})")
                    return True

                except Exception as e:
                    logger.warning(f"[KEY] Lỗi lần {attempt+1} khi gửi '{key}' cho {instance_name}: {e}")
                    
                    if attempt < max_retries - 1:
                        logger.debug(f"[KEY] Retry lần {attempt+2}...")
                        time.sleep(0.5)
                        continue
                    else:
                        logger.error(f"[KEY] ❌ Không gửi được phím '{key}' cho {instance_name} sau {max_retries} lần thử")
                        return False

            return False
            
        except Exception as e:
            logger.error(f"[KEY] Lỗi nghiêm trọng khi gửi phím '{key}' cho {instance_name}: {e}")
            return False
        finally:
            try:
                pyautogui.moveTo(old_x, old_y, duration=0)
            except:
                pass

def run_key_press(instance_name, key):
    """
    Gửi phím đơn giản.
    Wrapper để giữ compatibility với code cũ.
    """
    return send_key_to_ldplayer(instance_name, key)

def execute_single_job(job):
    """Thực thi một job đơn lẻ (không phải nhóm)"""
    try:
        logger.info(f"[EXEC] Bắt đầu thực thi job: {job}")
        success = False

        if job.job_type == "record":
            success = safe_execute(run_record_line, job.instance, int(job.value))
            if success:
                logger.info(f"[EXEC] ✅ Job record thành công: dòng {job.value}")
            else:
                logger.error(f"[EXEC] ❌ Job record thất bại: dòng {job.value}")
                
        elif job.job_type == "key":
            success = safe_execute(send_key_to_ldplayer, job.instance, job.value)
            if success:
                logger.info(f"[EXEC] ✅ Job key thành công: {job.value}")
            else:
                logger.error(f"[EXEC] ❌ Job key thất bại: {job.value}")
                
        elif job.job_type == "launch":
            success = safe_execute(launch_instance, job.instance)
            if success:
                logger.info(f"[EXEC] ✅ Job launch thành công")
                time.sleep(0.5)
            else:
                logger.error(f"[EXEC] ❌ Job launch thất bại")
                
        elif job.job_type == "quit":
            success = safe_execute(quit_instance, job.instance)
            if success:
                logger.info(f"[EXEC] ✅ Job quit thành công")
            else:
                logger.error(f"[EXEC] ❌ Job quit thất bại")
                
        elif job.job_type == "notification":
            auto_close_messagebox("info", "Thông báo", f"Đã đến giờ {job.time_str[:-3]}")
            success = True
            logger.info(f"[EXEC] ✅ Notification thành công")
            
        else:
            logger.warning(f"[EXEC] ⚠️ Loại job không hỗ trợ: {job.job_type}")
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
    
    **MỚI: Trước khi gửi PHÍM BẤT CỨ LÚC NÀO đều làm Ctrl+8 chuẩn bị trước**
    
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
                        action_success = run_group_actions(instance, sub_group["actions"], visited, sub_name, instance)
                    else:
                        logger.warning(f"[GROUP] ❌ Nhóm con '{sub_name}' không tồn tại")
                    visited.remove(sub_name)

                elif action_type == "record":
                    # Chạy dòng script
                    action_success = safe_execute(run_record_line, instance, int(value))
                    if action_success:
                        logger.info(f"[GROUP] ✅ Record dòng {value} thành công")
                    else:
                        logger.error(f"[GROUP] ❌ Record dòng {value} thất bại")
                        
                elif action_type == "key":
                    # **MỚI: GỬI PHÍM LUÔN CÓ Ctrl+8 CHUẨN BỊ TRƯỚC**
                    action_success = safe_execute(send_key_to_ldplayer, instance, value)
                    if action_success:
                        logger.info(f"[GROUP] ✅ Gửi phím '{value}' thành công (có Ctrl+8 chuẩn bị)")
                    else:
                        logger.error(f"[GROUP] ❌ Gửi phím '{value}' thất bại")
                        
                elif action_type == "launch":
                    action_success = safe_execute(launch_instance, instance)
                    if action_success:
                        logger.info(f"[GROUP] ✅ Launch thành công")
                        time.sleep(0.5)
                    else:
                        logger.error(f"[GROUP] ❌ Launch thất bại")
                        
                elif action_type == "quit":
                    action_success = safe_execute(quit_instance, instance)
                    if action_success:
                        logger.info(f"[GROUP] ✅ Quit thành công")
                    else:
                        logger.error(f"[GROUP] ❌ Quit thất bại")
                        
                else:
                    logger.warning(f"[GROUP] ⚠️ Loại hành động không hỗ trợ: {action_type}")

                if action_success:
                    action_success_count += 1

            except Exception as e:
                logger.error(f"[GROUP] ❌ Lỗi hành động {idx} trong nhóm {group_name}: {e}\n{traceback.format_exc()}")

            # Chờ delay giữa các hành động
            if delay > 0:
                logger.debug(f"[GROUP] ⏳ Chờ {delay} giây trước hành động tiếp theo...")
                remaining = delay
                while remaining > 0:
                    time.sleep(min(remaining, 1.0))
                    remaining -= 1.0

        logger.info(f"[GROUP] ✅ Hoàn thành nhóm '{group_name}' trên {instance} ({action_success_count}/{len(actions)} hành động thành công)")
        return action_success_count == len(actions)
        
    except Exception as e:
        logger.error(f"[GROUP] ❌ Lỗi toàn bộ run_group_actions cho nhóm {group_name}: {e}\n{traceback.format_exc()}")
        return False
