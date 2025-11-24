# 2Dcutter ver4.0 — main entry
# New features:
# - currency support
# - polished summary tables
# - white-background cut labels
# - Lucida Sans Unicode for PDF
# - stacked summary tables (A layout)

import argparse
from io_utils import parse_items, parse_materials, parse_properties
from wrap_rules import validate_wrapping
from packing import assign_any_items_to_materials, build_boards_for_material
from costing import compute_summary
from pdf_export import generate_pdf


def main():
    parser = argparse.ArgumentParser(description="2Dcutter 4.0 polished build")
    parser.add_argument("items_csv", help="items.csv input")
    parser.add_argument("materials_csv", help="materials.csv input")
    parser.add_argument("config_properties", help="config.properties input")
    parser.add_argument("output_pdf", help="output PDF path")
    parser.add_argument("--ignore-wrap-validation", action="store_true",
                        help="ignore wrap-size rules (debug mode)")
    args = parser.parse_args()

    # --- LOAD INPUT FILES ---
    items = parse_items(args.items_csv)
    materials = parse_materials(args.materials_csv)
    cfg = parse_properties(args.config_properties)

    # --- WRAP VALIDATION ---
    if not args.ignore_wrap_validation:
        validate_wrapping(items)

    # --- ASSIGN MATERIALS ---
    assign_any_items_to_materials(
        items,
        materials,
        enforce_wrap_rules=not args.ignore_wrap_validation
    )

    # Group items by material
    items_by_material = {}
    for item in items:
        items_by_material.setdefault(item.material_key, []).append(item)

    # --- CONFIG VALUES ---
    kerf = float(cfg.get("kerf", "4.0"))
    cut_cost = float(cfg.get("cut_cost", "0.0"))
    wrap_cost = float(cfg.get("side_wrapping_cost", "0.0"))
    currency = cfg.get("currency", "zł")  # NEW IN 4.0

    # --- PACKING ---
    material_boards = {}
    for mat_name, its in items_by_material.items():
        mat = materials[mat_name]
        boards = build_boards_for_material(
            mat,
            its,
            kerf,
            enforce_wrap_rules=not args.ignore_wrap_validation
        )
        material_boards[mat_name] = boards

    # --- SUMMARY CALC ---
    summary = compute_summary(
        material_boards=material_boards,
        materials=materials,
        cut_cost_per_mm=cut_cost,
        wrap_cost_per_mm=wrap_cost,
        currency=currency
    )

    # --- PDF OUTPUT ---
    generate_pdf(
        output_path=args.output_pdf,
        material_boards=material_boards,
        materials=materials,
        summary=summary,
        cfg=cfg,
        currency=currency
    )

    print(f"Success! PDF saved to {args.output_pdf}")
    print(f"Total cost: {summary.grand_total_cost:.2f} {currency}")


if __name__ == "__main__":
    main()
