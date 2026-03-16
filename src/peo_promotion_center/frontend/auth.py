"""Módulo de autenticación para la aplicación Streamlit."""

import os

import extra_streamlit_components as stx
import streamlit as st
from dotenv import load_dotenv

from peo_promotion_center.frontend.cookies import is_authenticated_by_cookie, save_auth_cookie

_MIN_API_KEY_LENGTH = 20


def _get_app_password() -> str | None:
    """
    Retorna el valor de APP_PASSWORD desde st.secrets o la variable de entorno.

    En Streamlit Cloud usa st.secrets. En local usa el archivo .env via os.getenv.

    Returns:
        La contraseña de la aplicación, o None si no está configurada en ningún lado.
    """
    try:
        secret = st.secrets.get("APP_PASSWORD", None)
        if secret:
            return secret
    except Exception:
        pass
    load_dotenv()
    return os.getenv("APP_PASSWORD") or None


def render_auth_gate(cm: stx.CookieManager) -> None:
    """
    Renderiza el gate de autenticación.

    Si APP_PASSWORD no está configurado (entorno local), autentica automáticamente
    sin mostrar ningún formulario.

    Si existe una cookie de autenticación válida, autentica de forma transparente
    sin solicitar contraseña (comportamiento "Recuérdame").

    Presenta dos tabs:
    - "Acceso con contraseña": para el dueño de la app, usa la OPENAI_API_KEY
      configurada en secrets/env.
    - "Invitado": el usuario ingresa su propia OpenAI API key, que se usa
      en lugar de la del dueño y no se persiste entre sesiones.
    """
    app_password = _get_app_password()

    if not app_password:
        st.session_state.authenticated = True
        return

    if is_authenticated_by_cookie(cm, app_password):
        st.session_state.authenticated = True
        st.rerun()

    st.title("PEO Promotion Center")
    st.subheader("Acceso")

    tab_owner, tab_guest = st.tabs(["Acceso con contraseña", "Invitado"])

    with tab_owner:
        with st.form("login_form"):
            pwd = st.text_input("Contraseña", type="password")
            remember_me = st.checkbox("Recuérdame por 30 días")
            submitted = st.form_submit_button("Ingresar")

        if submitted:
            if pwd == app_password:
                st.session_state.authenticated = True
                st.session_state.openai_api_key = None
                if remember_me:
                    save_auth_cookie(cm, app_password)
                st.rerun()
            else:
                st.error("Contraseña incorrecta.")

    with tab_guest:
        st.info(
            "Ingresá tu propia API key de OpenAI. "
            "No se almacena entre sesiones: cada vez que cerrás el navegador debés volver a ingresarla."
        )
        with st.form("guest_form"):
            guest_key = st.text_input(
                "OpenAI API Key",
                type="password",
                placeholder="sk-...",
            )
            submitted_guest = st.form_submit_button("Continuar como invitado")

        if submitted_guest:
            if guest_key.startswith("sk-") and len(guest_key) > _MIN_API_KEY_LENGTH:
                st.session_state.authenticated = True
                st.session_state.openai_api_key = guest_key
                st.rerun()
            else:
                st.error("API key inválida. Debe comenzar con 'sk-' y tener más de 20 caracteres.")
