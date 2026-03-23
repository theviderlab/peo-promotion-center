"""Pruebas unitarias para _render_scrape_metadata en scrape_display."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from peo_promotion_center.backend.models import ScrapeResult
from peo_promotion_center.frontend.scrape_display import _render_scrape_metadata


def _make_sr(**overrides) -> ScrapeResult:
    """Crea un ScrapeResult con valores por defecto, permitiendo overrides."""
    defaults = {
        "image_path": Path("img.jpg"),
        "nombre_paquete": "Paquete A",
        "frecuencia": "Lunes y viernes",
        "destinos": "Punta del Este",
        "precio": "USD 1.200",
        "duracion": "7 noches",
        "incluye": "Vuelos, hotel",
        "no_incluye": "Traslados",
        "slug": "paquete-a",
    }
    return ScrapeResult(**{**defaults, **overrides})


def test_expander_is_collapsed_by_default():
    """st.expander se invoca con expanded=False."""
    sr = _make_sr()
    mock_st = MagicMock()
    mock_st.expander.return_value.__enter__ = MagicMock(return_value=None)
    mock_st.expander.return_value.__exit__ = MagicMock(return_value=False)
    mock_st.columns.return_value = [MagicMock(), MagicMock()]

    with patch("peo_promotion_center.frontend.scrape_display.st", mock_st):
        _render_scrape_metadata(sr)

    mock_st.expander.assert_called_once_with("Datos extraídos del paquete", expanded=False)


def test_empty_field_renders_dash():
    """Un campo vacío se muestra como '—' en lugar de cadena vacía."""
    sr = _make_sr(no_incluye="")
    mock_st = MagicMock()
    mock_st.expander.return_value.__enter__ = MagicMock(return_value=None)
    mock_st.expander.return_value.__exit__ = MagicMock(return_value=False)

    col_label = MagicMock()
    col_value = MagicMock()
    col_label.__enter__ = MagicMock(return_value=None)
    col_label.__exit__ = MagicMock(return_value=False)
    col_value.__enter__ = MagicMock(return_value=None)
    col_value.__exit__ = MagicMock(return_value=False)
    mock_st.columns.return_value = [col_label, col_value]

    with patch("peo_promotion_center.frontend.scrape_display.st", mock_st):
        _render_scrape_metadata(sr)

    # Recopilar todas las llamadas a st.markdown dentro del contexto col_value
    markdown_calls = [c.args[0] for c in mock_st.markdown.call_args_list]
    assert "—" in markdown_calls


def test_non_empty_field_renders_value():
    """Un campo con valor se muestra tal cual, sin modificar."""
    sr = _make_sr(precio="USD 2.500")
    mock_st = MagicMock()
    mock_st.expander.return_value.__enter__ = MagicMock(return_value=None)
    mock_st.expander.return_value.__exit__ = MagicMock(return_value=False)

    col_label = MagicMock()
    col_value = MagicMock()
    col_label.__enter__ = MagicMock(return_value=None)
    col_label.__exit__ = MagicMock(return_value=False)
    col_value.__enter__ = MagicMock(return_value=None)
    col_value.__exit__ = MagicMock(return_value=False)
    mock_st.columns.return_value = [col_label, col_value]

    with patch("peo_promotion_center.frontend.scrape_display.st", mock_st):
        _render_scrape_metadata(sr)

    markdown_calls = [c.args[0] for c in mock_st.markdown.call_args_list]
    assert "USD 2.500" in markdown_calls
