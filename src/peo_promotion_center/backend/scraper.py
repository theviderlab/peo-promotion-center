"""Módulo de autenticación y descarga de paquetes turísticos."""

import os
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from .exceptions import AuthenticationError, ImageNotFoundError, ScraperError
from .models import ScrapeResult, make_slug

_BASE_URL = "https://www.operadorapuntadeleste.com"
_ALLOWED_HOSTS: frozenset[str] = frozenset(
    {"www.operadorapuntadeleste.com", "operadorapuntadeleste.com"}
)


def _validate_ope_url(url: str) -> None:
    """
    Valida que la URL pertenezca al dominio permitido y use HTTPS.

    Args:
        url: URL a validar.

    Raises:
        ScraperError: Si el esquema no es HTTPS o el host no está en _ALLOWED_HOSTS.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ScraperError(
            f"URL rechazada: el esquema debe ser HTTPS (recibido: '{parsed.scheme}')."
        )
    if parsed.netloc not in _ALLOWED_HOSTS:
        raise ScraperError(
            f"URL rechazada: el host '{parsed.netloc}' no pertenece a operadorapuntadeleste.com."
        )


def login(session: requests.Session, usuario: str, clave: str) -> None:
    """
    Autentica la sesión contra operadorapuntadeleste.com.

    Replica el flujo del script PowerShell de referencia:
    GET /acceso/ → POST /login.asp → seguir redirección si la hay.

    Args:
        session: Sesión requests activa.
        usuario: Nombre de usuario.
        clave: Contraseña.

    Raises:
        AuthenticationError: Si el servidor devuelve "error".
    """
    session.get(f"{_BASE_URL}/acceso/")
    resp = session.post(
        f"{_BASE_URL}/login.asp",
        data={"Usuario": usuario, "Clave": clave},
    )
    body = resp.text.strip()
    if body.lower() == "error":
        raise AuthenticationError("Login fallido: usuario o contraseña incorrectos.")
    if body:
        redirect_url = urljoin(_BASE_URL, body)
        if urlparse(redirect_url).netloc in _ALLOWED_HOSTS:
            session.get(redirect_url)


def find_image_url(html: str, base_url: str) -> str:
    """
    Detecta la URL de la imagen promocional aplicando 5 patrones en orden de prioridad.

    Orden idéntico al script PowerShell de referencia:
    1. div#collapseMatProImg → primera img
    2. img con src en /Uploads/Material_Promocional/Thumb/
    3. a con href que contiene create_image_collage_new.php
    4. meta property="og:image"
    5. meta name="twitter:image"

    Args:
        html: Contenido HTML de la página del paquete.
        base_url: URL base para resolver URLs relativas.

    Returns:
        URL absoluta de la imagen.

    Raises:
        ImageNotFoundError: Si ningún patrón encuentra la imagen.
    """
    soup = BeautifulSoup(html, "html.parser")

    div = soup.find("div", id="collapseMatProImg")
    if div:
        img = div.find("img", src=True)
        if img:
            return urljoin(base_url, img["src"])

    img = soup.find(
        "img", src=re.compile(r"/Uploads/Material_Promocional/Thumb/", re.I)
    )
    if img:
        return urljoin(base_url, img["src"])

    anchor = soup.find("a", href=re.compile(r"create_image_collage_new\.php", re.I))
    if anchor:
        return urljoin(base_url, anchor["href"])

    meta = soup.find("meta", attrs={"property": "og:image"})
    if meta and meta.get("content"):
        return urljoin(base_url, meta["content"])

    meta = soup.find("meta", attrs={"name": "twitter:image"})
    if meta and meta.get("content"):
        return urljoin(base_url, meta["content"])

    raise ImageNotFoundError("No se encontró ninguna imagen promocional en el HTML.")


def download_image(session: requests.Session, image_url: str, dest_dir: Path) -> Path:
    """
    Descarga la imagen intentando primero la versión de alta calidad (/A4/).

    Si la URL contiene /Thumb/, sustituye por /A4/ e intenta esa URL primero.
    Si devuelve HTTP error, cae a la URL original.

    Args:
        session: Sesión requests autenticada.
        image_url: URL de la imagen detectada.
        dest_dir: Directorio de destino para el archivo descargado.

    Returns:
        Path al archivo descargado.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    high_res = (
        image_url.replace("/Thumb/", "/A4/") if "/Thumb/" in image_url else image_url
    )
    urls = [high_res, image_url] if high_res != image_url else [image_url]
    last_exc: Exception = RuntimeError("No URL attempted")
    for url in urls:
        try:
            resp = session.get(url)
            resp.raise_for_status()
            filename = Path(urlparse(url).path).name or "imagen-promocional.jpg"
            filename = re.sub(r"[^\w.\-]", "_", filename)[:200] or "imagen-promocional.jpg"
            out_path = dest_dir / filename
            out_path.write_bytes(resp.content)
            return out_path
        except requests.HTTPError as exc:
            last_exc = exc
    raise last_exc


def _near_label(soup: BeautifulSoup, *patterns: str) -> str:
    """Extrae el texto del elemento hermano siguiente a un nodo de texto que coincida con el patrón dado."""
    for pat in patterns:
        for node in soup.find_all(string=re.compile(pat, re.I)):
            sibling = node.parent.find_next_sibling()
            if sibling:
                return sibling.get_text(" ", strip=True)
    return ""


def extract_metadata(html: str) -> dict:
    """
    Extrae los campos de metadata del HTML del paquete.

    Los campos ausentes devuelven cadena vacía, nunca None.

    Args:
        html: Contenido HTML de la página del paquete.

    Returns:
        Diccionario con campos: nombre_paquete, descripcion, destinos,
        precio, duracion, incluye, no_incluye.
    """
    soup = BeautifulSoup(html, "html.parser")

    def text(tag) -> str:
        """Extrae texto de un tag o retorna cadena vacía si es None."""
        return tag.get_text(" ", strip=True) if tag else ""

    return {
        "nombre_paquete": text(soup.find("h1")) or text(soup.find("title")),
        "descripcion": text(
            soup.find("div", class_=re.compile(r"descripci[oó]n|resumen", re.I))
        )
        or text(soup.select_one("main p, .contenido p, article p")),
        "destinos": _near_label(soup, r"destinos?"),
        "precio": text(soup.find(class_=re.compile(r"precio|price", re.I)))
        or _near_label(soup, r"precio"),
        "duracion": _near_label(soup, r"duraci[oó]n"),
        "incluye": _near_label(soup, r"^\s*incluye\s*$"),
        "no_incluye": _near_label(soup, r"no\s+incluye", r"excluye"),
    }


def scrape_package(url: str, session_dir: Path) -> ScrapeResult:
    """
    Autentica, descarga la imagen y extrae metadata de un paquete.

    Lee las credenciales OPE_USUARIO y OPE_CLAVE del archivo .env.

    Args:
        url: URL del paquete en operadorapuntadeleste.com.
        session_dir: Directorio temporal exclusivo de la sesión del usuario.

    Returns:
        ScrapeResult con la ruta local de la imagen y la metadata extraída.

    Raises:
        AuthenticationError: Si el login falla.
        ImageNotFoundError: Si no se encuentra la imagen en el HTML.
    """
    load_dotenv()
    usuario = os.getenv("OPE_USUARIO", "")
    clave = os.getenv("OPE_CLAVE", "")
    if not usuario or not clave:
        raise AuthenticationError("OPE_USUARIO y OPE_CLAVE deben estar configuradas en .env.")
    _validate_ope_url(url)

    with requests.Session() as session:
        login(session, usuario, clave)
        resp = session.get(url)
        resp.raise_for_status()
        html = resp.text

        image_url = find_image_url(html, url)
        _validate_ope_url(image_url)
        image_path = download_image(session, image_url, session_dir)
        meta = extract_metadata(html)

        return ScrapeResult(
            image_path=image_path,
            nombre_paquete=meta["nombre_paquete"],
            descripcion=meta["descripcion"],
            destinos=meta["destinos"],
            precio=meta["precio"],
            duracion=meta["duracion"],
            incluye=meta["incluye"],
            no_incluye=meta["no_incluye"],
            slug=make_slug(meta["nombre_paquete"]),
        )
