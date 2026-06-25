# gui_group_management.py - Quản lý nhóm hành động
import tkinter as tk
from tkinter import ttk, messagebox
from action_groups import ACTION_GROUPS, save_action_groups
from utils import auto_close_messagebox
from logger import get_logger

logger = get_logger()

# Biến toàn cục
groups_listbox = None
group_combo = None
group_var = None

def update_group_combobox():
    """Cập nhật danh sách nhóm trong combobox"""
    try:
        if group_combo:
            names = [g["name"] for g in ACTION_GROUPS]
            group_combo['values'] = names
            print(f"[UPDATE_COMBO] Hiện tại có {len(names)} nhóm: {names}")
            if names and (not group_var.get() or group_var.get() not in names):
                group_var.set(names[0])
    except Exception as e:
        print(f"[UPDATE_COMBO] Lỗi: {e}")

def manage_groups():
    """Mở cửa sổ quản lý nhóm hành động"""
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

def edit_group_window(group):
    """Cửa sổ chỉnh sửa/tạo nhóm hành động"""
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
            action = {"type": "group", "value": value, "delay": int(delay)}
        elif action_type == "record":
            if not value.isdigit():
                auto_close_messagebox("error", "Lỗi", "Giá trị cho 'record' phải là số!")
                return
            action = {"type": "record", "value": int(value), "delay": int(delay)}
        else:
            if not value:
                auto_close_messagebox("error", "Lỗi", "Vui lòng nhập giá trị hành động!")
                return
            action = {"type": action_type, "value": value, "delay": int(delay)}
       
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
            if not value or value not in [g["name"] for g in ACTION_GROUPS]:
                auto_close_messagebox("error", "Lỗi", f"Nhóm '{value}' không tồn tại!")
                return
            group_data["actions"][selected_action_index] = {"type": "group", "value": value, "delay": int(delay)}
        elif action_type == "record":
            if not value.isdigit():
                auto_close_messagebox("error", "Lỗi", "Giá trị cho 'record' phải là số!")
                return
            group_data["actions"][selected_action_index] = {"type": "record", "value": int(value), "delay": int(delay)}
        else:
            if not value:
                auto_close_messagebox("error", "Lỗi", "Vui lòng nhập giá trị hành động!")
                return
            group_data["actions"][selected_action_index] = {"type": action_type, "value": value, "delay": int(delay)}
        update_actions_listbox()
        selected_action_index = None
        value_var.set("")
        delay_var.set("")
  
    def delete_action():
        try:
            selected_idx = actions_listbox.curselection()[0]
            group_data["actions"].pop(selected_idx)
            update_actions_listbox()
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
            print(f"[SAVE_GROUP] Đã append nhóm mới: {new_name}")
        else:
            group.update(group_data)
            print(f"[SAVE_GROUP] Đã update nhóm cũ: {new_name}")
        save_action_groups()
        update_group_combobox()
        window.destroy()
        auto_close_messagebox("info", "Thành công", f"Nhóm '{new_name}' đã được {'tạo' if is_new else 'cập nhật'}.")
  
    ttk.Button(main_frame, text="Lưu nhóm", command=save_group).pack(side="right", padx=5, pady=10)
    ttk.Button(main_frame, text="Hủy", command=window.destroy).pack(side="right", padx=5, pady=10)
