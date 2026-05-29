"""
main.py — MVP entry point
Run this file to see the full pipeline:
  1. Submit multiple cut list jobs (with validation)
  2. Queue processes them concurrently
  3. PDF generated for each successful job
  4. Status report printed
"""

import os
from queue_runner import create_job, run_queue, get_job_status, _job_store, STATUS
from pdf_generator import generate_pdf


# ── Sample cut list jobs (edit these freely) ─────────────────────────────────

SAMPLE_JOBS = [
    {
        "name": "Kitchen Cabinet Doors",
        "payload": {
            "board": {"w": 2440, "h": 1220},
            "kerf": 3,
            "pieces": [
                {"id": "Door-A", "w": 600, "h": 400, "qty": 4},
                {"id": "Door-B", "w": 500, "h": 400, "qty": 2},
                {"id": "Panel",  "w": 800, "h": 300, "qty": 2},
            ],
        },
    },
    {
        "name": "Bookshelf Panels",
        "payload": {
            "board": {"w": 2440, "h": 1220},
            "kerf": 4,
            "pieces": [
                {"id": "Side",   "w": 900, "h": 350, "qty": 2},
                {"id": "Shelf",  "w": 800, "h": 300, "qty": 4},
                {"id": "Back",   "w": 800, "h": 900, "qty": 1},
            ],
        },
    },
    {
        "name": "Small Offcuts",
        "payload": {
            "board": {"w": 1200, "h": 600},
            "kerf": 3,
            "pieces": [
                {"id": "Block-A", "w": 200, "h": 150, "qty": 6},
                {"id": "Block-B", "w": 300, "h": 200, "qty": 3},
            ],
        },
    },
    {
        "name": "INVALID — piece too large (shows validation)",
        "payload": {
            "board": {"w": 1000, "h": 500},
            "kerf": 3,
            "pieces": [
                {"id": "Giant", "w": 1200, "h": 400, "qty": 1},  # wider than board
            ],
        },
    },
]


def main():
    print("\n" + "═"*60)
    print("  CutList Optimizer MVP — Full Pipeline Demo")
    print("═"*60 + "\n")

    # ── Step 1: Submit all jobs ──────────────────────────────────────────────
    print("STEP 1: Submitting jobs to queue\n")
    job_ids = []

    for job_def in SAMPLE_JOBS:
        print(f"  → Submitting: {job_def['name']}")
        try:
            job_id = create_job(job_def["payload"])
            job_ids.append(job_id)
        except ValueError as e:
            print(f"    ✗ Rejected: {e}\n")

    # ── Step 2: Run queue concurrently ──────────────────────────────────────
    print("\nSTEP 2: Running queue with concurrent workers\n")
    run_queue(max_workers=4)

    # ── Step 3: Generate PDFs for successful jobs ───────────────────────────
    print("STEP 3: Generating PDFs\n")
    pdf_paths = []

    for job_id in job_ids:
        state = get_job_status(job_id)
        if state["status"] == "SUCCESS":
            path = generate_pdf(
                result=state["result"],
                job_id=job_id,
                output_dir="output",
            )
            pdf_paths.append(path)
            print(f"  ✓ PDF saved: {path}")
        elif state["status"] == "FAILED":
            print(f"  ✗ {job_id} failed: {state['error']}")

    # ── Step 4: Print final status report ───────────────────────────────────
    print("\n" + "═"*60)
    print("  FINAL STATUS REPORT")
    print("═"*60)

    header = f"  {'Job ID':<20} {'Status':<14} {'Boards':>7} {'Waste':>8}  Name"
    print(header)
    print("  " + "─"*70)

    for job_id in job_ids:
        state = get_job_status(job_id)
        result = state.get("result") or {}
        boards = result.get("boards_needed", "—")
        waste  = f"{result.get('waste_pct', '—')}%" if result.get("waste_pct") is not None else "—"
        status = state["status"]

        # Find name from job store
        raw_payload = _job_store[job_id]["payload"]

        icon = "✓" if status == "SUCCESS" else "✗"
        print(f"  {icon} {job_id:<18} {status:<14} {str(boards):>7} {waste:>8}")

    print("\n  PDFs saved to: ./output/")
    print("═"*60 + "\n")


if __name__ == "__main__":
    main()
