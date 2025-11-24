# pdf_export.py — 2Dcutter ver4.0 (Part 1/4)
#
# This file handles all PDF output:
# - Board pages with items and kerf cuts
# - White-background cut labels
# - Summary page with 4 stacked tables
# - Lucida Sans Unicode fonts + optional monospace for numeric alignment
# - Currency formatting
#
# PART 1/4:
#   - Imports
#   - Unit conversions (mm→pt)
#   - Color parsing
#   - Font registration / fallback logic
#   - Basic drawing helpers

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, portrait, landscape
from reportlab.lib.colors import Color, black, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from typing import List, Dict

from models import BoardLayout, PlacedItem, CutRect, MaterialSpec
from costing import GlobalSummary
from io_utils import parse_bool

import math
import os


# ------------------------------------------------------------
# mm → pt
# ------------------------------------------------------------
def mm_to_pt(mm: float) -> float:
    return mm * 72.0 / 25.4


# ------------------------------------------------------------
# Parse hex RGB like "F00", "FF0000"
# ------------------------------------------------------------
def parse_rgb(hex_str: str) -> Color:
    s = hex_str.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    if len(s) != 6:
        return black
    r = int(s[0:2], 16) / 255
    g = int(s[2:4], 16) / 255
    b = int(s[4:6], 16) / 255
    return Color(r, g, b)


# ------------------------------------------------------------
# FONT LOADING (Lucida Sans Unicode)
# ------------------------------------------------------------
# We attempt to load Lucida Sans Unicode automatically.
# If unavailable on the system, we fall back to Helvetica.
#
# Numeric columns may optionally use a monospace font (Courier).

LUCIDA_NAME = "LucidaSansUnicode_4_0"
MONO_NAME = "Monospace_4_0"


def register_fonts():
    global LUCIDA_NAME, MONO_NAME

    """
    Try to register Lucida Sans Unicode. If the TTF is not available,
    fallback to Helvetica. For monospace numeric table cells, use builtin Courier.
    """

    # Try Lucida Sans Unicode from common OS paths
    possible = [
        "/usr/share/fonts/truetype/lucida/LucidaSansUnicode.ttf",
        "/usr/share/fonts/truetype/LucidaSansUnicode.ttf",
        "/Library/Fonts/LucidaSansUnicode.ttf",
        "C:/Windows/Fonts/l_10646.ttf",
        "C:/Windows/Fonts/LSANS.TTF",
    ]

    lucida_path = None
    for p in possible:
        if os.path.isfile(p):
            lucida_path = p
            break

    if lucida_path:
        try:
            pdfmetrics.registerFont(TTFont(LUCIDA_NAME, lucida_path))
        except:
            pdfmetrics.registerFont(TTFont(LUCIDA_NAME, lucida_path))
    else:
        # fallback → Helvetica
        LUCIDA_NAME = "Helvetica"

    # MONOSPACE FONT FIX:
    # Use builtin Courier — DO NOT register a TTF called "Courier"
    MONO_NAME = "Courier"


# ------------------------------------------------------------
# WHITE BACKGROUND LABEL FOR CUT LENGTHS
# ------------------------------------------------------------

def draw_cut_label(c: canvas.Canvas, text: str, x_pt: float, y_pt: float,
                   font_size: float, cuts_color: Color, mono: bool = False):
    """
    Draws a cut length label with a white padded background box.
    (Improved readability for red-on-red etc.)
    """
    font = MONO_NAME if mono else LUCIDA_NAME
    c.setFont(font, font_size)

    # Measure text
    w = pdfmetrics.stringWidth(text, font, font_size)
    pad = font_size * 0.4
    box_w = w + pad * 2
    box_h = font_size * 1.5

    # Draw white background rectangle
    c.setFillColor(white)
    c.rect(
        x_pt - box_w / 2,
        y_pt - box_h / 2,
        box_w,
        box_h,
        fill=1,
        stroke=0
    )

    # Draw the text
    c.setFillColor(cuts_color)
    c.drawCentredString(x_pt, y_pt - font_size * 0.45, text)


# ------------------------------------------------------------
# ITEM RECTANGLES WITH LABEL
# ------------------------------------------------------------

def draw_item_rect(c: canvas.Canvas,
                   x_pt: float, y_top_pt: float,
                   w_pt: float, h_pt: float,
                   item_color: Color,
                   label: str,
                   font_size: float = 8):
    """
    Draw rectangle + centered label for a placed item.
    """
    # Outline only
    c.setStrokeColor(item_color)
    # No fill color needed; fill=0 on the rect handles transparency
    c.rect(x_pt, y_top_pt - h_pt, w_pt, h_pt, stroke=1, fill=0)

    # Label in middle
    cx = x_pt + w_pt / 2
    cy = y_top_pt - h_pt / 2 - font_size * 0.4
    c.setFillColor(item_color)
    c.setFont(LUCIDA_NAME, font_size)
    c.drawCentredString(cx, cy, label)


# ------------------------------------------------------------
# KERF RECTANGLES + BOARD DRAWING (MISSING PART 2)
# ------------------------------------------------------------

def draw_cut_rect(c: canvas.Canvas,
                  cr: CutRect,
                  board_x0_pt: float,
                  board_y0_pt: float,
                  scale: float,
                  cuts_color: Color,
                  font_size: float = 6):
    """
    Render a kerf rectangle and a centered label with white background.
    (No fill color set — fill=0 in rect handles transparency.)
    """
    x_pt = board_x0_pt + cr.x_mm * scale
    y_pt_top = board_y0_pt - cr.y_mm * scale
    w_pt = cr.width_mm * scale
    h_pt = cr.height_mm * scale

    # Outline only — do NOT setFillColor(None)
    c.setStrokeColor(cuts_color)

    # Draw rectangle
    c.rect(x_pt, y_pt_top - h_pt, w_pt, h_pt, stroke=1, fill=0)

    # Centered label
    cx = x_pt + w_pt / 2
    cy = y_pt_top - h_pt / 2
    draw_cut_label(c, f"{int(cr.cut_length_mm)}", cx, cy, font_size, cuts_color, mono=True)



def draw_board_page(c: canvas.Canvas,
                    page_width_pt: float, page_height_pt: float,
                    margin_mm: float,
                    board_color: Color, item_color: Color, cuts_color: Color,
                    generate_cuts: bool,
                    board: BoardLayout,
                    board_number_for_material: int,
                    total_boards_for_material: int,
                    currency: str):
    """
    Draws:
      - Header
      - Board outline
      - Items
      - Kerf rectangles
    """

    margin_pt = mm_to_pt(margin_mm)
    header_h_mm = 20.0
    header_h_pt = mm_to_pt(header_h_mm)

    usable_w_pt = page_width_pt - 2 * margin_pt
    usable_h_pt = page_height_pt - 2 * margin_pt - header_h_pt

    board_w_mm = board.width_mm
    board_h_mm = board.length_mm

    scale = min(
        usable_w_pt / board_w_mm if board_w_mm > 0 else 1,
        usable_h_pt / board_h_mm if board_h_mm > 0 else 1
    )

    board_x0_pt = margin_pt + (usable_w_pt - board_w_mm * scale) / 2
    board_y0_pt = page_height_pt - margin_pt - header_h_pt

    # HEADER
    c.setFont(LUCIDA_NAME, 14)
    c.setFillColor(board_color)
    c.setStrokeColor(board_color)

    mat = board.material
    board_type = board.classify_board_size()
    type_label = {
        "full": "full board",
        "narrow_half": "narrow half board",
        "wide_half": "wide half board"
    }[board_type]

    header_text = (
        f"Material: {mat.name}, size: {mat.width_mm} x {mat.length_mm} mm "
        f"(board {board_number_for_material}/{total_boards_for_material}, {type_label})"
    )
    c.drawString(margin_pt, page_height_pt - margin_pt - 12, header_text)

    # BOARD OUTLINE
    c.setStrokeColor(board_color)
    c.rect(
        board_x0_pt,
        board_y0_pt - board_h_mm * scale,
        board_w_mm * scale,
        board_h_mm * scale,
        stroke=1,
        fill=0
    )

    # DRAW ITEMS
    for p in board.placed_items:
        x_pt = board_x0_pt + p.x_mm * scale
        y_top_pt = board_y0_pt - p.y_mm * scale
        w_pt = p.width_mm * scale
        h_pt = p.height_mm * scale

        label = f"{p.spec.name}.({int(p.height_mm)}x{int(p.width_mm)})"
        draw_item_rect(c, x_pt, y_top_pt, w_pt, h_pt, item_color, label, font_size=8)

    # DRAW KERF CUTS
    if generate_cuts:
        for cr in board.cut_rects:
            draw_cut_rect(c, cr, board_x0_pt, board_y0_pt, scale, cuts_color, font_size=6)


# -----------------------------------------------------
# ------------------------------------------------------------
# TABLE DRAWING ENGINE (FULL-WIDTH, STACKED TABLES)
# ------------------------------------------------------------

def draw_table(
    c: canvas.Canvas,
    x0_pt: float, y0_pt: float,
    col_widths: List[float],
    row_height_pt: float,
    data: List[List[str]],
    header_rows: int,
    font_size: float = 10,
    numeric_cols: List[int] = None
):
    """
    Draws a table with:
      - black grid
      - separate header rows
      - Lucida Sans Unicode font
      - monospace for numeric columns (for alignment)
      - full-width table with each cell defined by col_widths[]
    (0,0) cell is top-left.

    x0_pt, y0_pt = top-left corner of table.
    data = list of rows, each row is list of cell strings.
    """

    if numeric_cols is None:
        numeric_cols = []

    n_rows = len(data)
    n_cols = len(col_widths)

    # Borders & text
    for r in range(n_rows):
        y_top = y0_pt - r * row_height_pt

        for c_idx in range(n_cols):
            x_left = x0_pt + sum(col_widths[:c_idx])
            w = col_widths[c_idx]

            # Draw cell rectangle
            c.setStrokeColor(black)
            c.setLineWidth(1)
            c.rect(
                x_left,
                y_top - row_height_pt,
                w,
                row_height_pt,
                stroke=1,
                fill=0
            )

            # Cell text
            text = data[r][c_idx]
            if text is None:
                text = ""

            # Choose font
            if c_idx in numeric_cols:
                font_name = MONO_NAME
            else:
                font_name = LUCIDA_NAME

            c.setFont(font_name, font_size)

            # Text position
            tx = x_left + 3
            ty = y_top - row_height_pt + (row_height_pt * 0.33)

            if c_idx in numeric_cols:
                # RIGHT aligned numeric columns
                tw = pdfmetrics.stringWidth(text, font_name, font_size)
                c.drawString(x_left + w - tw - 3, ty, text)
            else:
                # LEFT aligned
                c.drawString(tx, ty, text)


# ------------------------------------------------------------
# SUMMARY PAGE WITH FOUR STACKED TABLES
# ------------------------------------------------------------

def draw_summary_page(
    c: canvas.Canvas,
    page_w_pt: float,
    page_h_pt: float,
    margin_mm: float,
    summary: GlobalSummary,
    currency: str
):
    """
    Draws:
      Header
      Table 1: Boards
      Table 2: Wrap
      Table 3: Cut
      Table 4: SUM
    """

    margin_pt = mm_to_pt(margin_mm)
    y = page_h_pt - margin_pt

    # Header
    c.setFont(LUCIDA_NAME, 20)
    c.setFillColor(black)
    c.drawString(margin_pt, y, "2Dcutter cost summary")
    y -= mm_to_pt(15)

    # Measurements
    table_width = page_w_pt - 2 * margin_pt
    default_row_height = mm_to_pt(7)

    # --------------------------------------------------------
    # TABLE 1 — BOARDS
    # --------------------------------------------------------

    board_headers = ["Material", "Cost/pcs", "Quantity (pcs)", "Total cost"]

    # Build data for boards
    board_data = [board_headers]
    numeric_cols_1 = [1, 2, 3]  # numeric columns

    for mname, mu in summary.material_usages.items():
        row = [
            mname,
            f"{mu.material.cost:.2f} {currency}",
            f"{mu.billed_quantity:.2f}",
            f"{mu.cost:.2f} {currency}",
        ]
        board_data.append(row)

    # Compute 4 col widths (simple even layout)
    col_w = table_width / 4
    col_widths_1 = [col_w] * 4

    draw_table(
        c,
        margin_pt,
        y,
        col_widths_1,
        default_row_height,
        board_data,
        header_rows=1,
        font_size=9,
        numeric_cols=numeric_cols_1,
    )

    # Move y below this table
    y -= default_row_height * len(board_data) + mm_to_pt(10)

    # --------------------------------------------------------
    # TABLE 2 — WRAP
    # --------------------------------------------------------

    wrap_headers = ["Cost/mm", "Quantity (mm)", "Total cost"]
    wrap_data = [wrap_headers]

    wrap_data.append([
        f"{summary.total_wrap_cost / summary.total_wrap_length_mm:.4f} {currency}"
        if summary.total_wrap_length_mm > 0 else f"0.0000 {currency}",
        f"{summary.total_wrap_length_mm:.2f}",
        f"{summary.total_wrap_cost:.2f} {currency}"
    ])

    col_w = table_width / 3
    col_widths_2 = [col_w] * 3
    numeric_cols_2 = [0, 1, 2]

    draw_table(
        c,
        margin_pt,
        y,
        col_widths_2,
        default_row_height,
        wrap_data,
        header_rows=1,
        font_size=9,
        numeric_cols=numeric_cols_2,
    )

    y -= default_row_height * len(wrap_data) + mm_to_pt(10)

    # --------------------------------------------------------
    # TABLE 3 — CUT
    # --------------------------------------------------------

    cut_headers = ["Cost/mm", "Quantity (mm)", "Total cost"]
    cut_data = [cut_headers]

    cut_data.append([
        f"{summary.total_cut_cost / summary.total_cut_length_mm:.4f} {currency}"
        if summary.total_cut_length_mm > 0 else f"0.0000 {currency}",
        f"{summary.total_cut_length_mm:.2f}",
        f"{summary.total_cut_cost:.2f} {currency}"
    ])

    draw_table(
        c,
        margin_pt,
        y,
        col_widths_2,
        default_row_height,
        cut_data,
        header_rows=1,
        font_size=9,
        numeric_cols=numeric_cols_2,
    )

    y -= default_row_height * len(cut_data) + mm_to_pt(10)

    # --------------------------------------------------------
    # TABLE 4 — SUM
    # --------------------------------------------------------

    sum_headers = ["Category", "Cost"]
    sum_data = [
        sum_headers,
        ["Boards", f"{sum(mu.cost for mu in summary.material_usages.values()):.2f} {currency}"],
        ["Wrap", f"{summary.total_wrap_cost:.2f} {currency}"],
        ["Cut", f"{summary.total_cut_cost:.2f} {currency}"],
        ["TOTAL", f"{summary.grand_total_cost:.2f} {currency}"],
    ]

    col_widths_4 = [table_width * 0.4, table_width * 0.6]
    numeric_cols_4 = [1]

    draw_table(
        c,
        margin_pt,
        y,
        col_widths_4,
        default_row_height,
        sum_data,
        header_rows=1,
        font_size=10,
        numeric_cols=numeric_cols_4,
    )

# ------------------------------------------------------------
# FINAL PDF GENERATOR
# ------------------------------------------------------------

def generate_pdf(
    output_path: str,
    material_boards: Dict[str, List[BoardLayout]],
    materials: Dict[str, MaterialSpec],
    summary: GlobalSummary,
    cfg: Dict[str, str],
    currency: str
):
    """
    Generates the complete PDF:
      - optional summary page
      - board pages
    """

    # Register fonts (Lucida Sans Unicode + monospace)
    register_fonts()

    # Config booleans
    gen_summary = parse_bool(cfg.get("generate-summary", "true"))
    gen_cuts = parse_bool(cfg.get("generate-cuts", "true"))

    # Colors
    board_color = parse_rgb(cfg.get("board-color", "000"))
    item_color = parse_rgb(cfg.get("item-color", "777"))
    cuts_color = parse_rgb(cfg.get("cuts-color", "F00"))

    # Margin
    margin_mm = float(cfg.get("margin", "10"))

    # Orientation
    orientation = (cfg.get("orientation", "h") or "h").lower()
    if orientation == "h":
        pagesize = landscape(A4)
    else:
        pagesize = portrait(A4)

    page_w_pt, page_h_pt = pagesize

    # Create PDF canvas
    c = canvas.Canvas(output_path, pagesize=pagesize)

    # --------------------------------------------------------
    # SUMMARY PAGE (optional)
    # --------------------------------------------------------
    if gen_summary:
        draw_summary_page(
            c=c,
            page_w_pt=page_w_pt,
            page_h_pt=page_h_pt,
            margin_mm=margin_mm,
            summary=summary,
            currency=currency
        )
        c.showPage()

    # --------------------------------------------------------
    # BOARD PAGES
    # --------------------------------------------------------
    for mname in sorted(material_boards.keys()):
        boards = material_boards[mname]
        total_b = len(boards)

        for idx, board in enumerate(boards, start=1):
            draw_board_page(
                c=c,
                page_width_pt=page_w_pt,
                page_height_pt=page_h_pt,
                margin_mm=margin_mm,
                board_color=board_color,
                item_color=item_color,
                cuts_color=cuts_color,
                generate_cuts=gen_cuts,
                board=board,
                board_number_for_material=idx,
                total_boards_for_material=total_b,
                currency=currency
            )
            c.showPage()

    # Finalize PDF
    c.save()
