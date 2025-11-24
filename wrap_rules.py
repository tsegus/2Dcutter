# wrap_rules.py — 2Dcutter ver4.0
#
# Handles checking whether an item can be wrapped under the 150x150 and
# 300x65 rules, depending on which sides are wrapped and whether rotation
# is allowed.

from typing import List, Tuple
from models import ItemSpec


# ---------------------------------------
# Helper: count wrapped sides
# ---------------------------------------

def _side_count(a: float, b: float) -> int:
    """
    Returns:
        0 → none wrapped
        1 → one wrapped (left OR right, or top OR bottom)
        2 → both wrapped (left AND right, or top AND bottom)
    """
    return int(a > 0) + int(b > 0)


# ---------------------------------------
# Orientation rule
# ---------------------------------------

def orientation_allowed_for_wrap(
    length_mm: int,
    width_mm: int,
    wrap_l: float,
    wrap_r: float,
    wrap_t: float,
    wrap_b: float
) -> Tuple[bool, str]:
    """
    Evaluates whether given oriented dimensions (length_mm vertical, width_mm horizontal)
    satisfy the wrapping rules:
      - Perpendicular wrapping → require >=150 x >=150
      - Only parallel wrapping → require >=300 x >=65
      - No wrapping           → always allowed
    """

    parallel_wrapped = _side_count(wrap_l, wrap_r) > 0
    perpendicular_wrapped = _side_count(wrap_t, wrap_b) > 0

    # No wrap → always allowed
    if not parallel_wrapped and not perpendicular_wrapped:
        return True, ""

    # Perpendicular wrapping → 150×150 rule
    if perpendicular_wrapped:
        if length_mm >= 150 and width_mm >= 150:
            return True, ""
        return False, (
            f"needs ≥150×150 mm for perpendicular wrap, "
            f"has {length_mm}×{width_mm} mm"
        )

    # Only parallel wrapping → 300×65 rule
    if parallel_wrapped and not perpendicular_wrapped:
        if length_mm >= 300 and width_mm >= 65:
            return True, ""
        return False, (
            f"needs ≥300×65 mm for parallel wrap, "
            f"has {length_mm}×{width_mm} mm"
        )

    return True, ""


# ---------------------------------------
# Determine valid orientations
# ---------------------------------------

def get_orientation_candidates(
    item: ItemSpec,
    enforce_wrap_rules: bool = True
) -> Tuple[List[Tuple[float, float, bool]], str]:
    """
    Returns a list of (width_mm, height_mm, rotated) possible orientations.
    Only includes those that satisfy wrapping rules if enforce_wrap_rules=True.
    """

    candidates = []
    failure_reason = ""

    # Orientation A: original (length vertical)
    L, W = item.length_mm, item.width_mm
    A_ok, A_reason = orientation_allowed_for_wrap(
        length_mm=L,
        width_mm=W,
        wrap_l=item.wrap_l,
        wrap_r=item.wrap_r,
        wrap_t=item.wrap_t,
        wrap_b=item.wrap_b
    ) if enforce_wrap_rules else (True, "")

    if A_ok:
        candidates.append((W, L, False))
    else:
        failure_reason = A_reason

    # Orientation B: rotated (swap sides)
    B_reason = ""
    if item.rotation_allowed:
        L2, W2 = item.width_mm, item.length_mm
        B_ok, B_reason = orientation_allowed_for_wrap(
            length_mm=L2,
            width_mm=W2,
            wrap_l=item.wrap_l,
            wrap_r=item.wrap_r,
            wrap_t=item.wrap_t,
            wrap_b=item.wrap_b
        ) if enforce_wrap_rules else (True, "")

        if B_ok:
            candidates.append((W2, L2, True))
        else:
            if not failure_reason:
                failure_reason = B_reason

    if not candidates:
        return [], failure_reason or "orientation invalid under wrap rules"

    return candidates, ""


# ---------------------------------------
# Global validation before packing
# ---------------------------------------

def validate_wrapping(items):
    """
    Validates that each item has at least one valid orientation.
    If not, raises ValueError listing all violations.
    """
    problems = []
    for it in items:
        candidates, reason = get_orientation_candidates(it, enforce_wrap_rules=True)
        if not candidates:
            problems.append(f"{it.name}: {reason}")

    if problems:
        msg = "Wrapping constraints violated for the following items:\n"
        msg += "\n".join(f"- {p}" for p in problems)
        raise ValueError(msg)
