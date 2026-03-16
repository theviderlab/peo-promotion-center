"""Pruebas unitarias para el módulo scraper."""

import pytest
import requests
from unittest.mock import Mock

from peo_promotion_center.backend.exceptions import (
    AuthenticationError,
    ImageNotFoundError,
    ScraperError,
)
from peo_promotion_center.backend.scraper import (
    _validate_ope_url,
    download_image,
    extract_metadata,
    find_image_url,
    login,
)

_BASE_URL = "https://example.com/paquete/"


# ---------------------------------------------------------------------------
# find_image_url
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "html,expected",
    [
        (
            '<div id="collapseMatProImg"><img src="/img/promo.jpg"></div>',
            "https://example.com/img/promo.jpg",
        ),
        (
            '<img src="/Uploads/Material_Promocional/Thumb/img.jpg">',
            "https://example.com/Uploads/Material_Promocional/Thumb/img.jpg",
        ),
        (
            '<a href="/create_image_collage_new.php?id=1">link</a>',
            "https://example.com/create_image_collage_new.php?id=1",
        ),
        (
            '<meta property="og:image" content="https://cdn.example.com/og.jpg">',
            "https://cdn.example.com/og.jpg",
        ),
        (
            '<meta name="twitter:image" content="https://cdn.example.com/tw.jpg">',
            "https://cdn.example.com/tw.jpg",
        ),
    ],
    ids=["collapseMatProImg", "thumb_src", "collage_link", "og_image", "twitter_image"],
)
def test_find_image_url_patterns(html, expected):
    """Verifica que cada patrón de prioridad detecta la imagen correctamente."""
    assert find_image_url(html, _BASE_URL) == expected


def test_find_image_url_raises_when_no_match():
    """ImageNotFoundError cuando ningún patrón encuentra imagen."""
    with pytest.raises(ImageNotFoundError):
        find_image_url("<p>No hay imagen.</p>", _BASE_URL)


def test_find_image_url_priority_collapseMatProImg_over_thumb():
    """El patrón collapseMatProImg tiene prioridad sobre Thumb en src."""
    html = """
    <div id="collapseMatProImg"><img src="/img/preferred.jpg"></div>
    <img src="/Uploads/Material_Promocional/Thumb/other.jpg">
    """
    result = find_image_url(html, _BASE_URL)
    assert "preferred.jpg" in result


# ---------------------------------------------------------------------------
# extract_metadata
# ---------------------------------------------------------------------------

_FULL_HTML = """
<html><head><title>Paquete Roma</title></head><body>
<h1>Paquete Roma 7 Noches</h1>
<div class="descripcion">Viaje increíble a Roma.</div>
<dl>
  <dt>Destinos</dt><dd>Roma, Florencia</dd>
  <dt>Precio</dt><dd>USD 1,200</dd>
  <dt>Duración</dt><dd>7 días</dd>
  <dt>Incluye</dt><dd>Hotel y desayuno</dd>
  <dt>No incluye</dt><dd>Vuelos internacionales</dd>
</dl>
</body></html>
"""


def test_extract_metadata_full_html():
    """Extrae correctamente todos los campos cuando están presentes."""
    meta = extract_metadata(_FULL_HTML)

    assert meta["nombre_paquete"] == "Paquete Roma 7 Noches"
    assert meta["descripcion"] == "Viaje increíble a Roma."
    assert meta["destinos"] == "Roma, Florencia"
    assert meta["precio"] == "USD 1,200"
    assert meta["duracion"] == "7 días"
    assert meta["incluye"] == "Hotel y desayuno"
    assert meta["no_incluye"] == "Vuelos internacionales"


def test_extract_metadata_absent_fields_return_empty_string():
    """Los campos ausentes devuelven '' y nunca None."""
    meta = extract_metadata("<html><body><h1>Solo título</h1></body></html>")

    assert meta["nombre_paquete"] == "Solo título"
    for field in [
        "descripcion",
        "destinos",
        "precio",
        "duracion",
        "incluye",
        "no_incluye",
    ]:
        assert meta[field] == "", (
            f"Campo {field!r} debería ser '' pero fue {meta[field]!r}"
        )
        assert meta[field] is not None, f"Campo {field!r} no debe ser None"


def test_extract_metadata_falls_back_to_title():
    """nombre_paquete usa <title> si no hay <h1>."""
    html = "<html><head><title>Paquete Caribe</title></head><body></body></html>"
    meta = extract_metadata(html)
    assert meta["nombre_paquete"] == "Paquete Caribe"


# ---------------------------------------------------------------------------
# download_image
# ---------------------------------------------------------------------------


def test_download_image_tries_a4_first(tmp_path):
    """Cuando la URL tiene /Thumb/, intenta /A4/ como primera opción."""
    session = Mock()
    mock_resp = Mock()
    mock_resp.content = b"hq_image_data"
    session.get.return_value = mock_resp

    thumb_url = "https://example.com/Uploads/Material_Promocional/Thumb/img.jpg"
    result = download_image(session, thumb_url, tmp_path)

    expected_a4 = "https://example.com/Uploads/Material_Promocional/A4/img.jpg"
    session.get.assert_called_once_with(expected_a4)
    assert result.read_bytes() == b"hq_image_data"


def test_download_image_falls_back_on_http_error(tmp_path):
    """Si /A4/ falla con HTTP error, descarga la URL /Thumb/ original."""
    session = Mock()

    a4_resp = Mock()
    a4_resp.raise_for_status.side_effect = requests.HTTPError("404 Not Found")

    orig_resp = Mock()
    orig_resp.content = b"original_image_data"

    session.get.side_effect = [a4_resp, orig_resp]

    thumb_url = "https://example.com/Uploads/Material_Promocional/Thumb/img.jpg"
    result = download_image(session, thumb_url, tmp_path)

    assert session.get.call_count == 2
    assert result.read_bytes() == b"original_image_data"


def test_download_image_no_thumb_url_uses_single_request(tmp_path):
    """Sin /Thumb/ en la URL, solo realiza una petición a la URL original."""
    session = Mock()
    mock_resp = Mock()
    mock_resp.content = b"direct_image"
    session.get.return_value = mock_resp

    url = "https://example.com/img/direct.jpg"
    download_image(session, url, tmp_path)

    session.get.assert_called_once_with(url)


def test_download_image_saves_file(tmp_path):
    """El archivo descargado existe en disco con el contenido correcto."""
    session = Mock()
    mock_resp = Mock()
    mock_resp.content = b"file_bytes"
    session.get.return_value = mock_resp

    url = "https://example.com/img/foto.jpg"
    result = download_image(session, url, tmp_path)

    assert result.exists()
    assert result.name == "foto.jpg"
    assert result.read_bytes() == b"file_bytes"


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------


def test_login_raises_authentication_error_on_error_response():
    """AuthenticationError cuando el servidor devuelve 'error'."""
    session = Mock()
    bad_resp = Mock()
    bad_resp.text = "error"
    session.post.return_value = bad_resp

    with pytest.raises(AuthenticationError):
        login(session, "user", "wrong_password")


def test_login_follows_redirect_when_body_is_url():
    """Sigue la URL de redirección devuelta por login.asp."""
    session = Mock()
    ok_resp = Mock()
    ok_resp.text = "/mi-cuenta/"
    session.post.return_value = ok_resp

    login(session, "user", "pass")

    # GET /acceso/ + GET redirect URL
    assert session.get.call_count == 2


def test_login_no_redirect_when_body_empty():
    """No hace redirección si el cuerpo de la respuesta está vacío."""
    session = Mock()
    ok_resp = Mock()
    ok_resp.text = ""
    session.post.return_value = ok_resp

    login(session, "user", "pass")

    # Only GET /acceso/
    assert session.get.call_count == 1


# ---------------------------------------------------------------------------
# _validate_ope_url
# ---------------------------------------------------------------------------


def test_validate_ope_url_accepts_valid_https():
    """URL HTTPS de operadorapuntadeleste.com es aceptada sin excepción."""
    _validate_ope_url("https://www.operadorapuntadeleste.com/paquetes/test/")


def test_validate_ope_url_accepts_bare_domain():
    """Acepta también el dominio sin www."""
    _validate_ope_url("https://operadorapuntadeleste.com/paquetes/test/")


def test_validate_ope_url_rejects_http():
    """URL con esquema HTTP es rechazada."""
    with pytest.raises(ScraperError, match="HTTPS"):
        _validate_ope_url("http://www.operadorapuntadeleste.com/paquetes/test/")


def test_validate_ope_url_rejects_external_domain():
    """URL de dominio externo es rechazada."""
    with pytest.raises(ScraperError, match="operadorapuntadeleste.com"):
        _validate_ope_url("https://attacker.com/evil")


def test_validate_ope_url_rejects_localhost():
    """URL apuntando a localhost es rechazada."""
    with pytest.raises(ScraperError):
        _validate_ope_url("https://localhost/admin")


def test_validate_ope_url_rejects_internal_ip():
    """URL con IP privada es rechazada (SSRF)."""
    with pytest.raises(ScraperError):
        _validate_ope_url("https://192.168.1.1/router")


# ---------------------------------------------------------------------------
# login — redirect restringido al dominio
# ---------------------------------------------------------------------------


def test_login_ignores_redirect_to_external_domain():
    """El redirect de login no se sigue si apunta a un dominio externo."""
    session = Mock()
    ok_resp = Mock()
    ok_resp.text = "https://attacker.com/steal"
    session.post.return_value = ok_resp

    login(session, "user", "pass")

    # Solo GET /acceso/, no se sigue el redirect externo
    assert session.get.call_count == 1


# ---------------------------------------------------------------------------
# download_image — sanitización de filename
# ---------------------------------------------------------------------------


def test_download_image_sanitizes_filename_with_path_traversal(tmp_path):
    """Filename con path traversal es sanitizado antes de escribir a disco."""
    session = Mock()
    mock_resp = Mock()
    mock_resp.content = b"data"
    session.get.return_value = mock_resp

    url = "https://www.operadorapuntadeleste.com/img/%2F..%2Fetc%2Fpasswd"
    result = download_image(session, url, tmp_path)

    # El nombre resultante no debe contener separadores de directorio
    assert "/" not in result.name
    assert "\\" not in result.name
    assert result.parent == tmp_path


def test_download_image_sanitizes_special_chars(tmp_path):
    """Caracteres especiales en el filename son reemplazados por guiones bajos."""
    session = Mock()
    mock_resp = Mock()
    mock_resp.content = b"data"
    session.get.return_value = mock_resp

    url = "https://www.operadorapuntadeleste.com/img/foto con espacios!.jpg"
    result = download_image(session, url, tmp_path)

    assert " " not in result.name
    assert "!" not in result.name


# ---------------------------------------------------------------------------
# scrape_package — credenciales vacías
# ---------------------------------------------------------------------------


def test_scrape_package_raises_on_empty_credentials(monkeypatch):
    """scrape_package lanza AuthenticationError si las credenciales están vacías."""
    from peo_promotion_center.backend import scraper

    monkeypatch.setattr(scraper, "load_dotenv", lambda: None)
    monkeypatch.setenv("OPE_USUARIO", "")
    monkeypatch.setenv("OPE_CLAVE", "")

    with pytest.raises(AuthenticationError, match="OPE_USUARIO"):
        scraper.scrape_package("https://www.operadorapuntadeleste.com/paquetes/test/", __import__("pathlib").Path("/tmp"))


def test_scrape_package_raises_on_external_url(monkeypatch):
    """scrape_package lanza ScraperError si la URL no pertenece al dominio OPE."""
    from peo_promotion_center.backend import scraper

    monkeypatch.setattr(scraper, "load_dotenv", lambda: None)
    monkeypatch.setenv("OPE_USUARIO", "user")
    monkeypatch.setenv("OPE_CLAVE", "clave")

    with pytest.raises(ScraperError, match="rechazada"):
        scraper.scrape_package("https://evil.com/harvest", __import__("pathlib").Path("/tmp"))
