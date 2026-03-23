"""Compositing de overlays PNG sobre imágenes de salida."""

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from peo_promotion_center.backend.image_processor import POST, ImageFormat

ASSETS_DIR = Path(__file__).parents[3] / "assets"


@dataclass(frozen=True)
class TagDefinition:
    """
    Definición de un tag overlay disponible en el registro.

    Attributes:
        tag_id: Identificador único del tag.
        label: Texto descriptivo para mostrar en la UI.
        path: Ruta al archivo PNG del tag.
        default_x: Posición X por defecto (píxel superior izquierdo).
        default_y: Posición Y por defecto (píxel superior izquierdo).
    """

    tag_id: str
    label: str
    path: Path
    default_x: int
    default_y: int


TAG_REGISTRY: list[TagDefinition] = [
    TagDefinition(
        tag_id="circuito",
        label="Tag Circuito",
        path=ASSETS_DIR / "tag-circuito.png",
        default_x=925,
        default_y=1147,
    ),
]

OVERLAY_FORMATS: list[ImageFormat] = [POST]


@dataclass
class OverlaySpec:
    """
    Especificación de un overlay activo para aplicar sobre una imagen.

    Attributes:
        tag: Imagen RGBA del tag (precargada).
        x: Coordenada X del píxel superior izquierdo en el canvas de salida.
        y: Coordenada Y del píxel superior izquierdo en el canvas de salida.
    """

    tag: Image.Image
    x: int
    y: int


def apply_tag_overlay(
    base: Image.Image,
    tag: Image.Image,
    x: int,
    y: int,
) -> Image.Image:
    """
    Superpone `tag` (RGBA) sobre `base` en la posición (x, y).

    El canal alpha del tag se usa como máscara. La imagen base se convierte a
    RGBA para el composite y se devuelve como RGB. Maneja clipping si el tag
    desborda los bordes del canvas.

    Args:
        base: Imagen base (RGB o RGBA).
        tag: Imagen del tag en modo RGBA.
        x: Coordenada horizontal del píxel superior izquierdo del tag.
        y: Coordenada vertical del píxel superior izquierdo del tag.

    Returns:
        Imagen resultante en modo RGB.
    """
    base_rgba = base.convert("RGBA")
    tag_w, tag_h = tag.size

    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(base_rgba.width, x + tag_w)
    y2 = min(base_rgba.height, y + tag_h)

    if x1 < x2 and y1 < y2:
        visible_tag = tag.crop((x1 - x, y1 - y, x2 - x, y2 - y))
        mask = visible_tag.split()[3]
        base_rgba.paste(visible_tag, (x1, y1), mask)

    return base_rgba.convert("RGB")


def apply_overlays(
    base: Image.Image,
    overlays: list[OverlaySpec],
) -> Image.Image:
    """
    Aplica una lista de overlays sobre `base` en orden.

    Permite superponer múltiples tags en la misma imagen. Si `overlays` está
    vacío, retorna `base` sin modificar.

    Args:
        base: Imagen base.
        overlays: Lista de OverlaySpec a aplicar en orden.

    Returns:
        Imagen con todos los overlays aplicados.
    """
    if not overlays:
        return base
    result = base
    for spec in overlays:
        result = apply_tag_overlay(result, spec.tag, spec.x, spec.y)
    return result
