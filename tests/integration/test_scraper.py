"""Pruebas de integración para el módulo scraper.

Requiere las siguientes variables en el archivo .env:
  OPE_USUARIO   — usuario de operadorapuntadeleste.com
  OPE_CLAVE     — contraseña
  OPE_TEST_URL  — URL de un paquete real para testear, p. ej.:
                  https://www.operadorapuntadeleste.com/paquetes/nombre-del-paquete/
"""

import os

import pytest
from dotenv import load_dotenv

from peo_promotion_center.backend.scraper import scrape_package

load_dotenv()

_HAS_CREDENTIALS = bool(os.getenv("OPE_USUARIO") and os.getenv("OPE_CLAVE"))
_TEST_URL = os.getenv("OPE_TEST_URL", "")
_SKIP_REASON = "Requiere OPE_USUARIO, OPE_CLAVE y OPE_TEST_URL en .env"


@pytest.mark.skipif(not _HAS_CREDENTIALS or not _TEST_URL, reason=_SKIP_REASON)
def test_scrape_package_downloads_image(tmp_path):
    """La imagen descargada existe en disco y tiene tamaño mayor a cero."""
    result = scrape_package(_TEST_URL, tmp_path)

    assert result.image_path.exists(), "La imagen no existe en disco"
    assert result.image_path.stat().st_size > 0, "La imagen descargada está vacía"


@pytest.mark.skipif(not _HAS_CREDENTIALS or not _TEST_URL, reason=_SKIP_REASON)
def test_scrape_package_nombre_paquete_not_empty(tmp_path):
    """El ScrapeResult contiene al menos nombre_paquete y slug no vacíos."""
    result = scrape_package(_TEST_URL, tmp_path)

    assert result.nombre_paquete != "", "nombre_paquete no debe estar vacío"
    assert result.slug != "", "slug no debe estar vacío"


@pytest.mark.skipif(not _HAS_CREDENTIALS or not _TEST_URL, reason=_SKIP_REASON)
def test_scrape_result_fields_never_none(tmp_path):
    """Ningún campo del ScrapeResult es None."""
    result = scrape_package(_TEST_URL, tmp_path)

    str_fields = [
        "nombre_paquete",
        "descripcion",
        "destinos",
        "precio",
        "duracion",
        "incluye",
        "no_incluye",
        "slug",
    ]
    for field in str_fields:
        value = getattr(result, field)
        assert value is not None, f"Campo {field!r} es None"
        assert isinstance(value, str), f"Campo {field!r} no es str: {type(value)}"
