# recorder.py
import pyautogui
import time
import win32gui
import win32con
from config import OPR_WINDOW_X, OPR_WINDOW_Y, OFFSET_X, OFFSET_Y, Y_STEP
from utils import focus_emulator, move_operation_recorder_window, close_operation_recorder, auto_close_messagebox
from ldconsole import launch_instance

def open_operation_recorder_for_instance(instance_name):
    if not focus_emulator(instance_name):
        print(f"[REC] Không focus được {instance_name}, thử launch...")
        launch_instance(instance_name)
        time.sleep(12)  # đợi giả lập khởi động
        if not focus_emulator(instance_name):
            auto_close_messagebox("error", "Lỗi", f"Không thể focus giả lập: {instance_name}")
            return False
    
    pyautogui.hotkey('ctrl', '8')
    time.sleep(1.2)
    print(f"[REC] Đã cố mở Operation Recorder cho {instance_name}")
    return True

def run_record_line(instance_name, line_number):
    print(f"[REC] Chạy dòng {line_number} trên {instance_name}")
    
    # Đảm bảo giả lập đang chạy và focus
    if not focus_emulator(instance_name):
        launch_instance(instance_name)
        time.sleep(12)
        if not focus_emulator(instance_name):
            auto_close_messagebox("error", "Lỗi", f"Không thể focus {instance_name} sau khi launch")
            return False
    
    # Mở recorder
    if not open_operation_recorder_for_instance(instance_name):
        return False
    
    # Di chuyển và click vào dòng
    if not move_operation_recorder_window():
        print(f"[REC] Không tìm thấy cửa sổ Operation Recorder")
        close_operation_recorder()
        return False
    
    click_x = OPR_WINDOW_X + OFFSET_X
    click_y = OPR_WINDOW_Y + OFFSET_Y + (line_number - 1) * Y_STEP
    
    pyautogui.moveTo(click_x, click_y, duration=0.3)
    pyautogui.click()
    time.sleep(0.8)
    
    # Đóng recorder
    close_operation_recorder()
    time.sleep(1.0)
    
    # Focus lại giả lập
    if not focus_emulator(instance_name):
        print(f"[REC] Cảnh báo: Không focus lại được {instance_name} sau khi chạy script")
    
    print(f"[REC] Hoàn thành chạy dòng {line_number} trên {instance_name}")
    return True