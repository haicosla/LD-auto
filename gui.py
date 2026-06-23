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

# New: scheduled panel reference
scheduled_panel = None

# Tính năng hành động mặc định
default_group_name = None
default_status_label = None

# ------------------- New: Scheduled Jobs Panel & helpers -------------------
_JOB_TAG_COLORS = {
    "Đã hẹn": "#1E90FF",
    "Đang chạy": "#FFA500",
    "Đã chạy": "#28A745",
    "Lỗi": "#DC3545"
}

def run_job_object(job):
    """Run a Job object immediately (can be group or single). Runs in current thread—caller should spawn a thread."""
    try:
        logger.info(f"[GUI_RUN] Thực thi job trực tiếp: {job}")
        if getattr(job, 'is_group', False):
            # ensure group_jobs available
            if not getattr(job, 'group_jobs', None):
                logger.debug("[GUI_RUN] Group job has no child jobs, skipping")
                return False
            for child in job.group_jobs:
                if getattr(job, 'should_stop', False):
                    logger.warning(f"[GUI_RUN] Job nhóm {job.group_name} trên {job.instance} bị dừng bởi người dùng")
                    return False
                logger.info(f"[GUI_RUN] Thực thi job con: {child.job_type} - {child.value} trên {child.instance}")
                execute_single_job(child)
                # respect child's scheduled delay is already encoded in times; we do not sleep here
            job.status = "Đã chạy"
            return True
        else:
            res = execute_single_job(job)
            job.status = "Đã chạy" if res else "Lỗi"
            return res
    except Exception as e:
        logger.error(f"[GUI_RUN] Lỗi khi chạy job object: {e}")
        job.status = "Lỗi"
        return False

def _spawn_run_for_job_index(idx):
    try:
        job = jobs[idx]
    except Exception:
        logger.error(f"[GUI_RUN] Không tìm thấy job với index {idx}")
        return
    run_job_object(job)
    save_jobs()
    # refresh UI
    if scheduled_panel and scheduled_panel.get('refresh'):
        scheduled_panel['refresh']()
    else:
        update_jobs_list()

def _on_action_run_selected(tree):
    sel = tree.selection()
    if not sel:
        messagebox.showinfo("Chọn job", "Vui lòng chọn 1 hoặc nhiều job con để chạy ngay.")
        return
    run_count = 0
    for item in sel:
        iid = tree.item(item, 'iid') if 'iid' in tree.item(item) else item
        # our child job ids will be like 'job_{index}'
        if isinstance(iid, str) and iid.startswith('job_'):
            try:
                idx = int(iid.split('_', 1)[1])
                t = threading.Thread(target=_spawn_run_for_job_index, args=(idx,), daemon=True)
                t.start()
                run_count += 1
            except Exception as e:
                logger.error(f"[GUI_RUN] Không chạy được job từ iid {iid}: {e}")
    if run_count == 0:
        messagebox.showinfo("Chạy job", "Vui lòng mở rộng nhóm và chọn job con (các dòng cụ thể) để chạy ngay.")

def _on_action_delete_selected(tree):
    sel = tree.selection()
    if not sel:
        messagebox.showinfo("Chọn job", "Vui lòng chọn job để xóa (chọn job con để xóa cụ thể)")
        return
    removed = 0
    # collect indices to remove
    idxs = set()
    for item in sel:
        iid = tree.item(item, 'iid') if 'iid' in tree.item(item) else item
        if isinstance(iid, str) and iid.startswith('job_'):
            try:
                idx = int(iid.split('_', 1)[1])
                idxs.add(idx)
            except:
                pass
        else:
            # if parent selected, remove all its child job indices
            for child in tree.get_children(item):
                child_iid = tree.item(child, 'iid')
                if isinstance(child_iid, str) and child_iid.startswith('job_'):
                    try:
                        idx = int(child_iid.split('_',1)[1])
                        idxs.add(idx)
                    except:
                        pass
    if not idxs:
        messagebox.showinfo("Xóa job", "Không có job con hợp lệ được chọn để xóa.")
        return
    # confirm
    if not messagebox.askyesno("Xác nhận", f"Xóa {len(idxs)} job? Đây là thao tác không thể hoàn tác."):
        return
    # remove by index, ensure we delete from highest to lowest to keep indices valid
    for idx in sorted(idxs, reverse=True):
        try:
            job = jobs[idx]
            jobs.pop(idx)
            removed += 1
            logger.info(f"[GUI_DEL] Đã xóa job: {job}")
        except Exception as e:
            logger.error(f"[GUI_DEL] Lỗi xóa job index {idx}: {e}")
    save_jobs()
    if scheduled_panel and scheduled_panel.get('refresh'):
        scheduled_panel['refresh']()
    else:
        update_jobs_list()
    messagebox.showinfo("Xóa job", f"Đã xóa {removed} job.")

def _on_action_stop_selected(tree):
    sel = tree.selection()
    if not sel:
        messagebox.showinfo("Chọn job", "Vui lòng chọn job đang chạy để dừng.")
        return
    stopped = 0
    for item in sel:
        iid = tree.item(item, 'iid') if 'iid' in tree.item(item) else item
        if isinstance(iid, str) and iid.startswith('job_'):
            try:
                idx = int(iid.split('_', 1)[1])
                job = jobs[idx]
                job.should_stop = True
                # remove running thread reference if exists
                try:
                    from scheduler import running_threads
                    if job in running_threads:
                        del running_threads[job]
                except Exception:
                    pass
                stopped += 1
            except Exception as e:
                logger.error(f"[GUI_STOP] Lỗi dừng job index {iid}: {e}")
    if stopped > 0:
        save_jobs()
        if scheduled_panel and scheduled_panel.get('refresh'):
            scheduled_panel['refresh']()
        else:
            update_jobs_list()
        messagebox.showinfo("Dừng job", f"Đã dừng {stopped} job.")


def build_scheduled_jobs_panel(parent_frame, jobs_list, on_run, on_edit, on_delete, on_stop):
    frame = ttk.LabelFrame(parent_frame, text="Danh sách công việc (gợi ý)", padding=(8,6))
    frame.pack(fill="both", expand=True, padx=6, pady=6)

    # Top filter bar
    topbar = ttk.Frame(frame)
    topbar.pack(fill="x", pady=(0,6))

    ttk.Label(topbar, text="Instance:").pack(side="left", padx=(0,4))
    instance_filter = ttk.Combobox(topbar, values=["All"], width=24, state="readonly")
    instance_filter.current(0)
    instance_filter.pack(side="left", padx=(0,8))

    ttk.Label(topbar, text="Group:").pack(side="left", padx=(0,4))
    group_filter = ttk.Combobox(topbar, values=["All"], width=24, state="readonly")
    group_filter.current(0)
    group_filter.pack(side="left", padx=(0,8))

    ttk.Label(topbar, text="Tìm: ").pack(side="left", padx=(0,4))
    search_var = tk.StringVar()
    search_entry = ttk.Entry(topbar, textvariable=search_var, width=24)
    search_entry.pack(side="left", padx=(0,8))

    refresh_btn = ttk.Button(topbar, text="Refresh", width=10)
    refresh_btn.pack(side="right", padx=(4,0))

    # Treeview
    columns = ("instance", "group", "next_run", "repeat", "count", "status")
    tree = ttk.Treeview(frame, columns=columns, show="tree headings", selectmode="extended", height=12)
    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="left", fill="y")

    tree.heading("#0", text="")
    tree.column("#0", width=0, stretch=False)

    for col in columns:
        tree.heading(col, text=col.title())
    tree.column("instance", width=160, anchor="w")
    tree.column("group", width=160, anchor="w")
    tree.column("next_run", width=160, anchor="center")
    tree.column("repeat", width=80, anchor="center")
    tree.column("count", width=60, anchor="center")
    tree.column("status", width=90, anchor="center")

    # action bar
    actionbar = ttk.Frame(frame)
    actionbar.pack(fill="x", pady=(6,0))

    run_btn = ttk.Button(actionbar, text="Chạy ngay", width=12, command=lambda: _on_action_run_selected(tree))
    stop_btn = ttk.Button(actionbar, text="Dừng", width=12, command=lambda: _on_action_stop_selected(tree))
    del_btn = ttk.Button(actionbar, text="Xóa", width=12, command=lambda: _on_action_delete_selected(tree))
    run_btn.pack(side="left", padx=4)
    stop_btn.pack(side="left", padx=4)
    del_btn.pack(side="left", padx=4)

    def build_groups():
        groups = {}
        for idx, j in enumerate(jobs_list):
            key = (j.instance or "-", j.group_name or (j.job_type if getattr(j,'is_group',False) else "single"))
            groups.setdefault(key, []).append((idx, j))
        return groups

    def refresh_tree():
        groups = build_groups()
        instances = sorted({k[0] for k in groups.keys()})
        groups_names = sorted({k[1] for k in groups.keys()})

        instance_vals = ["All"] + instances
        group_vals = ["All"] + groups_names
        instance_filter.configure(values=instance_vals)
        group_filter.configure(values=group_vals)

        inst_sel = instance_filter.get()
        grp_sel = group_filter.get()
        search_text = search_var.get().strip().lower()

        for it in tree.get_children():
            tree.delete(it)

        # sort groups by earliest scheduled_time
        def group_key(kv):
            job_list = kv[1]
            times = [getattr(j,'scheduled_time') or datetime.max for _,j in job_list]
            return min(times) if times else datetime.max

        sorted_groups = sorted(groups.items(), key=group_key)
        for (inst, grp), job_list in sorted_groups:
            if inst_sel and inst_sel != "All" and inst != inst_sel:
                continue
            if grp_sel and grp_sel != "All" and grp != grp_sel:
                continue
            next_times = sorted((getattr(j,'scheduled_time') for _,j in job_list if getattr(j,'scheduled_time',None)), key=lambda x: x or datetime.max)
            next_run = next_times[0] if next_times else None
            next_run_str = next_run.strftime("%Y-%m-%d %H:%M:%S") if next_run else (job_list[0][1].time_str or "-")
            repeat = "Yes" if any(getattr(j,'is_repeating',False) for _,j in job_list) else "No"
            count = len(job_list)
            status = "Đã hẹn"
            if any(j.status == "Đang chạy" for _,j in job_list): status = "Đang chạy"
            elif all(j.status == "Đã chạy" for _,j in job_list): status = "Đã chạy"
            elif any(j.status == "Lỗi" for _,j in job_list): status = "Lỗi"

            label_text = f"{inst} | {grp} | {next_run_str}"
            if search_text and search_text not in label_text.lower():
                continue

            parent_id = tree.insert("", "end", iid=f"group_{inst}_{grp}", values=(inst, grp, next_run_str, repeat, count, status), tags=(status,))
            for idx, j in sorted(job_list, key=lambda x: getattr(x[1],'scheduled_time') or datetime.max):
                sub_time = getattr(j,'scheduled_time',None)
                sub_time_str = sub_time.strftime("%Y-%m-%d %H:%M:%S") if sub_time else (j.time_str or "-")
                # child iid is job_{index}
                tree.insert(parent_id, "end", iid=f"job_{idx}", values=(j.instance, j.group_name or j.job_type, sub_time_str, '-', '-', j.status), tags=(j.status,))

    refresh_btn.configure(command=refresh_tree)
    instance_filter.bind("<<ComboboxSelected>>", lambda e: refresh_tree())
    group_filter.bind("<<ComboboxSelected>>", lambda e: refresh_tree())
    search_entry.bind("<Return>", lambda e: refresh_tree())

    # initial populate
    refresh_tree()

    return {
        "frame": frame,
        "tree": tree,
        "refresh": refresh_tree,
        "instance_filter": instance_filter,
        "group_filter": group_filter,
        "search_var": search_var
    }

# ------------------- End new scheduled panel -------------------

# ... rest of existing gui.py functions remain unchanged until update_jobs_list

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

# (Keep all other functions as in original file) -- truncated here for brevity in this message

# We need to update update_jobs_list to use scheduled_panel if exists

def update_jobs_list():
    global scheduled_panel
    # If we have the new scheduled panel, use its refresh which provides grouped view
    if scheduled_panel and scheduled_panel.get('refresh'):
        try:
            scheduled_panel['refresh']()
        except Exception as e:
            logger.error(f"Lỗi khi refresh scheduled_panel: {e}")
        return

    # Original fallback behavior (keeps existing UI if scheduled_panel not initialized)
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

            # ==================== CÔNG VIỆC ĐÃ HOÀN THÀNH ====================
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

            # Cập nhật nút tạm dừng
            global pause_button
            if pause_button and pause_button.winfo_exists():
                pause_button.config(text="Tiếp tục" if is_paused else "Tạm dừng")
                
        except Exception as e:
            logger.error(f"Lỗi khi update_jobs_list (safe_update): {e}")

    # Đẩy về main thread
    if root and root.winfo_exists():
        root.after(0, safe_update)

# ----------------- In create_gui we'll replace the old jobs_list_frame block with the new panel -----------------

def create_gui():
    global var_dict, record_line_var, schedule_time_var, key_input_var, group_var, group_combo
    global delay_time_var, subtract_time_var, repeat_interval_var, schedule_list_frame, root, default_status_label
    global pause_button
    global canvas, scrollable_frame, scheduled_panel

    load_action_groups()
    load_jobs()

    root = tk.Tk()
    filename = os.path.basename(sys.argv[0]) if sys.argv else "unknown.py"
    root.title(f"LDPlayer Multi-Launcher + Script Clicker ({filename})")
    root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
    root.protocol("WM_DELETE_WINDOW", on_closing)

    main_frame = ttk.Frame(root, padding=10)
    main_frame.pack(fill="both", expand=True)

    # ... existing setup code unchanged until group_frame creation ...

    # After creating group_frame and key_frame, create the new scheduled jobs panel
    scheduled_panel = build_scheduled_jobs_panel(main_frame, jobs, None, None, None, None)

    # start scheduler thread
    threading.Thread(target=scheduled_checker, args=(jobs, update_jobs_list, save_jobs), daemon=True).start()
    update_jobs_list()
    root.mainloop()

# keep on_closing and main guard

def on_closing():
    global is_running, root
    is_running = False
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
