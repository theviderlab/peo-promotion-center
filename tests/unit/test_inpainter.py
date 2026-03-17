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


def test_inpainted_images_bypasses_generate_format() -> None:
    """zip_builder usa la imagen aceptada directamente sin llamar a generate_format."""
    from peo_promotion_center.frontend.zip_builder import build_zip
    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Imagen fuente requerida para el ZIP
        source = tmp_path / "test.png"
        source.write_bytes(b"FAKE_FLYER")

        # Pre-crear archivos para historia/google (generados via mock)
        fake_pngs: dict[str, Path] = {}
        for slug in ("historia", "google"):
            p = tmp_path / f"test-slug_{slug}.png"
            p.write_bytes(b"FAKE_PNG")
            fake_pngs[slug] = p

        inpainted_post = Image.new("RGB", (1080, 1350), color=(10, 20, 30))

        with patch(
            "peo_promotion_center.frontend.zip_builder.generate_format",
            side_effect=lambda src, fmt, offset, slug, outdir: fake_pngs[fmt.slug],
        ) as mock_gen:
            build_zip(
                source_path=source,
                slug="test-slug",
                offsets={"post": 0.4, "historia": 0.5, "google": 0.25},
                copy_redes="Test copy",
                asuntos_mailing=["A1", "A2", "A3"],
                preview_texts_mailing=["P1", "P2", "P3"],
                output_dir=tmp_path,
                inpainted_images={"post": inpainted_post, "historia": None, "google": None},
            )

        called_slugs = [c[0][1].slug for c in mock_gen.call_args_list]
        assert "post" not in called_slugs
        assert "historia" in called_slugs
        assert "google" in called_slugs


def test_inpainted_images_none_calls_generate_format_for_all() -> None:
    """zip_builder llama a generate_format para todos los formatos si no hay inpainted_images."""
    from peo_promotion_center.frontend.zip_builder import build_zip
    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        source = tmp_path / "test.png"
        source.write_bytes(b"FAKE_FLYER")

        fake_pngs: dict[str, Path] = {}
        for slug in ("post", "historia", "google"):
            p = tmp_path / f"test-slug_{slug}.png"
            p.write_bytes(b"FAKE_PNG")
            fake_pngs[slug] = p

        with patch(
            "peo_promotion_center.frontend.zip_builder.generate_format",
            side_effect=lambda src, fmt, offset, slug, outdir: fake_pngs[fmt.slug],
        ) as mock_gen:
            build_zip(
                source_path=source,
                slug="test-slug",
                offsets={"post": 0.4, "historia": 0.5, "google": 0.25},
                copy_redes="Test copy",
                asuntos_mailing=["A1", "A2", "A3"],
                preview_texts_mailing=["P1", "P2", "P3"],
                output_dir=tmp_path,
                inpainted_images=None,
            )

        assert mock_gen.call_count == 3
