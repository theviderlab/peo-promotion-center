"""Pruebas de integración end-to-end del flujo completo.

Requiere las siguientes variables en el archivo .env:
  OPE_USUARIO   — usuario de operadorapuntadeleste.com
  OPE_CLAVE     — contraseña
  OPENAI_API_KEY — clave de la API de OpenAI
  OPE_TEST_URL  — URL de un paquete real, p. ej.:
                  https://www.operadorapuntadeleste.com/paquetes/nombre-del-paquete/
"""

import os
import zipfile
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv()

_HAS_CREDENTIALS = bool(os.getenv("OPE_USUARIO") and os.getenv("OPENAI_API_KEY"))
_TEST_URL = os.getenv("OPE_TEST_URL", "")
_SKIP_REASON = "Requiere OPE_USUARIO, OPE_CLAVE, OPENAI_API_KEY y OPE_TEST_URL en .env"

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def require_credentials():
    """Salta todos los tests si las credenciales no están disponibles."""
    if not _HAS_CREDENTIALS or not _TEST_URL:
        pytest.skip(_SKIP_REASON)


@pytest.fixture()
def session_dir(tmp_path: Path) -> Path:
    """Directorio de sesión temporal; se limpia automáticamente al finalizar."""
    sdir = tmp_path / "session"
    sdir.mkdir()
    return sdir


def test_full_pipeline(session_dir: Path) -> None:
    """
    Ejercita el flujo completo: scraping → procesado de imagen → generación IA → ZIP.

    1. Autentica y descarga el paquete desde la URL real.
    2. Genera los tres formatos PNG con offsets por defecto.
    3. Genera copy para redes sociales y 3 asuntos de mailing con OpenAI.
    4. Verifica dimensiones exactas de los PNG (POST 1080×1350, HISTORIA 1080×1920,
       GOOGLE 960×640).
    5. Verifica que el copy y los asuntos son no vacíos.
    6. Construye el ZIP y verifica que contiene los 5 archivos esperados.
    """
    from peo_promotion_center.backend.content_generator import generate_content
    from peo_promotion_center.backend.image_processor import (
        ALL_FORMATS,
        process_all_formats,
    )
    from peo_promotion_center.backend.scraper import scrape_package
    from peo_promotion_center.frontend.zip_builder import build_zip

    # --- Paso 1: Scraping ---
    scrape_result = scrape_package(_TEST_URL, session_dir)
    assert scrape_result.image_path.exists(), "La imagen descargada no existe en disco"
    assert scrape_result.image_path.stat().st_size > 0, (
        "La imagen descargada está vacía"
    )
    assert scrape_result.nombre_paquete, "nombre_paquete no debe estar vacío"
    assert scrape_result.slug, "slug no debe estar vacío"

    # --- Paso 2: Procesado de imagen ---
    offsets: dict[str, float] = {}
    png_paths = process_all_formats(
        source_path=scrape_result.image_path,
        slug=scrape_result.slug,
        offsets=offsets,
        output_dir=session_dir,
    )

    expected_dims = {
        "post": (1080, 1350),
        "historia": (1080, 1920),
        "google": (960, 640),
    }

    assert set(png_paths.keys()) == set(fmt.slug for fmt in ALL_FORMATS), (
        "El diccionario de PNGs debe contener los tres formatos"
    )

    from PIL import Image

    for fmt_slug, png_path in png_paths.items():
        assert png_path.exists(), f"El archivo PNG '{fmt_slug}' no existe"
        with Image.open(png_path) as img:
            assert img.size == expected_dims[fmt_slug], (
                f"Dimensiones incorrectas para '{fmt_slug}': "
                f"esperado {expected_dims[fmt_slug]}, obtenido {img.size}"
            )

    # --- Paso 3: Generación de contenido IA ---
    metadata = {
        "nombre_paquete": scrape_result.nombre_paquete,
        "frecuencia": scrape_result.frecuencia,
        "destinos": scrape_result.destinos,
        "precio": scrape_result.precio,
        "duracion": scrape_result.duracion,
        "incluye": scrape_result.incluye,
        "no_incluye": scrape_result.no_incluye,
    }
    generated = generate_content(metadata)

    assert generated.copy_redes, "copy_redes no debe estar vacío"
    assert len(generated.asuntos_mailing) == 3, "Deben generarse exactamente 3 asuntos"
    assert all(s for s in generated.asuntos_mailing), "Ningún asunto debe estar vacío"

    # --- Paso 4: Construcción del ZIP ---
    zip_bytes = build_zip(
        source_path=scrape_result.image_path,
        slug=scrape_result.slug,
        offsets=offsets,
        copy_redes=generated.copy_redes,
        asuntos_mailing=generated.asuntos_mailing,
        output_dir=session_dir,
    )

    assert isinstance(zip_bytes, bytes), "build_zip debe retornar bytes"
    assert len(zip_bytes) > 0, "El ZIP no debe estar vacío"

    with zipfile.ZipFile(
        zip_bytes if False else __import__("io").BytesIO(zip_bytes)
    ) as zf:
        names = zf.namelist()
        assert len(names) == 5, f"El ZIP debe contener 5 archivos, encontrados: {names}"
        assert "copy_redes.txt" in names, "Falta copy_redes.txt en el ZIP"
        assert "asuntos_mailing.txt" in names, "Falta asuntos_mailing.txt en el ZIP"
        png_names = [n for n in names if n.endswith(".png")]
        assert len(png_names) == 3, (
            f"El ZIP debe contener 3 PNG, encontrados: {png_names}"
        )
