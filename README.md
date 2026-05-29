# CutList Optimiser

A backend pipeline that receives a cut list, optimises piece placement across the minimum number of stock boards using Google OR-Tools, and generates a PDF layout plan with kerf-aware positioning.

Built as an MVP to demonstrate the core logic before cloud deployment (Pub/Sub, Cloud Run, Firestore).

---

## What It Does

1. Accepts a cut list payload (board dimensions, piece sizes, blade kerf)
2. Validates the input and assigns a unique Job ID
3. Runs a 2D bin-packing optimisation using OR-Tools CP-SAT
4. Generates a PDF showing exact piece placement per board
5. Reports job status (QUEUED, PROCESSING, SUCCESS, FAILED)

---

## Project Structure

```
cutlist-optimiser/
├── main.py            # Entry point — runs the full pipeline demo
├── solver.py          # OR-Tools CP-SAT optimisation logic
├── queue_runner.py    # Job queue with concurrent workers
├── pdf_generator.py   # ReportLab PDF generation
├── requirements.txt   # Python dependencies
└── output/            # Generated PDFs saved here (auto-created)
```

---

## Requirements

- Python 3.11+
- Conda (recommended for environment isolation)

Create a clean environment before installing — OR-Tools can conflict 
with existing protobuf versions in shared environments:

    conda create -n cutlist
    conda activate cutlist
    pip install -r requirements.txt

## Running the Demo

Make sure the cutlist environment is active first:

    conda activate cutlist
    python main.py

This runs a full pipeline with four sample jobs including one 
intentionally invalid payload to demonstrate validation. 
PDFs are saved to the output/ folder.

## Payload Format

```json
{
  "board": { "w": 2440, "h": 1220 },
  "kerf": 3,
  "pieces": [
    { "id": "Door-A", "w": 600, "h": 400, "qty": 4 },
    { "id": "Door-B", "w": 500, "h": 400, "qty": 2 }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `board.w` / `board.h` | integer (mm) | Stock board dimensions |
| `kerf` | integer (mm) | Blade thickness, default 3 mm |
| `pieces[].id` | string | Unique piece identifier |
| `pieces[].w` / `.h` | integer (mm) | Piece dimensions |
| `pieces[].qty` | integer | Number of this piece required |

---

## Sample Output

```
STEP 1: Submitting jobs to queue

  [18:00:01] NOTIFICATION  JOB-3F9A2C1B | QUEUED       | Job received and queued.
  [18:00:01] NOTIFICATION  JOB-7D4B8E2A | QUEUED       | Job received and queued.

STEP 2: Running queue with concurrent workers

  [18:00:03] NOTIFICATION  JOB-3F9A2C1B | SUCCESS      | Optimisation complete -- 2 board(s) needed
  [18:00:04] NOTIFICATION  JOB-7D4B8E2A | SUCCESS      | Optimisation complete -- 3 board(s) needed

STEP 3: Generating PDFs

  PDF saved: output/JOB-3F9A2C1B_cutlist.pdf
  PDF saved: output/JOB-7D4B8E2A_cutlist.pdf
```

---

## Planned Cloud Architecture

| Component | Solution |
|---|---|
| REST API | FastAPI on Cloud Run |
| Job Queue | Google Cloud Pub/Sub |
| Workers | Cloud Run (stateless, concurrent) |
| Job Storage | Cloud Firestore |
| PDF Storage | Google Cloud Storage |

---

## Notes

- Workers are stateless - each job is fully isolated, which avoids race conditions at scale
- The solver uses OR-Tools CP-SAT, the same engine used in Google's supply chain tooling
- Designed to handle 500,000+ requests per day via horizontal scaling

---

*Gomolemo -- Computer Science and Business Computing*
