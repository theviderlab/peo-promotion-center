"""Gestión de cookies para autenticación persistente."""

import hashlib
import hmac
from datetime import datetime, timedelta

import extra_streamlit_components as stx

_REMEMBER_ME_DAYS = 30
_COOKIE_NAME = "peo_auth_token"
_HMAC_MSG = b"peo_auth_verified"
_COOKIE_MANAGER_KEY = "peo_cookie_manager"


def get_cookie_manager() -> stx.CookieManager:
    """
    Retorna una instancia del CookieManager.

    Usa una clave fija para que Streamlit reutilice el mismo componente
    durante toda la sesión de la página.

    Returns:
        Instancia de CookieManager lista para usar.
    """
    return stx.CookieManager(key=_COOKIE_MANAGER_KEY)


def _generate_auth_token(app_password: str) -> str:
    """
    Genera un token HMAC-SHA256 derivado de la contraseña de la aplicación.

    El token nunca contiene la contraseña en texto plano. Si APP_PASSWORD
    cambia, todos los tokens previamente guardados se invalidan.

    Args:
        app_password: Contraseña de la aplicación.

    Returns:
        Hexdigest del HMAC-SHA256.
    """
    return hmac.new(
        app_password.encode(),
        _HMAC_MSG,
        hashlib.sha256,
    ).hexdigest()


def _verify_auth_token(token: str, app_password: str) -> bool:
    """
    Verifica que el token corresponde a la contraseña actual.

    Usa `hmac.compare_digest` para evitar timing attacks.

    Args:
        token: Token extraído de la cookie del navegador.
        app_password: Contraseña actual de la aplicación.

    Returns:
        True si el token es válido, False en caso contrario.
    """
    expected = _generate_auth_token(app_password)
    return hmac.compare_digest(token, expected)


def is_authenticated_by_cookie(cm: stx.CookieManager, app_password: str) -> bool:
    """
    Verifica si existe una cookie de autenticación válida en el navegador.

    Args:
        cm: Instancia del CookieManager.
        app_password: Contraseña actual de la aplicación.

    Returns:
        True si la cookie existe y el token es válido.
    """
    token = cm.get(_COOKIE_NAME)
    if not token:
        return False
    return _verify_auth_token(token, app_password)


def save_auth_cookie(cm: stx.CookieManager, app_password: str) -> None:
    """
    Guarda la cookie de autenticación con expiración de _REMEMBER_ME_DAYS días.

    Args:
        cm: Instancia del CookieManager.
        app_password: Contraseña de la aplicación para derivar el token.
    """
    token = _generate_auth_token(app_password)
    cm.set(
        _COOKIE_NAME,
        token,
        expires_at=datetime.now() + timedelta(days=_REMEMBER_ME_DAYS),
    )


def delete_auth_cookie(cm: stx.CookieManager) -> None:
    """
    Elimina la cookie de autenticación del navegador.

    Args:
        cm: Instancia del CookieManager.
    """
    cm.delete(_COOKIE_NAME)
