# BRAND_SYSTEM — Wiener Kingdom (design tokens + identidad)

> Fuente de verdad visual: lámina Canva seleccionada por el equipo
> `docs/proposal/assets/marca_oficial_canva.png` y `smart_fit_editorial.png`.
> Los SVG antiguos de dachshund/caricaturas NO se reutilizan.

## 1. Nombre
- Aprobado: **Wiener Kingdom**.
- ⚠️ Pendiente de acuerdo: plantillas originales usan "Weiner Kingdom"; corregir spelling solo en PR de textos con aprobación.

## 2. Paleta (tokens CSS propuestos)
| Token | Hex | Uso |
|---|---|---|
| `--wk-navy` | #101E36 | fondo primario, header |
| `--wk-carmine` | #AF3635 | acentos, CTAs |
| `--wk-burgundy` | #842F34 | hover/estados |
| `--wk-steel` | #366A91 | secundarios, enlaces |
| `--wk-silver` | #C5CBD5 | bordes, divisores |
| `--wk-ivory` | #FAF8F6 | fondo claro, texto sobre navy |

> Nota: el Atlas (cap. 18) lista otra paleta (Obsidian #20151E, Midnight #0C2949, Crimson #AE2D28, Signal red #D74637, Electric blue #3078A3, Steel #7F94A8, Silver #C3CCD4). **Resolver conflicto:** la lámina Canva es la referencia oficial provisional; registrar decisión del equipo.

## 3. Tipografía (propuesta)
- Display: serif premium (fallback Georgia/"Times New Roman").
- Body: sans legible (system-ui / -apple-system / Segoe UI).
- Escala fluida con `clamp()`; contraste AA mínimo 4.5:1 texto, 3:1 UI.

## 4. Logo
- Concepto: corona geométrica + silueta dachshund (sin personajes/marcas de terceros).
- Entregable: lámina Canva oficial; no reinventar aquí.

## 5. Fotografía (regla dura)
- Usar las fotos reales del catálogo original cuando estén disponibles.
- Fallback honesto (placeholder etiquetado "imagen no disponible"), NUNCA imágenes generadas presentadas como fotos del producto.
- Revisar peso de imágenes (algunas 300–450KB) para Core Web Vitals.

## 6. Voz de marca
- "Commerce, reimagined." / "Descubre más. Compra mejor."
- Tono premium, honesto, sin urgencia manipuladora, sin ratings inventados.

## 7. Accesibilidad de marca
- Contraste sobre #101E36 y #AF3635 verificado (WCAG AA).
- Foco visible, reduced-motion, navegación por teclado.