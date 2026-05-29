"""
solver.py — 2D CutList Optimiser using OR-Tools
Solves: how many boards are needed, and where to place each piece.
Accounts for blade kerf (material lost per cut).
"""

from ortools.sat.python import cp_model


def solve_cutlist(board_w: int, board_h: int, pieces: list[dict], kerf: int = 3) -> dict:
    """
    Solve the 2D bin packing problem for a cut list.

    Args:
        board_w:  Stock board width  in mm
        board_h:  Stock board height in mm
        pieces:   List of dicts: [{"id": "P1", "w": 400, "h": 300, "qty": 2}, ...]
        kerf:     Blade thickness in mm (default 3mm)

    Returns:
        dict with keys:
            boards_needed   — integer count
            placements      — list of placed piece dicts with board/x/y/w/h
            waste_pct       — percentage of board area wasted
            status          — "OPTIMAL" | "FEASIBLE" | "INFEASIBLE"
    """

    # Expand pieces by quantity into a flat list
    flat_pieces = []
    for p in pieces:
        for _ in range(p.get("qty", 1)):
            flat_pieces.append({
                "id": p["id"],
                "w": p["w"] + kerf,   # effective width includes one kerf
                "h": p["h"] + kerf,   # effective height includes one kerf
                "actual_w": p["w"],
                "actual_h": p["h"],
            })

    n = len(flat_pieces)
    # Upper bound: worst case is one piece per board
    max_boards = n

    model = cp_model.CpModel()

    # --- Decision variables ---
    # x[i], y[i]: top-left corner of piece i on its board
    # b[i]:       which board piece i is placed on
    x = [model.new_int_var(0, board_w, f"x_{i}") for i in range(n)]
    y = [model.new_int_var(0, board_h, f"y_{i}") for i in range(n)]
    b = [model.new_int_var(0, max_boards - 1, f"b_{i}") for i in range(n)]

    # board_used[k]: 1 if board k has at least one piece
    board_used = [model.new_bool_var(f"board_used_{k}") for k in range(max_boards)]

    # --- Constraints ---

    for i, piece in enumerate(flat_pieces):
        w_i = piece["w"]
        h_i = piece["h"]

        # Piece must fit within board boundaries
        model.add(x[i] + w_i <= board_w)
        model.add(y[i] + h_i <= board_h)

        # Link piece to board_used flag
        for k in range(max_boards):
            is_on_k = model.new_bool_var(f"piece_{i}_on_board_{k}")
            model.add(b[i] == k).only_enforce_if(is_on_k)
            model.add(b[i] != k).only_enforce_if(is_on_k.negated())
            # If piece is on board k, mark board k as used
            model.add_implication(is_on_k, board_used[k])

    # No overlap between pieces on the same board
    for i in range(n):
        for j in range(i + 1, n):
            w_i = flat_pieces[i]["w"]
            h_i = flat_pieces[i]["h"]
            w_j = flat_pieces[j]["w"]
            h_j = flat_pieces[j]["h"]

            same_board = model.new_bool_var(f"same_board_{i}_{j}")
            model.add(b[i] == b[j]).only_enforce_if(same_board)
            model.add(b[i] != b[j]).only_enforce_if(same_board.negated())

            # At least one separation must hold if on same board
            left  = model.new_bool_var(f"left_{i}_{j}")
            right = model.new_bool_var(f"right_{i}_{j}")
            above = model.new_bool_var(f"above_{i}_{j}")
            below = model.new_bool_var(f"below_{i}_{j}")

            model.add(x[i] + w_i <= x[j]).only_enforce_if([same_board, left])
            model.add(x[j] + w_j <= x[i]).only_enforce_if([same_board, right])
            model.add(y[i] + h_i <= y[j]).only_enforce_if([same_board, above])
            model.add(y[j] + h_j <= y[i]).only_enforce_if([same_board, below])

            model.add_bool_or([left, right, above, below, same_board.negated()])

    # Symmetry breaking: boards must be used in order (board 0 before board 1, etc.)
    for k in range(1, max_boards):
        model.add(board_used[k] <= board_used[k - 1])

    # --- Objective: minimise number of boards ---
    model.minimize(sum(board_used))

    # --- Solve ---
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0
    solver.parameters.num_search_workers = 4
    status = solver.solve(model)

    status_map = {
        cp_model.OPTIMAL:   "OPTIMAL",
        cp_model.FEASIBLE:  "FEASIBLE",
        cp_model.INFEASIBLE:"INFEASIBLE",
        cp_model.UNKNOWN:   "UNKNOWN",
    }

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        boards_needed = int(solver.objective_value)
        placements = []
        for i, piece in enumerate(flat_pieces):
            placements.append({
                "piece_id":  piece["id"],
                "board":     solver.value(b[i]),
                "x":         solver.value(x[i]),
                "y":         solver.value(y[i]),
                "w":         piece["actual_w"],
                "h":         piece["actual_h"],
                "w_kerf":    piece["w"],
                "h_kerf":    piece["h"],
            })

        total_piece_area = sum(p["actual_w"] * p["actual_h"] for p in flat_pieces)
        total_board_area = boards_needed * board_w * board_h
        waste_pct = round((1 - total_piece_area / total_board_area) * 100, 1) if total_board_area > 0 else 0

        return {
            "status":        status_map[status],
            "boards_needed": boards_needed,
            "placements":    placements,
            "waste_pct":     waste_pct,
            "board_w":       board_w,
            "board_h":       board_h,
            "kerf":          kerf,
        }
    else:
        return {
            "status":        status_map.get(status, "UNKNOWN"),
            "boards_needed": None,
            "placements":    [],
            "waste_pct":     None,
            "board_w":       board_w,
            "board_h":       board_h,
            "kerf":          kerf,
        }
