"""
queue_runner.py — Local job queue with concurrent workers
Simulates Cloud Pub/Sub + Cloud Run workers on your local machine.
Jobs are picked up first-come-first-served and run in parallel.
"""

import uuid
import time
import json
import multiprocessing
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
from solver import solve_cutlist


# ── Status codes (mirrors production Firestore design) ──────────────────────
STATUS = {
    "QUEUED":     0,
    "PROCESSING": 1,
    "SUCCESS":    2,
    "FAILED":    -1,
}

# In-memory store (replaces Firestore for the MVP)
_job_store: dict = {}


def create_job(payload: dict) -> str:
    """Validate payload, assign a Job ID, add to queue. Returns job_id."""

    errors = _validate(payload)
    if errors:
        raise ValueError(f"Invalid payload: {errors}")

    job_id = f"JOB-{uuid.uuid4().hex[:8].upper()}"
    _job_store[job_id] = {
        "job_id":     job_id,
        "status":     STATUS["QUEUED"],
        "created_at": datetime.utcnow().isoformat(),
        "payload":    payload,
        "result":     None,
        "error":      None,
    }
    _notify(job_id, "QUEUED", f"Job received and queued. Your ID: {job_id}")
    return job_id


def get_job_status(job_id: str) -> dict:
    """Return current state of a job."""
    job = _job_store.get(job_id)
    if not job:
        return {"error": f"Job {job_id} not found"}
    label = {v: k for k, v in STATUS.items()}.get(job["status"], "UNKNOWN")
    return {
        "job_id":     job["job_id"],
        "status":     label,
        "status_code":job["status"],
        "created_at": job["created_at"],
        "result":     job["result"],
        "error":      job["error"],
    }


def _validate(payload: dict) -> list[str]:
    """Returns list of validation errors. Empty list = valid."""
    errors = []

    board = payload.get("board")
    if not board:
        errors.append("Missing 'board' field")
    else:
        if not isinstance(board.get("w"), (int, float)) or board["w"] <= 0:
            errors.append("board.w must be a positive number")
        if not isinstance(board.get("h"), (int, float)) or board["h"] <= 0:
            errors.append("board.h must be a positive number")

    kerf = payload.get("kerf", 3)
    if not isinstance(kerf, (int, float)) or kerf < 0:
        errors.append("kerf must be a non-negative number")

    pieces = payload.get("pieces")
    if not pieces or not isinstance(pieces, list):
        errors.append("'pieces' must be a non-empty list")
    else:
        for i, p in enumerate(pieces):
            if not p.get("id"):
                errors.append(f"pieces[{i}] missing 'id'")
            if not isinstance(p.get("w"), (int, float)) or p["w"] <= 0:
                errors.append(f"pieces[{i}].w must be positive")
            if not isinstance(p.get("h"), (int, float)) or p["h"] <= 0:
                errors.append(f"pieces[{i}].h must be positive")
            if board and p.get("w") and p.get("h"):
                if p["w"] >= board.get("w", 0) or p["h"] >= board.get("h", 0):
                    errors.append(f"pieces[{i}] ({p['w']}x{p['h']}) is too large for the board ({board.get('w')}x{board.get('h')})")

    return errors


def _notify(job_id: str, event: str, message: str):
    """Simulates the push notification back to the app."""
    ts = datetime.utcnow().strftime("%H:%M:%S")
    print(f"  [{ts}] NOTIFICATION → {job_id} | {event:12s} | {message}")


def _worker(job_id: str, job: dict) -> tuple[str, dict]:
    """
    Runs inside a separate process.
    This is the equivalent of one Cloud Run instance picking up a job.
    """
    payload = job["payload"]
    try:
        result = solve_cutlist(
            board_w=int(payload["board"]["w"]),
            board_h=int(payload["board"]["h"]),
            pieces=payload["pieces"],
            kerf=int(payload.get("kerf", 3)),
        )
        return (job_id, {"success": True, "result": result})
    except Exception as e:
        return (job_id, {"success": False, "error": str(e)})


def run_queue(max_workers: int = 4):
    """
    Processes all queued jobs concurrently.
    max_workers = number of parallel processes (mirrors Cloud Run instances).
    """
    queued = [
        (jid, job)
        for jid, job in _job_store.items()
        if job["status"] == STATUS["QUEUED"]
    ]

    if not queued:
        print("Queue is empty — nothing to process.")
        return

    print(f"\n{'─'*60}")
    print(f"  Queue: {len(queued)} jobs | Workers: {max_workers} parallel processes")
    print(f"{'─'*60}\n")

    # Mark all as PROCESSING before handing off
    for job_id, _ in queued:
        _job_store[job_id]["status"] = STATUS["PROCESSING"]
        _notify(job_id, "PROCESSING", "Worker picked up job — optimising now...")

    start = time.time()

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_worker, job_id, job): job_id
            for job_id, job in queued
        }
        for future in as_completed(futures):
            job_id, outcome = future.result()
            if outcome["success"]:
                _job_store[job_id]["status"] = STATUS["SUCCESS"]
                _job_store[job_id]["result"] = outcome["result"]
                _notify(job_id, "SUCCESS", f"Optimisation complete — {outcome['result']['boards_needed']} board(s) needed")
            else:
                _job_store[job_id]["status"] = STATUS["FAILED"]
                _job_store[job_id]["error"] = outcome["error"]
                _notify(job_id, "FAILED", f"Error: {outcome['error']}")

    elapsed = time.time() - start
    print(f"\n  All jobs processed in {elapsed:.2f}s\n")
