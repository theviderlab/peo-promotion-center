"""Excepciones personalizadas del módulo scraper."""


class ScraperError(Exception):
    """Error base para los fallos del scraper."""


class AuthenticationError(ScraperError):
    """Fallo en la autenticación contra operadorapuntadeleste.com."""


class ImageNotFoundError(ScraperError):
    """No se encontró ninguna imagen promocional en el HTML del paquete."""
