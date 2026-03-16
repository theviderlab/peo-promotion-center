# PEO Promotion Center

Automated marketing content generator for tourism packages from [Operadora Punta del Este](https://www.operadorapuntadeleste.com). Given a package URL, the app logs in, downloads the main promotional image, resizes it into three publication-ready formats, generates AI-written social media copy and email subject lines via OpenAI, and delivers everything as a ZIP file — ready to use in campaigns.

## How It Works

The application is a 4-step web workflow:

1. **Enter a package URL** — paste any `operadorapuntadeleste.com` package page URL and click *Procesar paquete*. The app logs in, downloads the flyer image, and generates AI copy automatically.
2. **Adjust cropping** — three sliders let you independently control the vertical crop position for each image format (Post, Historia, Google). Live previews update in real time.
3. **Edit AI content** — review and refine the generated social media post and three email subject line suggestions directly in the interface.
4. **Download** — click *Generar y descargar paquete* to receive a ZIP file with all assets ready for use.

### ZIP Contents

| File | Format | Dimensions | Use |
|---|---|---|---|
| `{slug}_post.png` | PNG | 1080 × 1350 px | Instagram / Facebook post |
| `{slug}_historia.png` | PNG | 1080 × 1920 px | Instagram / Facebook story |
| `{slug}_google.png` | PNG | 960 × 640 px | Google display / banner |
| `{slug}_flyer.{ext}` | Original | — | Source image |
| `copy_redes.txt` | Text | — | Social media post copy |
| `asuntos_mailing.txt` | Text | — | 3 email subject line options |

## Tech Stack

| Component | Library |
|---|---|
| Web UI | [Streamlit](https://streamlit.io/) |
| Web scraping | [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) + [Requests](https://requests.readthedocs.io/) |
| Image processing | [Pillow](https://python-pillow.org/) |
| AI content generation | [LangChain](https://www.langchain.com/) + [OpenAI](https://openai.com/) |
| Package manager | [uv](https://docs.astral.sh/uv/) |
| Python | 3.12+ |

## Prerequisites

- Python 3.12 or higher
- [uv](https://docs.astral.sh/uv/) installed

## Installation

```bash
git clone https://github.com/tu-org/peo-promotion-center.git
cd peo-promotion-center
uv sync
```

## Configuration

Create a `.env` file in the project root with the following variables:

```bash
cp .env.example .env
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPE_USUARIO` | Yes | — | operadorapuntadeleste.com username |
| `OPE_CLAVE` | Yes | — | operadorapuntadeleste.com password |
| `OPENAI_API_KEY` | Yes | — | OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o` | OpenAI model to use |
| `OPE_TEST_URL` | No | — | A real package URL for integration tests |

## Running

```bash
uv run python -m peo_promotion_center.main
```

Opens the web interface at `http://localhost:8501`.

## Testing

```bash
make test               # All tests
make test-unit          # Unit tests only (no credentials required)
make test-integration   # Integration tests (requires valid .env credentials)
```

Integration tests are automatically skipped when credentials are not configured.

## Code Quality

```bash
make format     # Auto-format with ruff
make lint       # Lint with ruff
make pre-commit # Unit tests + format + lint
```

## Project Structure

```
src/peo_promotion_center/
├── main.py                    # CLI entry point (launches Streamlit)
├── backend/
│   ├── scraper.py             # Login, image download, metadata extraction
│   ├── image_processor.py     # Resize/crop/pad pipeline for 3 image formats
│   ├── content_generator.py   # OpenAI-powered copy and subject line generation
│   ├── models.py              # Shared dataclasses (ScrapeResult, GeneratedContent)
│   └── exceptions.py          # Custom exception hierarchy
└── frontend/
    ├── app.py                 # Streamlit UI (4-section workflow)
    ├── session.py             # Session state initialization
    └── zip_builder.py         # In-memory ZIP assembly

prompts/
├── redes_sociales.txt         # Social media copy prompt template
└── mailing.txt                # Email subject lines prompt template
```

## Further Reading

- [Architecture](docs/architecture.md) — system design, data flow, module breakdown, key decisions
- [Configuration Reference](docs/configuration.md) — env vars, image formats, prompt customization
- [Development Guide](docs/development.md) — setup, testing, conventions, extending the app

