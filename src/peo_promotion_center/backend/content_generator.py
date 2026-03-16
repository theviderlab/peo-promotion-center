"""Módulo de generación de contenido mediante IA para los paquetes turísticos."""

# load_dotenv debe ejecutarse antes de importar langchain/langsmith para evitar
# que su lru_cache en get_env_var cachee las env vars antes de que el .env esté cargado.
from dotenv import load_dotenv

load_dotenv()

import os
import re
import uuid
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langsmith import set_run_metadata, traceable
from langsmith.run_helpers import tracing_context

from peo_promotion_center.backend.models import GeneratedContent

_PROJECT_ROOT = Path(__file__).parents[3]


def _build_llm(api_key: str | None = None) -> ChatOpenAI:
    """Instancia el modelo LangChain con la configuración del entorno.

    Args:
        api_key: API key de OpenAI. Si es None, se usa la variable de entorno
                 OPENAI_API_KEY.

    Raises:
        ValueError: Si no se encuentra ninguna API key configurada.
    """
    resolved_key = api_key or os.getenv("OPENAI_API_KEY")
    if not resolved_key:
        raise ValueError("OPENAI_API_KEY no configurada en el archivo .env.")
    model = os.getenv("OPENAI_MODEL", "gpt-4o")
    return ChatOpenAI(model=model, api_key=resolved_key)


def load_prompt(prompt_name: str) -> str:
    """
    Lee el contenido de un archivo de prompt.

    Args:
        prompt_name: Nombre del prompt (sin extensión .txt) dentro de prompts/.

    Returns:
        Contenido del archivo de prompt como cadena de texto.

    Raises:
        FileNotFoundError: Si el archivo de prompt no existe.
    """
    prompt_path = _PROJECT_ROOT / "prompts" / f"{prompt_name}.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Archivo de prompt no encontrado: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


@traceable(name="generate_social_copy")
def generate_social_copy(metadata: dict, llm: ChatOpenAI) -> str:
    """
    Genera copy para redes sociales a partir de la metadata del paquete.

    Args:
        metadata: Diccionario con los campos del paquete turístico.
        llm: Instancia del modelo LangChain a usar.

    Returns:
        Texto generado para publicar en redes sociales.
    """
    template = load_prompt("redes_sociales")
    messages = ChatPromptTemplate.from_template(template).invoke(metadata).to_messages()
    return llm.invoke(messages).content


@traceable(name="generate_mailing_subjects")
def generate_mailing_subjects(metadata: dict, llm: ChatOpenAI) -> list[str]:
    """
    Genera exactamente 3 asuntos de mailing a partir de la metadata del paquete.

    Args:
        metadata: Diccionario con los campos del paquete turístico.
        llm: Instancia del modelo LangChain a usar.

    Returns:
        Lista de exactamente 3 asuntos de correo. Se trunca o se completa
        con cadena vacía si el LLM devuelve un número distinto de 3.
    """
    template = load_prompt("mailing")
    messages = ChatPromptTemplate.from_template(template).invoke(metadata).to_messages()
    response = llm.invoke(messages).content
    lines = [line.strip() for line in response.splitlines() if line.strip()]
    subjects = [re.sub(r"^\d+\.\s*", "", line) for line in lines]
    subjects = subjects[:3]
    while len(subjects) < 3:
        subjects.append("")
    return subjects


@traceable(name="generate_preview_texts")
def generate_preview_texts(metadata: dict, llm: ChatOpenAI) -> list[str]:
    """
    Genera exactamente 3 preview texts de mailing a partir de la metadata del paquete.

    Args:
        metadata: Diccionario con los campos del paquete turístico.
        llm: Instancia del modelo LangChain a usar.

    Returns:
        Lista de exactamente 3 preview texts. Se trunca o se completa
        con cadena vacía si el LLM devuelve un número distinto de 3.
    """
    template = load_prompt("preview_text_mailing")
    messages = ChatPromptTemplate.from_template(template).invoke(metadata).to_messages()
    response = llm.invoke(messages).content
    lines = [line.strip() for line in response.splitlines() if line.strip()]
    texts = [re.sub(r"^\d+\.\s*", "", line) for line in lines]
    texts = texts[:3]
    while len(texts) < 3:
        texts.append("")
    return texts


@traceable(name="generate_content")
def generate_content(metadata: dict, api_key: str | None = None) -> GeneratedContent:
    """
    Genera copy para redes sociales, asuntos y preview texts de mailing usando OpenAI.

    Args:
        metadata: Diccionario con los campos del paquete turístico
                  (nombre_paquete, descripcion, destinos, precio,
                   duracion, incluye, no_incluye).
        api_key: API key de OpenAI. Si es None, se usa la variable de entorno
                 OPENAI_API_KEY (modo dueño) o se lanza ValueError.

    Returns:
        GeneratedContent con el copy, los 3 asuntos y los 3 preview texts generados.

    Raises:
        FileNotFoundError: Si alguno de los archivos de prompt no existe.
        openai.AuthenticationError: Si la API key es inválida.
        ValueError: Si no hay ninguna API key disponible.
    """
    thread_id = str(uuid.uuid4())
    set_run_metadata(thread_id=thread_id)

    # with_config propaga thread_id al nodo ChatOpenAI auto-traced por LangChain
    llm = _build_llm(api_key=api_key).with_config(
        {"metadata": {"thread_id": thread_id}}
    )

    # tracing_context propaga thread_id a los child runs @traceable
    with tracing_context(metadata={"thread_id": thread_id}):
        copy_redes = generate_social_copy(metadata, llm)
        asuntos_mailing = generate_mailing_subjects(metadata, llm)
        preview_texts_mailing = generate_preview_texts(metadata, llm)
    return GeneratedContent(
        copy_redes=copy_redes,
        asuntos_mailing=asuntos_mailing,
        preview_texts_mailing=preview_texts_mailing,
    )
