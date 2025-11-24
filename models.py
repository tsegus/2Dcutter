# models.py — 2Dcutter ver4.0
# Data structures for materials, items, placed items, and layout units.

from dataclasses import dataclass
from typing import Optional, List


# ------------------------------
# Basic Specs
# ------------------------------

@dataclass
class MaterialSpec:
    name: str
    length_mm: int      # board dimension along Y (top→bottom)
    width_mm: int       # board dimension along X (left→right)
    cost: float         # price per full board


@dataclass
class ItemSpec:
    name: str
    length_mm: int
    width_mm: int
    quantity: int
    rotation_allowed: bool
    wrap_l: float
    wrap_r: float
    wrap_t: float
    wrap_b: float
    material_key: Optional[str]   # None = "any"


# ------------------------------
# Placed geometry
# ------------------------------

@dataclass
class PlacedItem:
    spec: ItemSpec
    material_name: str
    board_index: int
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    rotated: bool


@dataclass
class CutRect:
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    cut_length_mm: float
    orientation: str     # 'H' or 'V'


# ------------------------------
# Layout structures
# ------------------------------

class RowLayout:
    """
    One horizontal row of items. The row has:
    - a fixed height (h_mm)
    - a fixed Y position (y_mm)
    - items placed left→right (X direction)
    """

    def __init__(self, y_mm: float, h_mm: float, board_width_mm: float):
        self.y_mm = y_mm
        self.h_mm = h_mm
        self.board_width_mm = board_width_mm
        self.items: List[PlacedItem] = []
        self.x_cursor: float = 0.0   # current X offset for next item


class BoardLayout:
    """
    Represents a single board (full or half). Stores:
    - material info
    - rows
    - placed items
    - kerf cut rectangles
    """

    def __init__(self, material: MaterialSpec, index: int, kerf: float):
        self.material = material
        self.index = index
        self.kerf = kerf

        self.rows: List[RowLayout] = []
        self.placed_items: List[PlacedItem] = []
        self.cut_rects: List[CutRect] = []

    @property
    def width_mm(self) -> int:
        return self.material.width_mm

    @property
    def length_mm(self) -> int:
        return self.material.length_mm

    def used_length_mm(self) -> float:
        """Vertical usage."""
        if not self.rows:
            return 0.0
        last = self.rows[-1]
        return last.y_mm + last.h_mm

    def used_width_mm(self) -> float:
        """Max horizontal usage across rows."""
        if not self.rows:
            return 0.0
        return max((sum(i.width_mm for i in r.items) for r in self.rows), default=0.0)

    def classify_board_size(self) -> str:
        """
        Returns:
            'full', 'narrow_half', or 'wide_half'
        Based on used width/length fitting these shapes:
            narrow half = (L/2, W)
            wide half   = (L, W/2)
        """
        uL = self.used_length_mm()
        uW = self.used_width_mm()
        L = self.length_mm
        W = self.width_mm

        narrow_ok = (uL <= L/2) and (uW <= W)
        wide_ok   = (uL <= L)   and (uW <= W/2)

        if narrow_ok and wide_ok:
            return "narrow_half"
        elif narrow_ok:
            return "narrow_half"
        elif wide_ok:
            return "wide_half"
        else:
            return "full"
