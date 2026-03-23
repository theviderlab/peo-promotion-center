"""Tests unitarios para el módulo de compositing de overlays."""

import pytest
from PIL import Image

from peo_promotion_center.backend.compositing import (
    OverlaySpec,
    apply_overlays,
    apply_tag_overlay,
)


def _solid_rgb(width: int, height: int, color: tuple) -> Image.Image:
    return Image.new("RGB", (width, height), color)


def _solid_rgba(width: int, height: int, color: tuple) -> Image.Image:
    return Image.new("RGBA", (width, height), color)


def test_apply_tag_overlay_basic():
    """La zona del tag muestra los colores del tag (alpha=255); fuera del tag, el base no cambia."""
    base = _solid_rgb(100, 100, (255, 255, 255))
    tag = _solid_rgba(20, 20, (255, 0, 0, 255))
    result = apply_tag_overlay(base, tag, 10, 10)

    assert result.mode == "RGB"
    assert result.getpixel((10, 10)) == (255, 0, 0)
    assert result.getpixel((0, 0)) == (255, 255, 255)


def test_apply_tag_overlay_clipping():
    """Posición desbordante no lanza excepción; sólo la porción visible se pega."""
    base = _solid_rgb(100, 100, (255, 255, 255))
    tag = _solid_rgba(50, 50, (0, 255, 0, 255))
    result = apply_tag_overlay(base, tag, 90, 90)

    assert result.mode == "RGB"
    assert result.size == (100, 100)
    assert result.getpixel((90, 90)) == (0, 255, 0)


def test_apply_overlays_empty():
    """Lista vacía → imagen de salida idéntica a la entrada (mismo objeto)."""
    base = _solid_rgb(100, 100, (128, 64, 32))
    result = apply_overlays(base, [])
    assert result is base


def test_apply_overlays_multiple():
    """Dos tags en posiciones distintas → ambos aparecen en el resultado."""
    base = _solid_rgb(200, 200, (255, 255, 255))
    tag_red = _solid_rgba(30, 30, (255, 0, 0, 255))
    tag_blue = _solid_rgba(30, 30, (0, 0, 255, 255))
    overlays = [
        OverlaySpec(tag=tag_red, x=0, y=0),
        OverlaySpec(tag=tag_blue, x=100, y=100),
    ]
    result = apply_overlays(base, overlays)

    assert result.getpixel((0, 0)) == (255, 0, 0)
    assert result.getpixel((100, 100)) == (0, 0, 255)
    assert result.getpixel((50, 50)) == (255, 255, 255)


def test_apply_overlays_order():
    """El segundo overlay pinta encima del primero si se superponen."""
    base = _solid_rgb(100, 100, (255, 255, 255))
    tag_red = _solid_rgba(50, 50, (255, 0, 0, 255))
    tag_blue = _solid_rgba(50, 50, (0, 0, 255, 255))
    overlays = [
        OverlaySpec(tag=tag_red, x=0, y=0),
        OverlaySpec(tag=tag_blue, x=0, y=0),
    ]
    result = apply_overlays(base, overlays)

    assert result.getpixel((0, 0)) == (0, 0, 255)
