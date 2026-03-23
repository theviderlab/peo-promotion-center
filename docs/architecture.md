# Architecture

## System Overview

PEO Promotion Center is a single-process Streamlit application. All backend work runs synchronously in the same Python process as the UI, triggered by user interactions. Each user session gets an isolated working directory under `descargas/` identified by a UUID, which allows multiple concurrent users without interference.

```
User (browser)
    │
    ▼
┌─────────────────────────────────────────┐
│  Streamlit UI  (frontend/app.py)        │
│                                         │
│  1. URL Input  ──────────────────────►  Scraper
│                                         │    └─ Login → Find image URL → Download
│                                         │    └─ Extract metadata
│                                         │    └─ Returns ScrapeResult
│                                         │
│  2. URL Input  ──────────────────────►  ContentGenerator
│                                         │    └─ Load prompt templates
│                                         │    └─ Call OpenAI via LangChain
│                                         │    └─ Parse response
│                                         │    └─ Returns GeneratedContent
│                                         │
│  3. Crop Sliders ────────────────────►  ImageProcessor (preview)
│                                         │    └─ scale → crop → pad → PNG bytes
│                                         │
│  4. Download Button  ────────────────►  ImageProcessor (final)
│                                         │    └─ Generate 3 PNG files to disk
│                                         │
│                  ────────────────────►  ZipBuilder
│                                             └─ Assemble ZIP in memory
│                                             └─ Return bytes for download
└─────────────────────────────────────────┘
```

## Module Breakdown

| File | Responsibility |
|---|---|
| `backend/scraper.py` | Authentication to OPE site, image URL discovery (5-priority search), image download with `/A4/` quality upgrade, package metadata extraction |
| `backend/image_processor.py` | Resize, crop (with vertical offset), and pad images into 3 publication formats; in-memory preview generation |
| `backend/content_generator.py` | Load prompt templates from disk, substitute metadata placeholders, invoke OpenAI via LangChain, parse and normalize responses |
| `backend/models.py` | Shared frozen dataclasses: `ScrapeResult`, `GeneratedContent`, `ImageFormat`; `make_slug()` utility |
| `backend/exceptions.py` | Custom exception hierarchy for scraping failures |
| `frontend/app.py` | Streamlit UI orchestrating the 4-section workflow; `@st.cache_data` for preview caching |
| `frontend/session.py` | Idempotent session state initialization (UUID, session dir, default offsets) |
| `frontend/zip_builder.py` | Generates final PNGs and assembles the downloadable ZIP in memory |
| `main.py` | CLI entry point that launches `streamlit run` via subprocess |

## Data Models

### `ScrapeResult` (frozen dataclass)

| Field | Type | Description |
|---|---|---|
| `image_path` | `Path` | Path to the downloaded original image |
| `nombre_paquete` | `str` | Package name (from `<h1>`) |
| `frecuencia` | `str` | Frecuencias/salidas del paquete (from `#pills-frecuencia`) |
| `destinos` | `str` | Ciudades que recorre el paquete (from `div.head-det-price.det-separator p`) |
| `precio` | `str` | Price |
| `duracion` | `str` | Duration |
| `incluye` | `str` | What's included (from `#pills-descripcion`) |
| `no_incluye` | `str` | What's not included (from `#pills-consideraciones`) |
| `slug` | `str` | URL-safe package name (used for file naming) |

### `GeneratedContent` (frozen dataclass)

| Field | Type | Description |
|---|---|---|
| `copy_redes` | `str` | Full social media post (150–200 words, Mexican Spanish) |
| `asuntos_mailing` | `list[str]` | Exactly 3 email subject line options (max 60 chars each) |

### `ImageFormat` (dataclass)

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Display name (e.g., `"Post"`) |
| `width` | `int` | Canvas width in pixels |
| `height` | `int` | Canvas height in pixels |
| `slug` | `str` | File suffix (e.g., `"post"`) |

## Session Isolation

Each browser session receives a unique `session_id` (UUID4) generated on first load via `frontend/session.py`. All files for that session are written to `descargas/{session_id}/`. This directory is created at session init and used as the working directory throughout the session.

```
descargas/
├── 2883ff81-eaa2-4d9e-9260-8566895b76df/   ← user A's session
│   ├── original_image.jpg
│   ├── slug_post.png
│   ├── slug_historia.png
│   └── slug_google.png
└── 4dd4f2d5-61c3-49bc-b800-447a1470bf0e/   ← user B's session
    └── ...
```

The final ZIP is assembled in memory (`BytesIO`) and never written to disk, keeping the session directory small.

## Image Processing Pipeline

For each of the three output formats, the pipeline is:

```
Source image (original download)
    │
    ▼
scale_to_width(target_width)
    │  Resize to format width preserving aspect ratio (LANCZOS resampling)
    ▼
crop_to_canvas(fmt, offset_y)
    │  top = round(offset_y * (img.height - fmt.height))
    │  Crops [top : top + fmt.height] vertically
    │  No-op if image height ≤ canvas height
    ▼
pad_bottom(target_height)          ← Historia only
    │  Average color of last pixel row → solid fill
    │  Paste original at top of new canvas
    ▼
Save as PNG  →  {slug}_{fmt.slug}.png
```

**Offset semantics**: `offset_y = 0.0` crops from the top; `offset_y = 1.0` crops from the bottom. The slider default values are: Post = 0.4, Historia = 0.5, Google = 0.25.

**Preview path**: `preview_format()` performs the same pipeline but returns PNG bytes into memory (via `BytesIO`) without touching disk. It is wrapped with `@st.cache_data` in `app.py` so slider drags don't recompute unchanged formats.

## Image URL Discovery

`find_image_url()` in `scraper.py` searches the package page HTML for the promotional image using a 5-priority strategy:

| Priority | Pattern | Description |
|---|---|---|
| 1 | `<div id="collapseMatProImg">` | Dedicated collapsible image section (most reliable) |
| 2 | `<img src="...Thumb...">` | Any thumbnail `<img>` tag in the page |
| 3 | `<a href="...collage_new.php...">` | Collage page link |
| 4 | `<meta property="og:image">` | Open Graph image meta tag |
| 5 | `<meta name="twitter:image">` | Twitter card image meta tag |

If none of these match, `ImageNotFoundError` is raised.

After finding the URL, `download_image()` attempts a `/Thumb/` → `/A4/` substitution to obtain the highest-quality version. If the `/A4/` URL returns a non-200 response, it falls back to the original URL.

## Error Hierarchy

```
ScraperError                (base class for all scraping errors)
├── AuthenticationError     (login failed — bad credentials or unexpected response)
└── ImageNotFoundError      (no image URL found in the page HTML)
```

All three are defined in `backend/exceptions.py`. The Streamlit UI catches them individually and displays user-friendly messages via `st.error()` without crashing the session.

## Key Design Decisions

| Decision | Rationale |
|---|---|
| ZIP assembled in memory (`BytesIO`) | Avoids leaving ZIP files on disk per session; Python's `st.download_button` accepts bytes directly |
| Frozen dataclasses for `ScrapeResult` / `GeneratedContent` | Immutability prevents accidental mutation across UI re-renders |
| `@st.cache_data` on preview generation | Streamlit re-runs the entire script on each slider interaction; caching prevents redundant PIL work for unchanged formats |
| Prompt templates in external `.txt` files | Allows prompt iteration without touching Python code |
| `/A4/` URL upgrade attempt | The OPE site serves higher-resolution images at `/A4/` paths; falling back gracefully ensures the app never fails just because a higher-res version is unavailable |
| UUID session directories | Enables safe concurrent use without server-side session management infrastructure |
