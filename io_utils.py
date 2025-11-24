# io_utils.py — 2Dcutter ver4.0
# Reading CSV files, parsing config, validating fields.

import csv
from typing import Dict, List

from models import ItemSpec, MaterialSpec


# ------------------------------
# Boolean parser
# ------------------------------

def parse_bool(val: str) -> bool:
    if val is None:
        return False
    v = val.strip().lower()
    return v in ("1", "true", "yes", "tak", "y")


# ------------------------------
# Config parser (strict one key per line)
# ------------------------------

def parse_properties(path: str) -> Dict[str, str]:
    """
    Conservative parser:
    - One key=value per line
    - Lines without '=' are ignored
    - '#' at start of line = comment
    """
    props: Dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            props[key.strip()] = val.strip()
    return props


# ------------------------------
# Items CSV
# ------------------------------

def parse_items(path: str) -> List[ItemSpec]:
    items: List[ItemSpec] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        required = {
            "name", "length", "width", "quantity",
            "rotation", "wrap_l", "wrap_r", "wrap_t", "wrap_b",
            "material"
        }
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError("items.csv missing required columns")

        for row in reader:
            if not row["name"]:
                continue

            name = row["name"].strip()
            length_mm = int(row["length"])
            width_mm = int(row["width"])

            quantity = int(row["quantity"]) if row.get("quantity") else 1
            rotation_allowed = (row.get("rotation", "").strip().upper() == "TAK")

            def f0(x):
                return float(x.strip()) if x and x.strip() else 0.0

            wrap_l = f0(row.get("wrap_l"))
            wrap_r = f0(row.get("wrap_r"))
            wrap_t = f0(row.get("wrap_t"))
            wrap_b = f0(row.get("wrap_b"))

            material_key = row.get("material", "").strip()
            if material_key == "":
                material_key = None

            items.append(
                ItemSpec(
                    name=name,
                    length_mm=length_mm,
                    width_mm=width_mm,
                    quantity=quantity,
                    rotation_allowed=rotation_allowed,
                    wrap_l=wrap_l,
                    wrap_r=wrap_r,
                    wrap_t=wrap_t,
                    wrap_b=wrap_b,
                    material_key=material_key
                )
            )

    # Ensure uniqueness
    names = [i.name for i in items]
    if len(names) != len(set(names)):
        raise ValueError("Item names must be unique.")

    return items


# ------------------------------
# Materials CSV
# ------------------------------

def parse_materials(path: str) -> Dict[str, MaterialSpec]:
    materials: Dict[str, MaterialSpec] = {}

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = set(reader.fieldnames or [])
        if "material" not in fields:
            raise ValueError("materials.csv missing 'material' column")
        if "cost" not in fields:
            raise ValueError("materials.csv missing 'cost' column")
        if "width" not in fields:
            raise ValueError("materials.csv missing 'width' column")
        if not (("length" in fields) or ("height" in fields)):
            raise ValueError("materials.csv must have length OR height column")

        length_field = "length" if "length" in fields else "height"

        for row in reader:
            name = row["material"].strip()
            if not name:
                continue

            length_mm = int(row[length_field])
            width_mm = int(row["width"])
            cost = float(row["cost"])

            materials[name] = MaterialSpec(
                name=name,
                length_mm=length_mm,
                width_mm=width_mm,
                cost=cost
            )

    return materials
