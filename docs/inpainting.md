# Inpainting — Especificación de implementación

## Objetivo

Permitir al usuario borrar regiones de una imagen (logos, textos recortados, marcas de agua)
en cada formato de salida de forma independiente, como paso de refinamiento posterior al
recorte. El relleno de las zonas borradas se genera automáticamente con un modelo de ML
local, sin enviar imágenes a servicios externos.

---

## Fundamento del diseño

El inpainting opera **sobre la imagen ya recortada de cada formato**, no sobre la fuente
original. Esto es correcto por varias razones:

- Cada formato tiene dimensiones y recorte distintos: un logo que aparece en el borde
  inferior del Post puede no ser visible en Historia o Google, y viceversa.
- Historia en particular nunca recorta verticalmente (la imagen se extiende con padding
  de color); modificar la fuente antes del recorte podría borrar contenido visible en
  otros formatos.
- El usuario sabe exactamente qué quiere borrar sólo después de ver el recorte final de
  cada formato.

---

## Tecnología seleccionada

| Componente | Librería / Modelo | Motivo |
|---|---|---|
| Modelo de inpainting | **LaMa** vía `simple-lama-inpainting` | Mejor calidad/simplicidad en CPU; modelo ~200 MB auto-descargable; API de 3 líneas |
| Canvas de dibujo UI | **`streamlit-drawable-canvas`** | Componente nativo Streamlit para pintar la máscara sobre la imagen |

```bash
uv add simple-lama-inpainting streamlit-drawable-canvas
```

El modelo se descarga automáticamente en `~/.cache/simple-lama` la primera vez que se
instancia `SimpleLama()` y queda cacheado para ejecuciones posteriores.

---

## Posición en el flujo de la app

```
Sección 1 — URL del paquete      → descarga imagen fuente
Sección 2 — Selección de recorte → sliders por formato + preview
Sección 3 — Refinamiento (NUEVO) → inpainting opcional por formato
Sección 4 — Contenido generado   → copy de IA editable
Sección 5 — Descarga             → genera y descarga el ZIP
```

La sección de refinamiento aparece **después** de confirmar los recortes y **antes** de
la descarga, de modo que el usuario puede limpiar cada formato de forma independiente y
opcional.

---

## Diseño de la solución

### Módulo backend: `backend/inpainter.py`

Responsabilidad única: aplicar inpainting a una imagen PIL dada una máscara PIL.

```python
# src/peo_promotion_center/backend/inpainter.py

from PIL import Image
from simple_lama_inpainting import SimpleLama

_lama: SimpleLama | None = None


def get_lama() -> SimpleLama:
    """Devuelve la instancia singleton de SimpleLama, inicializándola si es necesario."""
    global _lama
    if _lama is None:
        _lama = SimpleLama()
    return _lama


def inpaint(image: Image.Image, mask: Image.Image) -> Image.Image:
    """
    Borra la región marcada en mask y rellena con LaMa.

    Args:
        image: Imagen RGB a procesar (en la resolución final del formato).
        mask:  Imagen en escala de grises; blanco (255) = zona a borrar.

    Returns:
        Imagen RGB con la región borrada y reconstruida.
    """
    return get_lama()(image, mask.convert("L"))
```

- El singleton `_lama` evita recargar el modelo en cada llamada (costoso en CPU).
- La función es stateless: recibe PIL Images, devuelve PIL Image.

### Estado de sesión: máscaras por formato

Las máscaras pintadas por el usuario se almacenan en `st.session_state` como objetos
`Image.Image | None`, indexadas por el `slug` del formato:

```python
# En session.py, dentro de _init_session():
if "inpaint_masks" not in st.session_state:
    st.session_state.inpaint_masks = {fmt.slug: None for fmt in ALL_FORMATS}
    # None = sin máscara → no se aplica inpainting para ese formato
```

Las máscaras se almacenan en resolución **original del formato** (ej. 1080×1350 para Post),
escaladas desde el canvas de visualización al momento de confirmar.

Las máscaras se invalidan (reset a `None`) cada vez que el usuario procesa un nuevo paquete
(paso 1), junto con el resto del estado de sesión.

### Módulo frontend: `frontend/inpaint_ui.py`

Responsabilidad única: renderizar la sección de refinamiento con un expander por formato.

```python
# src/peo_promotion_center/frontend/inpaint_ui.py

import io
import numpy as np
import streamlit as st
from PIL import Image
from streamlit_drawable_canvas import st_canvas

from peo_promotion_center.backend.image_processor import ALL_FORMATS, preview_format
from peo_promotion_center.backend.inpainter import inpaint

BRUSH_SIZE_DEFAULT = 20
CANVAS_WIDTH = 400  # px de visualización (no afecta resolución de salida)


def render_refinement_section() -> None:
    """
    Sección 3: refinamiento opcional por inpainting, un expander por formato.

    Lee scrape_result y offsets del session_state.
    Escribe máscaras confirmadas en st.session_state.inpaint_masks[fmt.slug].
    """
    if st.session_state.scrape_result is None:
        return

    st.header("3. Refinamiento (opcional)")
    st.caption(
        "Si algún formato quedó con logos, textos o elementos no deseados, "
        "pintá el área y aplicá el borrado. Cada formato se procesa de forma independiente."
    )

    sr = st.session_state.scrape_result

    for fmt in ALL_FORMATS:
        with st.expander(f"✏️ {fmt.name} ({fmt.width}×{fmt.height})", expanded=False):
            offset = st.session_state.offsets[fmt.slug]

            # Obtener la imagen recortada del formato (bytes de preview)
            cropped_bytes = preview_format(sr.image_path, fmt, offset)
            cropped_img = Image.open(io.BytesIO(cropped_bytes)).convert("RGB")

            # Escalar al ancho de canvas manteniendo proporción del formato
            scale = CANVAS_WIDTH / fmt.width
            canvas_height = round(fmt.height * scale)
            preview = cropped_img.resize((CANVAS_WIDTH, canvas_height), Image.LANCZOS)

            buf = io.BytesIO()
            preview.save(buf, format="PNG")

            brush_size = st.slider(
                "Tamaño del pincel",
                min_value=5,
                max_value=60,
                value=BRUSH_SIZE_DEFAULT,
                key=f"brush_{fmt.slug}",
            )

            canvas_result = st_canvas(
                fill_color="rgba(255, 255, 255, 1)",
                stroke_width=brush_size,
                stroke_color="rgba(255, 255, 255, 1)",
                background_image=Image.open(io.BytesIO(buf.getvalue())),
                update_streamlit=True,
                width=CANVAS_WIDTH,
                height=canvas_height,
                drawing_mode="freedraw",
                key=f"canvas_{fmt.slug}",
            )

            current_mask = st.session_state.inpaint_masks.get(fmt.slug)
            if current_mask is not None:
                st.success("Máscara guardada. Se aplicará al generar el ZIP.")

            col_apply, col_clear = st.columns([1, 1])

            with col_apply:
                if st.button("Guardar máscara", key=f"apply_{fmt.slug}"):
                    if canvas_result.image_data is None:
                        st.warning("Dibujá sobre la imagen primero.")
                    else:
                        # Extraer canal alfa del canvas (blanco = zona pintada)
                        alpha = canvas_result.image_data[:, :, 3].astype(np.uint8)
                        mask_preview = Image.fromarray(alpha)

                        if mask_preview.getextrema() == (0, 0):
                            st.warning("No hay trazos en el canvas.")
                        else:
                            # Escalar máscara a la resolución real del formato
                            mask_full = mask_preview.resize(
                                (fmt.width, fmt.height), Image.NEAREST
                            )
                            st.session_state.inpaint_masks[fmt.slug] = mask_full
                            st.success("Máscara guardada.")

            with col_clear:
                if st.button("Limpiar máscara", key=f"clear_{fmt.slug}"):
                    st.session_state.inpaint_masks[fmt.slug] = None
                    st.rerun()
```

### Integración en `frontend/zip_builder.py`

El builder recibe las máscaras de sesión y aplica inpainting a cada formato que tenga
una máscara definida, antes de guardar el PNG final.

```python
# Cambio en zip_builder.py: build_zip recibe un parámetro adicional

from peo_promotion_center.backend.inpainter import inpaint

def build_zip(
    source_path: Path,
    slug: str,
    offsets: dict[str, float],
    copy_redes: str,
    asuntos_mailing: list[str],
    preview_texts_mailing: list[str],
    output_dir: Path,
    inpaint_masks: dict[str, Image.Image | None] | None = None,  # NUEVO
) -> bytes:
    ...
    for fmt in ALL_FORMATS:
        img = _process_format(source_path, fmt, offsets[fmt.slug])

        if inpaint_masks and inpaint_masks.get(fmt.slug) is not None:
            img = inpaint(img, inpaint_masks[fmt.slug])

        out_path = output_dir / f"{slug}_{fmt.slug}.png"
        img.save(out_path, format="PNG")
    ...
```

> La firma existente de `build_zip` no cambia en su uso actual: `inpaint_masks=None` es
> el valor por defecto, por lo que el comportamiento sin inpainting queda intacto.

### Integración en `frontend/app.py`

```python
# En render_download_section(), al llamar a build_zip:
st.session_state.zip_bytes = build_zip(
    source_path=sr.image_path,
    slug=sr.slug,
    offsets=st.session_state.offsets,
    copy_redes=copy_redes,
    asuntos_mailing=asuntos,
    preview_texts_mailing=preview_texts,
    output_dir=st.session_state.session_dir,
    inpaint_masks=st.session_state.get("inpaint_masks"),  # NUEVO
)

# En render_url_section(), al resetear el estado tras un nuevo paquete:
st.session_state.inpaint_masks = {fmt.slug: None for fmt in ALL_FORMATS}  # NUEVO

# En main(), agregar la nueva sección entre crop y content:
render_crop_section()
st.divider()
render_refinement_section()   # NUEVO
st.divider()
render_content_section()
```

El hash del ZIP debe incluir las máscaras para que se regenere cuando cambien:

```python
# En render_download_section(), en el cálculo de current_hash:
masks_hash = str({k: (v.tobytes() if v else None)
                  for k, v in st.session_state.get("inpaint_masks", {}).items()})
current_hash = hashlib.md5("|".join([..., masks_hash]).encode()).hexdigest()
```

---

## Flujo de datos

```
Sección 2 — Recorte
    ImageProcessor.preview_format(source, fmt, offset)
        │  → PNG bytes (resolución del formato)
        ▼
Sección 3 — Refinamiento (por formato, opcional)
    st_canvas  ──► máscara RGBA (canvas resolution, CANVAS_WIDTH px)
        │
        resize(NEAREST) → máscara en resolución del formato (fmt.width × fmt.height)
        │
        save en session_state.inpaint_masks[fmt.slug]
        │
Sección 5 — Descarga
    zip_builder.build_zip(…, inpaint_masks=…)
        │
        por cada formato con máscara:
            image_processor._process_format(source, fmt, offset)  → img PIL
            inpainter.inpaint(img, mask)                           → img limpia
            img.save(out_path)
        │
        ▼
    ZIP en memoria → st.download_button
```

---

## Archivos afectados / creados

| Archivo | Acción |
|---|---|
| `src/peo_promotion_center/backend/inpainter.py` | **Nuevo** |
| `src/peo_promotion_center/frontend/inpaint_ui.py` | **Nuevo** |
| `src/peo_promotion_center/frontend/session.py` | Modificar: inicializar `inpaint_masks` en `_init_session()` |
| `src/peo_promotion_center/frontend/app.py` | Modificar: llamar `render_refinement_section()`, pasar máscaras a `build_zip`, invalidar máscaras en reset |
| `src/peo_promotion_center/frontend/zip_builder.py` | Modificar: aceptar `inpaint_masks`, aplicar inpainting antes de guardar cada PNG |
| `pyproject.toml` | Agregar `simple-lama-inpainting` y `streamlit-drawable-canvas` |
| `tests/unit/test_inpainter.py` | **Nuevo** (tests unitarios, ver sección Testing) |

---

## Testing

### Unit tests — `tests/unit/test_inpainter.py`

Se mockea `SimpleLama` para aislar la lógica del módulo sin descargar el modelo:

```python
from unittest.mock import MagicMock, patch
from PIL import Image
import pytest


@pytest.fixture
def rgb_image():
    return Image.new("RGB", (1080, 1350), color=(128, 64, 32))


@pytest.fixture
def mask_image():
    return Image.new("L", (1080, 1350), 0)


def test_inpaint_calls_lama(rgb_image, mask_image):
    expected = Image.new("RGB", (1080, 1350), color=(10, 20, 30))
    mock_lama = MagicMock(return_value=expected)

    with patch("peo_promotion_center.backend.inpainter._lama", mock_lama):
        from peo_promotion_center.backend.inpainter import inpaint
        result = inpaint(rgb_image, mask_image)

    mock_lama.assert_called_once()
    assert result is expected


def test_inpaint_converts_mask_to_grayscale(rgb_image):
    rgba_mask = Image.new("RGBA", (1080, 1350), (255, 255, 255, 128))
    mock_lama = MagicMock(return_value=rgb_image)

    with patch("peo_promotion_center.backend.inpainter._lama", mock_lama):
        from peo_promotion_center.backend.inpainter import inpaint
        inpaint(rgb_image, rgba_mask)

    _, mask_arg = mock_lama.call_args[0]
    assert mask_arg.mode == "L"


def test_inpaint_none_mask_skipped_by_zip_builder():
    """zip_builder no debe llamar a inpaint si la máscara es None."""
    # Este test vive en el módulo de zip_builder; se incluye aquí como referencia.
    pass
```

### Consideraciones de integración

- No se escriben integration tests automáticos para inpainting porque requieren el modelo
  descargado (~200 MB) y tiempo de CPU significativo. La validación se hace manualmente.
- El modelo LaMa acepta imágenes de cualquier tamaño; no hay restricción de resolución.

---

## Rendimiento esperado

| Hardware | Tiempo por formato con máscara |
|---|---|
| CPU moderna (8 cores) | 5–15 segundos |
| GPU (CUDA, si disponible) | < 2 segundos |

`simple-lama-inpainting` usa CUDA automáticamente si `torch` detecta GPU disponible;
de lo contrario cae a CPU sin configuración adicional.

El inpainting sólo se ejecuta al generar el ZIP (sección 5), no al guardar la máscara,
por lo que la interacción con el canvas es siempre fluida.

---

## Limitaciones conocidas

- **Zonas muy grandes**: El modelo puede generar artefactos si la máscara cubre más del 50 %
  del área de la imagen. Para esos casos se recomienda borrar por partes.
- **Bordes de canvas**: LaMa puede tener menor calidad en los bordes extremos de la imagen.
- **Primera ejecución**: La descarga del modelo tarda ~30–60 segundos según la conexión.
  Esto ocurre al generar el primer ZIP con inpainting; el canvas de dibujo es siempre
  instantáneo.
