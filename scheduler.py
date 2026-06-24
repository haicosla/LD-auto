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
    """Chạy một job nhóm trong thread riêng biệt"""
    thread_name = f"GroupThread-{group_job.group_name}-{group_job.instance}"
    threading.current_thread().name = thread_name

    try:
        logger.info(f"[SCHED] Bắt đầu thread nhóm '{group_job.group_name}' trên {group_job.instance}")

        group = next((g for g in ACTION_GROUPS if g["name"] == group_job.group_name), None)
        if not group:
            group_job.status = "Lỗi - Nhóm không tồn tại"
            logger.error(f"Nhóm '{group_job.group_name}' không tồn tại")
            return False

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
        # Import từ utils để tránh circular import
        from utils import run_default_group_if_exists
        
        # Lấy giá trị default_group_name tại thời điểm này (snapshot)
        try:
            from gui import default_group_name
            default_group_snapshot = default_group_name
        except:
            default_group_snapshot = None

        if default_group_snapshot:
            try:
                logger.info(f"[SCHED] Chạy nhóm mặc định '{default_group_snapshot}' trước nhóm chính")
                run_default_group_if_exists(group_job.instance, default_group_snapshot)
                logger.info(f"[SCHED] Hoàn thành nhóm mặc định")
                time.sleep(1)  # Đợi một chút sau nhóm mặc định
            except Exception as e:
                logger.warning(f"[SCHED] Không chạy được nhóm mặc định cho {group_job.instance}: {e}")

        # === THỰC THI CÁC HÀNH ĐỘNG CON ===
        action_success_count = 0
        while group_job.current_child_index < len(group_job.group_jobs) and not getattr(group_job, 'should_stop', False):
            child = group_job.group_jobs[group_job.current_child_index]

            # Chờ đến giờ của child job
            if child.scheduled_time:
                diff = (child.scheduled_time - datetime.now()).total_seconds()
                if diff > 0:
                    logger.debug(f"[SCHED] Chờ {diff:.1f}s để thực thi hành động tiếp theo")
                    sleep_sec = min(diff, 1.0)
                    while sleep_sec > 0 and not getattr(group_job, 'should_stop', False):
                        time.sleep(sleep_sec)
                        sleep_sec = min((child.scheduled_time - datetime.now()).total_seconds(), 1.0)

            if getattr(group_job, 'should_stop', False):
                logger.info(f"[SCHED] Job nhóm đã được dừng ở hành động {group_job.current_child_index + 1}")
                break

            logger.info(f"[SCHED] Thực thi hành động {group_job.current_child_index + 1}/{len(group_job.group_jobs)}: {child.job_type} - {child.value}")

            # Thực thi child job
            try:
                if child.job_type == "group":
                    # Nhóm con lồng nhau
                    sub_group = next((g for g in ACTION_GROUPS if g["name"] == child.value), None)
                    if sub_group:
                        success = run_group_actions(child.instance, sub_group["actions"], group_name=child.value)
                        child.status = "Đã chạy" if success else "Lỗi"
                    else:
                        child.status = "Lỗi - Nhóm con không tồn tại"
                        logger.error(f"[SCHED] Nhóm con '{child.value}' không tồn tại")
                else:
                    # Job đơn lẻ
                    success = execute_single_job(child)
                    if success:
                        action_success_count += 1
                        child.status = "Đã chạy"
                    else:
                        child.status = "Lỗi"
            except Exception as e:
                logger.error(f"[SCHED] Lỗi khi thực thi hành động {group_job.current_child_index + 1}: {e}")
                child.status = "Lỗi"

            group_job.current_child_index += 1
            
            # Update UI sau mỗi hành động
            if update_ui_callback:
                update_ui_callback()

        # Kết thúc nhóm
        if getattr(group_job, 'should_stop', False):
            group_job.status = "Đã dừng"
            logger.warning(f"[SCHED] Nhóm '{group_job.group_name}' đã bị dừng bởi người dùng")
        else:
            group_job.status = "Đã chạy"
            logger.info(f"[SCHED] Nhóm '{group_job.group_name}' hoàn thành thành công ({action_success_count} hành động)")

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

        return True

    except Exception as e:
        logger.error(f"[SCHED] Lỗi nghiêm trọng trong thread nhóm {group_job.group_name}: {e}\n{traceback.format_exc()}")
        group_job.status = "Lỗi"
        return False
    finally:
        if group_job in running_threads:
            del running_threads[group_job]

def scheduled_checker(jobs_list_ref, update_ui_callback, save_jobs_callback):
    """
    Vòng lặp chính để kiểm tra và thực thi các job hẹn giờ.
    Chạy trong thread daemon.
    """
    logger.info("[SCHED] Scheduler checker đã khởi động")

    while is_running:
        try:
            if is_paused:
                logger.debug("[SCHED] Scheduler tạm dừng")
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
                # Cửa sổ thực thi: ±10 giây (tránh miss job, tránh chạy 2 lần)
                if diff > 10 or diff < -10:
                    continue

                logger.info(f"[SCHED] Đến giờ job: {job} (diff = {diff:.1f}s)")

                if not job.is_group:
                    # Job đơn lẻ - thực thi ngay
                    success = execute_single_job(job)
                    job.status = "Đã chạy" if success else "Lỗi"
                    logger.info(f"[SCHED] Job đơn lẻ kết thúc: {job.job_type} - {job.status}")
                else:
                    # Job nhóm - chạy trong thread riêng
                    if job not in running_threads:
                        job.status = "Đang chạy"
                        t = threading.Thread(
                            target=run_group_in_thread,
                            args=(job, update_ui_callback, save_jobs_callback),
                            daemon=False   # Không daemon để thread quan trọng không bị kill đột ngột
                        )
                        running_threads[job] = t
                        t.start()
                        logger.info(f"[SCHED] Khởi tạo thread cho nhóm '{job.group_name}' trên {job.instance}")

                if update_ui_callback:
                    update_ui_callback()
                if save_jobs_callback:
                    save_jobs_callback()

            time.sleep(0.5)   # Check mỗi 0.5 giây (thay vì 0.8s) để không miss job

        except Exception as e:
            logger.error(f"[SCHED] Lỗi trong scheduled_checker: {e}\n{traceback.format_exc()}")
            time.sleep(2)   # tránh loop crash liên tục
