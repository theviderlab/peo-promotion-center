# Tag Overlay

Permite superponer uno o más PNGs (tags/overlays) sobre la imagen final del formato
**Post**. Cada overlay puede activarse/desactivarse de forma independiente y el usuario
ajusta su posición mediante coordenadas X / Y del píxel superior izquierdo. El composite
respeta el canal alpha de cada tag.

---

## Alcance de formatos

| Formato | Soporta overlay |
|---|---|
| **Post** | ✅ Sí |
| Historia | ❌ No (por ahora) |
| Google | ❌ No (por ahora) |

El sistema está parametrizado por formato mediante la constante `OVERLAY_FORMATS` en
`backend/compositing.py`. Habilitar overlays en un nuevo formato sólo requiere agregar
su `ImageFormat` a esa lista.

---

## Registro de tags disponibles

Los tags se definen en `TAG_REGISTRY`, una lista de `TagDefinition` en `backend/compositing.py`.

```python
@dataclass(frozen=True)
class TagDefinition:
    tag_id: str        # identificador único, p.ej. "circuito"
    label: str         # texto para mostrar en la UI
    path: Path         # ruta al PNG en assets/
    default_x: int     # posición X por defecto (píxel superior izquierdo)
    default_y: int     # posición Y por defecto
```

Registro actual:

| `tag_id` | `label` | Archivo | Dimensiones | Modo | `default_x` | `default_y` |
|---|---|---|---|---|---|---|
| `circuito` | "Tag Circuito" | `assets/tag-circuito.png` | 135 × 183 px | RGBA | 925 | 1147 |

La posición por defecto del tag `circuito` corresponde a la esquina inferior derecha con
margen de 20 px en el canvas Post (1080 × 1350):

```
default_x = 1080 - 135 - 20 = 925
default_y = 1350 - 183 - 20 = 1147
```

Todos los tags se usan en su **tamaño original** (sin escalar). El canal alpha del PNG
actúa como máscara del composite.

---

## Agregar un nuevo tag

1. Depositar el PNG en `assets/`.
2. Agregar una entrada a `TAG_REGISTRY` en `backend/compositing.py`:
   ```python
   TagDefinition(tag_id="verano", label="Tag Verano", path=ASSETS_DIR / "tag-verano.png", default_x=20, default_y=20)
   ```
3. El resto del sistema (UI, session state, pipeline, ZIP) lo recoge automáticamente.

---

## Posición

### Modelo de coordenadas

- `x` (int): coordenada horizontal del **píxel superior izquierdo** del tag, en píxeles del canvas de salida.
- `y` (int): coordenada vertical del **píxel superior izquierdo** del tag, en píxeles del canvas de salida.

### Controles en la UI

Dentro del expander **Post** en la sección "Recorte y refinamiento", cuando el canvas de
inpainting no está abierto, se renderiza una sección **Overlays** que itera sobre
`TAG_REGISTRY`. Por cada tag:

1. **Checkbox** `"<label>"` — activa / desactiva el overlay.
2. Cuando está activo, se muestran en la misma fila dos `st.number_input` para X e Y:
   - Rango X: `0` – `fmt.width - tag_width`.
   - Rango Y: `0` – `fmt.height - tag_height`.
   - Valores iniciales: `default_x`, `default_y` de la `TagDefinition`.
3. La preview refleja **todos** los overlays activos en tiempo real.
4. Los controles de overlay se ocultan mientras el canvas de inpainting está abierto.

---

## API de compositing (`backend/compositing.py`)

```python
@dataclass
class OverlaySpec:
    """Especificación de un overlay activo para aplicar sobre una imagen."""
    tag: Image.Image   # imagen RGBA del tag (precargada)
    x: int
    y: int


def apply_tag_overlay(
    base: Image.Image,
    tag: Image.Image,
    x: int,
    y: int,
) -> Image.Image:
    """
    Superpone `tag` (RGBA) sobre `base` en la posición (x, y).
    Convierte `base` a RGBA para el composite y devuelve RGB.
    Recorta el tag al área visible si desborda el canvas (sin error).
    """


def apply_overlays(
    base: Image.Image,
    overlays: list[OverlaySpec],
) -> Image.Image:
    """
    Aplica una lista de overlays sobre `base` en orden.
    Si `overlays` está vacío, retorna `base` sin modificar (mismo objeto).
    """
```

El pipeline siempre llama a `apply_overlays()` (incluso con lista vacía).

### Reglas de clipping

Si el tag en la posición (x, y) sobresale del canvas, se recorta al área visible y se
pega la porción recortada. No se lanza excepción.

---

## Pipeline de generación

El overlay se aplica como **última operación**, después del crop y del inpainting
opcional:

```
imagen fuente
    → scale_to_width()
    → crop_to_canvas()
    → pad_bottom()           (sólo Historia si la imagen es más corta)
    → apply_overlays()       ← overlays activos (lista puede estar vacía)
    → guardar PNG
```

Tanto `preview_format()` como `generate_format()` en `backend/image_processor.py`
aceptan el parámetro `overlays: list | None = None`.

---

## Estado de sesión

| Clave | Tipo | Descripción |
|---|---|---|
| `tag_overlays` | `dict[str, dict[str, dict]]` | Estado de cada overlay por formato y tag_id |

Estructura del dict anidado: `formato_slug → tag_id → {enabled, x, y}`.

```python
st.session_state.tag_overlays = {
    fmt.slug: {
        tag.tag_id: {"enabled": False, "x": tag.default_x, "y": tag.default_y}
        for tag in TAG_REGISTRY
    }
    for fmt in OVERLAY_FORMATS
}
```

Se inicializa en `frontend/session.py::_init_session()` via `_build_initial_tag_overlays()`
y se resetea al procesar un nuevo paquete.

---

## Invalidación del ZIP cacheado

El hash en `render_download_section()` incluye el estado completo de overlays:

```python
str(st.session_state.get("tag_overlays", {}))
```

Cualquier cambio en `enabled`, `x` o `y` para cualquier tag y formato provoca la
regeneración del ZIP.

---

## Archivos relevantes

| Archivo | Rol |
|---|---|
| `src/peo_promotion_center/backend/compositing.py` | `TagDefinition`, `TAG_REGISTRY`, `OVERLAY_FORMATS`, `OverlaySpec`, `apply_tag_overlay()`, `apply_overlays()` |
| `src/peo_promotion_center/backend/image_processor.py` | `preview_format()` y `generate_format()` reciben `overlays` |
| `src/peo_promotion_center/frontend/crop_refine_ui.py` | Sección "Overlays" en expander Post; `_render_overlay_section()`, `_build_overlay_specs()` |
| `src/peo_promotion_center/frontend/zip_builder.py` | `_build_overlay_specs_for_format()` construye `OverlaySpec` antes de guardar cada PNG |
| `src/peo_promotion_center/frontend/session.py` | `_build_initial_tag_overlays()` construye el estado inicial desde el registro |
| `src/peo_promotion_center/frontend/app.py` | Incluye `tag_overlays` en el hash del ZIP; pasa el estado a `build_zip` |
| `assets/tag-circuito.png` | PNG RGBA del tag inicial |
| `tests/unit/test_compositing.py` | Tests unitarios del módulo de compositing |

---

## Tests (`tests/unit/test_compositing.py`)

- `test_apply_tag_overlay_basic`: imagen base sólida + tag RGBA → píxeles en zona del tag con el color del tag.
- `test_apply_tag_overlay_clipping`: posición desbordante → no lanza excepción, recorta correctamente.
- `test_apply_overlays_empty`: lista vacía → retorna el mismo objeto de imagen sin modificar.
- `test_apply_overlays_multiple`: dos tags en posiciones distintas → ambos colores aparecen en el resultado.
- `test_apply_overlays_order`: el segundo overlay pinta encima del primero si se superponen.

---

## Extensibilidad futura

Para habilitar overlays en un nuevo formato (ej. Historia):

1. Agregar el `ImageFormat` deseado a `OVERLAY_FORMATS` en `compositing.py`.
2. El session state y la UI se generan dinámicamente a partir de esa lista; no se requiere
   ningún otro cambio.
