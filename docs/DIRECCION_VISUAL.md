# Reino Commerce — Dirección visual (v2)

Sistema visual propio de la plataforma. **Reino Commerce es la marca paraguas**;
Wiener Kingdom y Estudio Nube son tiendas inquilinas con su identidad por tema
(color, tipografía, forma, hero, módulos) publicada por versión.

## Fundamentos

| Token | Valor WK (tema publicado) | Rol |
|---|---|---|
| `--rk-bg` | `#FFF7EE` (crema cálido) | fondo |
| `--rk-ink` | `#241E3F` (tinta violeta) | texto |
| `--rk-primary` | `#6C4CF1` (violeta Reino) | acción |
| `--rk-on_primary` | `#FFFFFF` validado ≥ 4.5:1 por par | texto sobre acción |
| `--rk-accent` | `#C6F24E` (lima) | acento/insignias |
| `--rk-card` | `#FFFFFF` | superficie |
| `--rk-line` | `#E9E2F5` | bordes |
| `--rk-btn-radius` | `999px` por defecto; el tema puede usar radios rectos | forma real de botones |

Tipografías: **Fraunces** (display, auto-hospedada woff2) + **Manrope** (texto).
Estudio Nube publica su propio par tipográfico y paleta por versión de tema.

## Reglas de componentes (página viva: `/plataforma/componentes/`)

1. **Botones**: una acción principal por bloque; la forma sale de
   `--rk-btn-radius` (la elección «forma de botones» del estudio tiene efecto
   real); hover nunca oscurece sobre acento (contraste validado del par
   primary/on_primary ≥ 4.5:1 — se rechazan combinaciones ilegibles).
2. **Tarjetas**: producto y tienda comparten esqueleto (`_product_card`,
   `_store_card`); foto real o placeholder declarado, jamás stock falso.
3. **Insignias/estados**: `rk-badge`, `rk-chip`, `rk-stock--ok|low|out`;
   los estados vacíos son honestos y ofrecen siguiente paso.
4. **Formularios**: `rk-field` + `rk-choice` (radios/checkbox como tarjetas
   seleccionables); errores por campo, sin toasts efímeros para errores de
   validación.
5. **Movimiento**: stop-motion con `steps()` (`rk-crown-bounce`, `rk-pop`,
   `rk-seal`); `prefers-reduced-motion` respeta el sistema y el conmutador
   persistente «Reducir movimiento» (localStorage) lo fuerza en todo.

## Movimiento

- Coronas/sellos «estampados» con steps (2–3 fotogramas), no transiciones
  suaves: el carácter es *artesanal*, no *líquido*.
- Todo movimiento desaparece con movimiento reducido (media query + toggle).
- Evidencia: `docs/capturas/movimiento_hero_wk.webm` (ronda 3),
  `shots4/movimiento_reducido_movil.png` (ronda 4).

## Responsive

- Comparador verificado en 390×844: tarjetas apiladas con scroll horizontal,
  acciones visibles, insignia de «mejor … entre estas opciones» (evidencia
  `shots4/comparar_movil.png`).
- Navegación móvil con menú; footer con el conmutador de movimiento siempre
  alcanzable.
