"""Sección de refinamiento por inpainting para el PEO Promotion Center."""

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


def _render_format_expander(fmt: object, sr: object) -> None:
    """
    Renderiza el expander de inpainting para un formato dado.

    Estados posibles:
    - Canvas: el usuario pinta la máscara sobre la imagen de referencia actual.
    - Pendiente: LaMa procesó; el usuario acepta o rechaza el resultado.
    """
    with st.expander(f"✏️ {fmt.name} ({fmt.width}×{fmt.height})", expanded=False):  # type: ignore[attr-defined]
        offset = st.session_state.offsets[fmt.slug]  # type: ignore[attr-defined]
        cropped_bytes = preview_format(sr.image_path, fmt, offset)  # type: ignore[attr-defined]
        cropped_img = Image.open(io.BytesIO(cropped_bytes)).convert("RGB")

        current_final: Image.Image | None = st.session_state.inpainted_finals.get(fmt.slug)  # type: ignore[attr-defined]
        ref_img: Image.Image = current_final if current_final is not None else cropped_img

        scale = CANVAS_WIDTH / fmt.width  # type: ignore[attr-defined]
        canvas_height = round(fmt.height * scale)  # type: ignore[attr-defined]
        bg_data_url = _img_to_data_url(ref_img.resize((CANVAS_WIDTH, canvas_height), Image.LANCZOS))

        pending: Image.Image | None = st.session_state.inpaint_pending.get(fmt.slug)  # type: ignore[attr-defined]

        if pending is not None:
            st.image(pending, caption="Resultado — ¿Aceptar o rechazar?", use_container_width=True)
            col_acc, col_rej = st.columns(2)
            with col_acc:
                if st.button("✅ Aceptar", key=f"accept_{fmt.slug}"):  # type: ignore[attr-defined]
                    if current_final is not None:
                        st.session_state.inpaint_history[fmt.slug].append(current_final)  # type: ignore[attr-defined]
                    st.session_state.inpainted_finals[fmt.slug] = pending  # type: ignore[attr-defined]
                    st.session_state.inpaint_pending[fmt.slug] = None  # type: ignore[attr-defined]
                    st.session_state[f"_clear_{fmt.slug}"] = True  # type: ignore[attr-defined]
                    st.rerun()
            with col_rej:
                if st.button("❌ Rechazar", key=f"reject_{fmt.slug}"):  # type: ignore[attr-defined]
                    st.session_state.inpaint_pending[fmt.slug] = None  # type: ignore[attr-defined]
                    st.rerun()
            return

        brush_size = st.slider(
            "Tamaño del pincel",
            min_value=5,
            max_value=60,
            value=BRUSH_SIZE_DEFAULT,
            key=f"brush_{fmt.slug}",  # type: ignore[attr-defined]
        )

        clear_flag = st.session_state.pop(f"_clear_{fmt.slug}", False)  # type: ignore[attr-defined]
        canvas_value: str | None = _inpaint_canvas(
            bg_image=bg_data_url,
            brush_size=brush_size,
            width=CANVAS_WIDTH,
            height=canvas_height,
            clear=clear_flag,
            key=f"canvas_{fmt.slug}",  # type: ignore[attr-defined]
            default=None,
        )

        has_history = bool(st.session_state.inpaint_history.get(fmt.slug))  # type: ignore[attr-defined]
        col_apply, col_undo = st.columns(2)

        with col_apply:
            if st.button("Aplicar", key=f"apply_{fmt.slug}"):  # type: ignore[attr-defined]
                if canvas_value is None:
                    st.warning("Dibujá sobre la imagen primero.")
                else:
                    mask_full = _data_url_to_mask(canvas_value, fmt.width, fmt.height)  # type: ignore[attr-defined]
                    with st.spinner("Aplicando borrado…"):
                        result = inpaint(ref_img, mask_full)
                    st.session_state.inpaint_pending[fmt.slug] = result  # type: ignore[attr-defined]
                    st.rerun()

        with col_undo:
            if st.button("Deshacer", key=f"undo_{fmt.slug}", disabled=not has_history):  # type: ignore[attr-defined]
                prev = st.session_state.inpaint_history[fmt.slug].pop()  # type: ignore[attr-defined]
                st.session_state.inpainted_finals[fmt.slug] = prev  # type: ignore[attr-defined]
                st.session_state[f"_clear_{fmt.slug}"] = True  # type: ignore[attr-defined]
                st.rerun()


def render_refinement_section() -> None:
    """
    Sección 3: refinamiento opcional por inpainting, un expander por formato.

    Lee scrape_result y offsets del session_state.
    Escribe resultados aceptados en st.session_state.inpainted_finals[fmt.slug].
    """
    if st.session_state.scrape_result is None:
        return

    st.header("3. Refinamiento (opcional)")
    st.caption(
        "Si algún formato quedó con logos, textos o elementos no deseados, "
        "pintá el área y aplicá el borrado. Cada formato se procesa de forma independiente."
    )

    sr = st.session_state.scrape_result
    for fmt in ALL_FORMATS:
        _render_format_expander(fmt, sr)
