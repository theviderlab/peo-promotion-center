"""Pruebas unitarias para los módulos auxiliares del frontend (session y zip_builder)."""

import io
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch


from peo_promotion_center.frontend.session import _init_session
from peo_promotion_center.frontend.zip_builder import build_zip


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeSessionState(dict):
    """Simula st.session_state: soporta acceso por atributo y el operador 'in'."""

    def __getattr__(self, key: str):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key: str, value) -> None:
        self[key] = value


# ---------------------------------------------------------------------------
# _init_session
# ---------------------------------------------------------------------------


def test_init_session_creates_all_keys(tmp_path: Path, monkeypatch):
    """_init_session inicializa todas las claves con sus valores por defecto."""
    fake_state = FakeSessionState()
    mock_st = MagicMock()
    mock_st.session_state = fake_state

    monkeypatch.setattr("peo_promotion_center.frontend.session.st", mock_st)
    monkeypatch.chdir(tmp_path)

    _init_session()

    assert "session_id" in fake_state
    assert isinstance(fake_state["session_id"], str)
    assert len(fake_state["session_id"]) > 0
    assert "session_dir" in fake_state
    assert fake_state["scrape_result"] is None
    assert fake_state["generated_content"] is None
    assert fake_state["zip_bytes"] is None
    assert fake_state["zip_hash"] is None
    assert fake_state["offsets"] == {"post": 0.4, "historia": 0.5, "google": 0.25}
    assert fake_state["authenticated"] is False
    assert fake_state["openai_api_key"] is None


def test_init_session_creates_session_dir(tmp_path: Path, monkeypatch):
    """_init_session crea el directorio de sesión en disco."""
    fake_state = FakeSessionState()
    mock_st = MagicMock()
    mock_st.session_state = fake_state

    monkeypatch.setattr("peo_promotion_center.frontend.session.st", mock_st)
    monkeypatch.chdir(tmp_path)

    _init_session()

    assert fake_state["session_dir"].exists()


def test_init_session_is_idempotent(tmp_path: Path, monkeypatch):
    """_init_session no sobreescribe el estado si session_id ya existe."""
    existing_id = "already-set-uuid"
    fake_state = FakeSessionState({"session_id": existing_id})
    mock_st = MagicMock()
    mock_st.session_state = fake_state

    monkeypatch.setattr("peo_promotion_center.frontend.session.st", mock_st)

    _init_session()

    assert fake_state["session_id"] == existing_id
    assert len(fake_state) == 1  # no se añadieron nuevas claves


# ---------------------------------------------------------------------------
# _cleanup_old_sessions
# ---------------------------------------------------------------------------


def test_cleanup_removes_old_session_dirs(tmp_path: Path):
    """Los directorios cuya mtime supera max_age_hours son eliminados."""
    import time
    from peo_promotion_center.frontend.session import _cleanup_old_sessions

    old_dir = tmp_path / "sesion-vieja"
    old_dir.mkdir()
    # Retroceder mtime 25 horas
    old_mtime = time.time() - 25 * 3600
    import os
    os.utime(old_dir, (old_mtime, old_mtime))

    _cleanup_old_sessions(tmp_path, max_age_hours=24)

    assert not old_dir.exists()


def test_cleanup_preserves_recent_session_dirs(tmp_path: Path):
    """Los directorios recientes (dentro de max_age_hours) no son eliminados."""
    from peo_promotion_center.frontend.session import _cleanup_old_sessions

    recent_dir = tmp_path / "sesion-reciente"
    recent_dir.mkdir()

    _cleanup_old_sessions(tmp_path, max_age_hours=24)

    assert recent_dir.exists()


def test_cleanup_does_nothing_when_base_dir_missing(tmp_path: Path):
    """No lanza excepción si el directorio base no existe."""
    from peo_promotion_center.frontend.session import _cleanup_old_sessions

    non_existing = tmp_path / "no-existe"
    # No debe lanzar ninguna excepción
    _cleanup_old_sessions(non_existing, max_age_hours=24)


# ---------------------------------------------------------------------------
# build_zip
# ---------------------------------------------------------------------------


def _make_fake_pngs(tmp_path: Path) -> dict[str, Path]:
    """Crea tres archivos PNG ficticios en tmp_path y retorna el dict de paths."""
    paths: dict[str, Path] = {}
    for slug in ("post", "historia", "google"):
        p = tmp_path / f"pkg_{slug}.png"
        p.write_bytes(b"FAKE_PNG_DATA")
        paths[slug] = p
    return paths


def test_build_zip_contains_five_files(tmp_path: Path):
    """El ZIP resultante contiene exactamente 6 archivos con los nombres correctos."""
    fake_pngs = _make_fake_pngs(tmp_path)
    source = tmp_path / "source.png"
    source.write_bytes(b"FAKE_FLYER")

    with patch(
        "peo_promotion_center.frontend.zip_builder.process_all_formats",
        return_value=fake_pngs,
    ):
        result = build_zip(
            source_path=source,
            slug="mi-paquete",
            offsets={"post": 0.5, "historia": 0.5, "google": 0.5},
            copy_redes="Copy de redes",
            asuntos_mailing=["Asunto 1", "Asunto 2", "Asunto 3"],
            preview_texts_mailing=["Preview 1", "Preview 2", "Preview 3"],
            output_dir=tmp_path,
        )

    with zipfile.ZipFile(io.BytesIO(result)) as zf:
        names = zf.namelist()

    assert len(names) == 7
    assert "mi-paquete_flyer.png" in names
    assert "mi-paquete_post.png" in names
    assert "mi-paquete_historia.png" in names
    assert "mi-paquete_google.png" in names
    assert "copy_redes.txt" in names
    assert "asuntos_mailing.txt" in names
    assert "preview_texts_mailing.txt" in names


def test_build_zip_text_content(tmp_path: Path):
    """copy_redes.txt y asuntos_mailing.txt tienen el contenido exacto esperado."""
    fake_pngs = _make_fake_pngs(tmp_path)
    source = tmp_path / "source.png"
    source.write_bytes(b"FAKE_FLYER")

    with patch(
        "peo_promotion_center.frontend.zip_builder.process_all_formats",
        return_value=fake_pngs,
    ):
        result = build_zip(
            source_path=source,
            slug="slug",
            offsets={},
            copy_redes="Copy de redes\nSegunda línea",
            asuntos_mailing=["A1", "A2", "A3"],
            preview_texts_mailing=["P1", "P2", "P3"],
            output_dir=tmp_path,
        )

    with zipfile.ZipFile(io.BytesIO(result)) as zf:
        copy_text = zf.read("copy_redes.txt").decode()
        asuntos_text = zf.read("asuntos_mailing.txt").decode()
        preview_text = zf.read("preview_texts_mailing.txt").decode()

    assert copy_text == "Copy de redes\nSegunda línea"
    assert asuntos_text == "A1\nA2\nA3"
    assert preview_text == "P1\nP2\nP3"


def test_build_zip_retorna_bytes(tmp_path: Path):
    """build_zip retorna un objeto bytes (no un Path ni un str)."""
    fake_pngs = _make_fake_pngs(tmp_path)
    source = tmp_path / "source.png"
    source.write_bytes(b"FAKE_FLYER")

    with patch(
        "peo_promotion_center.frontend.zip_builder.process_all_formats",
        return_value=fake_pngs,
    ):
        result = build_zip(
            source_path=source,
            slug="slug",
            offsets={},
            copy_redes="",
            asuntos_mailing=[],
            preview_texts_mailing=[],
            output_dir=tmp_path,
        )

    assert isinstance(result, bytes)
    assert len(result) > 0
