# costing.py — 2Dcutter ver4.0
#
# Computes material usage, wrap and cut totals, and prepares values for summary tables.
# Currency formatting is done in pdf_export.py, but numeric totals are prepared here.

from dataclasses import dataclass, field
from typing import Dict, List
from models import BoardLayout, MaterialSpec, PlacedItem
from wrap_rules import _side_count


# -------------------------------------------------------------
# Data structures
# -------------------------------------------------------------

@dataclass
class MaterialUsageSummary:
    material: MaterialSpec
    full_boards: int = 0
    narrow_halves: int = 0
    wide_halves: int = 0
    billed_quantity: float = 0.0    # full + half fractions
    cost: float = 0.0               # billed_quantity * material.cost


@dataclass
class GlobalSummary:
    material_usages: Dict[str, MaterialUsageSummary] = field(default_factory=dict)

    total_wrap_length_mm: float = 0.0
    total_wrap_cost: float = 0.0

    total_cut_length_mm: float = 0.0
    total_cut_cost: float = 0.0

    grand_total_cost: float = 0.0

# -------------------------------------------------------------
# Helpers
# -------------------------------------------------------------

def compute_wrap_length_for_item(pi: PlacedItem) -> float:
    """
    wrap_length_mm = length * x + width * y
    where:
        x = left/right wrap count (0–2)
        y = top/bottom wrap count (0–2)
    Final oriented dimensions (height=length, width) are used.
    """
    s = pi.spec
    length_mm = pi.height_mm
    width_mm = pi.width_mm

    x = _side_count(s.wrap_l, s.wrap_r)
    y = _side_count(s.wrap_t, s.wrap_b)

    return length_mm * x + width_mm * y



# -------------------------------------------------------------
# Main summary computation
# -------------------------------------------------------------

def compute_summary(
    material_boards: Dict[str, List[BoardLayout]],
    materials: Dict[str, MaterialSpec],
    cut_cost_per_mm: float,
    wrap_cost_per_mm: float,
    currency: str
) -> GlobalSummary:

    summary = GlobalSummary()

    # --- MATERIAL BOARDS USAGE ---
    for mat_name, boards in material_boards.items():
        mat = materials[mat_name]
        mu = MaterialUsageSummary(material=mat)
        summary.material_usages[mat_name] = mu

        for b in boards:
            t = b.classify_board_size()
            if t == "full":
                mu.full_boards += 1
            elif t == "narrow_half":
                mu.narrow_halves += 1
            elif t == "wide_half":
                mu.wide_halves += 1

        # convert halves into billed full boards
        halves = mu.narrow_halves + mu.wide_halves
        whole_from_halves = halves // 2
        leftover_half = halves % 2

        mu.billed_quantity = (
            mu.full_boards +
            whole_from_halves +
            0.5 * leftover_half
        )

        mu.cost = mu.billed_quantity * mu.material.cost
        summary.grand_total_cost += mu.cost

    # --- CUTS ---
    total_cut = 0.0
    for boards in material_boards.values():
        for b in boards:
            for cr in b.cut_rects:
                total_cut += cr.cut_length_mm

    summary.total_cut_length_mm = total_cut
    summary.total_cut_cost = total_cut * cut_cost_per_mm
    summary.grand_total_cost += summary.total_cut_cost

    # --- WRAP ---
    total_wrap = 0.0
    for boards in material_boards.values():
        for b in boards:
            for p in b.placed_items:
                total_wrap += compute_wrap_length_for_item(p)

    summary.total_wrap_length_mm = total_wrap
    summary.total_wrap_cost = total_wrap * wrap_cost_per_mm
    summary.grand_total_cost += summary.total_wrap_cost

    return summary
