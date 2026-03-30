"""Interfaz de usuario Streamlit para el PEO Promotion Center."""

import dataclasses
import json

import streamlit as st
import streamlit.components.v1 as components

from peo_promotion_center.backend.content_generator import generate_content
from peo_promotion_center.backend.exceptions import (
    AuthenticationError,
    ImageNotFoundError,
    ScraperError,
)
from peo_promotion_center.backend.models import GeneratedContent
from peo_promotion_center.backend.scraper import scrape_package
from peo_promotion_center.frontend.auth import render_auth_gate
from peo_promotion_center.frontend.cookies import delete_auth_cookie, get_cookie_manager
from peo_promotion_center.frontend.crop_refine_ui import render_crop_refine_section
from peo_promotion_center.frontend.scrape_display import _render_scrape_metadata
from peo_promotion_center.frontend.session import _build_initial_tag_overlays, _init_session
from peo_promotion_center.frontend.zip_builder import build_zip


_COPY_BTN_HTML = """
<button
  onclick="
    var t = document.createElement('textarea');
    t.value = {text_json};
    document.body.appendChild(t);
    t.select();
    document.execCommand('copy');
    document.body.removeChild(t);
    this.textContent = '\u2713';
    setTimeout(function() {{ this.textContent = '\U0001F4CB'; }}.bind(this), 1500);
  "
  title="Copiar al portapapeles"
  style="font-size:1.2em;border:none;background:transparent;cursor:pointer;padding:0;"
>\U0001F4CB</button>
"""


def _copy_button(text: str, label_spacer: bool = True) -> None:
    """Renderiza un bot\u00f3n HTML que copia `text` al portapapeles del usuario."""
    if label_spacer:
        st.markdown('<p style="margin-bottom:5px;visibility:hidden">x</p>', unsafe_allow_html=True)
    html = _COPY_BTN_HTML.replace("{text_json}", json.dumps(text))
    components.html(html, height=36)


def render_url_section() -> None:
    """Sección 1: ingreso de URL y procesamiento del paquete."""
    st.header("1. URL del paquete")
    with st.form("url_form"):
        url = st.text_input(
            "URL del paquete", placeholder="https://...", label_visibility="collapsed"
        )
        col_m, col_r, col_ai = st.columns(3)
        with col_m:
            include_mailing = st.checkbox(
                "Mailing",
                value=st.session_state.get("include_mailing", True),
                help="Descarga flyer y genera asuntos y preview texts de mailing",
            )
        with col_r:
            include_rrss = st.checkbox(
                "RRSS",
                value=st.session_state.get("include_rrss", True),
                help="Genera im\u00e1genes de post, historia y Google, y copy para redes sociales",
            )
        with col_ai:
            include_ai_text = st.checkbox(
                "Texto con IA",
                value=st.session_state.get("include_ai_text", True),
                help="Habilita la generaci\u00f3n de textos con LLM",
            )
        submitted = st.form_submit_button("Procesar paquete")

    if st.session_state.scrape_result is not None:
        st.link_button("🔗 Ver paquete en PEO", url=st.session_state.last_url)
        _render_scrape_metadata(st.session_state.scrape_result)

    if not submitted:
        return

    if not url:
        st.error("Ingresá una URL válida.")
        return

    st.session_state.include_mailing = include_mailing
    st.session_state.include_rrss = include_rrss
    st.session_state.include_ai_text = include_ai_text

    try:
        with st.spinner("Conectando y descargando imagen..."):
            sr = scrape_package(url, st.session_state.session_dir)
        st.session_state.last_url = url
        st.session_state.scrape_result = sr
        st.session_state.generated_content = None
        st.session_state.zip_bytes = None
        st.session_state.zip_hash = None
        st.session_state.inpainted_finals = {"post": None, "historia": None, "google": None}
        st.session_state.inpaint_pending = {"post": None, "historia": None, "google": None}
        st.session_state.inpaint_history = {"post": [], "historia": [], "google": []}
        st.session_state.canvas_open = {"post": False, "historia": False, "google": False}
        st.session_state.tag_overlays = _build_initial_tag_overlays()
        metadata = {
            k: v for k, v in dataclasses.asdict(sr).items() if k != "image_path"
        }
    except (AuthenticationError, ImageNotFoundError, ScraperError, Exception) as exc:
        st.error(f"Error al procesar el paquete: {exc}")
        return

    if include_ai_text:
        try:
            with st.spinner("Generando contenido con IA..."):
                st.session_state.generated_content = generate_content(
                    metadata,
                    api_key=st.session_state.openai_api_key,
                    include_rrss=include_rrss,
                    include_mailing=include_mailing,
                )
        except Exception as exc:
            st.error(f"Error al generar contenido con IA: {exc}")
    else:
        st.session_state.generated_content = GeneratedContent(
            copy_redes="",
            asuntos_mailing=["", "", ""],
            preview_texts_mailing=["", "", ""],
        )

    gc = st.session_state.generated_content
    if gc is not None:
        st.session_state.edited_copy = gc.copy_redes
        st.session_state.edited_asuntos = list(gc.asuntos_mailing)
        _preview_texts = list(getattr(gc, "preview_texts_mailing", ["", "", ""]))
        st.session_state.edited_preview_texts = _preview_texts
        for _i, _asunto in enumerate(gc.asuntos_mailing):
            st.session_state[f"asunto_{_i}"] = _asunto
        for _i, _pt in enumerate(_preview_texts):
            st.session_state[f"preview_text_{_i}"] = _pt

    st.rerun()


def render_content_section() -> None:
    """Sección 3: copy de IA editable."""
    if not st.session_state.get("include_ai_text", True):
        return

    gc = st.session_state.generated_content
    if gc is None:
        return

    st.header("3. Contenido generado por IA")

    if "edited_copy" not in st.session_state:
        st.session_state.edited_copy = gc.copy_redes
    if "edited_asuntos" not in st.session_state:
        st.session_state.edited_asuntos = list(gc.asuntos_mailing)
    gc_preview_texts = list(getattr(gc, "preview_texts_mailing", ["", "", ""]))
    if "edited_preview_texts" not in st.session_state:
        st.session_state.edited_preview_texts = gc_preview_texts

    if st.session_state.get("include_rrss", True):
        col_field, col_btn = st.columns([12, 1])
        with col_field:
            st.text_area(
                "Copy para redes sociales",
                key="edited_copy",
                height=400,
            )
        with col_btn:
            _copy_button(st.session_state.edited_copy)

    if st.session_state.get("include_mailing", True):
        for i in range(len(gc.asuntos_mailing)):
            col_field, col_btn = st.columns([12, 1])
            with col_field:
                st.session_state.edited_asuntos[i] = st.text_input(
                    f"Asunto {i + 1}",
                    value=st.session_state.edited_asuntos[i],
                    key=f"asunto_{i}",
                )
            with col_btn:
                _copy_button(st.session_state.edited_asuntos[i])
        for i in range(len(getattr(gc, "preview_texts_mailing", ["", "", ""]))):
            col_field, col_btn = st.columns([12, 1])
            with col_field:
                st.session_state.edited_preview_texts[i] = st.text_input(
                    f"Preview Text {i + 1}",
                    value=st.session_state.edited_preview_texts[i],
                    key=f"preview_text_{i}",
                )
            with col_btn:
                _copy_button(st.session_state.edited_preview_texts[i])


def render_download_section() -> None:
    """Sección 4: generación y descarga del ZIP con todos los archivos."""
    import hashlib

    sr = st.session_state.scrape_result
    gc = st.session_state.generated_content
    if sr is None or gc is None:
        return

    copy_redes = st.session_state.get("edited_copy", gc.copy_redes)
    asuntos = st.session_state.get("edited_asuntos", list(gc.asuntos_mailing))
    preview_texts = st.session_state.get(
        "edited_preview_texts", list(getattr(gc, "preview_texts_mailing", ["", "", ""]))
    )

    include_mailing = st.session_state.get("include_mailing", True)
    include_rrss = st.session_state.get("include_rrss", True)

    finals_hash = str({
        k: (v.tobytes() if v is not None else None)
        for k, v in st.session_state.get("inpainted_finals", {}).items()
    })
    current_hash = hashlib.md5(
        "|".join([
            str(sr.image_path),
            sr.slug,
            str(st.session_state.offsets),
            copy_redes,
            str(asuntos),
            str(preview_texts),
            finals_hash,
            str(st.session_state.get("tag_overlays", {})),
            str(include_mailing),
            str(include_rrss),
        ]).encode()
    ).hexdigest()

    if st.session_state.get("zip_bytes") is None or st.session_state.get("zip_hash") != current_hash:
        with st.spinner("Generando paquete..."):
            st.session_state.zip_bytes = build_zip(
                source_path=sr.image_path,
                slug=sr.slug,
                offsets=st.session_state.offsets,
                copy_redes=copy_redes,
                asuntos_mailing=asuntos,
                preview_texts_mailing=preview_texts,
                output_dir=st.session_state.session_dir,
                inpainted_images=st.session_state.get("inpainted_finals"),
                tag_overlays=st.session_state.get("tag_overlays"),
                include_mailing=include_mailing,
                include_rrss=include_rrss,
            )
        st.session_state.zip_hash = current_hash

    st.header("4. Descarga")
    st.download_button(
        label="Descargar paquete",
        data=st.session_state.zip_bytes,
        file_name=f"{sr.slug}.zip",
        mime="application/zip",
    )


def main() -> None:
    """Renderiza la aplicación Streamlit principal."""
    _init_session()
    cm = get_cookie_manager()

    if not st.session_state.get("authenticated", False):
        render_auth_gate(cm)
    if not st.session_state.get("authenticated", False):
        st.stop()

    st.title("PEO Promotion Center")
    render_url_section()
    st.divider()
    if st.session_state.get("include_rrss", True):
        render_crop_refine_section()
        st.divider()
    render_content_section()
    st.divider()
    render_download_section()

    st.markdown("<br>" * 2, unsafe_allow_html=True)
    _, col_logout = st.columns([8, 1])
    with col_logout:
        if st.button("Cerrar sesión", width="stretch", type="tertiary"):
            delete_auth_cookie(cm)
            st.session_state.authenticated = False
            st.rerun()


if __name__ == "__main__":
    main()
