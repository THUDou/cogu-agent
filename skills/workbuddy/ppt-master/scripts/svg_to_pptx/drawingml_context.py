
from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET
from dataclasses import dataclass, field

AffineMatrix = tuple[float, float, float, float, float, float]
IDENTITY_MATRIX: AffineMatrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


@dataclass
class ShapeResult:

    xml: str
    bounds_emu: tuple[int, int, int, int] | None = None


@dataclass
class ConvertContext:

    defs: dict[str, ET.Element] = field(default_factory=dict)
    id_counter: int = 2  # 1 is reserved for spTree root
    slide_num: int = 1
    translate_x: float = 0.0
    translate_y: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    transform_matrix: AffineMatrix = IDENTITY_MATRIX
    use_transform_matrix: bool = False
    filter_id: str | None = None
    media_files: dict[str, bytes] = field(default_factory=dict)
    rel_entries: list[dict[str, str]] = field(default_factory=list)
    rel_id_counter: int = 2  # rId1 reserved for slideLayout
    svg_dir: Path | None = None
    inherited_styles: dict[str, str] = field(default_factory=dict)
    depth: int = 0
    anim_targets: list = field(default_factory=list)

    def next_id(self) -> int:
        cid = self.id_counter
        self.id_counter += 1
        return cid

    def next_rel_id(self) -> str:
        rid = f'rId{self.rel_id_counter}'
        self.rel_id_counter += 1
        return rid

    def child(
        self,
        dx: float = 0,
        dy: float = 0,
        sx: float = 1.0,
        sy: float = 1.0,
        transform_matrix: AffineMatrix | None = None,
        filter_id: str | None = None,
        style_overrides: dict[str, str] | None = None,
    ) -> ConvertContext:
        local_matrix = transform_matrix or IDENTITY_MATRIX
        a1, b1, c1, d1, e1, f1 = self.transform_matrix
        a2, b2, c2, d2, e2, f2 = local_matrix
        combined_matrix: AffineMatrix = (
            a1 * a2 + c1 * b2,
            b1 * a2 + d1 * b2,
            a1 * c2 + c1 * d2,
            b1 * c2 + d1 * d2,
            a1 * e2 + c1 * f2 + e1,
            b1 * e2 + d1 * f2 + f1,
        )

        merged = dict(self.inherited_styles)

        if style_overrides:
            _OPACITY_KEYS = ('opacity', 'fill-opacity', 'stroke-opacity')
            for op_key in _OPACITY_KEYS:
                if op_key in style_overrides and op_key in merged:
                    try:
                        merged[op_key] = str(
                            float(merged[op_key]) * float(style_overrides[op_key])
                        )
                    except ValueError:
                        merged[op_key] = style_overrides[op_key]
                elif op_key in style_overrides:
                    merged[op_key] = style_overrides[op_key]

            for k, v in style_overrides.items():
                if k not in _OPACITY_KEYS:
                    merged[k] = v

        return ConvertContext(
            defs=self.defs,
            id_counter=self.id_counter,
            slide_num=self.slide_num,
            translate_x=self.translate_x + dx,
            translate_y=self.translate_y + dy,
            scale_x=self.scale_x * sx,
            scale_y=self.scale_y * sy,
            transform_matrix=combined_matrix,
            use_transform_matrix=self.use_transform_matrix or transform_matrix is not None,
            filter_id=filter_id or self.filter_id,
            media_files=self.media_files,
            rel_entries=self.rel_entries,
            rel_id_counter=self.rel_id_counter,
            svg_dir=self.svg_dir,
            inherited_styles=merged,
            depth=self.depth + 1,
        )

    def sync_from_child(self, child_ctx: ConvertContext) -> None:
        self.id_counter = child_ctx.id_counter
        self.rel_id_counter = child_ctx.rel_id_counter
