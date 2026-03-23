# Tag Overlay — Especificación de requerimiento

## Resumen

En la sección **"Recorte y refinamiento"**, dentro del expander del formato **Post**, se debe agregar la opción de superponer uno o más PNGs (tags/overlays) sobre la imagen final. Cada overlay puede activarse/desactivarse de forma independiente y el usuario ajusta su posición mediante coordenadas X / Y del píxel superior izquierdo. El merge respeta el canal alpha de cada tag. El diseño debe soportar de forma nativa múltiples overlays simultáneos sobre la misma imagen, y permitir agregar nuevos tipos de tags en el futuro sin modificar la lógica de composite.

---

## Alcance de formatos

| Formato | Soporta overlay |
|---|---|
| **Post** | ✅ Sí |
| Historia | ❌ No (por ahora) |
| Google | ❌ No (por ahora) |

El código debe diseñarse de forma que agregar overlay a otros formatos en el futuro sea trivial (parametrizar por `ImageFormat`, no hardcodear "post").

---

## Registro de tags disponibles

Los tags se definen en un **registro centralizado** (un diccionario o lista de `dataclass` en `backend/compositing.py`). Cada entrada describe un tag disponible:

```python
@dataclass(frozen=True)
class TagDefinition:
    tag_id: str        # identificador único, p.ej. "circuito"
    label: str         # texto para mostrar en la UI
    path: Path         # ruta al PNG en assets/
    default_x: int     # posición X por defecto (píxel superior izquierdo)
    default_y: int     # posición Y por defecto
```

Registro inicial:

| `tag_id` | `label` | Archivo | Dimensiones | Modo | `default_x` | `default_y` |
|---|---|---|---|---|---|---|
| `circuito` | "Tag Circuito" | `assets/tag-circuito.png` | 135 × 183 px | RGBA | 925 | 1147 |

Para agregar un nuevo tag sólo hay que añadir una entrada a este registro y depositar el PNG en `assets/`. El resto del sistema lo recoge automáticamente.

Todos los tags se usan en su **tamaño original** (sin escalar). El canal alpha del PNG es la máscara del composite: alpha=0 es completamente transparente, alpha=255 es opaco.

---

## Posición

### Modelo de coordenadas

- `tag_x` (int): coordenada horizontal del **píxel superior izquierdo** del tag, en píxeles del canvas de salida (referencia: 0 = borde izquierdo).
- `tag_y` (int): coordenada vertical del **píxel superior izquierdo** del tag, en píxeles del canvas de salida (referencia: 0 = borde superior).

### Posición por defecto

Cada `TagDefinition` define su propio par `(default_x, default_y)`. Para el tag inicial `circuito`, la posición es esquina inferior derecha con margen de 20 px:

```
default_x = 1080 - 135 - 20 = 925
default_y = 1350 - 183 - 20 = 1147
```

### Controles en la UI

Dentro del expander **Post** en "Recorte y refinamiento", se renderiza una sección **"Overlays"** que itera sobre todos los tags registrados. Por cada tag:

1. **Checkbox** `"<label>"` — activa / desactiva ese overlay.
2. Cuando está activo, se muestran en la misma fila dos `st.number_input` para X e Y:
   - Rango X: `0` – `fmt.width - tag.width` (para no salir del canvas).
   - Rango Y: `0` – `fmt.height - tag.height`.
   - Valores iniciales: `default_x`, `default_y` de la `TagDefinition`.
3. Múltiples overlays pueden estar activos simultáneamente; cada uno tiene su propio checkbox y controles.
4. La preview debe reflejar **todos** los overlays activos en tiempo real.

---

## Pipeline de generación

El overlay se aplica como **última operación**, después del crop y del inpainting opcional:

```
imagen fuente
    → scale_to_width()
    → crop_to_canvas()
    → (inpainting opcional)
    → apply_tag_overlay()   ← nueva función
    → guardar PNG
```

El módulo `backend/compositing.py` expone dos funciones principales:

```python
def apply_tag_overlay(
    base: Image.Image,
    tag: Image.Image,
    x: int,
    y: int,
) -> Image.Image:
    """
    Superpone `tag` (RGBA) sobre `base` en la posición (x, y).

    El canal alpha del tag se usa como máscara. La imagen base
    se convierte a RGBA para el composite y se devuelve como RGB.
    Maneja clipping si el tag desborda los bordes del canvas.
    """


@dataclass(frozen=True)
class OverlaySpec:
    """Especificación de un overlay activo para aplicar sobre una imagen."""
    tag: Image.Image   # imagen RGBA del tag (precargada)
    x: int
    y: int


def apply_overlays(
    base: Image.Image,
    overlays: list[OverlaySpec],
) -> Image.Image:
    """
    Aplica una lista de overlays sobre `base` en orden.

    Permite superponer múltiples tags en la misma imagen.
    Si `overlays` está vacío, retorna `base` sin modificar.
    """
```

El pipeline llama siempre a `apply_overlays()` (incluso con lista vacía), lo que garantiza que la firma no cambie al agregar más tags.

### Reglas de clipping

Si el tag en la posición (x, y) sobresale del canvas (parcialmente fuera de los bordes), se recorta el tag al área visible. No se lanza error, simplemente se pega la porción visible.

---

## Estado de sesión (nuevas claves)

El estado de los overlays se modela como un diccionario anidado: `formato → tag_id → estado`.

| Clave | Tipo | Valor inicial | Descripción |
|---|---|---|---|
| `tag_overlays` | `dict[str, dict[str, OverlaySessionState]]` | ver abajo | Estado de cada overlay, por formato y por tag_id |

`OverlaySessionState` es un dict simple (no dataclass, para compatibilidad con session_state de Streamlit):

```python
{
    "enabled": False,
    "x": <default_x de TagDefinition>,
    "y": <default_y de TagDefinition>,
}
```

Valor inicial construido dinámicamente a partir del registro de tags:

```python
st.session_state.tag_overlays = {
    fmt.slug: {
        tag.tag_id: {"enabled": False, "x": tag.default_x, "y": tag.default_y}
        for tag in TAG_REGISTRY
    }
    for fmt in OVERLAY_FORMATS  # formatos que soportan overlay, hoy solo POST
}
```

Esto garantiza que al agregar un nuevo tag al registro, el estado se inicializa automáticamente sin tocar otro código.

Se inicializa en `frontend/session.py` junto con el resto del estado.

---

## Invalidación del ZIP cacheado

El hash en `render_download_section()` debe incluir el estado completo de todos los overlays:

```python
str(st.session_state.tag_overlays)
```

Como `tag_overlays` es un dict anidado serializable a string, captura de forma íntegra cualquier cambio en enabled/x/y para cualquier tag y formato.

---

## Archivos a modificar

| Archivo | Cambio |
|---|---|
| `backend/compositing.py` | **Nuevo módulo.** Contiene `TagDefinition`, `TAG_REGISTRY`, `OverlaySpec`, `apply_tag_overlay()`, `apply_overlays()` |
| `backend/image_processor.py` | Importar y llamar `apply_overlays()` en `generate_format()` y `preview_format()` |
| `frontend/crop_refine_ui.py` | Sección "Overlays" en el expander Post: iterar `TAG_REGISTRY`, checkbox + X/Y por tag; aplicar en preview |
| `frontend/zip_builder.py` | Recibir `tag_overlays` dict y construir lista de `OverlaySpec` antes de guardar el PNG |
| `frontend/session.py` | Inicializar `tag_overlays` a partir del registro dinámico |
| `frontend/app.py` | Pasar `tag_overlays` a `build_zip`; incluirlo en el hash del ZIP; resetear en nuevo scrape |

---

## Extensibilidad futura

Para agregar un nuevo tag (ej. `tag-verano.png`) bastará con:

1. Depositar el PNG en `assets/`.
2. Agregar una entrada a `TAG_REGISTRY` en `backend/compositing.py`:
   ```python
   TagDefinition(tag_id="verano", label="Tag Verano", path=ASSETS_DIR / "tag-verano.png", default_x=20, default_y=20)
   ```
3. El resto del sistema (UI, session state, pipeline, ZIP) lo recoge automáticamente sin más cambios.

Para habilitar overlays en un nuevo formato (ej. Historia):

1. Agregar el `ImageFormat` a la constante `OVERLAY_FORMATS` en `compositing.py`.
2. El session state y la UI se generan dinámicamente a partir de esa lista.

No se requiere modificar la lógica de composite ni el pipeline de generación.

---

## Tests

### Unit tests (nuevos en `tests/unit/test_compositing.py`)

- `test_apply_tag_overlay_basic`: imagen base sólida + tag RGBA → verifica píxeles en zona del tag.
- `test_apply_tag_overlay_clipping`: posición que hace que el tag desborde el borde → no lanza excepción, recorta.
- `test_apply_overlays_empty`: lista vacía de overlays → imagen de salida idéntica a la entrada.
- `test_apply_overlays_multiple`: dos tags activos en posiciones distintas → ambos aparecen en el resultado.
- `test_apply_overlays_order`: el segundo overlay se pinta encima del primero si se superponen (orden de lista).

### Tests de integración

No se requieren nuevos tests de integración para esta feature.
