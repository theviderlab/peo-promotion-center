"""Pruebas unitarias para cookies.py y render_auth_gate."""

import hashlib
import hmac
from datetime import datetime
from unittest.mock import MagicMock

from peo_promotion_center.frontend.cookies import (
    _COOKIE_NAME,
    _HMAC_MSG,
    _REMEMBER_ME_DAYS,
    _generate_auth_token,
    _verify_auth_token,
    delete_auth_cookie,
    is_authenticated_by_cookie,
    save_auth_cookie,
)


# ---------------------------------------------------------------------------
# Helpers compartidos
# ---------------------------------------------------------------------------


class FakeSessionState(dict):
    """Simula st.session_state: soporta acceso por atributo y el operador 'in'."""

    def __getattr__(self, key: str):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key: str, value) -> None:
        self[key] = value


# ---------------------------------------------------------------------------
# _generate_auth_token
# ---------------------------------------------------------------------------


def test_generate_auth_token_is_deterministic():
    """El mismo password siempre produce el mismo token."""
    assert _generate_auth_token("my_password") == _generate_auth_token("my_password")


def test_generate_auth_token_differs_for_different_passwords():
    """Distintos passwords producen tokens distintos."""
    assert _generate_auth_token("password_a") != _generate_auth_token("password_b")


def test_generate_auth_token_matches_expected_hmac():
    """El token coincide con el HMAC-SHA256 esperado."""
    password = "test_password"
    expected = hmac.new(password.encode(), _HMAC_MSG, hashlib.sha256).hexdigest()
    assert _generate_auth_token(password) == expected


# ---------------------------------------------------------------------------
# _verify_auth_token
# ---------------------------------------------------------------------------


def test_verify_auth_token_returns_true_for_valid_token():
    password = "secure_password"
    token = _generate_auth_token(password)
    assert _verify_auth_token(token, password) is True


def test_verify_auth_token_returns_false_for_tampered_token():
    assert _verify_auth_token("tampered_token", "secure_password") is False


def test_verify_auth_token_returns_false_when_password_changes():
    """Si APP_PASSWORD cambia, el token guardado ya no es válido."""
    token = _generate_auth_token("old_password")
    assert _verify_auth_token(token, "new_password") is False


# ---------------------------------------------------------------------------
# is_authenticated_by_cookie
# ---------------------------------------------------------------------------


def test_is_authenticated_by_cookie_returns_true_for_valid_token():
    password = "app_password"
    cm = MagicMock()
    cm.get.return_value = _generate_auth_token(password)

    assert is_authenticated_by_cookie(cm, password) is True
    cm.get.assert_called_once_with(_COOKIE_NAME)


def test_is_authenticated_by_cookie_returns_false_for_invalid_token():
    cm = MagicMock()
    cm.get.return_value = "tampered_token"

    assert is_authenticated_by_cookie(cm, "app_password") is False


def test_is_authenticated_by_cookie_returns_false_when_no_cookie():
    cm = MagicMock()
    cm.get.return_value = None

    assert is_authenticated_by_cookie(cm, "app_password") is False


def test_is_authenticated_by_cookie_returns_false_for_empty_string():
    cm = MagicMock()
    cm.get.return_value = ""

    assert is_authenticated_by_cookie(cm, "app_password") is False


# ---------------------------------------------------------------------------
# save_auth_cookie
# ---------------------------------------------------------------------------


def test_save_auth_cookie_calls_set_with_correct_cookie_name_and_token():
    password = "my_secret"
    cm = MagicMock()

    save_auth_cookie(cm, password)

    assert cm.set.call_count == 1
    call_args = cm.set.call_args
    assert call_args[0][0] == _COOKIE_NAME
    assert call_args[0][1] == _generate_auth_token(password)


def test_save_auth_cookie_sets_expiry_at_30_days():
    cm = MagicMock()
    before = datetime.now()

    save_auth_cookie(cm, "password")

    call_args = cm.set.call_args
    expiry: datetime = call_args[1]["expires_at"]
    delta = expiry - before
    assert delta.days == _REMEMBER_ME_DAYS


# ---------------------------------------------------------------------------
# delete_auth_cookie
# ---------------------------------------------------------------------------


def test_delete_auth_cookie_calls_delete_with_correct_name():
    cm = MagicMock()
    delete_auth_cookie(cm)
    cm.delete.assert_called_once_with(_COOKIE_NAME)


# ---------------------------------------------------------------------------
# render_auth_gate — auto-autenticación por cookie
# ---------------------------------------------------------------------------


def test_render_auth_gate_auto_authenticates_with_valid_cookie(monkeypatch):
    """Si la cookie es válida, marca authenticated=True y llama st.rerun()."""
    fake_state = FakeSessionState()
    mock_st = MagicMock()
    mock_st.session_state = fake_state
    mock_st.tabs.return_value = [MagicMock(), MagicMock()]
    cm = MagicMock()

    monkeypatch.setattr("peo_promotion_center.frontend.auth.st", mock_st)
    monkeypatch.setattr(
        "peo_promotion_center.frontend.auth.is_authenticated_by_cookie",
        lambda _cm, _pw: True,
    )
    monkeypatch.setattr(
        "peo_promotion_center.frontend.auth._get_app_password",
        lambda: "test_password",
    )

    from peo_promotion_center.frontend.auth import render_auth_gate

    render_auth_gate(cm)

    assert fake_state.get("authenticated") is True
    mock_st.rerun.assert_called()


def test_render_auth_gate_shows_form_when_no_valid_cookie(monkeypatch):
    """Sin cookie válida, renderiza los tabs con el formulario."""
    fake_state = FakeSessionState()
    mock_st = MagicMock()
    mock_st.session_state = fake_state
    mock_st.tabs.return_value = [MagicMock(), MagicMock()]
    cm = MagicMock()

    monkeypatch.setattr("peo_promotion_center.frontend.auth.st", mock_st)
    monkeypatch.setattr(
        "peo_promotion_center.frontend.auth.is_authenticated_by_cookie",
        lambda _cm, _pw: False,
    )
    monkeypatch.setattr(
        "peo_promotion_center.frontend.auth._get_app_password",
        lambda: "test_password",
    )

    from peo_promotion_center.frontend.auth import render_auth_gate

    render_auth_gate(cm)

    mock_st.tabs.assert_called_once()


def test_render_auth_gate_saves_cookie_on_login_with_remember_me(monkeypatch):
    """Login exitoso con remember_me=True guarda la cookie."""
    fake_state = FakeSessionState()
    mock_st = MagicMock()
    mock_st.session_state = fake_state
    mock_st.tabs.return_value = [MagicMock(), MagicMock()]
    mock_st.text_input.return_value = "correct_password"
    mock_st.checkbox.return_value = True
    mock_st.form_submit_button.return_value = True
    cm = MagicMock()
    save_cookie_mock = MagicMock()

    monkeypatch.setattr("peo_promotion_center.frontend.auth.st", mock_st)
    monkeypatch.setattr(
        "peo_promotion_center.frontend.auth.is_authenticated_by_cookie",
        lambda _cm, _pw: False,
    )
    monkeypatch.setattr(
        "peo_promotion_center.frontend.auth._get_app_password",
        lambda: "correct_password",
    )
    monkeypatch.setattr(
        "peo_promotion_center.frontend.auth.save_auth_cookie",
        save_cookie_mock,
    )

    from peo_promotion_center.frontend.auth import render_auth_gate

    render_auth_gate(cm)

    assert fake_state.get("authenticated") is True
    save_cookie_mock.assert_called_once_with(cm, "correct_password")


def test_render_auth_gate_does_not_save_cookie_without_remember_me(monkeypatch):
    """Login exitoso con remember_me=False no guarda cookie."""
    fake_state = FakeSessionState()
    mock_st = MagicMock()
    mock_st.session_state = fake_state
    mock_st.tabs.return_value = [MagicMock(), MagicMock()]
    mock_st.text_input.return_value = "correct_password"
    mock_st.checkbox.return_value = False
    mock_st.form_submit_button.return_value = True
    cm = MagicMock()
    save_cookie_mock = MagicMock()

    monkeypatch.setattr("peo_promotion_center.frontend.auth.st", mock_st)
    monkeypatch.setattr(
        "peo_promotion_center.frontend.auth.is_authenticated_by_cookie",
        lambda _cm, _pw: False,
    )
    monkeypatch.setattr(
        "peo_promotion_center.frontend.auth._get_app_password",
        lambda: "correct_password",
    )
    monkeypatch.setattr(
        "peo_promotion_center.frontend.auth.save_auth_cookie",
        save_cookie_mock,
    )

    from peo_promotion_center.frontend.auth import render_auth_gate

    render_auth_gate(cm)

    assert fake_state.get("authenticated") is True
    save_cookie_mock.assert_not_called()
