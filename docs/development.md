# Development Guide

## Setup

```bash
# 1. Clone the repository
git clone https://github.com/tu-org/peo-promotion-center.git
cd peo-promotion-center

# 2. Install dependencies (creates .venv automatically)
uv sync

# 3. Configure credentials
cp .env.example .env
# Edit .env with your OPE credentials and OpenAI API key

# 4. Run the app
uv run python -m peo_promotion_center.main
```

## Project Structure

```
peo-promotion-center/
│
├── src/peo_promotion_center/         # Main package
│   ├── __init__.py
│   ├── main.py                       # CLI entrypoint: launches Streamlit via subprocess
│   │
│   ├── backend/                      # Business logic (no Streamlit dependencies)
│   │   ├── __init__.py
│   │   ├── models.py                 # ScrapeResult, GeneratedContent, ImageFormat dataclasses
│   │   ├── exceptions.py             # ScraperError, AuthenticationError, ImageNotFoundError
│   │   ├── scraper.py                # OPE login, image URL discovery, download, metadata
│   │   ├── image_processor.py        # scale_to_width, crop_to_canvas, pad_bottom, generate_format
│   │   └── content_generator.py     # load_prompt, generate_social_copy, generate_mailing_subjects
│   │
│   └── frontend/                     # Streamlit UI layer
│       ├── __init__.py
│       ├── session.py                # init_session(): UUID session dir, default offsets
│       ├── app.py                    # render_url_section, render_crop_section, etc.
│       └── zip_builder.py            # build_zip(): process_all_formats + BytesIO ZIP assembly
│
├── tests/
│   ├── unit/                         # Isolated tests with mocked dependencies
│   │   ├── test_scraper.py
│   │   ├── test_image_processor.py
│   │   ├── test_content_generator.py
│   │   └── test_app.py
│   └── integration/                  # Real-world tests (require .env credentials)
│       ├── test_scraper.py
│       ├── test_content_generator.py
│       ├── test_end_to_end.py
│       └── test_example_integration.py
│
├── prompts/
│   ├── redes_sociales.txt            # Social media copy prompt template
│   └── mailing.txt                   # Email subject lines prompt template
│
├── docs/
│   ├── architecture.md               # System design, data flow, key decisions
│   ├── configuration.md              # Env vars, image formats, prompt reference
│   └── development.md                # This file
│
├── descargas/                        # Runtime session directories (gitignored)
├── pyproject.toml                    # Project metadata, dependencies, tool config
├── Makefile                          # Development task shortcuts
└── .env                              # Local credentials (gitignored, never commit)
```

## Testing

### Unit Tests

Unit tests live in `tests/unit/` and cover all backend modules in isolation. External dependencies (HTTP calls, OpenAI API, file system) are mocked using `unittest.mock`.

```bash
make test-unit
# or: uv run pytest tests/unit
```

All unit tests should run in milliseconds and require no credentials or network access.

**Mocking patterns used:**

- `scraper.py` — `requests.Session` mocked to return synthetic HTML responses
- `content_generator.py` — `ChatOpenAI` instance mocked; `load_prompt` patched via `@patch`
- `image_processor.py` — synthetic `PIL.Image` objects created with `Image.new()`; no disk I/O

### Integration Tests

Integration tests live in `tests/integration/` and exercise real network calls and the actual OpenAI API. They require valid credentials in `.env` and are **automatically skipped** when `OPE_USUARIO`, `OPE_CLAVE`, or `OPENAI_API_KEY` are missing.

```bash
make test-integration
# or: uv run pytest tests/integration
```

The integration test skip guard pattern used throughout:

```python
import pytest
from dotenv import load_dotenv
import os

load_dotenv()

pytestmark = pytest.mark.skipif(
    not os.getenv("OPE_USUARIO"),
    reason="OPE credentials not configured"
)
```

### Running All Tests

```bash
make test
```

### Useful pytest Flags

```bash
uv run pytest -s                          # Print stdout (don't capture)
uv run pytest -v                          # Verbose test names
uv run pytest tests/unit/test_scraper.py  # Single file
uv run pytest -k "test_find_image"        # Filter by name
```

## Code Conventions

### Style

- Formatted and linted with **ruff** (line length 100, Python 3.12 target)
- Run `make format` before committing

### File Length

All Python source files in `src/` must stay **under 150 lines** (excluding comments and docstrings). If a file approaches this limit, split it into focused submodules.

### Type Hints

All public functions must have type-annotated signatures:

```python
def generate_format(
    source_path: Path,
    fmt: ImageFormat,
    offset_y: float,
    slug: str,
    output_dir: Path,
) -> Path:
```

### Docstrings

All public modules, classes, and functions must have docstrings:

```python
def make_slug(name: str) -> str:
    """
    Convert a package name to a URL-safe slug.

    Lowercases the name, removes accents, and replaces spaces with dashes.
    Example: "Cancún Mágico" → "cancun-magico"
    """
```

### Architecture Principles

- **Backend modules have no Streamlit imports** — they are pure Python and independently testable
- **Frozen dataclasses** for data transfer objects (`ScrapeResult`, `GeneratedContent`)
- **Guard clauses** over nested conditionals
- **Explicit error types** — raise specific exceptions, never bare `Exception`
- **No hardcoded secrets** — all credentials from environment variables

---

## How to Add a New Image Format

The three output formats are defined as constants in `backend/image_processor.py`. Adding a new format requires changes in 4 places:

### 1. Define the format in `backend/image_processor.py`

```python
# Add alongside POST, HISTORIA, GOOGLE
LINKEDIN: ImageFormat = ImageFormat(name="LinkedIn", width=1200, height=627, slug="linkedin")

ALL_FORMATS: list[ImageFormat] = [POST, HISTORIA, GOOGLE, LINKEDIN]
```

### 2. Add a default offset in `frontend/session.py`

```python
# Inside _init_session(), in the offsets dict:
st.session_state.offsets = {
    "post": 0.4,
    "historia": 0.5,
    "google": 0.25,
    "linkedin": 0.3,  # ← add this
}
```

### 3. Add a column in `render_crop_section()` in `frontend/app.py`

```python
# Add a new column alongside the existing three:
col_post, col_historia, col_google, col_linkedin = st.columns(4)
with col_linkedin:
    st.caption(f"LinkedIn — {LINKEDIN.width}×{LINKEDIN.height}")
    offsets["linkedin"] = st.slider("Posición vertical", 0.0, 1.0, offsets["linkedin"], 0.01, key="linkedin")
    st.image(_cached_preview(source_str, LINKEDIN.slug, offsets["linkedin"]))
```

### 4. The ZIP is assembled automatically

`build_zip()` calls `process_all_formats()` which iterates `ALL_FORMATS`. No changes needed in `zip_builder.py`.

---

## How to Customize AI Prompts

Edit `prompts/redes_sociales.txt` or `prompts/mailing.txt` directly. See [Configuration Reference → AI Prompt Customization](configuration.md#ai-prompt-customization) for available placeholders and format rules.

To add a new metadata field as a placeholder:

1. Extract the field in `scraper.py`'s `extract_metadata()` and add it to the returned dict
2. Add the field to the `ScrapeResult` dataclass in `backend/models.py`
3. Reference it in `scraper.py`'s `scrape_package()` when constructing `ScrapeResult`
4. Use `{field_name}` in the prompt template

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `AuthenticationError` on startup | Wrong OPE credentials | Check `OPE_USUARIO` / `OPE_CLAVE` in `.env` |
| `ImageNotFoundError` for a valid URL | Page structure changed or login failed silently | Inspect the page HTML; check if login succeeded |
| `FileNotFoundError: prompts/redes_sociales.txt` | Running from wrong directory | Run via `uv run python -m peo_promotion_center.main` from the project root |
| OpenAI `AuthenticationError` | Invalid or expired API key | Update `OPENAI_API_KEY` in `.env` |
| OpenAI `RateLimitError` | Quota exceeded | Wait or upgrade OpenAI plan |
| Integration tests skipped | Missing env vars | Ensure `.env` has `OPE_USUARIO`, `OPE_CLAVE`, `OPENAI_API_KEY` |
| Streamlit shows blank page | Port 8501 already in use | Stop other Streamlit instances; or run `streamlit run ... --server.port 8502` |
| `uv sync` fails with conflicts | Dependency version conflict | Run `uv lock --upgrade-package <package>` for the conflicting package |
| Ruff formatting errors on CI | Files not formatted locally | Run `make format` before committing |

---

## Pre-commit Checklist

Run this before every commit:

```bash
make pre-commit
```

Which executes, in order:

1. `make test-unit` — all unit tests pass
2. `make format` — code is auto-formatted
3. `make lint` — no linting errors

Ensure integration tests also pass before merging to main if credentials are available in your local environment:

```bash
make test-integration
```
