"""Construcción del paquete ZIP de descarga para el PEO Promotion Center."""

import io
import zipfile
from pathlib import Path

from PIL import Image

from peo_promotion_center.backend.compositing import TAG_REGISTRY, OverlaySpec, apply_overlays
from peo_promotion_center.backend.image_processor import ALL_FORMATS, generate_format


def _build_overlay_specs_for_format(
    fmt_slug: str,
    tag_overlays: dict[str, dict[str, dict]] | None,
) -> list[OverlaySpec]:
    """
    Construye la lista de OverlaySpec activos para un formato del ZIP.

    Args:
        fmt_slug: Slug del formato (p.ej. "post").
        tag_overlays: Estado de overlays por formato y tag_id.

    Returns:
        Lista de OverlaySpec con los tags habilitados para ese formato.
    """
    if not tag_overlays or fmt_slug not in tag_overlays:
        return []
    fmt_state = tag_overlays[fmt_slug]
    specs: list[OverlaySpec] = []
    for tag_def in TAG_REGISTRY:
        state = fmt_state.get(tag_def.tag_id)
        if state and state.get("enabled"):
            tag_img = Image.open(tag_def.path).convert("RGBA")
            specs.append(OverlaySpec(tag=tag_img, x=state["x"], y=state["y"]))
    return specs


def build_zip(
    source_path: Path,
    slug: str,
    offsets: dict[str, float],
    copy_redes: str,
    asuntos_mailing: list[str],
    preview_texts_mailing: list[str],
    output_dir: Path,
    inpainted_images: dict[str, Image.Image | None] | None = None,
    tag_overlays: dict[str, dict[str, dict]] | None = None,
    include_mailing: bool = True,
    include_rrss: bool = True,
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
        tag_overlays: Estado de overlays por formato y tag_id. Los tags habilitados se
                      superponen como última operación antes de guardar el PNG.
        include_mailing: Si es False, excluye el flyer y los archivos de texto de mailing del ZIP.
        include_rrss: Si es False, excluye los PNG de post/historia/google y el copy de redes del ZIP.

    Returns:
        Bytes del archivo ZIP generado en memoria.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        if include_mailing:
            flyer_suffix = source_path.suffix or ".png"
            zf.write(source_path, arcname=f"{slug}_flyer{flyer_suffix}")
            zf.writestr("asuntos_mailing.txt", "\n".join(asuntos_mailing))
            zf.writestr("preview_texts_mailing.txt", "\n".join(preview_texts_mailing))

        if include_rrss:
            for fmt in ALL_FORMATS:
                overlays = _build_overlay_specs_for_format(fmt.slug, tag_overlays)
                if inpainted_images and inpainted_images.get(fmt.slug) is not None:
                    img: Image.Image = inpainted_images[fmt.slug]
                    if overlays:
                        img = apply_overlays(img, overlays)
                    out_path = output_dir / f"{slug}_{fmt.slug}.png"
                    img.save(out_path, format="PNG")
                else:
                    out_path = generate_format(
                        source_path, fmt, offsets[fmt.slug], slug, output_dir, overlays=overlays
                    )
                zf.write(out_path, arcname=f"{slug}_{fmt.slug}.png")
            zf.writestr("copy_redes.txt", copy_redes)

    return buf.getvalue()
