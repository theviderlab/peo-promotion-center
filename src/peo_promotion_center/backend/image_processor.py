"""Módulo de procesamiento de imágenes de los paquetes turísticos."""

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageStat


@dataclass(frozen=True)
class ImageFormat:
    """Especificación de un formato de imagen de salida."""

    name: str
    width: int
    height: int
    slug: str


POST = ImageFormat("Post", 1080, 1350, "post")
HISTORIA = ImageFormat("Historia", 1080, 1920, "historia")
GOOGLE = ImageFormat("Google", 960, 640, "google")

ALL_FORMATS: list[ImageFormat] = [POST, HISTORIA, GOOGLE]


def scale_to_width(img: Image.Image, target_width: int) -> Image.Image:
    """
    Escala la imagen al ancho objetivo preservando la relación de aspecto.

    Args:
        img: Imagen fuente.
        target_width: Ancho objetivo en píxeles.

    Returns:
        Imagen reescalada.
    """
    target_height = round(img.height * target_width / img.width)
    return img.resize((target_width, target_height), Image.LANCZOS)


def crop_to_canvas(img: Image.Image, fmt: ImageFormat, offset_y: float) -> Image.Image:
    """
    Recorta la imagen al canvas del formato usando un offset vertical.

    Args:
        img: Imagen ya escalada al ancho del formato.
        fmt: Formato de salida objetivo.
        offset_y: Valor entre 0.0 (tope) y 1.0 (abajo) que controla el recorte.

    Returns:
        Imagen recortada al tamaño del canvas.
    """
    if img.height <= fmt.height:
        return img

    max_offset = img.height - fmt.height
    top = round(offset_y * max_offset)
    return img.crop((0, top, fmt.width, top + fmt.height))


def pad_bottom(img: Image.Image, target_height: int, sample_margin_px: int = 4) -> Image.Image:
    """
    Rellena la parte inferior de la imagen con un color promedio del borde inferior.

    Args:
        img: Imagen fuente más corta que target_height.
        target_height: Alto del canvas de destino.
        sample_margin_px: Píxeles del borde inferior a excluir del muestreo y
            sobrescribir con color sólido para evitar artefactos de exportación.

    Returns:
        Imagen con el relleno inferior aplicado.
    """
    sample_margin_px = max(0, sample_margin_px)

    if img.height <= sample_margin_px:
        sample_top = 0
        sample_bottom = img.height
    else:
        sample_top = img.height - sample_margin_px - 1
        sample_bottom = img.height - sample_margin_px

    sample_row = img.crop((0, sample_top, img.width, sample_bottom))
    avg = ImageStat.Stat(sample_row).mean
    fill_color = tuple(round(c) for c in avg[:3])

    canvas = Image.new("RGB", (img.width, target_height), fill_color)
    canvas.paste(img, (0, 0))

    if sample_margin_px > 0 and img.height > sample_margin_px:
        bottom_strip = Image.new("RGB", (img.width, sample_margin_px), fill_color)
        canvas.paste(bottom_strip, (0, img.height - sample_margin_px))

    return canvas


def preview_format(source_path: Path, fmt: ImageFormat, offset_y: float, overlays: list | None = None) -> bytes:
    """
    Genera una previsualización del recorte en memoria sin guardar a disco.

    Args:
        source_path: Ruta a la imagen fuente descargada.
        fmt: Formato de imagen objetivo.
        offset_y: Offset vertical de recorte (0.0–1.0).

    Returns:
        Bytes del PNG generado en memoria.
    """
    with Image.open(source_path) as raw:
        img = raw.convert("RGB")

    img = scale_to_width(img, fmt.width)
    img = crop_to_canvas(img, fmt, offset_y)

    if fmt is HISTORIA and img.height < fmt.height:
        img = pad_bottom(img, fmt.height)

    if overlays:
        from peo_promotion_center.backend.compositing import apply_overlays

        img = apply_overlays(img, overlays)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_format(
    source_path: Path,
    fmt: ImageFormat,
    offset_y: float,
    slug: str,
    output_dir: Path,
    overlays: list | None = None,
) -> Path:
    """
    Ejecuta el pipeline completo para un único formato de salida.

    Args:
        source_path: Ruta a la imagen fuente descargada.
        fmt: Formato de imagen objetivo.
        offset_y: Offset vertical de recorte (0.0–1.0).
        slug: Nombre URL-friendly del paquete (para nombrar el archivo).
        output_dir: Directorio donde se guarda la imagen generada.

    Returns:
        Path del archivo PNG generado.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(source_path) as raw:
        img = raw.convert("RGB")

    img = scale_to_width(img, fmt.width)
    img = crop_to_canvas(img, fmt, offset_y)

    if fmt is HISTORIA and img.height < fmt.height:
        img = pad_bottom(img, fmt.height)

    if overlays:
        from peo_promotion_center.backend.compositing import apply_overlays

        img = apply_overlays(img, overlays)

    out_path = output_dir / f"{slug}_{fmt.slug}.png"
    img.save(out_path, format="PNG")
    return out_path


def process_all_formats(
    source_path: Path,
    slug: str,
    offsets: dict[str, float],
    output_dir: Path,
) -> dict[str, Path]:
    """
    Genera los tres formatos de imagen a partir de la imagen fuente.

    Args:
        source_path: Ruta a la imagen descargada.
        slug: Nombre del paquete en formato URL (para nombrar archivos).
        offsets: Diccionario con offset_y por formato, e.g.
                 {"post": 0.3, "historia": 0.5, "google": 0.0}.
        output_dir: Directorio donde guardar las imágenes generadas.

    Returns:
        Diccionario {formato_slug: Path} con las rutas de los archivos generados.
    """
    return {
        fmt.slug: generate_format(
            source_path=source_path,
            fmt=fmt,
            offset_y=offsets.get(fmt.slug, 0.0),
            slug=slug,
            output_dir=output_dir,
        )
        for fmt in ALL_FORMATS
    }
