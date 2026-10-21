# Wiener Kingdom — Concept Experience Lab

Standalone visual demo; intentionally **not integrated** into the existing Django application at `web/`.

## Open
Open `index.html` in a browser. No build step. Data stored in localStorage.

## Try
- Collection search and category filters, add to cart, edit quantities.
- Local checkout and example order creation (NO actual payments).
- Studio inventory and products; Pulse sample analytics; Flow local rules; Concierge canned responses.
- Fully responsive layout and original SVG dachshund product illustrations.

## Source of content
Reference product names and base prices reflect the reviewed upstream `web/tienda/catalog.py`, October 17 2026. Images are original concept illustrations, not actual product photography, and inventory is invented for the demo. Actual merchant pricing and available products must be confirmed in the real system.

## Never confuse with production
Smart Fit and Smart Quote on Django are NOT connected to this standalone UI. No server-side persistence, PSP, order emails, logistics, seller accounts or AI model in this preview.

## Future work
Integrate **one Django page at a time** in a separate feature branch, preserve existing URLs, CSRF and tests, and compare the before/after checkout behavior. No merging without team review.


### Sistema gráfico (revisado)
Logo principal: recorte de la lámina Canva elegida. Hero: arte editorial aprobado de Smart Fit. Fichas: fotografías del catálogo real en el repositorio público cuando Chrome tenga conexión; si no, tarjetas visuales abstractas sin perros falsos. Todo el checkout de esta demo es simulado.
