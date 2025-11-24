# packing.py — 2Dcutter ver4.0
#
# Builds board layouts using a shelf/row-based guillotine-feasible strategy.
# Integrates wrap-rule–filtered orientation candidates.
# Produces rows, placed items, and kerf CutRect entries.

from typing import Dict, List
from models import (
    MaterialSpec, ItemSpec, BoardLayout, RowLayout,
    PlacedItem, CutRect
)
from wrap_rules import get_orientation_candidates


# -------------------------------------------------------------
# Material assignment for "any" items
# -------------------------------------------------------------

def assign_any_items_to_materials(
    items: List[ItemSpec],
    materials: Dict[str, MaterialSpec],
    enforce_wrap_rules: bool = True
) -> None:
    """
    Items with material_key=None are assigned to the cheapest material
    (per area) that is physically capable of hosting at least ONE valid
    orientation of the item.
    """

    if not materials:
        raise ValueError("No materials available for assignment.")

    mats = list(materials.values())

    for it in items:
        if it.material_key is not None:
            continue

        # get orientation candidates for *each material*
        valid_materials = []
        for m in mats:
            cands, _ = get_orientation_candidates(it, enforce_wrap_rules=enforce_wrap_rules)
            if not cands:
                continue
            # Check each orientation fits physically
            fits = any(
                (w <= m.width_mm and h <= m.length_mm)
                for (w, h, _) in cands
            )
            if fits:
                valid_materials.append(m)

        if not valid_materials:
            raise ValueError(
                f"Item '{it.name}' cannot fit ANY material (considering rotations & wrap rules)."
            )

        # choose cheapest per area
        chosen = min(valid_materials, key=lambda m: (m.cost / (m.length_mm * m.width_mm)))
        it.material_key = chosen.name


# -------------------------------------------------------------
# Board / placement helpers
# -------------------------------------------------------------

def try_place_on_row(
    row: RowLayout,
    item: ItemSpec,
    board: BoardLayout,
    w: float, h: float, rotated: bool
) -> bool:
    """
    Attempts to place item with dimensions (w,h) into an existing row.
    Includes kerf insertion if not the first item in the row.
    Returns True if placed.
    """
    kerf = board.kerf
    available_x = row.board_width_mm

    # row height mismatch
    if h != row.h_mm:
        return False

    # compute required width
    needed = w + (kerf if row.items else 0)

    if row.x_cursor + needed > available_x:
        return False

    # kerf rect before item (if not first)
    if row.items:
        kr = CutRect(
            x_mm=row.x_cursor,
            y_mm=row.y_mm,
            width_mm=kerf,
            height_mm=row.h_mm,
            cut_length_mm=row.h_mm,
            orientation="V"
        )
        board.cut_rects.append(kr)
        row.x_cursor += kerf

    # place item
    p = PlacedItem(
        spec=item,
        material_name=board.material.name,
        board_index=board.index,
        x_mm=row.x_cursor,
        y_mm=row.y_mm,
        width_mm=w,
        height_mm=h,
        rotated=rotated
    )
    row.items.append(p)
    board.placed_items.append(p)
    row.x_cursor += w

    return True


def start_new_row(board: BoardLayout, h: float) -> RowLayout:
    """
    Creates a new row at next available Y, inserting a horizontal kerf if needed.
    """
    kerf = board.kerf

    if not board.rows:
        y0 = 0.0
    else:
        prev = board.rows[-1]
        # horizontal kerf
        kr = CutRect(
            x_mm=0.0,
            y_mm=prev.y_mm + prev.h_mm,
            width_mm=board.material.width_mm,
            height_mm=kerf,
            cut_length_mm=board.material.width_mm,
            orientation="H"
        )
        board.cut_rects.append(kr)
        y0 = prev.y_mm + prev.h_mm + kerf

    # create row
    r = RowLayout(y_mm=y0, h_mm=h, board_width_mm=board.material.width_mm)
    board.rows.append(r)
    return r


# -------------------------------------------------------------
# Board construction for one material
# -------------------------------------------------------------

def build_boards_for_material(
    material: MaterialSpec,
    item_specs: List[ItemSpec],
    kerf: float,
    enforce_wrap_rules: bool = True
) -> List[BoardLayout]:

    # expand quantities
    units: List[ItemSpec] = []
    for it in item_specs:
        for _ in range(it.quantity):
            units.append(it)

    # sort large-first
    units.sort(key=lambda it: max(it.length_mm, it.width_mm), reverse=True)

    boards: List[BoardLayout] = []

    for unit in units:
        placed = False

        # orientation candidates
        cands, _ = get_orientation_candidates(unit, enforce_wrap_rules=enforce_wrap_rules)
        if not cands:
            raise ValueError(f"Item '{unit.name}' has no valid orientation.")

        # try place in existing boards
        for b in boards:
            for w, h, rotated in cands:
                # try existing rows
                for row in b.rows:
                    if try_place_on_row(row, unit, b, w, h, rotated):
                        placed = True
                        break
                if placed:
                    break

                # try new row
                # check height feasibility
                if b.used_length_mm() + (b.kerf if b.rows else 0) + h <= material.length_mm:
                    new_row = start_new_row(b, h)
                    if try_place_on_row(new_row, unit, b, w, h, rotated):
                        placed = True
                        break
            if placed:
                break

        if placed:
            continue

        # else create new board
        nb = BoardLayout(material=material, index=len(boards), kerf=kerf)
        # try orientations; orientation guaranteed to fit as long as it's the first placement
        placed_in_new = False
        for w, h, rotated in cands:
            if w <= material.width_mm and h <= material.length_mm:
                # place first row
                first_row = start_new_row(nb, h)
                try_place_on_row(first_row, unit, nb, w, h, rotated)
                placed_in_new = True
                break
        if not placed_in_new:
            raise ValueError(f"Item '{unit.name}' cannot fit even on empty board.")
        boards.append(nb)

    return boards
