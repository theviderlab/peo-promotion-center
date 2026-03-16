"""Modelos de datos del módulo backend."""

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ScrapeResult:
    """Resultado del scraping de un paquete turístico."""

    image_path: Path
    nombre_paquete: str
    descripcion: str
    destinos: str
    precio: str
    duracion: str
    incluye: str
    no_incluye: str
    slug: str


@dataclass(frozen=True)
class GeneratedContent:
    """Contenido de marketing generado por el LLM."""

    copy_redes: str
    asuntos_mailing: list[str]  # Siempre 3 elementos
    preview_texts_mailing: list[str]  # Siempre 3 elementos


def make_slug(name: str) -> str:
    """
    Genera una versión URL-friendly de un nombre.

    Args:
        name: Nombre del paquete turístico.

    Returns:
        Cadena en minúsculas, sin acentos, con guiones en lugar de espacios.
    """
    normalized = unicodedata.normalize("NFKD", name)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^\w\s-]", "", ascii_text).lower().strip()
    return re.sub(r"[\s_]+", "-", slug)
