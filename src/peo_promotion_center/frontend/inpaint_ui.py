"""Sección de refinamiento por inpainting para el PEO Promotion Center."""

import base64
import io
import os

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

from peo_promotion_center.backend.image_processor import ALL_FORMATS, preview_format

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
    # Canal alfa: zonas pintadas tienen alpha > 0; umbral para máscara binaria
    alpha = img.split()[3].point(lambda p: 255 if p > 50 else 0)
    return alpha.resize((target_w, target_h), Image.NEAREST)


def render_refinement_section() -> None:
    """
    Sección 3: refinamiento opcional por inpainting, un expander por formato.

    Lee scrape_result y offsets del session_state.
    Escribe máscaras confirmadas en st.session_state.inpaint_masks[fmt.slug].
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
        with st.expander(f"✏️ {fmt.name} ({fmt.width}×{fmt.height})", expanded=False):
            offset = st.session_state.offsets[fmt.slug]

            # Obtener la imagen recortada del formato (bytes de preview)
            cropped_bytes = preview_format(sr.image_path, fmt, offset)
            cropped_img = Image.open(io.BytesIO(cropped_bytes)).convert("RGB")

            # Escalar al ancho de canvas manteniendo proporción del formato
            scale = CANVAS_WIDTH / fmt.width
            canvas_height = round(fmt.height * scale)
            preview = cropped_img.resize((CANVAS_WIDTH, canvas_height), Image.LANCZOS)
            bg_data_url = _img_to_data_url(preview)

            brush_size = st.slider(
                "Tamaño del pincel",
                min_value=5,
                max_value=60,
                value=BRUSH_SIZE_DEFAULT,
                key=f"brush_{fmt.slug}",
            )

            clear_flag = st.session_state.pop(f"_clear_{fmt.slug}", False)

            # Canvas personalizado: compatible con Streamlit ≥1.55.
            # Retorna un data URL PNG con los trazos del usuario (canal alfa),
            # o None si el canvas está vacío.
            canvas_value: str | None = _inpaint_canvas(
                bg_image=bg_data_url,
                brush_size=brush_size,
                width=CANVAS_WIDTH,
                height=canvas_height,
                clear=clear_flag,
                key=f"canvas_{fmt.slug}",
                default=None,
            )

            current_mask = st.session_state.inpaint_masks.get(fmt.slug)
            if current_mask is not None:
                st.success("Máscara guardada. Se aplicará al generar el ZIP.")

            col_apply, col_clear = st.columns([1, 1])

            with col_apply:
                if st.button("Guardar máscara", key=f"apply_{fmt.slug}"):
                    if canvas_value is None:
                        st.warning("Dibujá sobre la imagen primero.")
                    else:
                        mask_full = _data_url_to_mask(
                            canvas_value, fmt.width, fmt.height
                        )
                        st.session_state.inpaint_masks[fmt.slug] = mask_full
                        st.success("Máscara guardada.")

            with col_clear:
                if st.button("Limpiar máscara", key=f"clear_{fmt.slug}"):
                    st.session_state.inpaint_masks[fmt.slug] = None
                    st.session_state[f"_clear_{fmt.slug}"] = True
                    st.rerun()
