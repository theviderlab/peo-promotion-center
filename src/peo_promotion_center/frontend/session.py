"""Inicialización del estado de sesión para la aplicación Streamlit."""

import shutil
import time
import uuid
from pathlib import Path

import streamlit as st

_SESSION_BASE_DIR = Path("descargas")
_MAX_SESSION_AGE_HOURS = 24


def _cleanup_old_sessions(base_dir: Path, max_age_hours: int = _MAX_SESSION_AGE_HOURS) -> None:
    """
    Elimina subdirectorios de sesión cuya última modificación supere max_age_hours.

    Args:
        base_dir: Directorio raíz que contiene los subdirectorios de sesión.
        max_age_hours: Antigüedad máxima permitida en horas.
    """
    if not base_dir.exists():
        return
    cutoff = time.time() - max_age_hours * 3600
    for entry in base_dir.iterdir():
        if entry.is_dir() and entry.stat().st_mtime < cutoff:
            shutil.rmtree(entry, ignore_errors=True)


def _init_session() -> None:
    """
    Inicializa el estado de sesión si es la primera ejecución.

    Si ``session_id`` ya existe en ``st.session_state``, la función retorna
    sin modificar ninguna clave, garantizando idempotencia.
    """
    if "session_id" in st.session_state:
        return

    _cleanup_old_sessions(_SESSION_BASE_DIR)
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.session_dir = _SESSION_BASE_DIR / st.session_state.session_id
    st.session_state.session_dir.mkdir(parents=True, exist_ok=True)
    st.session_state.scrape_result = None
    st.session_state.generated_content = None
    st.session_state.zip_bytes = None
    st.session_state.zip_hash = None
    st.session_state.offsets = {"post": 0.4, "historia": 0.5, "google": 0.25}
    st.session_state.authenticated = False
    st.session_state.openai_api_key = None  # None = usa OPENAI_API_KEY de secrets/env
    st.session_state.inpainted_finals = {"post": None, "historia": None, "google": None}
    st.session_state.inpaint_pending = {"post": None, "historia": None, "google": None}
    st.session_state.inpaint_history = {"post": [], "historia": [], "google": []}
