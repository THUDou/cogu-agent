
from __future__ import annotations

import sys
from pathlib import Path
from xml.etree import ElementTree as ET


def flatten_positional_tspans(tree: ET.ElementTree) -> bool:
    scripts_dir = Path(__file__).resolve().parent.parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from svg_finalize.flatten_tspan import flatten_text_with_tspans  # type: ignore
    return flatten_text_with_tspans(tree)
