"""Integration tests para el módulo content_generator (requiere OPENAI_API_KEY en .env)."""

import os

import pytest
from dotenv import load_dotenv

load_dotenv()

_SAMPLE_METADATA = {
    "nombre_paquete": "Riviera Maya Todo Incluido",
    "frecuencia": "Salidas los lunes y jueves",
    "destinos": "Playa del Carmen, Tulum",
    "precio": "$35,000 MXN por persona",
    "duracion": "5 noches / 6 días",
    "incluye": "Vuelo redondo, hotel todo incluido, traslados aeropuerto",
    "no_incluye": "Tours opcionales, visa (si aplica)",
}


@pytest.fixture(autouse=True)
def require_api_key():
    """Salta todos los tests de integración si no hay OPENAI_API_KEY configurada."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY no configurada en .env")


def test_generate_content_real_api():
    """Verifica que generate_content retorna contenido válido con la API real de OpenAI."""
    from peo_promotion_center.backend.content_generator import generate_content
    from peo_promotion_center.backend.models import GeneratedContent

    result = generate_content(_SAMPLE_METADATA)

    assert isinstance(result, GeneratedContent)
    assert result.copy_redes and len(result.copy_redes) > 0
    assert len(result.asuntos_mailing) == 3
    assert all(subject for subject in result.asuntos_mailing)
