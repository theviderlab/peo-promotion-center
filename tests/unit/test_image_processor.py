"""Pruebas unitarias para el módulo image_processor."""

import io
from pathlib import Path

import pytest
from PIL import Image

from peo_promotion_center.backend.image_processor import (
    ALL_FORMATS,
    HISTORIA,
    POST,
    ImageFormat,
    crop_to_canvas,
    generate_format,
    pad_bottom,
    preview_format,
    process_all_formats,
    scale_to_width,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_image(width: int, height: int, color: tuple = (100, 150, 200)) -> Image.Image:
    """Crea una imagen RGB sintética en memoria."""
    return Image.new("RGB", (width, height), color)


def _save_image(img: Image.Image, path: Path) -> None:
    """Guarda una imagen PIL en disco como PNG."""
    img.save(path, format="PNG")


# ---------------------------------------------------------------------------
# scale_to_width
# ---------------------------------------------------------------------------


def test_scale_to_width_reduces():
    """Una imagen más ancha se reduce al ancho objetivo."""
    img = _make_image(2000, 1000)
    result = scale_to_width(img, 1000)
    assert result.width == 1000


def test_scale_to_width_upscales():
    """Una imagen más angosta se amplía al ancho objetivo."""
    img = _make_image(500, 300)
    result = scale_to_width(img, 1080)
    assert result.width == 1080


def test_scale_to_width_preserves_aspect_ratio():
    """El alto calculado preserva la relación de aspecto original."""
    img = _make_image(2000, 1000)  # ratio 2:1
    result = scale_to_width(img, 1000)
    assert result.width == 1000
    assert result.height == 500  # ratio 2:1 preservado


def test_scale_to_width_exact_width():
    """Si el ancho es igual al objetivo la imagen se mantiene igual."""
    img = _make_image(1080, 800)
    result = scale_to_width(img, 1080)
    assert result.width == 1080
    assert result.height == 800


# ---------------------------------------------------------------------------
# crop_to_canvas
# ---------------------------------------------------------------------------


def _tall_image(fmt: ImageFormat, extra: int = 400) -> Image.Image:
    """Crea una imagen más alta que el canvas del formato dado."""
    return _make_image(fmt.width, fmt.height + extra)


def test_crop_to_canvas_offset_0_recorta_desde_arriba():
    """offset_y=0.0 recorta desde el tope (top=0)."""
    img = _tall_image(POST, extra=400)
    result = crop_to_canvas(img, POST, offset_y=0.0)
    assert result.size == (POST.width, POST.height)


def test_crop_to_canvas_offset_1_recorta_desde_abajo():
    """offset_y=1.0 recorta desde abajo (top=max_offset)."""
    img = _tall_image(POST, extra=400)
    result = crop_to_canvas(img, POST, offset_y=1.0)
    assert result.size == (POST.width, POST.height)


def test_crop_to_canvas_offset_05_recorta_al_centro():
    """offset_y=0.5 recorta al centro."""
    img = _tall_image(HISTORIA, extra=600)
    result = crop_to_canvas(img, HISTORIA, offset_y=0.5)
    assert result.size == (HISTORIA.width, HISTORIA.height)


def test_crop_to_canvas_sin_recorte_cuando_igual():
    """Cuando el alto de la imagen es igual al canvas no se recorta."""
    img = _make_image(POST.width, POST.height)
    result = crop_to_canvas(img, POST, offset_y=0.5)
    assert result is img  # debe retornar el mismo objeto sin modificar


def test_crop_to_canvas_sin_recorte_cuando_menor():
    """Cuando el alto de la imagen es menor al canvas se retorna intacta."""
    img = _make_image(POST.width, POST.height - 100)
    result = crop_to_canvas(img, POST, offset_y=0.5)
    assert result is img


# ---------------------------------------------------------------------------
# pad_bottom
# ---------------------------------------------------------------------------


def test_pad_bottom_alto_correcto():
    """El canvas resultante tiene el alto de destino correcto."""
    img = _make_image(1080, 1500)
    result = pad_bottom(img, 1920)
    assert result.height == 1920
    assert result.width == 1080


def test_pad_bottom_color_de_relleno_ignora_los_ultimos_4px():
    """El color de relleno se calcula excluyendo los últimos 4 píxeles."""
    fill = (200, 100, 50)
    noise = (10, 240, 10)
    img = Image.new("RGB", (1080, 1500), (128, 128, 128))

    # La fila de referencia para muestreo con margen=4 es y=1495.
    sample_row = Image.new("RGB", (1080, 1), fill)
    img.paste(sample_row, (0, 1495))

    # Simula artefactos de exportación en los últimos 4px.
    noisy_rows = Image.new("RGB", (1080, 4), noise)
    img.paste(noisy_rows, (0, 1496))

    result = pad_bottom(img, 1920)

    sample_pixel = result.getpixel((540, 1700))
    assert sample_pixel == fill

    # Los últimos 4px de la imagen original quedan pisados con color sólido.
    assert result.getpixel((540, 1496)) == fill
    assert result.getpixel((540, 1499)) == fill


def test_pad_bottom_imagen_original_en_parte_superior():
    """La imagen original queda pegada en la parte superior del canvas."""
    color = (10, 20, 30)
    img = _make_image(1080, 1500, color=color)
    result = pad_bottom(img, 1920)
    assert result.getpixel((0, 0)) == color


# ---------------------------------------------------------------------------
# generate_format
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fmt", ALL_FORMATS)
def test_generate_format_dimensiones_exactas(tmp_path: Path, fmt: ImageFormat):
    """Los archivos PNG generados tienen exactamente las dimensiones del formato."""
    # Imagen sintética más alta que cualquier formato
    source = tmp_path / "source.png"
    _save_image(_make_image(2000, 3000), source)

    out = generate_format(
        source_path=source,
        fmt=fmt,
        offset_y=0.5,
        slug="test-slug",
        output_dir=tmp_path / "out",
    )

    assert out.exists()
    with Image.open(out) as img:
        assert img.size == (fmt.width, fmt.height)


def test_generate_format_nombre_archivo(tmp_path: Path):
    """El archivo de salida sigue el patrón {slug}_{fmt.slug}.png."""
    source = tmp_path / "source.png"
    _save_image(_make_image(2000, 3000), source)

    out = generate_format(
        source_path=source,
        fmt=POST,
        offset_y=0.0,
        slug="mi-paquete",
        output_dir=tmp_path / "out",
    )

    assert out.name == "mi-paquete_post.png"


def test_generate_format_historia_con_padding(tmp_path: Path):
    """Historia activa pad_bottom cuando la imagen escalada es más corta que 1920px."""
    # Imagen con ratio muy ancho → al escalar a 1080px, el alto será < 1920
    source = tmp_path / "source.png"
    _save_image(_make_image(4000, 1000), source)  # ratio 4:1, alto scaled=270

    out = generate_format(
        source_path=source,
        fmt=HISTORIA,
        offset_y=0.0,
        slug="slug",
        output_dir=tmp_path / "out",
    )

    with Image.open(out) as img:
        assert img.size == (HISTORIA.width, HISTORIA.height)


def test_generate_format_salida_es_rgb(tmp_path: Path):
    """La imagen de salida siempre es RGB (sin canal alpha)."""
    source = tmp_path / "source.png"
    rgba_img = Image.new("RGBA", (2000, 3000), (100, 150, 200, 128))
    rgba_img.save(source, format="PNG")

    out = generate_format(
        source_path=source,
        fmt=POST,
        offset_y=0.0,
        slug="slug",
        output_dir=tmp_path / "out",
    )

    with Image.open(out) as img:
        assert img.mode == "RGB"


# ---------------------------------------------------------------------------
# process_all_formats
# ---------------------------------------------------------------------------


def test_process_all_formats_retorna_todos_los_slugs(tmp_path: Path):
    """El dict de salida contiene las tres claves de formato."""
    source = tmp_path / "source.png"
    _save_image(_make_image(2000, 3000), source)

    result = process_all_formats(
        source_path=source,
        slug="paquete-test",
        offsets={"post": 0.3, "historia": 0.5, "google": 0.0},
        output_dir=tmp_path / "out",
    )

    assert set(result.keys()) == {"post", "historia", "google"}


def test_process_all_formats_archivos_existen(tmp_path: Path):
    """Todos los archivos del dict de salida existen en disco."""
    source = tmp_path / "source.png"
    _save_image(_make_image(2000, 3000), source)

    result = process_all_formats(
        source_path=source,
        slug="paquete-test",
        offsets={},
        output_dir=tmp_path / "out",
    )

    for path in result.values():
        assert path.exists()


def test_process_all_formats_offsets_vacios_usa_cero(tmp_path: Path):
    """Un dict offsets vacío usa offset_y=0.0 para todos los formatos sin error."""
    source = tmp_path / "source.png"
    _save_image(_make_image(2000, 3000), source)

    result = process_all_formats(
        source_path=source,
        slug="slug",
        offsets={},
        output_dir=tmp_path / "out",
    )

    assert len(result) == 3


# ---------------------------------------------------------------------------
# preview_format
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fmt", ALL_FORMATS)
def test_preview_format_retorna_bytes_no_vacios(tmp_path: Path, fmt: ImageFormat):
    """preview_format retorna bytes PNG no vacíos para los tres formatos."""
    source = tmp_path / "source.png"
    _save_image(_make_image(2000, 3000), source)

    result = preview_format(source, fmt, offset_y=0.5)

    assert isinstance(result, bytes)
    assert len(result) > 0


@pytest.mark.parametrize("fmt", ALL_FORMATS)
def test_preview_format_dimensiones_exactas(tmp_path: Path, fmt: ImageFormat):
    """El PNG en memoria tiene exactamente las dimensiones del formato."""
    source = tmp_path / "source.png"
    _save_image(_make_image(2000, 3000), source)

    result = preview_format(source, fmt, offset_y=0.5)

    with Image.open(io.BytesIO(result)) as img:
        assert img.size == (fmt.width, fmt.height)


def test_preview_format_historia_con_padding(tmp_path: Path):
    """Historia activa pad_bottom cuando la imagen escalada es más corta que 1920px."""
    source = tmp_path / "source.png"
    _save_image(_make_image(4000, 1000), source)  # ratio 4:1 → scaled height ≈ 270

    result = preview_format(source, HISTORIA, offset_y=0.0)

    with Image.open(io.BytesIO(result)) as img:
        assert img.size == (HISTORIA.width, HISTORIA.height)


def test_preview_format_no_guarda_en_disco(tmp_path: Path):
    """preview_format no escribe ningún archivo en el directorio de trabajo."""
    source = tmp_path / "source.png"
    _save_image(_make_image(2000, 3000), source)

    preview_format(source, POST, offset_y=0.5)

    generated = [p for p in tmp_path.iterdir() if p.name != "source.png"]
    assert generated == []
