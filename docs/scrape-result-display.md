# Especificación: Visualización del resultado del scraping

## Contexto

El scraper extrae metadata del paquete turístico (nombre, descripción, destinos, precio, duración, incluye, no incluye) y la usa internamente para generar contenido con IA. Sin embargo, el usuario no tiene visibilidad de qué se extrajo. Esta especificación define dos mejoras a la sección 1 de la UI.

---

## Mejora 1: Link para abrir la URL en nueva pestaña

### Comportamiento

- Se muestra **solo después de un scraping exitoso**, no antes ni durante la carga.
- Se coloca debajo del formulario de URL, en la misma sección 1.
- Al hacer clic abre la URL procesada en una nueva pestaña del navegador.

### Implementación

Usar `st.link_button` de Streamlit (disponible desde v1.27) con la URL almacenada en `st.session_state.scrape_result` (la URL original se puede recuperar del session_state o guardarse explícitamente al momento del submit).

```python
# Después del form, si hay scrape_result exitoso:
st.link_button("🔗 Ver paquete en OPE", url=st.session_state.last_url, use_container_width=False)
```

> **Nota**: la URL ingresada por el usuario debe guardarse en `st.session_state.last_url` al momento del submit para poder mostrarla luego fuera del form.

---

## Mejora 2: Expandible con los datos extraídos del scraping

### Comportamiento

- Se muestra **solo después de un scraping exitoso**, en la misma sección 1, debajo del link de apertura.
- Está **colapsado por defecto** (`expanded=False`).
- Los campos son **solo lectura** — no se permite edición. El usuario puede verificar qué extrajo el scraper pero no modificar los valores.
- Si un campo está vacío (el scraper no encontró el dato), se muestra el texto `—` en su lugar.

### Campos a mostrar

| Campo | Label en UI |
|---|---|
| `nombre_paquete` | Nombre del paquete |
| `frecuencia` | Frecuencia |
| `destinos` | Destinos |
| `precio` | Precio |
| `duracion` | Duración |
| `incluye` | Incluye |
| `no_incluye` | No incluye |

> El campo `image_path` y `slug` son internos y no se muestran.

### Layout

Usar `st.expander` con el label **"Datos extraídos del paquete"** y `expanded=False`. Dentro, renderizar los campos como pares label/valor usando `st.markdown` o columnas de Streamlit. Sugerencia de layout:

```
┌─ Datos extraídos del paquete ──────────────────────────┐
│  Nombre del paquete   Punta del Este Completo 7 noches  │
│  Frecuencia           Lunes y viernes                   │
│  Destinos             Punta del Este                    │
│  Precio               USD 1.200                         │
│  Duración             7 noches / 8 días                 │
│  Incluye              Vuelos, hotel, desayuno           │
│  No incluye           Cenas, traslados internos         │
└─────────────────────────────────────────────────────────┘
```

### Implementación sugerida

Extraer la lógica de renderizado a una función privada `_render_scrape_metadata(sr: ScrapeResult) -> None` dentro de `app.py` o en un módulo auxiliar si `app.py` supera el límite de 150 líneas.

```python
def _render_scrape_metadata(sr: ScrapeResult) -> None:
    """Muestra los metadatos extraídos del paquete en un expander colapsado."""
    with st.expander("Datos extraídos del paquete", expanded=False):
        fields = [
            ("Nombre del paquete", sr.nombre_paquete),
            ("Frecuencia", sr.frecuencia),
            ("Destinos", sr.destinos),
            ("Precio", sr.precio),
            ("Duración", sr.duracion),
            ("Incluye", sr.incluye),
            ("No incluye", sr.no_incluye),
        ]
        for label, value in fields:
            col_label, col_value = st.columns([1, 2])
            with col_label:
                st.markdown(f"**{label}**")
            with col_value:
                st.markdown(value or "—")
```

---

## Ubicación en el flujo de la UI

```
Sección 1: URL del paquete
  [input URL]  [Procesar paquete]

  ← solo tras scraping exitoso →
  🔗 Ver paquete en OPE
  ▶ Datos extraídos del paquete   ← colapsado
─────────────────────────────────
Sección 2: Recorte y refinamiento
  ▶ Post (1080×1080)
  ▶ Historia (1080×1920)
  ▶ Google (...)
─────────────────────────────────
Sección 3: Contenido generado por IA
...
```

---

## Archivos a modificar

| Archivo | Cambio |
|---|---|
| `src/peo_promotion_center/frontend/app.py` | Guardar `last_url` en session_state; agregar `st.link_button` y llamada a `_render_scrape_metadata` en `render_url_section`; definir `_render_scrape_metadata`. |

---

## Criterios de aceptación

- [ ] El link "Ver paquete en OPE" no aparece si no hay scraping previo exitoso.
- [ ] El link abre la URL en nueva pestaña (comportamiento nativo de `st.link_button`).
- [ ] El expander aparece colapsado tras el scraping.
- [ ] Los campos son solo lectura.
- [ ] Los campos vacíos muestran `—` en lugar de cadena vacía.
- [ ] Los unit tests de `test_app.py` cubren que `_render_scrape_metadata` se llama cuando `scrape_result` existe y no cuando es `None`.
