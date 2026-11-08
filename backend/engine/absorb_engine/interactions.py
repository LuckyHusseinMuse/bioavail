"""Nodes and edges for the interaction map (ProjectDefinition.md section 8)."""
from __future__ import annotations

from absorb_engine.loaders import ReferenceData

NODES = [
    {"id": "haem_iron", "label": "Haem iron", "kind": "iron"},
    {"id": "nonhaem_iron", "label": "Non-haem iron", "kind": "iron"},
    {"id": "vitamin_c", "label": "Vitamin C", "kind": "enhancer"},
    {"id": "meat_fish_poultry", "label": "Meat, fish, poultry", "kind": "enhancer"},
    {"id": "polyphenols", "label": "Polyphenols (tea, coffee, cocoa)", "kind": "inhibitor"},
    {"id": "phytate", "label": "Phytate (wholegrains, beans)", "kind": "inhibitor"},
    {"id": "calcium", "label": "Calcium (dairy)", "kind": "inhibitor"},
]

# (from, to, effect, modifier ids whose effect sizes set the edge strength)
EDGES = [
    ("vitamin_c", "nonhaem_iron", "enhance", ["ABS_BASE_IRON_006"]),
    ("meat_fish_poultry", "nonhaem_iron", "enhance", ["ABS_BASE_IRON_006"]),
    ("polyphenols", "nonhaem_iron", "inhibit", ["ABS_MOD_IRON_002", "ABS_MOD_IRON_003", "ABS_MOD_IRON_004"]),
    ("phytate", "nonhaem_iron", "inhibit", ["ABS_MOD_IRON_005", "ABS_MOD_IRON_006", "ABS_MOD_IRON_007"]),
    ("calcium", "nonhaem_iron", "inhibit", ["ABS_MOD_IRON_009", "ABS_MOD_IRON_010"]),
    ("calcium", "haem_iron", "inhibit", ["ABS_MOD_IRON_011"]),
    ("vitamin_c", "phytate", "counteract", ["ABS_MOD_IRON_008"]),
]


def interaction_graph(ref: ReferenceData, result: dict | None = None) -> dict:
    """Graph for the interaction map. If a scored meal is given, mark edges active in that meal."""
    active: set[str] = set()
    if result:
        for c in result.get("contributions", []):
            if c["step"] in ("enhancer", "inhibitor"):
                active.add(c["factor"])
        if any(c["factor"] == "phytate" and c.get("detail", {}).get("vitamin_c_offset_share", 0) > 0
               for c in result.get("contributions", [])):
            active.add("vitamin_c->phytate")

    edges = []
    for src, dst, effect, ids in EDGES:
        mods = [ref.modifiers[i] for i in ids if i in ref.modifiers]
        if effect == "enhance":
            b = ref.baselines["ABS_BASE_IRON_006"]
            strength = float(b["baseline_absorption_upper"]) / float(b["baseline_absorption_lower"]) - 1  # up to x2.67
        else:
            vals = [abs(m.point) for m in mods if m.calculation_eligible and (m.value is not None or m.lower is not None)]
            strength = max(vals) / 100 if vals else None
        key = f"{src}->{dst}" if effect == "counteract" else src
        edges.append({
            "id": f"{src}->{dst}", "source": src, "target": dst, "effect": effect,
            "strength": None if strength is None else round(strength, 2),
            "qualitative_only": strength is None,
            "active": key in active,
            "sources": ids,
        })
    return {"nodes": NODES, "edges": edges}
