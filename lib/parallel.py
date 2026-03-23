"""Parallel sprint execution using ThreadPoolExecutor."""
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from lib.checkpoint import save_checkpoint


def execute_parallel(sprints, queue, queue_path, checkpoints_dir, repo_root,
                     timeout=1800, notifier=None, max_workers=2, on_sprint_done=None):
    """Execute independent sprints in parallel using ThreadPoolExecutor."""
    queue_lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for sprint in sprints:
            future = executor.submit(
                _worker, sprint, queue, queue_path, checkpoints_dir,
                repo_root, timeout, notifier, queue_lock
            )
            futures[future] = sprint

        for future in as_completed(futures):
            sprint = futures[future]
            try:
                future.result()
            except Exception as e:
                with queue_lock:
                    queue.mark_failed(sprint["id"], str(e))
                    queue.save(queue_path)
                from lib.supervisor import _now_iso
                save_checkpoint(checkpoints_dir, sprint["id"], {
                    "sprint_id": sprint["id"],
                    "status": "failed",
                    "failed_at": _now_iso(),
                    "error": str(e)[:500],
                })

            if on_sprint_done:
                on_sprint_done()


def _worker(sprint, queue, queue_path, checkpoints_dir, repo_root,
            timeout, notifier, queue_lock):
    """Worker function for ThreadPoolExecutor."""
    from lib.supervisor import execute_sprint
    execute_sprint(sprint, queue, queue_path, checkpoints_dir, repo_root,
                   timeout=timeout, notifier=notifier, queue_lock=queue_lock)
