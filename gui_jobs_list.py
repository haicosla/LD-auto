# gui_jobs_list.py - Quản lý danh sách công việc
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from job import jobs, save_jobs
from recorder import run_record_line
from executor import run_key_press, launch_instance, quit_instance
from utils import auto_close_messagebox
from logger import get_logger

logger = get_logger()

# Biến toàn cục
schedule_list_frame = None
root = None
pause_button = None
is_paused = False
running_threads = {}

def update_jobs_list():
    """Cập nhật danh sách công việc trên GUI"""
    if not schedule_list_frame or not root or not root.winfo_exists():
        return

    def safe_update():
        if not schedule_list_frame or not root.winfo_exists():
            return
        try:
            for widget in list(schedule_list_frame.winfo_children()):
                widget.destroy()

            pending_jobs = [j for j in jobs if (not j.group_name or j.is_group) and j.status == "Đã hẹn"]
            completed_jobs = [j for j in jobs if (not j.group_name or j.is_group) and j.status != "Đã hẹn"]

            # Công việc đang chờ
            pending_frame = ttk.LabelFrame(schedule_list_frame, text="Công việc đang chờ")
            pending_frame.pack(fill="both", expand=True, pady=(0, 5))

            sorted_pending = sorted(pending_jobs, key=lambda j: j.scheduled_time if j.scheduled_time else datetime.max)
            for idx, job in enumerate(sorted_pending):
                frame = ttk.Frame(pending_frame)
                frame.pack(fill="x", anchor="w", pady=1)
                
                icon = "📋" if job.is_group else ("🎬" if job.job_type == "record" else "⌨️" if job.job_type == "key" else "🚀" if job.job_type == "launch" else "🛑")
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

            # Công việc đã hoàn thành
            completed_frame = ttk.LabelFrame(schedule_list_frame, text="Công việc đã hoàn thành")
            completed_frame.pack(fill="both", expand=True, pady=5)
            sorted_completed = sorted(completed_jobs, key=lambda j: j.scheduled_time if j.scheduled_time else datetime.max)
            for idx, job in enumerate(sorted_completed):
                frame = ttk.Frame(completed_frame)
                frame.pack(fill="x", anchor="w", pady=1)
                icon = "📋" if job.is_group else ("🎬" if job.job_type == "record" else "⌨️" if job.job_type == "key" else "🚀" if job.job_type == "launch" else "🛑")
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

            global pause_button
            if pause_button and pause_button.winfo_exists():
                pause_button.config(text="Tiếp tục" if is_paused else "Tạm dừng")
                
        except Exception as e:
            logger.error(f"Lỗi khi update_jobs_list: {e}")

    if root and root.winfo_exists():
        root.after(0, safe_update)

def remove_job(display_index, is_pending=True):
    """Xóa một công việc"""
    display_jobs = [j for j in jobs if (not j.group_name or j.is_group) and (j.status == "Đã hẹn" if is_pending else j.status != "Đã hẹn")]
    sorted_display_jobs = sorted(display_jobs, key=lambda j: j.scheduled_time if j.scheduled_time else datetime.max)
  
    if 0 <= display_index < len(sorted_display_jobs):
        job_to_remove = sorted_display_jobs[display_index]
        jobs.remove(job_to_remove)
        update_jobs_list()
        save_jobs()

def edit_job(display_index, is_pending=True):
    """Chỉnh sửa thời gian của một công việc"""
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
        else:
            info_text = f"Loại: {'Chạy dòng' if job.job_type == 'record' else 'Gửi phím'}\nGiá trị: {job.value}\nTrạng thái: {job.status}"
      
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

def reschedule_job(display_index, is_pending=True):
    """Hẹn lại một công việc cho ngày tiếp theo"""
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
    """Hẹn lại tất cả công việc đã chạy cho ngày tiếp theo"""
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
    """Tạm dừng/tiếp tục kiểm tra lịch trình"""
    global is_paused, pause_button
    is_paused = not is_paused
    if pause_button:
        pause_button.config(text="Tiếp tục" if is_paused else "Tạm dừng")
    print(f"[LOG] {'Tạm dừng' if is_paused else 'Tiếp tục'} kiểm tra lịch trình")

def stop_job(job):
    """Dừng một công việc nhóm"""
    job.should_stop = True
    if job in running_threads:
        del running_threads[job]
    job.status = "Đã dừng"
    print(f"[LOG] Nhóm {job.group_name} trên {job.instance} đã bị dừng")
    update_jobs_list()
    save_jobs()

def stop_repeating(job):
    """Dừng lặp lại một công việc"""
    job.is_repeating = False
    if hasattr(job, 'repeat_interval'):
        job.repeat_interval = 0
    update_jobs_list()
    save_jobs()
    auto_close_messagebox("info", "Thông báo", f"Đã dừng lặp lại cho nhóm {job.group_name} trên {job.instance}")

def clear_all_completed_repeating():
    """Xóa tất cả job lặp lại đã chạy xong"""
    try:
        to_remove = [j for j in jobs if getattr(j, 'is_repeating', False) and j.status != "Đã hẹn"]
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
        update_jobs_list()
        save_jobs()
        logger.info(f"[CLEAR] Tổng cộng đã xóa {removed_count} job lặp lại đã chạy xong.")
        messagebox.showinfo("Thành công", f"Đã xóa {removed_count} job lặp lại đã hoàn thành.\nĐã lưu thay đổi vào scheduled_jobs.json.")
    except Exception as e:
        logger.error(f"Lỗi trong clear_all_completed_repeating: {e}")
        messagebox.showerror("Lỗi", f"Không thể xóa job lặp lại:\n{str(e)}")
