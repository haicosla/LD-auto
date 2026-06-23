import threading
import time
import traceback
from datetime import datetime, timedelta

from config import is_running, is_paused, running_threads
from job import Job, jobs, save_jobs
from action_groups import ACTION_GROUPS
from executor import execute_single_job, run_group_actions
from logger import get_logger

logger = get_logger()

def run_group_in_thread(group_job, update_ui_callback, save_jobs_callback):
    thread_name = f"GroupThread-{group_job.group_name}-{group_job.instance}"
    threading.current_thread().name = thread_name

    try:
        logger.info(f"[SCHED] Bắt đầu thread nhóm '{group_job.group_name}' trên {group_job.instance}")

        group = next((g for g in ACTION_GROUPS if g["name"] == group_job.group_name), None)
        if not group:
            group_job.status = "Lỗi - Nhóm không tồn tại"
            logger.error(f"Nhóm '{group_job.group_name}' không tồn tại")
            return

        # === REBUILD group_jobs nếu cần (lặp lại) ===
        if not group_job.group_jobs or group_job.current_child_index >= len(group_job.group_jobs):
            logger.info(f"[SCHED] Rebuild group_jobs cho nhóm '{group_job.group_name}'")
            group_job.group_jobs = []
            group_job.current_child_index = 0
            now = datetime.now()
            current_time = group_job.scheduled_time or now

            for action in group["actions"]:
                time_str = current_time.strftime("%H:%M:%S")
                child = Job(
                    time_str=time_str,
                    instance=group_job.instance,
                    job_type=action["type"],
                    value=action.get("value"),
                    group_name=group_job.group_name
                )
                child.scheduled_time = current_time
                group_job.group_jobs.append(child)
                current_time += timedelta(seconds=action.get("delay", 0))

        # === CHẠY NHÓM MẶC ĐỊNH CHỈ 1 LẦN DUY NHẤT Ở ĐÂY ===
        from gui import default_group_name
        if default_group_name:
            try:
                from utils import run_default_group_if_exists
                run_default_group_if_exists(group_job.instance, default_group_name)
            except Exception as e:
                logger.warning(f"Không chạy được nhóm mặc định cho {group_job.instance}: {e}")

        # === THỰC THI CÁC HÀNH ĐỘNG CON ===
        while group_job.current_child_index < len(group_job.group_jobs) and not getattr(group_job, 'should_stop', False):
            child = group_job.group_jobs[group_job.current_child_index]

            # Chờ đến giờ
            if child.scheduled_time:
                diff = (child.scheduled_time - datetime.now()).total_seconds()
                if diff > 0:
                    sleep_sec = min(diff, 1.0)
                    while sleep_sec > 0 and not getattr(group_job, 'should_stop', False):
                        time.sleep(sleep_sec)
                        sleep_sec = min((child.scheduled_time - datetime.now()).total_seconds(), 1.0)

            if getattr(group_job, 'should_stop', False):
                break

            logger.info(f"[GROUP] Thực thi hành động {group_job.current_child_index + 1}/{len(group_job.group_jobs)}: {child.job_type} - {child.value}")

            # Thực thi child job (KHÔNG chạy default nữa ở đây)
            if child.job_type == "group":
                sub_group = next((g for g in ACTION_GROUPS if g["name"] == child.value), None)
                if sub_group:
                    run_group_actions(child.instance, sub_group["actions"])
                    child.status = "Đã chạy"
            else:
                success = execute_single_job(child)   # execute_single_job sẽ không chạy default nữa
                child.status = "Đã chạy" if success else "Lỗi"

            group_job.current_child_index += 1

            # Delay giữa các hành động
            if group_job.current_child_index < len(group["actions"]):
                delay = group["actions"][group_job.current_child_index - 1].get("delay", 0)
                if delay > 0:
                    remaining = delay
                    while remaining > 0 and not getattr(group_job, 'should_stop', False):
                        time.sleep(min(remaining, 1.0))
                        remaining -= 1.0

        # Kết thúc nhóm
        if getattr(group_job, 'should_stop', False):
            group_job.status = "Đã dừng"
        else:
            group_job.status = "Đã chạy"

        logger.info(f"[SCHED] Hoàn thành nhóm '{group_job.group_name}' trên {group_job.instance} → {group_job.status}")

        # Xử lý lặp lại
        if getattr(group_job, 'is_repeating', False) and not getattr(group_job, 'should_stop', False):
            next_time = datetime.now() + timedelta(seconds=group_job.repeat_interval)
            next_time_str = next_time.strftime("%H:%M:%S")

            new_job = Job(
                time_str=next_time_str,
                instance=group_job.instance,
                group_name=group_job.group_name,
                is_group=True,
                group_jobs=[],
                status="Đã hẹn"
            )
            new_job.is_repeating = True
            new_job.repeat_interval = group_job.repeat_interval
            new_job.update_scheduled_time()

            jobs.append(new_job)
            logger.info(f"[SCHED] Tạo job lặp mới lúc {next_time_str} (mỗi {group_job.repeat_interval}s)")

            save_jobs()
            if update_ui_callback:
                update_ui_callback()

    except Exception as e:
        logger.error(f"[SCHED] Lỗi nghiêm trọng trong thread nhóm {group_job.group_name}: {e}\n{traceback.format_exc()}")
        group_job.status = "Lỗi"
    finally:
        if group_job in running_threads:
            del running_threads[group_job]

def scheduled_checker(jobs_list_ref, update_ui_callback, save_jobs_callback):
    logger.info("[SCHED] Scheduler checker đã khởi động")

    while is_running:
        try:
            if is_paused:
                time.sleep(1)
                continue

            now = datetime.now()

            for job in jobs_list_ref[:]:   # copy list để tránh lỗi modify trong lúc duyệt
                if job.status != "Đã hẹn":
                    continue
                if job.scheduled_time is None:
                    job.update_scheduled_time()
                    continue

                diff = (job.scheduled_time - now).total_seconds()
                if diff > 15 or diff < -10:   # cửa sổ rộng hơn một chút
                    continue

                logger.info(f"[SCHED] Đến giờ job: {job} (diff = {diff:.1f}s)")

                if not job.is_group:
                    execute_single_job(job)
                    job.status = "Đã chạy" if job.status != "Lỗi" else "Lỗi"
                else:
                    if job not in running_threads:
                        job.status = "Đang chạy"
                        t = threading.Thread(
                            target=run_group_in_thread,
                            args=(job, update_ui_callback, save_jobs_callback),
                            daemon=False   # Không daemon để thread quan trọng không bị kill đột ngột
                        )
                        running_threads[job] = t
                        t.start()
                        logger.info(f"[SCHED] Khởi tạo thread cho nhóm {job.group_name}")

                if update_ui_callback:
                    update_ui_callback()
                if save_jobs_callback:
                    save_jobs_callback()

            time.sleep(0.8)   # giảm tần suất check một chút để đỡ CPU

        except Exception as e:
            logger.error(f"[SCHED] Lỗi trong scheduled_checker: {e}\n{traceback.format_exc()}")
            time.sleep(2)   # tránh loop crash liên tục