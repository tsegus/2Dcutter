# 2Dcutter ver4.1 — main entry
# - Moved ignore-wrap-validation to config.properties
# - Clean error reporting (no traceback)
# - PDF generation skipped or allowed based on config

import argparse
from io_utils import parse_items, parse_materials, parse_properties, parse_bool
from wrap_rules import validate_wrapping
from packing import assign_any_items_to_materials, build_boards_for_material
from costing import compute_summary
from pdf_export import generate_pdf


def main():
    parser = argparse.ArgumentParser(description="2Dcutter 4.1 polished build")
    parser.add_argument("items_csv", help="items.csv input")
    parser.add_argument("materials_csv", help="materials.csv input")
    parser.add_argument("config_properties", help="config.properties input")
    parser.add_argument("output_pdf", help="output PDF path")
    # NOTE: CLI ignore-wrap-validation removed in 4.1 (now config-based)
    args = parser.parse_args()

    # --- LOAD INPUT FILES ---
    items = parse_items(args.items_csv)
    materials = parse_materials(args.materials_csv)
    cfg = parse_properties(args.config_properties)

    # --- CONFIG FLAGS ---
    ignore_wrap_val = parse_bool(cfg.get("ignore-wrap-validation", "false"))

    # --- WRAP VALIDATION ---
    try:
        validate_wrapping(items)
        wrap_ok = True
    except ValueError as ve:
        wrap_ok = False
        message = str(ve).strip()

        if ignore_wrap_val:
            print("\n[WARNING] Wrapping validation failed but ignored (ignore-wrap-validation=true):")
            print(message)
            print("Proceeding to generate PDF anyway.\n")
        else:
            print("\n[ERROR] Wrapping validation failed:")
            print(message)
            print("No PDF created. To override, set ignore-wrap-validation=true in config.properties.\n")
            return  # STOP execution

    # --- ASSIGN MATERIALS ---
    assign_any_items_to_materials(
        items,
        materials,
        enforce_wrap_rules=not ignore_wrap_val
    )

    # Group items by material
    items_by_material = {}
    for item in items:
        items_by_material.setdefault(item.material_key, []).append(item)

    # --- CONFIG COST VALUES ---
    kerf = float(cfg.get("kerf", "4.0"))
    cut_cost = float(cfg.get("cut_cost", "0.0"))
    wrap_cost = float(cfg.get("side_wrapping_cost", "0.0"))
    currency = cfg.get("currency", "zł")

    # --- PACKING ---
    material_boards = {}
    for mat_name, its in items_by_material.items():
        mat = materials[mat_name]
        boards = build_boards_for_material(
            mat,
            its,
            kerf,
            enforce_wrap_rules=not ignore_wrap_val
        )
        material_boards[mat_name] = boards

    # --- SUMMARY ---
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
