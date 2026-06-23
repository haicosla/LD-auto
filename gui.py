import tkinter as tk
from tkinter import ttk, messagebox, filedialog  # THÊM filedialog
import threading
import time
import pyautogui
import win32gui
import win32con
import sys
from datetime import datetime, timedelta
from config import *
from utils import auto_close_messagebox, focus_emulator, validate_time_input, validate_key_input
from ldconsole import get_instances, launch_instance, quit_instance
from recorder import run_record_line
from executor import run_key_press, execute_single_job, run_group_actions
from scheduler import scheduled_checker, run_group_in_thread
from job import Job, jobs, load_jobs, save_jobs
from action_groups import ACTION_GROUPS, load_action_groups, save_action_groups
from logger import get_logger
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
repeat_interval_var = None  # Mới: khoảng lặp lại
schedule_list_frame = None
root = None
groups_listbox = None

# Tính năng hành động mặc định
default_group_name = None
default_status_label = None

def set_default_group():
    global default_group_name
    group_name = group_var.get()
    if not group_name:
        auto_close_messagebox("error", "Lỗi", "Vui lòng chọn một nhóm trước!")
        return
    default_group_name = group_name
    if default_status_label:
        default_status_label.config(text=f"Mặc định hiện tại: {group_name}")
    auto_close_messagebox("info", "Thành công", f"Đã đặt nhóm '{group_name}' làm hành động mặc định.\nMọi lịch trình sẽ chạy nhóm này trước.")
    print(f"[DEFAULT] Đặt nhóm mặc định: {default_group_name}")

def clear_default_group():
    global default_group_name
    default_group_name = None
    if default_status_label:
        default_status_label.config(text="Chưa có nhóm mặc định")
    auto_close_messagebox("info", "Thành công", "Đã xóa nhóm mặc định.")
    print("[DEFAULT] Đã xóa nhóm mặc định")

def update_default_label():
    if default_status_label:
        text = f"Mặc định hiện tại: {default_group_name}" if default_group_name else "Chưa có nhóm mặc định"
        default_status_label.config(text=text)


def update_jobs_list():
    if not schedule_list_frame or not root or not root.winfo_exists():
        return

    # Đẩy toàn bộ việc update GUI về main thread an toàn
    def safe_update():
        if not schedule_list_frame or not root.winfo_exists():
            return
        try:
            # Xóa hết widget cũ
            for widget in list(schedule_list_frame.winfo_children()):
                widget.destroy()

            pending_jobs = [j for j in jobs if (not j.group_name or j.is_group) and j.status == "Đã hẹn"]
            completed_jobs = [j for j in jobs if (not j.group_name or j.is_group) and j.status != "Đã hẹn"]

            # ==================== CÔNG VIỆC ĐANG CHỜ ====================
            pending_frame = ttk.LabelFrame(schedule_list_frame, text="Công việc đang chờ")
            pending_frame.pack(fill="both", expand=True, pady=(0, 5))

            sorted_pending = sorted(pending_jobs, key=lambda j: j.scheduled_time if j.scheduled_time else datetime.max)
            for idx, job in enumerate(sorted_pending):
                frame = ttk.Frame(pending_frame)
                frame.pack(fill="x", anchor="w", pady=1)
                
                icon = "📋" if job.is_group else ("🎬" if job.job_type == "record" else "⌨️" if job.job_type == "key" else "🚀" if job.job_type == "launch" else "🛑" if job.job_type == "quit" else "🔔")
                label = ttk.Label(frame, text=f"{icon} {str(job)}")
                label.pack(side="left")
                
                btn_frame = ttk.Frame(frame)
                btn_frame.pack(side="right")
                
                if hasattr(job, 'is_repeating') and job.is_repeating:
                    ttk.Button(btn_frame, text="Dừng lặp", width=8, 
                               command=lambda j=job: stop_repeating(j)).pack(side="left", padx=(0, 2))
                
                ttk.Button(btn_frame, text="Chạy", width=5, 
                           command=lambda i=idx, p=True: run_job_now(i)).pack(side="left", padx=(0, 2))
                ttk.Button(btn_frame, text="Sửa", width=5, 
                           command=lambda i=idx, p=True: edit_job(i, True)).pack(side="left", padx=(0, 2))
                ttk.Button(btn_frame, text="Xóa", width=5, 
                           command=lambda i=idx, p=True: remove_job(i, True)).pack(side="left", padx=(0, 2))

            # ==================== CÔNG VIỆC ĐÃ HOÀN THÀNH ====================
            completed_frame = ttk.LabelFrame(schedule_list_frame, text="Công việc đã hoàn thành")
            completed_frame.pack(fill="both", expand=True, pady=5)
            sorted_completed = sorted(completed_jobs, key=lambda j: j.scheduled_time if j.scheduled_time else datetime.max)
            for idx, job in enumerate(sorted_completed):
                frame = ttk.Frame(completed_frame)
                frame.pack(fill="x", anchor="w", pady=1)
                icon = "📋" if job.is_group else ("🎬" if job.job_type == "record" else "⌨️" if job.job_type == "key" else "🚀" if job.job_type == "launch" else "🛑" if job.job_type == "quit" else "🔔")
                label = ttk.Label(frame, text=f"{icon} {str(job)}")
                label.pack(side="left")
                btn_frame = ttk.Frame(frame)
                btn_frame.pack(side="right")
                if job.is_group and job.status == "Đang chạy":
                    ttk.Button(btn_frame, text="Dừng", width=5, 
                               command=lambda j=job: stop_job(j)).pack(side="left", padx=(0, 2))
                ttk.Button(btn_frame, text="Sửa", width=5, 
                           command=lambda i=idx, p=False: edit_job(i, False)).pack(side="left", padx=(0, 2))
                ttk.Button(btn_frame, text="Hẹn lại", width=6, 
                           command=lambda i=idx, p=False: reschedule_job(i, False)).pack(side="left", padx=(0, 2))
                ttk.Button(btn_frame, text="Xóa", width=5, 
                           command=lambda i=idx, p=False: remove_job(i, False)).pack(side="left")

            # Cập nhật nút tạm dừng
            global pause_button
            if pause_button and pause_button.winfo_exists():
                pause_button.config(text="Tiếp tục" if is_paused else "Tạm dừng")
                
        except Exception as e:
            logger.error(f"Lỗi khi update_jobs_list (safe_update): {e}")

    # Đẩy về main thread
    if root and root.winfo_exists():
        root.after(0, safe_update)
        
def remove_group_jobs(group_jobs):
    global jobs
    for job in group_jobs:
        if job in jobs:
            jobs.remove(job)
    update_jobs_list()
    save_jobs()
    messagebox.showinfo("Thông báo", f"Đã xóa nhóm công việc.")        
        
def update_group_combobox():
    try:
        if group_combo:
            names = [g["name"] for g in ACTION_GROUPS]
            group_combo['values'] = names
            print(f"[UPDATE_COMBO] Hiện tại có {len(names)} nhóm: {names}")
            if names and (not group_var.get() or group_var.get() not in names):
                group_var.set(names[0])
            root.update_idletasks()
    except Exception as e:
        print(f"[UPDATE_COMBO] Lỗi: {e}")

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
      
        # Chèn nhóm mặc định nếu có
        
      
        time_str = current_time.strftime("%H:%M:%S")
        job = Job(time_str, name, "launch")
        group_jobs.append(job)
      
        # Tạo job launch đơn giản, không gán is_group=True để tránh chạy logic nhóm
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
    # Lấy khoảng lặp lại (dùng cùng logic validate_time_input như giờ chờ/giờ trừ)
    repeat_input = repeat_interval_var.get().strip()
    repeat_seconds = 0
    if repeat_input and repeat_input != "00:00" and repeat_input.lower() != "không":
        # Cho phép đặc biệt 24:00 = 24 giờ
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
        # Đánh dấu job lặp lại
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

def remove_job(display_index, is_pending=True):
    display_jobs = [j for j in jobs if (not j.group_name or j.is_group) and (j.status == "Đã hẹn" if is_pending else j.status != "Đã hẹn")]
    sorted_display_jobs = sorted(display_jobs, key=lambda j: j.scheduled_time if j.scheduled_time else datetime.max)
  
    if 0 <= display_index < len(sorted_display_jobs):
        job_to_remove = sorted_display_jobs[display_index]
        jobs.remove(job_to_remove)
        update_jobs_list()
        save_jobs()

def edit_job(display_index, is_pending=True):
    display_jobs = [j for j in jobs if (not j.group_name or j.is_group) and (j.status == "Đã hẹn" if is_pending else j.status != "Đã hẹn")]
    sorted_display_jobs = sorted(display_jobs, key=lambda j: j.scheduled_time if j.scheduled_time else datetime.max)
  
    if 0 <= display_index < len(sorted_display_jobs):
        job = sorted_display_jobs[display_index]
        edit_window = tk.Toplevel()
        edit_window.title(f"Chỉnh sửa công việc - {job.instance}")
        edit_window.geometry("400x200")
        edit_window.resizable(False, False)
        edit_window.attributes('-topmost', True)
      
        main_frame = ttk.Frame(edit_window, padding=10)
        main_frame.pack(fill="both", expand=True)
      
        if job.is_group:
            info_text = f"Loại: Nhóm hành động\nNhóm: {job.group_name}\nTrạng thái: {job.status}"
        elif job.job_type == "notification":
            info_text = f"Loại: Thông báo\nTrạng thái: {job.status}"
        elif job.job_type == "launch":
            info_text = f"Loại: Khởi động giả lập\nTrạng thái: {job.status}\nNhóm: {job.group_name if job.group_name else 'Không có'}"
        elif job.job_type == "quit":
            info_text = f"Loại: Tắt giả lập\nTrạng thái: {job.status}\nNhóm: {job.group_name if job.group_name else 'Không có'}"
        else:
            info_text = f"Loại: {'Chạy dòng' if job.job_type == 'record' else 'Gửi phím'}\nGiá trị: {job.value}\nTrạng thái: {job.status}\nNhóm: {job.group_name if job.group_name else 'Không có'}"
      
        ttk.Label(main_frame, text=info_text, justify="left").pack(anchor="w", pady=(0, 10))
      
        time_frame = ttk.Frame(main_frame)
        time_frame.pack(fill="x", pady=5)
        ttk.Label(time_frame, text="Thời gian mới (HH:MM):").pack(side="left")
      
        edit_time_var = tk.StringVar(value=job.time_str[:-3])
        time_entry = ttk.Entry(time_frame, textvariable=edit_time_var, width=10)
        time_entry.pack(side="left", padx=5)
      
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=10)
      
        def save_changes():
            new_time = edit_time_var.get().strip()
            if new_time.isdigit() and len(new_time) == 4:
                new_time = f"{new_time[:2]}:{new_time[2:]}"
          
            try:
                new_start_time = datetime.strptime(new_time, "%H:%M")
                if job.is_group:
                    old_start_time = datetime.strptime(job.time_str, "%H:%M:%S")
                    new_start_time_full = datetime.strptime(new_time + ":00", "%H:%M:%S").replace(
                        year=old_start_time.year, month=old_start_time.month, day=old_start_time.day
                    )
                    if new_start_time_full < datetime.now():
                        new_start_time_full += timedelta(days=1)
                    time_diff = (new_start_time_full - old_start_time).total_seconds()
                    job.time_str = new_time + ":00"
                    job.status = "Đã hẹn"
                    job.current_child_index = 0
                    job.update_scheduled_time()
                    for gj in job.group_jobs:
                        gj_start_time = datetime.strptime(gj.time_str, "%H:%M:%S")
                        new_gj_time = (gj_start_time + timedelta(seconds=time_diff)).strftime("%H:%M:%S")
                        gj.time_str = new_gj_time
                        gj.status = "Đã hẹn"
                        gj.update_scheduled_time()
                else:
                    job.time_str = new_time + ":00"
                    job.status = "Đã hẹn"
                    job.update_scheduled_time()
                update_jobs_list()
                save_jobs()
                edit_window.destroy()
                auto_close_messagebox("info", "Thành công", f"Đã cập nhật thời gian thành {new_time}")
            except ValueError:
                auto_close_messagebox("error", "Lỗi", "Định dạng thời gian không hợp lệ. Vui lòng nhập theo định dạng HH:MM")
      
        ttk.Button(btn_frame, text="Lưu thay đổi", command=save_changes).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Hủy", command=edit_window.destroy).pack(side="right")
      
        time_entry.focus_set()
        time_entry.select_range(0, "end")
      
        edit_window.update_idletasks()
        width = edit_window.winfo_width()
        height = edit_window.winfo_height()
        x = (edit_window.winfo_screenwidth() // 2) - (width // 2)
        y = (edit_window.winfo_screenheight() // 2) - (height // 2)
        edit_window.geometry(f"{width}x{height}+{x}+{y}")

def reschedule_job(display_index, is_pending=True):
    display_jobs = [j for j in jobs if (not j.group_name or j.is_group) and (j.status == "Đã hẹn" if is_pending else j.status != "Đã hẹn")]
    sorted_display_jobs = sorted(display_jobs, key=lambda j: j.scheduled_time if j.scheduled_time else datetime.max)
  
    if 0 <= display_index < len(sorted_display_jobs):
        job = sorted_display_jobs[display_index]
        now = datetime.now()
        job_time = datetime.strptime(job.time_str, "%H:%M:%S").replace(
            year=now.year, month=now.month, day=now.day
        )
        job_time += timedelta(days=1)
        new_time_str = job_time.strftime("%H:%M:%S")
        if job.is_group:
            old_start_time = datetime.strptime(job.time_str, "%H:%M:%S")
            time_diff = (job_time - old_start_time).total_seconds()
            job.time_str = new_time_str
            job.scheduled_time = job_time
            job.status = "Đã hẹn"
            job.current_child_index = 0
            for gj in job.group_jobs:
                gj_start_time = datetime.strptime(gj.time_str, "%H:%M:%S")
                new_gj_time = (gj_start_time + timedelta(seconds=time_diff)).strftime("%H:%M:%S")
                gj.time_str = new_gj_time
                gj.scheduled_time = datetime.strptime(new_gj_time, "%H:%M:%S").replace(
                    year=now.year, month=now.month, day=now.day
                ) + (timedelta(days=1) if gj_start_time < now else timedelta())
                gj.status = "Đã hẹn"
        else:
            job.time_str = new_time_str
            job.scheduled_time = job_time
            job.status = "Đã hẹn"
        update_jobs_list()
        save_jobs()
        auto_close_messagebox("info", "Hẹn lại", f"Đã hẹn lại {job.instance} cho {job_time.strftime('%d/%m %H:%M')}")

def reschedule_all():
    now = datetime.now()
    rescheduled_count = 0
    for job in jobs:
        if job.status != "Đã hẹn":
            rescheduled_count += 1
            if not job.is_group:
                job_time = datetime.strptime(job.time_str, "%H:%M:%S").replace(
                    year=now.year, month=now.month, day=now.day
                )
                job_time += timedelta(days=1)
                job.time_str = job_time.strftime("%H:%M:%S")
                job.scheduled_time = job_time
                job.status = "Đã hẹn"
            else:
                old_start_time = datetime.strptime(job.time_str, "%H:%M:%S")
                job_time = old_start_time.replace(
                    year=now.year, month=now.month, day=now.day
                )
                job_time += timedelta(days=1)
                time_diff = (job_time - old_start_time).total_seconds()
                job.time_str = job_time.strftime("%H:%M:%S")
                job.scheduled_time = job_time
                job.status = "Đã hẹn"
                job.current_child_index = 0
                for gj in job.group_jobs:
                    gj_start_time = datetime.strptime(gj.time_str, "%H:%M:%S")
                    new_gj_time = (gj_start_time + timedelta(seconds=time_diff)).strftime("%H:%M:%S")
                    gj.time_str = new_gj_time
                    gj.scheduled_time = datetime.strptime(new_gj_time, "%H:%M:%S").replace(
                        year=now.year, month=now.month, day=now.day
                    ) + (timedelta(days=1) if gj_start_time < now else timedelta())
                    gj.status = "Đã hẹn"
    update_jobs_list()
    save_jobs()
    auto_close_messagebox("info", "Hẹn lại tất cả", f"Đã hẹn lại {rescheduled_count} công việc đã chạy cho ngày tiếp theo")

def toggle_pause():
    global is_paused, pause_button
    is_paused = not is_paused
    if pause_button:
        pause_button.config(text="Tiếp tục" if is_paused else "Tạm dừng")
    print(f"[LOG] {'Tạm dừng' if is_paused else 'Tiếp tục'} kiểm tra lịch trình")
    
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
                    update_group_jobs()
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

def stop_job(job):
    job.should_stop = True
    if job in running_threads:
        del running_threads[job]
    job.status = "Đã dừng"
    print(f"[LOG] Nhóm {job.group_name} trên {job.instance} đã bị dừng")
    update_jobs_list()
    save_jobs()

def stop_repeating(job):  # MỚI: dừng lặp lại
    job.is_repeating = False
    if hasattr(job, 'repeat_interval'):
        job.repeat_interval = 0
    update_jobs_list()
    save_jobs()
    auto_close_messagebox("info", "Thông báo", f"Đã dừng lặp lại cho nhóm {job.group_name} trên {job.instance}")

def manage_groups():
    global groups_listbox
    group_window = tk.Toplevel()
    group_window.title("Quản lý nhóm hành động")
    group_window.geometry("600x400")
    group_window.resizable(False, False)
    group_window.attributes('-topmost', True)
  
    main_frame = ttk.Frame(group_window, padding=10)
    main_frame.pack(fill="both", expand=True)
  
    groups_frame = ttk.LabelFrame(main_frame, text="Danh sách nhóm")
    groups_frame.pack(fill="both", expand=True)
  
    groups_listbox = tk.Listbox(groups_frame, height=10)
    groups_listbox.pack(fill="both", expand=True, padx=5, pady=5)
  
    def update_groups_listbox():
        groups_listbox.delete(0, tk.END)
        for group in ACTION_GROUPS:
            groups_listbox.insert(tk.END, group["name"])
        update_group_combobox()
  
    update_groups_listbox()
  
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill="x", pady=10)
  
    def create_new_group():
        edit_group_window(None)
        update_groups_listbox()
  
    def edit_selected_group():
        try:
            selected_idx = groups_listbox.curselection()[0]
            group = ACTION_GROUPS[selected_idx]
            edit_group_window(group)
            update_groups_listbox()
        except IndexError:
            auto_close_messagebox("warning", "Chọn nhóm", "Vui lòng chọn một nhóm để chỉnh sửa.")
  
    def delete_selected_group():
        try:
            selected_idx = groups_listbox.curselection()[0]
            group_name = ACTION_GROUPS[selected_idx]["name"]
            if messagebox.askyesno("Xác nhận", f"Bạn có chắc muốn xóa nhóm '{group_name}'?"):
                ACTION_GROUPS.pop(selected_idx)
                save_action_groups()
                update_groups_listbox()
        except IndexError:
            auto_close_messagebox("warning", "Chọn nhóm", "Vui lòng chọn một nhóm để xóa.")
  
    ttk.Button(btn_frame, text="Tạo nhóm mới", command=create_new_group).pack(side="left", padx=5)
    ttk.Button(btn_frame, text="Chỉnh sửa nhóm", command=edit_selected_group).pack(side="left", padx=5)
    ttk.Button(btn_frame, text="Xóa nhóm", command=delete_selected_group).pack(side="left", padx=5)
  
    group_window.update_idletasks()
    width = group_window.winfo_width()
    height = group_window.winfo_height()
    x = (group_window.winfo_screenwidth() // 2) - (width // 2)
    y = (group_window.winfo_screenheight() // 2) - (height // 2)
    group_window.geometry(f"{width}x{height}+{x}+{y}")

def edit_group_window(group):
    is_new = group is None
    group_data = {"name": "", "actions": []} if is_new else group.copy()
  
    window = tk.Toplevel()
    window.title("Tạo nhóm mới" if is_new else f"Chỉnh sửa nhóm: {group_data['name']}")
    window.geometry("500x500")
    window.resizable(False, False)
    window.attributes('-topmost', True)
  
    main_frame = ttk.Frame(window, padding=10)
    main_frame.pack(fill="both", expand=True)
  
    name_frame = ttk.Frame(main_frame)
    name_frame.pack(fill="x")
    ttk.Label(name_frame, text="Tên nhóm:").pack(side="left")
    name_var = tk.StringVar(value=group_data["name"])
    ttk.Entry(name_frame, textvariable=name_var).pack(side="left", fill="x", expand=True, padx=5)
  
    actions_frame = ttk.LabelFrame(main_frame, text="Danh sách hành động")
    actions_frame.pack(fill="both", expand=True, pady=10)
  
    actions_listbox = tk.Listbox(actions_frame, height=10)
    actions_listbox.pack(fill="both", expand=True, padx=5, pady=5)
  
    dragging = False
    drag_start_index = None
    selected_action_index = None
  
    def update_actions_listbox():
        actions_listbox.delete(0, tk.END)
        for action in group_data["actions"]:
            if action["type"] == "group":
                action_str = f"Nhóm con: {action['value']} (Trễ: {action['delay']}s)"
            else:
                action_str = f"Loại: {action['type']}, Giá trị: {action['value']}, Trễ: {action['delay']}s"
            actions_listbox.insert(tk.END, action_str)
  
    update_actions_listbox()
  
    def start_drag(event):
        nonlocal dragging, drag_start_index
        index = actions_listbox.nearest(event.y)
        if 0 <= index < len(group_data["actions"]):
            dragging = True
            drag_start_index = index
            actions_listbox.selection_clear(0, tk.END)
            actions_listbox.selection_set(index)
            actions_listbox.activate(index)
  
    def drag_motion(event):
        nonlocal dragging, drag_start_index
        if not dragging:
            return
        index = actions_listbox.nearest(event.y)
        if 0 <= index < len(group_data["actions"]) and index != drag_start_index:
            action = group_data["actions"].pop(drag_start_index)
            group_data["actions"].insert(index, action)
            update_actions_listbox()
            drag_start_index = index
            actions_listbox.selection_clear(0, tk.END)
            actions_listbox.selection_set(index)
            actions_listbox.activate(index)
  
    def end_drag(event):
        nonlocal dragging, drag_start_index
        dragging = False
        drag_start_index = None
  
    actions_listbox.bind("<Button-1>", start_drag)
    actions_listbox.bind("<B1-Motion>", drag_motion)
    actions_listbox.bind("<ButtonRelease-1>", end_drag)
  
    def on_select_action(event):
        nonlocal selected_action_index
        try:
            selected_idx = actions_listbox.curselection()[0]
            if 0 <= selected_idx < len(group_data["actions"]):
                selected_action_index = selected_idx
                action = group_data["actions"][selected_idx]
                type_var.set(action["type"])
                value_var.set(str(action["value"]) if action["type"] == "record" else action["value"])
                delay_var.set(str(action["delay"]))
        except IndexError:
            pass
  
    actions_listbox.bind("<<ListboxSelect>>", on_select_action)
  
    action_edit_frame = ttk.Frame(main_frame)
    action_edit_frame.pack(fill="x", pady=5)
  
    ttk.Label(action_edit_frame, text="Loại:").pack(side="left")
    type_var = tk.StringVar(value="record")
    ttk.Combobox(action_edit_frame, textvariable=type_var, values=["record", "key", "launch", "quit", "group"], state="readonly", width=10).pack(side="left", padx=5)
  
    ttk.Label(action_edit_frame, text="Giá trị:").pack(side="left")
    value_var = tk.StringVar()
    ttk.Entry(action_edit_frame, textvariable=value_var, width=10).pack(side="left", padx=5)
  
    ttk.Label(action_edit_frame, text="Trễ (s):").pack(side="left")
    delay_var = tk.StringVar()
    ttk.Entry(action_edit_frame, textvariable=delay_var, width=10).pack(side="left", padx=5)
  
    def add_action():
        action_type = type_var.get()
        value = value_var.get().strip()
        delay = delay_var.get().strip()
       
        if not delay.isdigit():
            auto_close_messagebox("error", "Lỗi", "Vui lòng nhập thời gian trễ là số nguyên!")
            return
       
        if action_type == "group":
            if not value:
                auto_close_messagebox("error", "Lỗi", "Vui lòng nhập tên nhóm con!")
                return
            if value not in [g["name"] for g in ACTION_GROUPS]:
                auto_close_messagebox("error", "Lỗi", f"Nhóm '{value}' không tồn tại!")
                return
            action = {
                "type": "group",
                "value": value,
                "delay": int(delay)
            }
        elif action_type == "record":
            if not value.isdigit():
                auto_close_messagebox("error", "Lỗi", "Giá trị cho 'record' phải là số!")
                return
            action = {
                "type": "record",
                "value": int(value),
                "delay": int(delay)
            }
        else:
            if not value:
                auto_close_messagebox("error", "Lỗi", "Vui lòng nhập giá trị hành động!")
                return
            action = {
                "type": action_type,
                "value": value,
                "delay": int(delay)
            }
       
        group_data["actions"].append(action)
        update_actions_listbox()
        value_var.set("")
        delay_var.set("")
  
    def edit_action():
        nonlocal selected_action_index
        if selected_action_index is None:
            auto_close_messagebox("warning", "Chọn hành động", "Vui lòng chọn một hành động để chỉnh sửa.")
            return
      
        action_type = type_var.get()
        value = value_var.get().strip()
        delay = delay_var.get().strip()
       
        if not delay.isdigit():
            auto_close_messagebox("error", "Lỗi", "Vui lòng nhập thời gian trễ là số nguyên!")
            return
       
        if action_type == "group":
            if not value:
                auto_close_messagebox("error", "Lỗi", "Vui lòng nhập tên nhóm con!")
                return
            if value not in [g["name"] for g in ACTION_GROUPS]:
                auto_close_messagebox("error", "Lỗi", f"Nhóm '{value}' không tồn tại!")
                return
            group_data["actions"][selected_action_index] = {
                "type": "group",
                "value": value,
                "delay": int(delay)
            }
        elif action_type == "record":
            if not value.isdigit():
                auto_close_messagebox("error", "Lỗi", "Giá trị cho 'record' phải là số!")
                return
            group_data["actions"][selected_action_index] = {
                "type": "record",
                "value": int(value),
                "delay": int(delay)
            }
        else:
            if not value:
                auto_close_messagebox("error", "Lỗi", "Vui lòng nhập giá trị hành động!")
                return
            group_data["actions"][selected_action_index] = {
                "type": action_type,
                "value": value,
                "delay": int(delay)
            }
        update_actions_listbox()
        selected_action_index = None
        value_var.set("")
        delay_var.set("")
  
    def delete_action():
        try:
            selected_idx = actions_listbox.curselection()[0]
            group_data["actions"].pop(selected_idx)
            update_actions_listbox()
            selected_action_index = None
        except IndexError:
            auto_close_messagebox("warning", "Chọn hành động", "Vui lòng chọn một hành động để xóa.")
  
    action_btn_frame = ttk.Frame(main_frame)
    action_btn_frame.pack(fill="x", pady=5)
    ttk.Button(action_btn_frame, text="Thêm hành động", command=add_action).pack(side="left", padx=5)
    ttk.Button(action_btn_frame, text="Chỉnh sửa hành động", command=edit_action).pack(side="left", padx=5)
    ttk.Button(action_btn_frame, text="Xóa hành động", command=delete_action).pack(side="left", padx=5)
  
    def save_group():
        new_name = name_var.get().strip()
        if not new_name:
            auto_close_messagebox("error", "Lỗi", "Vui lòng nhập tên nhóm!")
            return
        if not group_data["actions"]:
            auto_close_messagebox("error", "Lỗi", "Nhóm phải có ít nhất một hành động!")
            return
        if any(g["name"] == new_name for g in ACTION_GROUPS if g != group):
            auto_close_messagebox("error", "Lỗi", f"Nhóm '{new_name}' đã tồn tại!")
            return
      
        group_data["name"] = new_name
        if is_new:
            ACTION_GROUPS.append(group_data)
            print(f"[SAVE_GROUP] Đã append nhóm mới: {new_name}, tổng ACTION_GROUPS: {len(ACTION_GROUPS)}")
        else:
            group.update(group_data)
            print(f"[SAVE_GROUP] Đã update nhóm cũ: {new_name}")
        save_action_groups()
        update_groups_listbox()
        update_group_combobox()
        window.destroy()
        auto_close_messagebox("info", "Thành công", f"Nhóm '{new_name}' đã được {'tạo' if is_new else 'cập nhật'}.")
  
    ttk.Button(main_frame, text="Lưu nhóm", command=save_group).pack(side="right", padx=5, pady=10)
    ttk.Button(main_frame, text="Hủy", command=window.destroy).pack(side="right", padx=5, pady=10)
  
    window.update_idletasks()
    width = window.winfo_width()
    height = window.winfo_height()
    x = (window.winfo_screenwidth() // 2) - (width // 2)
    y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")

def update_groups_listbox():
    if groups_listbox:
        groups_listbox.delete(0, tk.END)
        for group in ACTION_GROUPS:
            groups_listbox.insert(tk.END, group["name"])
        update_group_combobox()
        
def clear_all_completed_repeating():
    """Xóa tất cả job lặp lại đã chạy xong"""
    global jobs
    try:
        # Lấy các job lặp lại đã chạy xong
        to_remove = [
            j for j in jobs 
            if getattr(j, 'is_repeating', False) and j.status != "Đã hẹn"
        ]

        if not to_remove:
            messagebox.showinfo("Thông báo", "Không có job lặp lại nào đã chạy xong để xóa.")
            return

        removed_count = 0
        for job in to_remove:
            if job in jobs:
                try:
                    jobs.remove(job)
                    removed_count += 1
                    logger.info(f"[CLEAR] Đã xóa job lặp lại: {job}")
                except Exception as e:
                    logger.error(f"Lỗi khi xóa job: {e}")

        # Cập nhật lại GUI và lưu file
        update_jobs_list()
        save_jobs()

        logger.info(f"[CLEAR] Tổng cộng đã xóa {removed_count} job lặp lại đã chạy xong.")
        messagebox.showinfo(
            "Thành công",
            f"Đã xóa {removed_count} job lặp lại đã hoàn thành.\n"
            f"Đã lưu thay đổi vào scheduled_jobs.json."
        )

    except Exception as e:
        logger.error(f"Lỗi trong clear_all_completed_repeating: {e}")
        messagebox.showerror("Lỗi", f"Không thể xóa job lặp lại:\n{str(e)}")

def create_gui():
    global var_dict, record_line_var, schedule_time_var, key_input_var, group_var, group_combo
    global delay_time_var, subtract_time_var, repeat_interval_var, schedule_list_frame, root, default_status_label
    global pause_button
    global canvas, scrollable_frame
    
    load_action_groups()
    load_jobs()
    
  
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
            # Đọc file config.json cũ (nếu có)
            config_data = {}
            if os.path.exists("config.json"):
                try:
                    with open("config.json", 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                except Exception as e:
                    print(f"[CONFIG] Lỗi đọc config.json cũ: {e}. Tạo mới.")
                    config_data = {}
            
            # Cập nhật chỉ LD_CONSOLE_PATH, giữ nguyên các biến khác
            config_data['LD_CONSOLE_PATH'] = new_path
            
            # Lưu lại toàn bộ
            try:
                with open("config.json", 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, ensure_ascii=False, indent=4)
                messagebox.showinfo("Thông báo", f"Đã lưu đường dẫn '{new_path}' vào config.json.\nCác biến offset giữ nguyên.\nReset chương trình để update danh sách giả lập.")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không lưu được config.json: {e}")
        else:
            messagebox.showwarning("Lỗi", "Đường dẫn không được để trống!")   
    
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
  
    # MỚI: Ô nhập khoảng lặp lại
    repeat_frame = ttk.Frame(group_frame)
    repeat_frame.pack(fill="x", pady=5)
    ttk.Label(repeat_frame, text="Tự động lặp lại sau (HH:MM):").pack(side="left")
    repeat_interval_var = tk.StringVar(value="00:00")  # mặc định không lặp
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
  
        # ==================== DANH SÁCH CÔNG VIỆC HẸN GIỜ ====================
    jobs_list_frame = ttk.LabelFrame(main_frame, text="Danh sách công việc hẹn giờ")
    jobs_list_frame.pack(fill="both", expand=True, pady=10)

    # === PHẦN 1: Khu vực có thể cuộn ===
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

    # Gán biến toàn cục để update_jobs_list() dùng
    global schedule_list_frame
    schedule_list_frame = scrollable_frame

    # Cuộn bằng chuột
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    # === PHẦN 2: 3 NÚT CỐ ĐỊNH Ở DƯỚI (KHÔNG BỊ CUỘN) ===
    button_frame = ttk.Frame(jobs_list_frame, padding=(0, 8, 0, 5))
    button_frame.pack(fill="x", padx=5)

    ttk.Button(button_frame, text="Hẹn lại tất cả", 
               command=reschedule_all).pack(side="left", expand=True, fill="x", padx=(0, 5))
    
    global pause_button
    pause_button = ttk.Button(button_frame, text="Tạm dừng", command=toggle_pause)
    pause_button.pack(side="left", expand=True, fill="x", padx=5)
    
    ttk.Button(button_frame, text="Xoá tất cả lặp lại - đã chạy xong", 
               command=clear_all_completed_repeating).pack(side="left", expand=True, fill="x", padx=(5, 0))

    # Bind chuột cuộn cho canvas
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    canvas.bind_all("<MouseWheel>", _on_mousewheel)
    

    
    threading.Thread(target=scheduled_checker, args=(jobs, update_jobs_list, save_jobs), daemon=True).start()
    update_jobs_list()
    root.mainloop()

def on_closing():
    global is_running, root
    is_running = False
    try:
        if root and root.winfo_exists():
            root.quit()      # Dừng mainloop trước
            root.destroy()   # Sau đó destroy
    except:
        pass
    save_jobs()
    save_action_groups()
    print("[LOG] Chương trình đã dừng hoàn toàn")

if __name__ == "__main__":
    create_gui()