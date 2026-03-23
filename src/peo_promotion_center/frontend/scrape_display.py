"""Componentes de UI para mostrar los metadatos extraídos del scraping."""

import streamlit as st

from peo_promotion_center.backend.models import ScrapeResult

_FIELDS: list[tuple[str, str]] = [
    ("Nombre del paquete", "nombre_paquete"),
    ("Frecuencia", "frecuencia"),
    ("Destinos", "destinos"),
    ("Precio", "precio"),
    ("Duración", "duracion"),
    ("Incluye", "incluye"),
    ("No incluye", "no_incluye"),
]


def _render_scrape_metadata(sr: ScrapeResult) -> None:
    """
    Muestra los metadatos extraídos del paquete en un expander colapsado.

    Los campos sin valor se muestran como '—'. Solo lectura.

    Args:
        sr: Resultado del scraping con los metadatos del paquete.
    """
    with st.expander("Datos extraídos del paquete", expanded=False):
        for label, attr in _FIELDS:
            col_label, col_value = st.columns([1, 2])
            with col_label:
                st.markdown(f"**{label}**")
            with col_value:
                st.markdown(getattr(sr, attr) or "—")
