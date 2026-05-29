"""
pdf_generator.py — Converts OR-Tools placement results into a visual PDF.
One page per board. Shows exact cut layout with dimensions and labels.
"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.units import mm


# Colour palette for pieces (cycles through for large cut lists)
PIECE_COLOURS = [
    colors.HexColor("#4A90D9"),
    colors.HexColor("#7BC67E"),
    colors.HexColor("#F5A623"),
    colors.HexColor("#E8584A"),
    colors.HexColor("#9B59B6"),
    colors.HexColor("#1ABC9C"),
    colors.HexColor("#F39C12"),
    colors.HexColor("#E74C3C"),
    colors.HexColor("#3498DB"),
    colors.HexColor("#2ECC71"),
]

PAGE_W, PAGE_H = A4          # 595 x 842 points
MARGIN        = 40           # points from edge
HEADER_H      = 80           # points reserved for header text
FOOTER_H      = 40


def _scale_factor(board_w: int, board_h: int) -> tuple[float, float, float]:
    """Calculate scale so the board fits on the page with margins."""
    draw_w = PAGE_W - 2 * MARGIN
    draw_h = PAGE_H - MARGIN - HEADER_H - FOOTER_H

    scale = min(draw_w / board_w, draw_h / board_h)
    offset_x = MARGIN + (draw_w - board_w * scale) / 2
    offset_y  = FOOTER_H + (draw_h - board_h * scale) / 2
    return scale, offset_x, offset_y


def generate_pdf(result: dict, job_id: str, output_dir: str = "output") -> str:
    """
    Generate a cut layout PDF from solver results.

    Args:
        result:     The dict returned by solver.solve_cutlist()
        job_id:     Used for filename and header label
        output_dir: Where to save the PDF

    Returns:
        Path to the saved PDF file.
    """
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f"{job_id}_cutlist.pdf")

    board_w = result["board_w"]
    board_h = result["board_h"]
    kerf    = result["kerf"]
    boards_needed = result["boards_needed"]
    placements    = result["placements"]

    # Group placements by board number
    boards: dict[int, list] = {}
    for p in placements:
        boards.setdefault(p["board"], []).append(p)

    # Assign a consistent colour per piece_id
    piece_ids = list({p["piece_id"] for p in placements})
    colour_map = {pid: PIECE_COLOURS[i % len(PIECE_COLOURS)] for i, pid in enumerate(piece_ids)}

    c = rl_canvas.Canvas(filename, pagesize=A4)
    scale, off_x, off_y = _scale_factor(board_w, board_h)

    for board_num in sorted(boards.keys()):
        pieces_on_board = boards[board_num]

        # ── Header ──────────────────────────────────────────────────────────
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(colors.HexColor("#1A1A2E"))
        c.drawString(MARGIN, PAGE_H - 30, f"CutList Optimizer — Job {job_id}")

        c.setFont("Helvetica", 10)
        c.setFillColor(colors.HexColor("#555555"))
        c.drawString(MARGIN, PAGE_H - 48,
                     f"Board {board_num + 1} of {boards_needed}    "
                     f"Stock: {board_w} x {board_h} mm    "
                     f"Kerf: {kerf} mm    "
                     f"Pieces on this board: {len(pieces_on_board)}")

        c.drawString(MARGIN, PAGE_H - 64,
                     f"Waste: {result['waste_pct']}% of total board area    "
                     f"Status: {result['status']}")

        # ── Board outline ────────────────────────────────────────────────────
        bx = off_x
        by = off_y
        bw = board_w * scale
        bh = board_h * scale

        c.setStrokeColor(colors.HexColor("#1A1A2E"))
        c.setLineWidth(1.5)
        c.setFillColor(colors.HexColor("#F5F5F0"))
        c.rect(bx, by, bw, bh, fill=1, stroke=1)

        # ── Draw pieces ──────────────────────────────────────────────────────
        for piece in pieces_on_board:
            px = off_x + piece["x"] * scale
            py = off_y + piece["y"] * scale
            pw = piece["w"] * scale
            ph = piece["h"] * scale

            colour = colour_map[piece["piece_id"]]

            # Fill
            c.setFillColor(colour)
            c.setStrokeColor(colors.white)
            c.setLineWidth(0.5)
            c.rect(px, py, pw, ph, fill=1, stroke=1)

            # Kerf gap indicator (dashed border showing blade loss)
            kerf_px = kerf * scale
            c.setStrokeColor(colors.HexColor("#CC3300"))
            c.setLineWidth(0.3)
            c.setDash([2, 2])
            c.rect(px + kerf_px / 2, py + kerf_px / 2,
                   pw - kerf_px, ph - kerf_px,
                   fill=0, stroke=1)
            c.setDash()

            # Piece label
            label = piece["piece_id"]
            dim   = f"{piece['w']}x{piece['h']}"

            font_size = max(5, min(9, int(pw / 6), int(ph / 3)))
            c.setFont("Helvetica-Bold", font_size)
            c.setFillColor(colors.white)

            label_x = px + pw / 2
            label_y = py + ph / 2 + font_size * 0.3

            # Only draw text if piece is large enough
            if pw > 25 and ph > 18:
                c.drawCentredString(label_x, label_y, label)
                c.setFont("Helvetica", max(5, font_size - 2))
                c.drawCentredString(label_x, label_y - font_size * 1.2, dim)

        # ── Legend ───────────────────────────────────────────────────────────
        legend_y = FOOTER_H - 10
        c.setFont("Helvetica", 7)
        c.setFillColor(colors.HexColor("#333333"))
        c.drawString(MARGIN, legend_y + 14, "Legend:")

        lx = MARGIN + 50
        for pid in piece_ids:
            col = colour_map[pid]
            c.setFillColor(col)
            c.rect(lx, legend_y + 6, 10, 10, fill=1, stroke=0)
            c.setFillColor(colors.HexColor("#333333"))
            c.setFont("Helvetica", 7)
            c.drawString(lx + 13, legend_y + 12, pid)
            lx += len(pid) * 5 + 30
            if lx > PAGE_W - MARGIN - 60:
                break

        # Red dashed = kerf zone indicator
        c.setStrokeColor(colors.HexColor("#CC3300"))
        c.setDash([2, 2])
        c.setLineWidth(0.5)
        c.rect(lx + 2, legend_y + 6, 10, 10, fill=0, stroke=1)
        c.setDash()
        c.setFillColor(colors.HexColor("#333333"))
        c.setFont("Helvetica", 7)
        c.drawString(lx + 15, legend_y + 12, "Kerf zone")

        c.showPage()

    # ── Summary page ─────────────────────────────────────────────────────────
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(colors.HexColor("#1A1A2E"))
    c.drawString(MARGIN, PAGE_H - 60, "CutList Optimisation Summary")

    c.setFont("Helvetica", 11)
    c.setFillColor(colors.HexColor("#333333"))
    rows = [
        ("Job ID",          job_id),
        ("Status",          result["status"]),
        ("Boards needed",   str(boards_needed)),
        ("Stock size",      f"{board_w} x {board_h} mm"),
        ("Kerf (blade)",    f"{kerf} mm"),
        ("Total pieces",    str(len(placements))),
        ("Waste",           f"{result['waste_pct']}% of total board area"),
    ]

    row_y = PAGE_H - 100
    for label, value in rows:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(MARGIN, row_y, f"{label}:")
        c.setFont("Helvetica", 10)
        c.drawString(MARGIN + 130, row_y, value)
        row_y -= 20

    # Piece summary table
    row_y -= 20
    c.setFont("Helvetica-Bold", 10)
    c.drawString(MARGIN, row_y, "Piece placement breakdown:")
    row_y -= 20

    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#1A1A2E"))
    for col, label in [(MARGIN, "Piece ID"), (MARGIN+80, "Board #"), (MARGIN+150, "X (mm)"), (MARGIN+220, "Y (mm)"), (MARGIN+290, "W (mm)"), (MARGIN+360, "H (mm)")]:
        c.drawString(col, row_y, label)

    row_y -= 5
    c.setStrokeColor(colors.HexColor("#CCCCCC"))
    c.line(MARGIN, row_y, PAGE_W - MARGIN, row_y)
    row_y -= 14

    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#333333"))
    for p in placements:
        if row_y < FOOTER_H + 20:
            c.showPage()
            row_y = PAGE_H - 60
        c.drawString(MARGIN,       row_y, p["piece_id"])
        c.drawString(MARGIN + 80,  row_y, str(p["board"] + 1))
        c.drawString(MARGIN + 150, row_y, str(p["x"]))
        c.drawString(MARGIN + 220, row_y, str(p["y"]))
        c.drawString(MARGIN + 290, row_y, str(p["w"]))
        c.drawString(MARGIN + 360, row_y, str(p["h"]))
        row_y -= 14

    c.save()
    return filename
