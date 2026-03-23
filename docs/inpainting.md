# Inpainting

Permite al usuario borrar regiones de una imagen (logos, textos indeseados, marcas de agua)
en cada formato de salida de forma independiente, dentro de la sección de recorte y
refinamiento. El relleno de las zonas borradas se genera con el modelo **LaMa** ejecutado
localmente, sin enviar imágenes a servicios externos.

---

## Fundamento del diseño

El inpainting opera **sobre la imagen ya recortada de cada formato**, no sobre la fuente
original:

- Cada formato tiene dimensiones y recorte distintos: un logo visible en el borde inferior
  del Post puede no aparecer en Historia o Google.
- Historia nunca recorta verticalmente (la imagen se extiende con padding de color);
  modificar la fuente antes del recorte borraría contenido visible en otros formatos.
- El usuario conoce qué quiere eliminar sólo después de ver el recorte final de cada
  formato.

---

## Tecnología

| Componente | Librería / Modelo |
|---|---|
| Modelo de inpainting | **LaMa** vía `simple-lama-inpainting` (~200 MB, auto-descargable) |
| Canvas de dibujo UI | Componente HTML/JS propio en `frontend/canvas_component/` |

El modelo se descarga automáticamente en `~/.cache/simple-lama` la primera vez que se
instancia `SimpleLama()` y queda cacheado a partir de entonces.

---

## Posición en el flujo de la app

El inpainting está integrado dentro de la **Sección 2 — Recorte y refinamiento**, no como
sección separada. Cada formato expone un botón **✏️ Editar** que abre el canvas de dibujo
dentro del mismo expander.

```
Sección 1 — URL del paquete     → descarga imagen fuente
Sección 2 — Recorte y refinamiento
    ├── Slider de posición de recorte (por formato)
    ├── Overlays activos (sólo Post)
    ├── Preview de la imagen recortada
    └── [✏️ Editar] → canvas de inpainting on-demand
Sección 3 — Contenido generado  → copy de IA editable
Sección 4 — Descarga            → genera y descarga el ZIP
```

---

## Módulo backend: `backend/inpainter.py`

Responsabilidad única: aplicar inpainting a una imagen PIL dada una máscara PIL.

```python
_lama: SimpleLama | None = None

def get_lama() -> SimpleLama:
    """Singleton de SimpleLama. Parchea torch.jit.load para forzar carga en CPU."""
    ...

def inpaint(image: Image.Image, mask: Image.Image) -> Image.Image:
    """Borra la región marcada en mask (blanco=255) y rellena con LaMa."""
    return get_lama()(image, mask.convert("L"))
```

**Nota de implementación**: la versión instalada de `simple-lama-inpainting` llama a
`torch.jit.load` sin `map_location`, lo que puede fallar cuando el modelo fue serializado
en CUDA y el entorno actual no tiene soporte CUDA completo. `get_lama()` parchea
temporalmente `torch.jit.load` durante la inicialización para forzar la carga en CPU, y
restaura la función original al terminar.

El singleton `_lama` evita recargar el modelo en cada llamada. La función `inpaint` es
stateless: recibe PIL Images y devuelve PIL Image.

---

## Flujo de usuario (por formato)

```
1. Usuario abre el expander del formato en Sección 2
2. Presiona "✏️ Editar" → se abre el canvas sobre la imagen actual
3. Pinta la zona a borrar con el pincel
4. Presiona "Aplicar" → LaMa procesa la imagen → resultado en estado "pendiente"
5. Decides "✅ Aceptar" o "❌ Rechazar"
   - Aceptar: la imagen procesada queda como "final" para ese formato;
              el slider de recorte se bloquea hasta resetear
   - Rechazar: se descarta el resultado pendiente
6. Con inpainting aceptado, se puede volver a editar (reintentos acumulables)
7. "Deshacer" revierte al estado final anterior (historial por formato)
8. "🔄 Resetear" descarta todo el inpainting del formato y reactiva el slider
```

---

## Estado de sesión

| Clave | Tipo | Descripción |
|---|---|---|
| `inpainted_finals` | `dict[str, Image.Image \| None]` | Última imagen aceptada por formato (o `None`) |
| `inpaint_pending` | `dict[str, Image.Image \| None]` | Resultado esperando aceptación/rechazo |
| `inpaint_history` | `dict[str, list[Image.Image]]` | Historial de imágenes finales para "Deshacer" |
| `canvas_open` | `dict[str, bool]` | Si el canvas está visible en cada formato |

Todas se inicializan en `frontend/session.py::_init_session()` y se resetean a sus valores
vacíos cuando el usuario procesa un nuevo paquete.

### Detalle de las claves de `session_state`

```python
st.session_state.inpainted_finals  = {"post": None, "historia": None, "google": None}
st.session_state.inpaint_pending   = {"post": None, "historia": None, "google": None}
st.session_state.inpaint_history   = {"post": [],   "historia": [],   "google": []}
st.session_state.canvas_open       = {"post": False, "historia": False, "google": False}
```

---

## Integración en `frontend/crop_refine_ui.py`

Toda la lógica de UI de inpainting vive en este módulo (no hay un módulo `inpaint_ui.py`
separado), junto con el recorte y los overlays.

- **`_render_pending_state(fmt)`**: muestra el resultado pendiente y los botones Aceptar/Rechazar.
- **`_render_canvas_editor(fmt, ref_img, …)`**: renderiza el canvas HTML/JS, el pincel,
  y los botones Aplicar / Deshacer / Cerrar editor.
- El canvas HTML/JS personalizado (`canvas_component/index.html`) recibe la imagen como
  data URL y devuelve la máscara pintada también como data URL. `_data_url_to_mask()`
  la convierte a PIL en resolución final del formato usando `Image.NEAREST`.

---

## Integración en `frontend/zip_builder.py`

`build_zip` recibe las imágenes ya procesadas (no las máscaras). Si un formato tiene
imagen aceptada, se usa directamente sin re-ejecutar LaMa:

```python
def build_zip(
    ...,
    inpainted_images: dict[str, Image.Image | None] | None = None,
    tag_overlays: dict[str, dict[str, dict]] | None = None,
) -> bytes:
```

Para cada formato:
- Si `inpainted_images[fmt.slug]` no es `None` → usar esa imagen (con overlays si hay).
- En caso contrario → ejecutar `generate_format()` desde la fuente.

---

## Integración en `frontend/app.py`

```python
# render_download_section(): hash incluye el estado de inpainted_finals
finals_hash = str({
    k: (v.tobytes() if v is not None else None)
    for k, v in st.session_state.get("inpainted_finals", {}).items()
})
current_hash = hashlib.md5("|".join([..., finals_hash, ...]).encode()).hexdigest()

# Llamada a build_zip:
build_zip(
    ...,
    inpainted_images=st.session_state.get("inpainted_finals"),
    tag_overlays=st.session_state.get("tag_overlays"),
)
```

---

## Flujo de datos completo

```
Sección 2 — Recorte y refinamiento
    preview_format(source, fmt, offset)
        │  → PNG bytes
        ▼
    Canvas HTML/JS ──► data URL de la máscara pintada
        │
        _data_url_to_mask() → PIL mask en resolución del formato
        │
        inpainter.inpaint(ref_img, mask) → imagen procesada (pending)
        │
        [Aceptar] → session_state.inpainted_finals[slug] = resultado
        │
Sección 4 — Descarga
    build_zip(inpainted_images=inpainted_finals, …)
        │
        por formato con imagen aceptada:
            apply_overlays(img, overlays)  → img final
            img.save(out_path)
        │
        ▼
    ZIP en memoria → st.download_button
```

---

## Archivos relevantes

| Archivo | Rol |
|---|---|
| `src/peo_promotion_center/backend/inpainter.py` | Lógica de inpainting (singleton LaMa, workaround CPU) |
| `src/peo_promotion_center/frontend/crop_refine_ui.py` | UI: canvas, pendiente, historial, reset |
| `src/peo_promotion_center/frontend/canvas_component/index.html` | Componente HTML/JS del canvas de dibujo |
| `src/peo_promotion_center/frontend/session.py` | Inicialización de claves de sesión |
| `src/peo_promotion_center/frontend/app.py` | Hash del ZIP, reset en nuevo paquete, llamada a `build_zip` |
| `src/peo_promotion_center/frontend/zip_builder.py` | Uso de `inpainted_images` en la generación del ZIP |
| `tests/unit/test_inpainter.py` | Tests unitarios (LaMa mockeado) |

---

## Tests (`tests/unit/test_inpainter.py`)

Se mockea `SimpleLama` para aislar la lógica sin descargar el modelo:

- `test_inpaint_calls_lama`: `inpaint()` delega en la instancia LaMa y retorna su resultado.
- `test_inpaint_converts_mask_to_grayscale`: la máscara se convierte a modo `"L"` antes de pasarla a LaMa.
- `test_inpainted_images_bypasses_generate_format`: con imagen aceptada, `build_zip` no vuelve a llamar a `generate_format`.

No se escriben integration tests automáticos porque requieren el modelo (~200 MB) y tiempo
de CPU significativo. La validación se realiza manualmente.

---

## Rendimiento esperado

| Hardware | Tiempo por formato con inpainting |
|---|---|
| CPU moderna (8 cores) | 5–15 segundos |
| GPU (CUDA, si disponible) | < 2 segundos |

`simple-lama-inpainting` usa CUDA automáticamente si `torch` detecta GPU disponible;
de lo contrario opera en CPU sin configuración adicional.

El inpainting sólo se ejecuta al presionar **Aplicar** en el canvas, no al generar el ZIP
(se guardan las imágenes ya procesadas), por lo que la descarga es siempre rápida.

---

## Limitaciones conocidas

- **Zonas muy grandes**: El modelo puede generar artefactos si la máscara cubre más del 50 %
  del área de la imagen. Se recomienda borrar por partes.
- **Bordes de canvas**: LaMa puede tener menor calidad en los bordes extremos de la imagen.
- **Primera ejecución**: La descarga del modelo tarda ~30–60 segundos según la conexión.
  Las ejecuciones posteriores usan la caché local.
