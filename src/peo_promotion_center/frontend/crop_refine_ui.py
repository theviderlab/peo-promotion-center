"""Sección unificada de recorte y refinamiento por inpainting."""

import base64
import io
import os

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

from peo_promotion_center.backend.image_processor import ALL_FORMATS, preview_format
from peo_promotion_center.backend.inpainter import inpaint

BRUSH_SIZE_DEFAULT = 20
CANVAS_WIDTH = 400  # px de visualización (no afecta resolución de salida)

_COMPONENT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "canvas_component"
)
_inpaint_canvas = components.declare_component("inpaint_canvas", path=_COMPONENT_DIR)


def _img_to_data_url(img: Image.Image) -> str:
    """Convierte una imagen PIL a data URL base64 PNG."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def _data_url_to_mask(data_url: str, target_w: int, target_h: int) -> Image.Image:
    """Convierte data URL PNG del canvas a máscara PIL en resolución de salida."""
    _, encoded = data_url.split(",", 1)
    img = Image.open(io.BytesIO(base64.b64decode(encoded))).convert("RGBA")
    alpha = img.split()[3].point(lambda p: 255 if p > 50 else 0)
    return alpha.resize((target_w, target_h), Image.NEAREST)


def _render_pending_state(fmt: object) -> bool:
    """
    Renderiza el estado de resultado pendiente (aceptar/rechazar).

    Args:
        fmt: Objeto de formato con atributos slug, width, height.

    Returns:
        True si hay un resultado pendiente (el caller debe hacer return).
    """
    slug = fmt.slug  # type: ignore[attr-defined]
    pending: Image.Image | None = st.session_state.inpaint_pending.get(slug)
    if pending is None:
        return False

    st.image(pending, caption="Resultado — ¿Aceptar o rechazar?", use_container_width=True)
    col_acc, col_rej = st.columns(2)
    with col_acc:
        if st.button("✅ Aceptar", key=f"accept_{slug}"):
            current_final: Image.Image | None = st.session_state.inpainted_finals.get(slug)
            if current_final is not None:
                st.session_state.inpaint_history[slug].append(current_final)
            st.session_state.inpainted_finals[slug] = pending
            st.session_state.inpaint_pending[slug] = None
            st.session_state[f"_clear_{slug}"] = True
            st.rerun()
    with col_rej:
        if st.button("❌ Rechazar", key=f"reject_{slug}"):
            st.session_state.inpaint_pending[slug] = None
            st.rerun()
    return True


def _render_canvas_editor(
    fmt: object,
    ref_img: Image.Image,
    canvas_height: int,
    bg_data_url: str,
) -> None:
    """
    Renderiza el canvas de dibujo y los controles del editor.

    Args:
        fmt: Objeto de formato con atributos slug, width, height.
        ref_img: Imagen de referencia actual (recortada o inpaintada).
        canvas_height: Altura del canvas en píxeles de visualización.
        bg_data_url: Data URL de la imagen de fondo para el canvas.
    """
    slug = fmt.slug  # type: ignore[attr-defined]

    brush_size = st.slider(
        "Tamaño del pincel",
        min_value=5,
        max_value=60,
        value=BRUSH_SIZE_DEFAULT,
        key=f"brush_{slug}",
    )

    clear_flag = st.session_state.pop(f"_clear_{slug}", False)
    canvas_value: str | None = _inpaint_canvas(
        bg_image=bg_data_url,
        brush_size=brush_size,
        width=CANVAS_WIDTH,
        height=canvas_height,
        clear=clear_flag,
        key=f"canvas_{slug}",
        default=None,
    )

    has_history = bool(st.session_state.inpaint_history.get(slug))
    col_apply, col_undo, col_close = st.columns(3)

    with col_apply:
        if st.button("Aplicar", key=f"apply_{slug}"):
            if canvas_value is None:
                st.warning("Dibujá sobre la imagen primero.")
            else:
                mask_full = _data_url_to_mask(canvas_value, fmt.width, fmt.height)  # type: ignore[attr-defined]
                with st.spinner("Aplicando borrado…"):
                    result = inpaint(ref_img, mask_full)
                st.session_state.inpaint_pending[slug] = result
                st.rerun()

    with col_undo:
        if st.button("Deshacer", key=f"undo_{slug}", disabled=not has_history):
            prev = st.session_state.inpaint_history[slug].pop()
            st.session_state.inpainted_finals[slug] = prev
            st.session_state[f"_clear_{slug}"] = True
            st.rerun()

    with col_close:
        if st.button("Cerrar editor", key=f"close_{slug}"):
            st.session_state.canvas_open[slug] = False
            st.rerun()


def _render_format_expander(fmt: object, sr: object) -> None:
    """
    Renderiza el expander de recorte + refinamiento para un formato.

    Args:
        fmt: Objeto de formato (ImageFormat) con name, slug, width, height.
        sr: ScrapeResult con image_path y resto de metadatos del paquete.
    """
    slug = fmt.slug  # type: ignore[attr-defined]

    with st.expander(f"{fmt.name} ({fmt.width}×{fmt.height})", expanded=False):  # type: ignore[attr-defined]
        offset = st.session_state.offsets[slug]
        cropped_bytes = preview_format(sr.image_path, fmt, offset)  # type: ignore[attr-defined]
        cropped_img = Image.open(io.BytesIO(cropped_bytes)).convert("RGB")

        current_final: Image.Image | None = st.session_state.inpainted_finals.get(slug)
        ref_img: Image.Image = current_final if current_final is not None else cropped_img

        # ── Slider de offset (deshabilitado si hay inpainting aceptado) ──
        has_inpainting = current_final is not None
        new_offset = st.slider(
            "Posición de recorte",
            min_value=0.0,
            max_value=1.0,
            value=offset,
            step=0.01,
            help="0 = arriba · 1 = abajo",
            key=f"slider_{slug}",
            disabled=has_inpainting,
        )
        if not has_inpainting:
            st.session_state.offsets[slug] = new_offset

        # ── Badge + botón de reset cuando hay inpainting activo ──
        if has_inpainting:
            col_badge, col_reset = st.columns([3, 1])
            with col_badge:
                st.success("✅ Ajuste activo")
            with col_reset:
                if st.button("🔄 Resetear", key=f"reset_{slug}"):
                    st.session_state.inpainted_finals[slug] = None
                    st.session_state.inpaint_pending[slug] = None
                    st.session_state.inpaint_history[slug] = []
                    st.session_state.canvas_open[slug] = False
                    st.session_state.pop(f"_clear_{slug}", None)
                    st.rerun()

        # ── Preview de la imagen (recortada o inpaintada) ──
        st.image(ref_img, use_container_width=True)

        # ── Estado pendiente: aceptar / rechazar ──
        if _render_pending_state(fmt):
            return

        # ── Canvas on-demand ──
        scale = CANVAS_WIDTH / fmt.width  # type: ignore[attr-defined]
        canvas_height = round(fmt.height * scale)  # type: ignore[attr-defined]
        bg_data_url = _img_to_data_url(
            ref_img.resize((CANVAS_WIDTH, canvas_height), Image.LANCZOS)
        )

        if st.session_state.canvas_open.get(slug, False):
            _render_canvas_editor(fmt, ref_img, canvas_height, bg_data_url)
        else:
            if st.button("✏️ Editar", key=f"open_canvas_{slug}"):
                st.session_state.canvas_open[slug] = True
                st.rerun()


def render_crop_refine_section() -> None:
    """
    Sección 2: recorte de imagen + refinamiento opcional por inpainting.

    Muestra un expander por formato con slider de recorte y canvas de edición
    on-demand. Si el usuario acepta un inpainting, el slider queda bloqueado
    hasta que se reseteen los cambios.

    Lee scrape_result y offsets del session_state.
    Escribe resultados aceptados en st.session_state.inpainted_finals[fmt.slug].
    """
    if st.session_state.scrape_result is None:
        return

    st.header("2. Recorte y refinamiento")
    st.caption(
        "Ajustá la posición de recorte de cada formato. "
        "Si necesitás borrar logos u otros elementos, usá ✏️ Editar para pintarlos."
    )

    sr = st.session_state.scrape_result
    for fmt in ALL_FORMATS:
        _render_format_expander(fmt, sr)
