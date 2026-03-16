# Configuration Reference

## Environment Variables

Create a `.env` file in the project root. The app loads it automatically at startup via `python-dotenv`.

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPE_USUARIO` | **Yes** | — | Username for operadorapuntadeleste.com login |
| `OPE_CLAVE` | **Yes** | — | Password for operadorapuntadeleste.com login |
| `OPENAI_API_KEY` | **Yes** | — | OpenAI API key for content generation |
| `OPENAI_MODEL` | No | `gpt-4o` | OpenAI model identifier (e.g. `gpt-4o-mini`, `gpt-4-turbo`) |
| `OPE_TEST_URL` | No | — | URL of a real package page used by integration tests |

**Example `.env`:**

```bash
OPE_USUARIO=your_username
OPE_CLAVE=your_password
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
OPE_TEST_URL=https://www.operadorapuntadeleste.com/paquetes/cancun-magico/
```

> **Security**: Never commit `.env` to version control. It is listed in `.gitignore`. Credentials are read at runtime and never logged.

---

## Image Output Formats

The app generates three PNG files from the downloaded package image:

| Format | Dimensions | Aspect Ratio | Intended Use | Output filename |
|---|---|---|---|---|
| **Post** | 1080 × 1350 px | 4:5 | Instagram / Facebook feed post | `{slug}_post.png` |
| **Historia** | 1080 × 1920 px | 9:16 | Instagram / Facebook story | `{slug}_historia.png` |
| **Google** | 960 × 640 px | 3:2 | Google Display Network / banner | `{slug}_google.png` |

`{slug}` is derived from the package name: lowercased, accents removed, spaces replaced with dashes (e.g., `cancun-magico`).

### Crop Offset (`offset_y`)

Each format has an independent vertical crop slider in the UI:

- `0.0` — crops from the **top** of the image (shows the top portion)
- `0.5` — crops from the **center**
- `1.0` — crops from the **bottom** (shows the bottom portion)

**Default values:**

| Format | Default `offset_y` |
|---|---|
| Post | 0.40 |
| Historia | 0.50 |
| Google | 0.25 |

For the Historia format only: if the scaled image is shorter than 1920 px, the bottom is padded with a solid color sampled from the last pixel row of the image.

---

## AI Prompt Customization

Prompts are stored as plain text files in the `prompts/` directory. You can edit them without modifying any Python code.

### `prompts/redes_sociales.txt`

Generates the social media post copy. The following placeholders are substituted from the scraped package data before the prompt is sent to OpenAI:

| Placeholder | Source | Description |
|---|---|---|
| `{nombre_paquete}` | `<h1>` tag | Package name |
| `{descripcion}` | Page text | Package description |
| `{destinos}` | Structured data | Destination(s) |
| `{precio}` | Structured data | Price |
| `{duracion}` | Structured data | Duration |
| `{incluye}` | Structured data | What's included |

**Expected output**: 150–200 words in Mexican Spanish, with relevant emojis, a clear call-to-action, and 5 hashtags at the end.

### `prompts/mailing.txt`

Generates email subject line options. Available placeholders:

| Placeholder | Source | Description |
|---|---|---|
| `{nombre_paquete}` | `<h1>` tag | Package name |
| `{descripcion}` | Page text | Package description |
| `{precio}` | Structured data | Price |
| `{duracion}` | Structured data | Duration |

**Expected output**: Exactly 3 subject lines, numbered 1–3, one per line, maximum 60 characters each, in Mexican Spanish. Avoid spam trigger words (gratis, oferta, etc.).

### Prompt Format Rules

- Use `{placeholder_name}` syntax for variable substitution (Python `str.format_map`)
- All placeholders listed above must be present in the template or the format call will raise a `KeyError`
- You can add instructions, tone guidance, or examples in plain text around the placeholders
- Do not use curly braces `{}` for anything other than placeholders (escape literal braces as `{{` and `}}`)

---

## Ruff Configuration

Code style is enforced by [ruff](https://docs.astral.sh/ruff/). Configuration lives in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]
```

| Rule Set | Description |
|---|---|
| `E` | pycodestyle error rules |
| `F` | Pyflakes rules (unused imports, undefined names) |
| `I` | isort import ordering |
| `N` | pep8-naming conventions |
| `W` | pycodestyle warning rules |
