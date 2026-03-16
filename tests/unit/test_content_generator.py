"""Unit tests para el módulo content_generator."""

import pytest
from unittest.mock import Mock, patch

from peo_promotion_center.backend.content_generator import (
    generate_content,
    generate_mailing_subjects,
    generate_preview_texts,
    generate_social_copy,
)
from peo_promotion_center.backend.models import GeneratedContent

_SAMPLE_METADATA = {
    "nombre_paquete": "Cancún Mágico",
    "descripcion": "Paquete todo incluido al Caribe mexicano",
    "destinos": "Cancún, Playa del Carmen",
    "precio": "$25,000 MXN",
    "duracion": "7 noches / 8 días",
    "incluye": "Vuelo, hotel, traslados",
    "no_incluye": "Tours opcionales",
}


def test_load_prompt_exists(tmp_path, monkeypatch):
    """load_prompt lee correctamente un archivo existente."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "test_prompt.txt").write_text(
        "Hola {nombre_paquete}", encoding="utf-8"
    )

    import peo_promotion_center.backend.content_generator as cg

    monkeypatch.setattr(cg, "_PROJECT_ROOT", tmp_path)

    result = cg.load_prompt("test_prompt")
    assert result == "Hola {nombre_paquete}"


def test_load_prompt_missing(tmp_path, monkeypatch):
    """load_prompt lanza FileNotFoundError si el prompt no existe."""
    import peo_promotion_center.backend.content_generator as cg

    monkeypatch.setattr(cg, "_PROJECT_ROOT", tmp_path)

    with pytest.raises(FileNotFoundError, match="Archivo de prompt no encontrado"):
        cg.load_prompt("inexistente")


def test_generate_social_copy_calls_llm():
    """generate_social_copy invoca al LLM y retorna el contenido de la respuesta."""
    mock_llm = Mock()
    mock_llm.invoke.return_value = Mock(content="¡Descubre el paraíso!")

    with patch(
        "peo_promotion_center.backend.content_generator.load_prompt",
        return_value="Paquete: {nombre_paquete}",
    ):
        result = generate_social_copy(_SAMPLE_METADATA, mock_llm)

    assert result == "¡Descubre el paraíso!"
    mock_llm.invoke.assert_called_once()


def test_generate_social_copy_substitutes_placeholders():
    """generate_social_copy sustituye los placeholders antes de enviar al LLM."""
    mock_llm = Mock()
    mock_llm.invoke.return_value = Mock(content="copy generado")

    with patch(
        "peo_promotion_center.backend.content_generator.load_prompt",
        return_value="Paquete: {nombre_paquete}",
    ):
        generate_social_copy(_SAMPLE_METADATA, mock_llm)

    call_arg = mock_llm.invoke.call_args[0][0]
    # call_arg es un ChatPromptValue; convertir a string para inspeccionar el contenido
    call_arg_str = str(call_arg)
    assert "Cancún Mágico" in call_arg_str
    assert "{nombre_paquete}" not in call_arg_str


def test_generate_mailing_subjects_3_lines():
    """generate_mailing_subjects retorna lista de 3 con respuesta de 3 asuntos."""
    mock_llm = Mock()
    mock_llm.invoke.return_value = Mock(
        content="1. Asunto uno\n2. Asunto dos\n3. Asunto tres"
    )

    with patch(
        "peo_promotion_center.backend.content_generator.load_prompt",
        return_value="Template {nombre_paquete}",
    ):
        result = generate_mailing_subjects(_SAMPLE_METADATA, mock_llm)

    assert result == ["Asunto uno", "Asunto dos", "Asunto tres"]
    assert len(result) == 3


def test_generate_mailing_subjects_more_than_3():
    """generate_mailing_subjects trunca a 3 si el LLM devuelve más."""
    mock_llm = Mock()
    mock_llm.invoke.return_value = Mock(
        content="1. Uno\n2. Dos\n3. Tres\n4. Cuatro\n5. Cinco"
    )

    with patch(
        "peo_promotion_center.backend.content_generator.load_prompt",
        return_value="Template {nombre_paquete}",
    ):
        result = generate_mailing_subjects(_SAMPLE_METADATA, mock_llm)

    assert len(result) == 3
    assert result == ["Uno", "Dos", "Tres"]


def test_generate_mailing_subjects_less_than_3():
    """generate_mailing_subjects completa con cadena vacía si el LLM devuelve menos de 3."""
    mock_llm = Mock()
    mock_llm.invoke.return_value = Mock(content="1. Solo uno")

    with patch(
        "peo_promotion_center.backend.content_generator.load_prompt",
        return_value="Template {nombre_paquete}",
    ):
        result = generate_mailing_subjects(_SAMPLE_METADATA, mock_llm)

    assert len(result) == 3
    assert result[0] == "Solo uno"
    assert result[1] == ""
    assert result[2] == ""


def test_generate_preview_texts_3_lines():
    """generate_preview_texts retorna lista de 3 con respuesta de 3 textos."""
    mock_llm = Mock()
    mock_llm.invoke.return_value = Mock(
        content="1. Preview uno\n2. Preview dos\n3. Preview tres"
    )

    with patch(
        "peo_promotion_center.backend.content_generator.load_prompt",
        return_value="Template {nombre_paquete}",
    ):
        result = generate_preview_texts(_SAMPLE_METADATA, mock_llm)

    assert result == ["Preview uno", "Preview dos", "Preview tres"]
    assert len(result) == 3


def test_generate_preview_texts_more_than_3():
    """generate_preview_texts trunca a 3 si el LLM devuelve más."""
    mock_llm = Mock()
    mock_llm.invoke.return_value = Mock(
        content="1. Uno\n2. Dos\n3. Tres\n4. Cuatro"
    )

    with patch(
        "peo_promotion_center.backend.content_generator.load_prompt",
        return_value="Template {nombre_paquete}",
    ):
        result = generate_preview_texts(_SAMPLE_METADATA, mock_llm)

    assert len(result) == 3
    assert result == ["Uno", "Dos", "Tres"]


def test_generate_preview_texts_less_than_3():
    """generate_preview_texts completa con cadena vacía si el LLM devuelve menos de 3."""
    mock_llm = Mock()
    mock_llm.invoke.return_value = Mock(content="1. Solo uno")

    with patch(
        "peo_promotion_center.backend.content_generator.load_prompt",
        return_value="Template {nombre_paquete}",
    ):
        result = generate_preview_texts(_SAMPLE_METADATA, mock_llm)

    assert len(result) == 3
    assert result[0] == "Solo uno"
    assert result[1] == ""
    assert result[2] == ""


def test_generate_content_mock():
    """generate_content retorna GeneratedContent válido usando mocks del LLM."""
    with (
        patch("peo_promotion_center.backend.content_generator._build_llm"),
        patch(
            "peo_promotion_center.backend.content_generator.generate_social_copy",
            return_value="copy redes",
        ),
        patch(
            "peo_promotion_center.backend.content_generator.generate_mailing_subjects",
            return_value=["A1", "A2", "A3"],
        ),
        patch(
            "peo_promotion_center.backend.content_generator.generate_preview_texts",
            return_value=["P1", "P2", "P3"],
        ),
    ):
        result = generate_content(_SAMPLE_METADATA)

    assert isinstance(result, GeneratedContent)
    assert result.copy_redes == "copy redes"
    assert result.asuntos_mailing == ["A1", "A2", "A3"]
    assert result.preview_texts_mailing == ["P1", "P2", "P3"]


# ---------------------------------------------------------------------------
# _build_llm — validación de API key
# ---------------------------------------------------------------------------


def test_build_llm_raises_when_api_key_missing(monkeypatch):
    """_build_llm lanza ValueError si OPENAI_API_KEY no está configurada."""
    import peo_promotion_center.backend.content_generator as cg

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        cg._build_llm()


def test_build_llm_raises_when_api_key_empty(monkeypatch):
    """_build_llm lanza ValueError si OPENAI_API_KEY es cadena vacía."""
    import peo_promotion_center.backend.content_generator as cg

    monkeypatch.setenv("OPENAI_API_KEY", "")

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        cg._build_llm()


def test_build_llm_uses_provided_api_key(monkeypatch):
    """_build_llm usa el api_key explícito en lugar de la variable de entorno."""
    import peo_promotion_center.backend.content_generator as cg

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with patch("peo_promotion_center.backend.content_generator.ChatOpenAI") as mock_chat:
        cg._build_llm(api_key="sk-explicit-key")

    mock_chat.assert_called_once()
    _, kwargs = mock_chat.call_args
    assert kwargs["api_key"] == "sk-explicit-key"


def test_build_llm_falls_back_to_env_when_no_explicit_key(monkeypatch):
    """_build_llm usa OPENAI_API_KEY del entorno si no se pasa api_key explícito."""
    import peo_promotion_center.backend.content_generator as cg

    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key")

    with patch("peo_promotion_center.backend.content_generator.ChatOpenAI") as mock_chat:
        cg._build_llm()

    mock_chat.assert_called_once()
    _, kwargs = mock_chat.call_args
    assert kwargs["api_key"] == "sk-env-key"


def test_generate_content_propagates_api_key():
    """generate_content pasa el api_key recibido a _build_llm."""
    with (
        patch("peo_promotion_center.backend.content_generator.load_dotenv"),
        patch("peo_promotion_center.backend.content_generator._build_llm") as mock_build,
        patch(
            "peo_promotion_center.backend.content_generator.generate_social_copy",
            return_value="copy",
        ),
        patch(
            "peo_promotion_center.backend.content_generator.generate_mailing_subjects",
            return_value=["A1", "A2", "A3"],
        ),
    ):
        generate_content(_SAMPLE_METADATA, api_key="sk-guest-key")

    mock_build.assert_called_once_with(api_key="sk-guest-key")
