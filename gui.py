import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
import pyautogui
import win32gui
import win32con
import sys
import os
import json
from datetime import datetime, timedelta

# Import từ config
from config import *

# Import từ utils
from utils import auto_close_messagebox, focus_emulator, validate_time_input, validate_key_input

# Import từ ldconsole
from ldconsole import get_instances, launch_instance, quit_instance

# Import từ recorder
from recorder import run_record_line

# Import từ executor
from executor import run_key_press, run_group_actions

# Import từ scheduler
from scheduler import scheduled_checker

# Import từ job
from job import Job, jobs, load_jobs, save_jobs

# Import từ action_groups
from action_groups import ACTION_GROUPS, load_action_groups, save_action_groups

# Import từ logger
from logger import get_logger

# Import từ các module tách ra
from gui_defaults import (
    set_default_group as set_default_group_module,
    clear_default_group as clear_default_group_module,
    update_default_label as update_default_label_module,
    default_group_name as default_group_name_module,
    default_status_label as default_status_label_module,
)

from gui_jobs_list import (
    update_jobs_list,
    remove_job,
    edit_job,
    reschedule_job,
    reschedule_all,
    toggle_pause,
    stop_job,
    stop_repeating,
    clear_all_completed_repeating,
    schedule_list_frame as schedule_list_frame_module,
    root as root_module,
    pause_button as pause_button_module,
    is_paused,
    running_threads,
)

from gui_group_management import (
    update_group_combobox,
    manage_groups,
    edit_group_window,
    groups_listbox as groups_listbox_module,
    group_combo as group_combo_module,
    group_var as group_var_module,
)

logger = get_logger()

# Biến toàn cục
var_dict = {}
record_line_var = None
schedule_time_var = None
key_input_var = None
group_var = None
group_combo = None
delay_time_var = None
subtract_time_var = None
repeat_interval_var = None
schedule_list_frame = None
root = None
groups_listbox = None
default_group_name = None
default_status_label = None
pause_button = None
canvas = None
scrollable_frame = None
is_paused = False

def set_default_group():
    global default_group_name, default_status_label
    group_name = group_var.get()
    if not group_name:
        auto_close_messagebox("error", "Lỗi", "Vui lòng chọn một nhóm trước!")
        return
    
    default_group_name = group_name
    from action_groups import save_default_group
    save_default_group()
    if default_status_label:
        default_status_label.config(text=f"Mặc định hiện tại: {group_name}")
    auto_close_messagebox("info", "Thành công", f"Đã đặt nhóm '{group_name}' làm hành động mặc định.")
    print(f"[DEFAULT] Đã lưu nhóm mặc định: {default_group_name}")

def clear_default_group():
    global default_group_name, default_status_label
    default_group_name = None
    from action_groups import save_default_group
    save_default_group()
    if default_status_label:
        default_status_label.config(text="Chưa có nhóm mặc định")
    auto_close_messagebox("info", "Thành công", "Đã xóa nhóm mặc định.")
    print("[DEFAULT] Đã xóa và lưu nhóm mặc định")

def update_default_label():
    global default_group_name, default_status_label
    if default_status_label:
        text = f"Mặc định hiện tại: {default_group_name}" if default_group_name else "Chưa có nhóm mặc định"
        default_status_label.config(text=text)

def remove_group_jobs(group_jobs):
    for job in group_jobs:
        if job in jobs:
            jobs.remove(job)
    update_jobs_list()
    save_jobs()
    messagebox.showinfo("Thông báo", "Đã xóa nhóm công việc.")

def launch_selected():
    selected = [name for name, var in var_dict.items() if var.get()]
    for name in selected:
        launch_instance(name)

def close_selected():
    selected = [name for name, var in var_dict.items() if var.get()]
    for name in selected:
        quit_instance(name)

def open_operation_recorder():
    selected = [name for name, var in var_dict.items() if var.get()]
    for name in selected:
        if focus_emulator(name):
            pyautogui.hotkey('ctrl', '8')
            time.sleep(1)
            print(f"[LOG] Đã mở Operation Recorder cho {name}")
        else:
            auto_close_messagebox("error", "Lỗi", f"Không tìm thấy cửa sổ giả lập: {name}")

def bring_to_front():
    selected = [name for name, var in var_dict.items() if var.get()]
    if not selected:
        auto_close_messagebox("warning", "Chọn giả lập", "Vui lòng chọn ít nhất một giả lập để đưa lên.")
        return
    for name in selected:
        focus_emulator(name)
        print(f"[LOG] Đã đưa giả lập {name} lên trên cùng")

def calculate_time():
    delay_time = delay_time_var.get().strip()
    subtract_time = subtract_time_var.get().strip() or "00:00"
  
    delay_time = validate_time_input(delay_time)
    subtract_time = validate_time_input(subtract_time)
  
    if not delay_time:
        auto_close_messagebox("error", "Lỗi", "Vui lòng nhập giờ chờ theo định dạng HHMM hoặc HH:MM")
        return
  
    try:
        now = datetime.now()
        delay_dt = datetime.strptime(delay_time, "%H:%M:%S")
        subtract_dt = datetime.strptime(subtract_time, "%H:%M:%S")
        new_time = now + timedelta(hours=delay_dt.hour, minutes=delay_dt.minute) - timedelta(hours=subtract_dt.hour, minutes=subtract_dt.minute)
        schedule_time_var.set(new_time.strftime("%H:%M"))
        auto_close_messagebox("info", "Thành công", f"Đã tính giờ mới: {new_time.strftime('%H:%M')} (Hiện tại: {now.strftime('%H:%M')})")
    except ValueError:
        auto_close_messagebox("error", "Lỗi", "Định dạng thời gian không hợp lệ!")

def set_schedule():
    time_input = schedule_time_var.get().strip()
    time_input = validate_time_input(time_input)
    if not time_input:
        auto_close_messagebox("error", "Lỗi", "Vui lòng nhập giờ theo định dạng HHMM hoặc HH:MM")
        return
  
    line_text = record_line_var.get().strip()
    if not line_text.isdigit():
        auto_close_messagebox("error", "Lỗi", "Vui lòng nhập số dòng hợp lệ!")
        return
  
    line_num = int(line_text)
    selected = [name for name, var in var_dict.items() if var.get()]
    if not selected:
        auto_close_messagebox("error", "Lỗi", "Vui lòng chọn ít nhất một giả lập để hẹn giờ.")
        return
  
    all_jobs = []
   
    for name in selected:
        group_jobs = []
        current_time = datetime.strptime(time_input, "%H:%M:%S").replace(
            year=datetime.now().year, month=datetime.now().month, day=datetime.now().day
        )
        if current_time < datetime.now():
            current_time += timedelta(days=1)
       
        time_str = current_time.strftime("%H:%M:%S")
        job = Job(time_str, name, "record", line_num)
        group_jobs.append(job)
       
        group_job = Job(time_input, name, "record", line_num, is_group=True, group_jobs=group_jobs)
        all_jobs.append(group_job)
   
    jobs.extend(all_jobs)
    update_jobs_list()
    save_jobs()
    auto_close_messagebox("info", "Đặt giờ", f"Đã hẹn chạy lúc {time_input[:-3]} cho {len(selected)} giả lập (có chèn nhóm mặc định nếu có).")

def set_key_schedule():
    time_input = schedule_time_var.get().strip()
    time_input = validate_time_input(time_input)
    if not time_input:
        auto_close_messagebox("error", "Lỗi", "Vui lòng nhập giờ theo định dạng HHMM hoặc HH:MM")
        return
  
    key = key_input_var.get().strip()
    if not validate_key_input(key):
        auto_close_messagebox("error", "Lỗi", "Vui lòng nhập phím hợp lệ!")
        return
  
    selected = [name for name, var in var_dict.items() if var.get()]
    if not selected:
        auto_close_messagebox("error", "Lỗi", "Vui lòng chọn ít nhất một giả lập.")
        return
  
    all_jobs = []
   
    for name in selected:
        group_jobs = []
        current_time = datetime.strptime(time_input, "%H:%M:%S").replace(
            year=datetime.now().year, month=datetime.now().month, day=datetime.now().day
        )
        if current_time < datetime.now():
            current_time += timedelta(days=1)
       
        time_str = current_time.strftime("%H:%M:%S")
        job = Job(time_str, name, "key", key)
        all_jobs.append(job)
       
        print(f"[SCHED] Thêm job gửi phím '{key}' cho {name} lúc {time_str}")
   
    jobs.extend(all_jobs)
    update_jobs_list()
    save_jobs()
    auto_close_messagebox("info", "Đặt giờ", f"Đã hẹn gửi phím {key} lúc {time_input[:-3]} cho {len(selected)} giả lập (có chèn nhóm mặc định nếu có).")

def set_notification_schedule():
    time_input = schedule_time_var.get().strip()
    time_input = validate_time_input(time_input)
    if not time_input:
        auto_close_messagebox("error", "Lỗi", "Vui lòng nhập giờ hợp lệ!")
        return
  
    all_jobs = []
   
    selected = [name for name, var in var_dict.items() if var.get()]
    if selected:
        for name in selected:
            group_jobs = []
            current_time = datetime.strptime(time_input, "%H:%M:%S").replace(
                year=datetime.now().year, month=datetime.now().month, day=datetime.now().day
            )
            if current_time < datetime.now():
                current_time += timedelta(days=1)
           
            time_str = current_time.strftime("%H:%M:%S")
            notif_job = Job(time_str, "Thông báo", "notification")
            group_jobs.append(notif_job)
           
            group_job = Job(time_input, "Thông báo", "notification", is_group=True, group_jobs=group_jobs)
            all_jobs.append(group_job)
    else:
        job = Job(time_input, "Thông báo", "notification")
        all_jobs.append(job)
   
    jobs.extend(all_jobs)
    update_jobs_list()
    save_jobs()
    auto_close_messagebox("info", "Đặt thông báo", f"Đã hẹn thông báo lúc {time_input[:-3]} (có chèn nhóm mặc định nếu có).")

def set_launch_schedule():
    time_input = schedule_time_var.get().strip()
    time_input = validate_time_input(time_input)
    if not time_input:
        auto_close_messagebox("error", "Lỗi", "Vui lòng nhập giờ hợp lệ!")
        return
 
    selected = [name for name, var in var_dict.items() if var.get()]
    if not selected:
        auto_close_messagebox("error", "Lỗi", "Vui lòng chọn ít nhất một giả lập.")
        return
 
    all_jobs = []
  
    for name in selected:
        group_jobs = []
        current_time = datetime.strptime(time_input, "%H:%M:%S").replace(
            year=datetime.now().year, month=datetime.now().month, day=datetime.now().day
        )
        if current_time < datetime.now():
            current_time += timedelta(days=1)
      
        time_str = current_time.strftime("%H:%M:%S")
        job = Job(time_str, name, "launch")
        group_jobs.append(job)
      
        group_job = Job(time_input, name, "launch", group_jobs=group_jobs)
        all_jobs.append(group_job)
  
    jobs.extend(all_jobs)
    update_jobs_list()
    save_jobs()
    auto_close_messagebox("info", "Đặt giờ khởi động", f"Đã hẹn khởi động lúc {time_input[:-3]} cho {len(selected)} giả lập (có chèn nhóm mặc định nếu có).")

def set_quit_schedule():
    time_input = schedule_time_var.get().strip()
    time_input = validate_time_input(time_input)
    if not time_input:
        auto_close_messagebox("error", "Lỗi", "Vui lòng nhập giờ hợp lệ!")
        return
 
    selected = [name for name, var in var_dict.items() if var.get()]
    if not selected:
        auto_close_messagebox("error", "Lỗi", "Vui lòng chọn ít nhất một giả lập.")
        return
 
    all_jobs = []
  
    for name in selected:
        group_jobs = []
        current_time = datetime.strptime(time_input, "%H:%M:%S").replace(
            year=datetime.now().year, month=datetime.now().month, day=datetime.now().day
        )
        if current_time < datetime.now():
            current_time += timedelta(days=1)
      
        time_str = current_time.strftime("%H:%M:%S")
        job = Job(time_str, name, "quit")
        group_jobs.append(job)
      
        group_job = Job(time_input, name, "quit", group_jobs=group_jobs)
        all_jobs.append(group_job)
  
    jobs.extend(all_jobs)
    update_jobs_list()
    save_jobs()
    auto_close_messagebox("info", "Đặt giờ tắt", f"Đã hẹn tắt lúc {time_input[:-3]} cho {len(selected)} giả lập (có chèn nhóm mặc định nếu có).")

def set_group_schedule():
    time_input = schedule_time_var.get().strip()
    time_input = validate_time_input(time_input)
    if not time_input:
        auto_close_messagebox("error", "Lỗi", "Vui lòng nhập giờ theo định dạng HHMM hoặc HH:MM")
        return
    group_name = group_var.get()
    if not group_name:
        auto_close_messagebox("error", "Lỗi", "Vui lòng chọn một nhóm hành động!")
        return
    selected = [name for name, var in var_dict.items() if var.get()]
    if not selected:
        auto_close_messagebox("error", "Lỗi", "Vui lòng chọn ít nhất một giả lập để hẹn giờ nhóm.")
        return
    
    repeat_input = repeat_interval_var.get().strip()
    repeat_seconds = 0
    if repeat_input and repeat_input != "00:00" and repeat_input.lower() != "không":
        if repeat_input == "24:00":
            repeat_seconds = 24 * 3600
        else:
            validated = validate_time_input(repeat_input)
            if validated:
                hh_mm = validated[:-3]
                h, m = map(int, hh_mm.split(':'))
                repeat_seconds = h * 3600 + m * 60
            else:
                try:
                    total_min = int(repeat_input)
                    repeat_seconds = total_min * 60
                except ValueError:
                    auto_close_messagebox("error", "Lỗi", f"Khoảng lặp lại không hợp lệ: {repeat_input}\nVui lòng nhập HH:MM (ví dụ 01:00, 24:00) hoặc số phút (ví dụ 60)")
                    return
        
        if repeat_seconds <= 0:
            repeat_seconds = 0
            
    now = datetime.now()
    try:
        start_time = datetime.strptime(time_input, "%H:%M:%S").replace(
            year=now.year, month=now.month, day=now.day
        )
        if start_time < now:
            start_time += timedelta(days=1)
    except ValueError:
        auto_close_messagebox("error", "Lỗi", "Định dạng thời gian không hợp lệ!")
        return
    
    group = next((g for g in ACTION_GROUPS if g["name"] == group_name), None)
    if not group:
        auto_close_messagebox("error", "Lỗi", f"Nhóm {group_name} không tồn tại!")
        return
    
    all_group_jobs = []
    for name in selected:
        group_jobs = []
        current_time = start_time
        
        for idx, action in enumerate(group["actions"], 1):
            action_time = current_time
            time_str = action_time.strftime("%H:%M:%S")
            if action["type"] == "group":
                sub_job = Job(time_str, name, "group", action["value"], group_name)
                group_jobs.append(sub_job)
            else:
                job = Job(time_str, name, action["type"], action["value"], group_name)
                group_jobs.append(job)
            print(f"[LOG] Thêm job con {idx} cho nhóm {group_name} trên {name}: {action['type']} - {action['value']} lúc {time_str}")
            current_time += timedelta(seconds=action["delay"])
        
        group_job = Job(time_input, name, group_name=group_name, is_group=True, group_jobs=group_jobs)
        if repeat_seconds > 0:
            group_job.repeat_interval = repeat_seconds
            group_job.is_repeating = True
        else:
            group_job.is_repeating = False
        all_group_jobs.append(group_job)
        print(f"[LOG] Thêm job nhóm {group_name} trên {name} lúc {time_input}")
    
    jobs.extend(all_group_jobs)
    update_jobs_list()
    save_jobs()
    save_action_groups()
    msg = f"Đã hẹn nhóm {group_name} lúc {time_input[:-3]} cho {len(selected)} giả lập"
    if repeat_seconds > 0:
        hours = repeat_seconds // 3600
        minutes = (repeat_seconds % 3600) // 60
        msg += f". Lặp lại sau {hours} giờ {minutes} phút (tự động tạo lịch mới sau mỗi lần chạy xong)."
    else:
        msg += " (không lặp lại)."
    auto_close_messagebox("info", "Đặt giờ nhóm", msg + " (có chèn nhóm mặc định nếu có).")

def run_group_now():
    group_name = group_var.get()
    if not group_name:
        auto_close_messagebox("error", "Lỗi", "Vui lòng chọn một nhóm hành động!")
        return
   
    selected = [name for name, var in var_dict.items() if var.get()]
    if not selected:
        auto_close_messagebox("error", "Lỗi", "Vui lòng chọn ít nhất một giả lập để chạy nhóm.")
        return
   
    group = next((g for g in ACTION_GROUPS if g["name"] == group_name), None)
    if not group:
        auto_close_messagebox("error", "Lỗi", f"Nhóm {group_name} không tồn tại!")
        return
   
    success_count = 0
    for name in selected:
        print(f"[LOG] Bắt đầu chạy nhóm {group_name} ngay lập tức trên {name}")
       
        if default_group_name:
            default_group = next((g for g in ACTION_GROUPS if g["name"] == default_group_name), None)
            if default_group:
                print(f"[DEFAULT] Chạy nhóm mặc định '{default_group_name}' trước trên {name}")
                run_group_actions(name, default_group["actions"])
                print(f"[DEFAULT] Hoàn thành nhóm mặc định '{default_group_name}' trên {name}")
                time.sleep(5)
            else:
                print(f"[DEFAULT] Nhóm mặc định '{default_group_name}' không tồn tại")
       
        run_group_actions(name, group["actions"])
        success_count += 1
   
    auto_close_messagebox("info", "Thành công", f"Đã chạy nhóm {group_name} trên {success_count}/{len(selected)} giả lập (có chạy nhóm mặc định trước nếu có).")

def run_key_now():
    key = key_input_var.get().strip()
    if not validate_key_input(key):
        auto_close_messagebox("error", "Lỗi", "Vui lòng nhập phím hợp lệ!")
        return
  
    selected = [name for name, var in var_dict.items() if var.get()]
    if not selected:
        auto_close_messagebox("error", "Lỗi", "Vui lòng chọn ít nhất một giả lập.")
        return
  
    for name in selected:
        try:
            success = run_key_press(name, key)
            if not success:
                raise Exception("Không thể gửi phím")
        except Exception as e:
            error_msg = f"Không thể gửi phím trên {name}: {e}"
            auto_close_messagebox("error", "Lỗi", error_msg)
            print(f"[LOG] {error_msg}")

def run_now():
    line_text = record_line_var.get().strip()
    if not line_text.isdigit():
        auto_close_messagebox("error", "Lỗi", "Vui lòng nhập số dòng hợp lệ!")
        return
  
    line_num = int(line_text)
    selected = [name for name, var in var_dict.items() if var.get()]
    if not selected:
        auto_close_messagebox("error", "Lỗi", "Vui lòng chọn ít nhất một giả lập.")
        return
  
    for name in selected:
        try:
            success = run_record_line(name, line_num)
            if not success:
                raise Exception("Không thể chạy script")
        except Exception as e:
            error_msg = f"Không thể chạy trên {name}: {e}"
            auto_close_messagebox("error", "Lỗi", error_msg)
            print(f"[LOG] {error_msg}")

def run_job_now(display_index):
    display_jobs = [j for j in jobs if (not j.group_name or j.is_group) and j.status == "Đã hẹn"]
    sorted_display_jobs = sorted(display_jobs, key=lambda j: j.scheduled_time if j.scheduled_time else datetime.max)
  
    if 0 <= display_index < len(sorted_display_jobs):
        job = sorted_display_jobs[display_index]
        try:
            if job.is_group:
                group = next((g for g in ACTION_GROUPS if g["name"] == job.group_name), None)
                if not group:
                    raise Exception(f"Nhóm {job.group_name} không tồn tại")
                if not job.group_jobs:
                    pass
                for idx, action in enumerate(group["actions"]):
                    if idx >= len(job.group_jobs):
                        break
                    child_job = job.group_jobs[idx]
                    print(f"[LOG] Chạy job con {child_job.job_type} cho {child_job.instance} (Hành động {idx+1})")
                    if child_job.job_type == "record":
                        success = run_record_line(child_job.instance, int(child_job.value))
                        child_job.status = "Đã chạy" if success else "Lỗi"
                    elif child_job.job_type == "key":
                        success = run_key_press(child_job.instance, child_job.value)
                        child_job.status = "Đã gửi" if success else "Lỗi"
                    elif child_job.job_type == "launch":
                        success = launch_instance(child_job.instance)
                        child_job.status = "Đã khởi động" if success else "Lỗi"
                    elif child_job.job_type == "quit":
                        success = quit_instance(child_job.instance)
                        child_job.status = "Đã tắt" if success else "Lỗi"
                    if action["delay"] > 0:
                        print(f"[LOG] Chờ {action['delay']}s trước khi chạy hành động tiếp theo")
                        time.sleep(action["delay"])
                    if child_job.status == "Lỗi":
                        break
                job.status = "Đã chạy" if all(cj.status in ["Đã chạy", "Đã gửi", "Đã khởi động", "Đã tắt"] for cj in job.group_jobs) else "Lỗi"
                job.current_child_index = len(job.group_jobs)
            else:
                if job.job_type == "record":
                    success = run_record_line(job.instance, int(job.value))
                    job.status = "Đã chạy" if success else "Lỗi"
                elif job.job_type == "key":
                    success = run_key_press(job.instance, job.value)
                    job.status = "Đã gửi" if success else "Lỗi"
                elif job.job_type == "launch":
                    success = launch_instance(job.instance)
                    job.status = "Đã khởi động" if success else "Lỗi"
                elif job.job_type == "quit":
                    success = quit_instance(job.instance)
                    job.status = "Đã tắt" if success else "Lỗi"
                elif job.job_type == "notification":
                    auto_close_messagebox("info", "Thông báo", f"Đã đến giờ {job.time_str[:-3]}")
                    job.status = "Đã thông báo"
            update_jobs_list()
            save_jobs()
        except Exception as e:
            error_msg = f"Lỗi thực hiện công việc [{job.job_type}]: {e}"
            print(f"[LOG] {error_msg}")
            auto_close_messagebox("error", "Lỗi", error_msg)
            job.status = "Lỗi"

def create_gui():
    global var_dict, record_line_var, schedule_time_var, key_input_var, group_var, group_combo
    global delay_time_var, subtract_time_var, repeat_interval_var, schedule_list_frame, root, default_status_label
    global pause_button, canvas, scrollable_frame
    
    load_action_groups()
    load_jobs()
    
    from action_groups import load_default_group
    load_default_group()
    
    root = tk.Tk()
    filename = os.path.basename(sys.argv[0]) if sys.argv else "unknown.py"
    root.title(f"LDPlayer Multi-Launcher + Script Clicker ({filename})")
    root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
    root.protocol("WM_DELETE_WINDOW", on_closing)
  
    main_frame = ttk.Frame(root, padding=10)
    main_frame.pack(fill="both", expand=True)
    
    # Ô chọn và lưu đường dẫn ldconsole.exe
    path_frame = ttk.LabelFrame(main_frame, text="Đường dẫn ldconsole.exe (lưu rồi reset để update)")
    path_frame.pack(fill="x", pady=5)
    
    ld_path_var = tk.StringVar(value=LD_CONSOLE_PATH or "Chưa chọn")
    
    ttk.Label(path_frame, text="Đường dẫn hiện tại:").pack(side="left", padx=5)
    ttk.Entry(path_frame, textvariable=ld_path_var, width=30).pack(side="left", padx=5, fill="x", expand=True)
    
    def browse_ld_path():
        file_path = filedialog.askopenfilename(
            title="Chọn ldconsole.exe",
            filetypes=[("Executable files", "*.exe"), ("All files", "*.*")],
            initialdir=os.path.dirname(LD_CONSOLE_PATH) if LD_CONSOLE_PATH else os.getcwd()
        )
        if file_path:
            ld_path_var.set(file_path)
    
    ttk.Button(path_frame, text="Chọn file", command=browse_ld_path).pack(side="left", padx=5)
    
    def save_ld_path():
        new_path = ld_path_var.get().strip()
        if new_path:
            config_data = {}
            if os.path.exists("config.json"):
                try:
                    with open("config.json", 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                except Exception as e:
                    print(f"[CONFIG] Lỗi đọc config.json cũ: {e}. Tạo mới.")
                    config_data = {}
            
            config_data['LD_CONSOLE_PATH'] = new_path
            
            try:
                with open("config.json", 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, ensure_ascii=False, indent=4)
                messagebox.showinfo("Thông báo", f"Đã lưu đường dẫn '{new_path}' vào config.json.\nCác biến offset giữ nguyên.\nReset chương trình để update danh sách giả lập.")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không lưu được config.json: {e}")
        else:
            messagebox.showwarning("Lỗi", "Đường dẫn không được đ��� trống!")   
    
    ttk.Button(path_frame, text="Lưu", command=save_ld_path).pack(side="right", padx=5)
    
    emulator_frame = ttk.LabelFrame(main_frame, text="Chọn các giả lập")
    emulator_frame.pack(fill="x", pady=5)
  
    instances = get_instances()
    var_dict = {}
    for name in instances:
        frame = ttk.Frame(emulator_frame)
        frame.pack(fill="x", pady=1)
      
        var = tk.BooleanVar()
        ttk.Checkbutton(frame, text=name, variable=var).pack(side="left", padx=5)
        var_dict[name] = var
      
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(side="right")
      
        ttk.Button(btn_frame, text="Khởi", width=5, command=launch_selected).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Đóng", width=5, command=close_selected).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="OpRec", width=5, command=open_operation_recorder).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Lên", width=5, command=bring_to_front).pack(side="left", padx=2)
  
    record_frame = ttk.Frame(main_frame)
    record_frame.pack(fill="x", pady=10)
    ttk.Label(record_frame, text="Chạy dòng số (VD: 1, 2, 3...):").pack(anchor="w")
    record_line_var = tk.StringVar()
    tk.Entry(record_frame, textvariable=record_line_var).pack(fill="x")
  
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill="x", pady=5)
    ttk.Button(button_frame, text="Đặt giờ chạy", command=set_schedule).pack(side="left", expand=True, fill="x", padx=(0, 5))
    ttk.Button(button_frame, text="Chạy ngay", command=run_now).pack(side="right", expand=True, fill="x", padx=(5, 0))
  
    schedule_time_frame = ttk.Frame(main_frame)
    schedule_time_frame.pack(fill="x", pady=10)
    ttk.Label(schedule_time_frame, text="Giờ chạy (HHMM hoặc HH:MM):").pack(anchor="w")
    schedule_time_var = tk.StringVar()
    tk.Entry(schedule_time_frame, textvariable=schedule_time_var).pack(fill="x")
  
    calc_frame = ttk.Frame(schedule_time_frame)
    calc_frame.pack(fill="x", pady=(5, 0))
    ttk.Label(calc_frame, text="Giờ chờ (HH:MM):").pack(side="left")
    delay_time_var = tk.StringVar()
    ttk.Entry(calc_frame, textvariable=delay_time_var, width=10).pack(side="left", padx=5)
    ttk.Label(calc_frame, text="Giờ trừ (HH:MM):").pack(side="left")
    subtract_time_var = tk.StringVar()
    ttk.Entry(calc_frame, textvariable=subtract_time_var, width=10).pack(side="left", padx=5)
    ttk.Button(calc_frame, text="Tính giờ", command=calculate_time).pack(side="left")
  
    schedule_button_frame = ttk.Frame(schedule_time_frame)
    schedule_button_frame.pack(fill="x", pady=(5, 0))
    ttk.Button(schedule_button_frame, text="Hẹn thông báo", command=set_notification_schedule).pack(side="left", expand=True, fill="x", padx=(0, 5))
    ttk.Button(schedule_button_frame, text="Hẹn khởi động", command=set_launch_schedule).pack(side="left", expand=True, fill="x", padx=(0, 5))
    ttk.Button(schedule_button_frame, text="Hẹn tắt", command=set_quit_schedule).pack(side="left", expand=True, fill="x", padx=(0, 5))
  
    group_frame = ttk.Frame(main_frame)
    group_frame.pack(fill="x", pady=10)
    ttk.Label(group_frame, text="Chọn nhóm hành động:").pack(anchor="w")
    group_var = tk.StringVar()
    group_combo = ttk.Combobox(group_frame, textvariable=group_var, values=[g["name"] for g in ACTION_GROUPS], state="readonly")
  
    update_group_combobox()
    group_combo.pack(fill="x")
  
    repeat_frame = ttk.Frame(group_frame)
    repeat_frame.pack(fill="x", pady=5)
    ttk.Label(repeat_frame, text="Tự động lặp lại sau (HH:MM):").pack(side="left")
    repeat_interval_var = tk.StringVar(value="00:00")
    ttk.Entry(repeat_frame, textvariable=repeat_interval_var, width=10).pack(side="left", padx=5)
    ttk.Label(repeat_frame, text="(để trống hoặc 00:00 để không lặp)").pack(side="left")
  
    button_container = ttk.Frame(group_frame)
    button_container.pack(fill="x", pady=5)
   
    ttk.Button(button_container, text="Chạy ngay", command=run_group_now).pack(side="left", expand=True, fill="x", padx=5)
    ttk.Button(button_container, text="Đặt giờ nhóm", command=set_group_schedule).pack(side="left", expand=True, fill="x", padx=5)
    ttk.Button(button_container, text="Quản lý nhóm", command=manage_groups).pack(side="left", expand=True, fill="x", padx=5)
    ttk.Button(button_container, text="Đặt làm mặc định", command=set_default_group).pack(side="left", expand=True, fill="x", padx=5)
    ttk.Button(button_container, text="Xóa mặc định", command=clear_default_group).pack(side="left", expand=True, fill="x", padx=5)
   
    default_status_label = ttk.Label(group_frame, text="Chưa có nhóm mặc định")
    default_status_label.pack(anchor="w", pady=(5, 0))
    update_default_label()
  
    key_frame = ttk.Frame(main_frame)
    key_frame.pack(fill="x", pady=10)
    ttk.Label(key_frame, text="Phím cần gửi (VD: a, ctrl+8, alt+ctrl+9):").pack(anchor="w")
    key_input_var = tk.StringVar()
    tk.Entry(key_frame, textvariable=key_input_var).pack(fill="x")
  
    key_button_frame = ttk.Frame(key_frame)
    key_button_frame.pack(fill="x", pady=(5, 0))
    ttk.Button(key_button_frame, text="Đặt giờ gửi phím", command=set_key_schedule).pack(side="left", expand=True, fill="x", padx=(0, 5))
    ttk.Button(key_button_frame, text="Gửi phím ngay", command=run_key_now).pack(side="right", expand=True, fill="x", padx=(5, 0))
  
    jobs_list_frame = ttk.LabelFrame(main_frame, text="Danh sách công việc hẹn giờ")
    jobs_list_frame.pack(fill="both", expand=True, pady=10)

    scroll_frame = ttk.Frame(jobs_list_frame)
    scroll_frame.pack(fill="both", expand=True, padx=5, pady=(5, 0))

    canvas = tk.Canvas(scroll_frame, highlightthickness=0)
    scrollbar = ttk.Scrollbar(scroll_frame, orient="vertical", command=canvas.yview)
    
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    schedule_list_frame = scrollable_frame

    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    button_frame = ttk.Frame(jobs_list_frame, padding=(0, 8, 0, 5))
    button_frame.pack(fill="x", padx=5)

    ttk.Button(button_frame, text="Hẹn lại tất cả", 
               command=reschedule_all).pack(side="left", expand=True, fill="x", padx=(0, 5))
    
    pause_button = ttk.Button(button_frame, text="Tạm dừng", command=toggle_pause)
    pause_button.pack(side="left", expand=True, fill="x", padx=5)
    
    ttk.Button(button_frame, text="Xoá tất cả lặp lại - đã chạy xong", 
               command=clear_all_completed_repeating).pack(side="left", expand=True, fill="x", padx=(5, 0))

    threading.Thread(target=scheduled_checker, args=(jobs, update_jobs_list, save_jobs), daemon=True).start()
    update_jobs_list()
    root.mainloop()

def on_closing():
    global root
    try:
        if root and root.winfo_exists():
            root.quit()
            root.destroy()
    except:
        pass
    save_jobs()
    save_action_groups()
    print("[LOG] Chương trình đã dừng hoàn toàn")

if __name__ == "__main__":
    create_gui()
