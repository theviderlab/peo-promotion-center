"""Tests unitarios para el módulo de inpainting."""

import pytest
from PIL import Image
from unittest.mock import MagicMock, patch


@pytest.fixture
def rgb_image() -> Image.Image:
    """Imagen RGB de prueba en resolución Post."""
    return Image.new("RGB", (1080, 1350), color=(128, 64, 32))


@pytest.fixture
def mask_image() -> Image.Image:
    """Máscara en escala de grises (todo negro = sin borrado)."""
    return Image.new("L", (1080, 1350), 0)


def test_inpaint_calls_lama(rgb_image: Image.Image, mask_image: Image.Image) -> None:
    """inpaint() debe delegar en la instancia LaMa y retornar su resultado."""
    expected = Image.new("RGB", (1080, 1350), color=(10, 20, 30))
    mock_lama = MagicMock(return_value=expected)

    with patch("peo_promotion_center.backend.inpainter._lama", mock_lama):
        from peo_promotion_center.backend.inpainter import inpaint

        result = inpaint(rgb_image, mask_image)

    mock_lama.assert_called_once()
    assert result is expected


def test_inpaint_converts_mask_to_grayscale(rgb_image: Image.Image) -> None:
    """inpaint() debe convertir la máscara a modo 'L' antes de pasarla a LaMa."""
    rgba_mask = Image.new("RGBA", (1080, 1350), (255, 255, 255, 128))
    mock_lama = MagicMock(return_value=rgb_image)

    with patch("peo_promotion_center.backend.inpainter._lama", mock_lama):
        from peo_promotion_center.backend.inpainter import inpaint

        inpaint(rgb_image, rgba_mask)

    _, mask_arg = mock_lama.call_args[0]
    assert mask_arg.mode == "L"


def test_inpaint_none_mask_skipped_by_zip_builder() -> None:
    """zip_builder no llama a inpaint() si la máscara del formato es None."""
    # zip_builder comprueba `if inpaint_masks and inpaint_masks.get(fmt.slug) is not None`
    # antes de invocar inpaint(), por lo que con None el modelo nunca se carga.
    # Este test verifica la lógica de guarda en zip_builder.
    from peo_promotion_center.frontend.zip_builder import build_zip
    from pathlib import Path
    import tempfile

    # Usamos una imagen temporal mínima para no requerir recursos reales
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        img_path = tmp_path / "test.png"
        Image.new("RGB", (1920, 1080), color=(200, 150, 100)).save(img_path)

        # inpaint_masks con None → build_zip no debe llamar a inpaint
        with patch("peo_promotion_center.frontend.zip_builder.inpaint") as mock_inpaint:
            build_zip(
                source_path=img_path,
                slug="test-slug",
                offsets={"post": 0.4, "historia": 0.5, "google": 0.25},
                copy_redes="Test copy",
                asuntos_mailing=["A1", "A2", "A3"],
                preview_texts_mailing=["P1", "P2", "P3"],
                output_dir=tmp_path,
                inpaint_masks={"post": None, "historia": None, "google": None},
            )

        mock_inpaint.assert_not_called()
