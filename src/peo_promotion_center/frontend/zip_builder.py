"""Construcción del paquete ZIP de descarga para el PEO Promotion Center."""

import io
import zipfile
from pathlib import Path

from PIL import Image

from peo_promotion_center.backend.image_processor import ALL_FORMATS, generate_format


def build_zip(
    source_path: Path,
    slug: str,
    offsets: dict[str, float],
    copy_redes: str,
    asuntos_mailing: list[str],
    preview_texts_mailing: list[str],
    output_dir: Path,
    inpainted_images: dict[str, Image.Image | None] | None = None,
) -> bytes:
    """
    Genera los tres formatos PNG y los empaqueta junto con los textos en un ZIP en memoria.

    Args:
        source_path: Ruta a la imagen fuente descargada.
        slug: Nombre URL-friendly del paquete (se usa para nombrar los archivos).
        offsets: Offsets verticales de recorte por formato, p.ej. ``{"post": 0.3}``.
        copy_redes: Texto de copy para redes sociales.
        asuntos_mailing: Lista de tres asuntos de mailing.
        preview_texts_mailing: Lista de tres preview texts de mailing.
        output_dir: Directorio donde se guardan los PNG generados.
        inpainted_images: Imágenes ya procesadas por inpainting opcionales por formato slug.
                          Si un formato tiene imagen aceptada, se usa directamente sin re-ejecutar LaMa.

    Returns:
        Bytes del archivo ZIP generado en memoria.
    """
    png_paths: dict[str, Path] = {}
    for fmt in ALL_FORMATS:
        if inpainted_images and inpainted_images.get(fmt.slug) is not None:
            out_path = output_dir / f"{slug}_{fmt.slug}.png"
            inpainted_images[fmt.slug].save(out_path, format="PNG")
        else:
            out_path = generate_format(source_path, fmt, offsets[fmt.slug], slug, output_dir)
        png_paths[fmt.slug] = out_path

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        flyer_suffix = source_path.suffix or ".png"
        zf.write(source_path, arcname=f"{slug}_flyer{flyer_suffix}")
        for fmt_slug, png_path in png_paths.items():
            zf.write(png_path, arcname=f"{slug}_{fmt_slug}.png")
        zf.writestr("copy_redes.txt", copy_redes)
        zf.writestr("asuntos_mailing.txt", "\n".join(asuntos_mailing))
        zf.writestr("preview_texts_mailing.txt", "\n".join(preview_texts_mailing))

    return buf.getvalue()
