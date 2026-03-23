"""Interfaz de usuario Streamlit para el PEO Promotion Center."""

import dataclasses

import streamlit as st

from peo_promotion_center.backend.content_generator import generate_content
from peo_promotion_center.backend.exceptions import (
    AuthenticationError,
    ImageNotFoundError,
    ScraperError,
)
from peo_promotion_center.backend.scraper import scrape_package
from peo_promotion_center.frontend.auth import render_auth_gate
from peo_promotion_center.frontend.cookies import delete_auth_cookie, get_cookie_manager
from peo_promotion_center.frontend.crop_refine_ui import render_crop_refine_section
from peo_promotion_center.frontend.scrape_display import _render_scrape_metadata
from peo_promotion_center.frontend.session import _build_initial_tag_overlays, _init_session
from peo_promotion_center.frontend.zip_builder import build_zip


def render_url_section() -> None:
    """Sección 1: ingreso de URL y procesamiento del paquete."""
    st.header("1. URL del paquete")
    with st.form("url_form"):
        url = st.text_input(
            "URL del paquete", placeholder="https://...", label_visibility="collapsed"
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
        st.session_state.pop("edited_copy", None)
        st.session_state.pop("edited_asuntos", None)
        st.session_state.pop("edited_preview_texts", None)
        for _i in range(3):
            st.session_state.pop(f"asunto_{_i}", None)
            st.session_state.pop(f"preview_text_{_i}", None)
        metadata = {
            k: v for k, v in dataclasses.asdict(sr).items() if k != "image_path"
        }
    except (AuthenticationError, ImageNotFoundError, ScraperError, Exception) as exc:
        st.error(f"Error al procesar el paquete: {exc}")
        return

    try:
        with st.spinner("Generando contenido con IA..."):
            st.session_state.generated_content = generate_content(
                metadata,
                api_key=st.session_state.openai_api_key,
            )
    except Exception as exc:
        st.error(f"Error al generar contenido con IA: {exc}")

    st.rerun()


def render_content_section() -> None:
    """Sección 3: copy de IA editable."""
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

    st.session_state.edited_copy = st.text_area(
        "Copy para redes sociales", value=st.session_state.edited_copy, height=200
    )
    for i in range(len(gc.asuntos_mailing)):
        st.session_state.edited_asuntos[i] = st.text_input(
            f"Asunto {i + 1}",
            value=st.session_state.edited_asuntos[i],
            key=f"asunto_{i}",
        )
    for i in range(len(getattr(gc, "preview_texts_mailing", ["", "", ""]))):
        st.session_state.edited_preview_texts[i] = st.text_input(
            f"Preview Text {i + 1}",
            value=st.session_state.edited_preview_texts[i],
            key=f"preview_text_{i}",
        )


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
