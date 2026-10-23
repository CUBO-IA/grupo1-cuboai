# 06 · Negocio y demostración (F10)

## Hipótesis económicas (sin cambios respecto del diseño; NO aprobadas)

| Plan | Mensualidad | Comisión sobre mercancía elegible neta cobrada |
|---|---|---|
| Starter | $0 | 7 % |
| Growth | $29 | 3.5 % |
| Pro | $99 | 1.5 % |
| Enterprise | Por acordar | Por acordar |

Puntos de cruce (aritmética del diseño): Growth < Starter sobre GMV mensual ≈ $828.57;
Pro < Growth sobre $3,500. Ninguna suscripción se cobra en la demostración. La cuota de IA
será transparente y con avisos; agotarla no bloquea pedidos ni oculta el catálogo.
TAM/SAM/SOM: tareas de validación comercial (censo, países, adopción) — no se completan
con imaginación. Objetivo operativo de piloto: cohorte de 10 comercios invitados.

## Guion de demostración (5 minutos) — ejecutable con esta build

| Tiempo | Acción | Qué demuestra |
|---|---|---|
| 0:00–0:25 | Abrir `/tiendas/` y entrar a Wiener Kingdom | Dos comercios, una plataforma; problema real (talla de dachshund) |
| 0:25–0:50 | Home + ficha de Wedding Dog | Diseño Royal Editorial, precio/variantes reales, «¿Qué talla le queda?» |
| 0:50–1:40 | LookLab completo: perfil Bruno → medidas (40/26/32 cm) → Royal Classic → Celebración → revelación | Selección explicada por códigos; total; talla por regla publicada |
| 1:40–2:35 | Royal Stylist: «algo elegante para Bruno, máximo $80» | Con clave: IA real con herramientas. Sin clave: **declarar** el modo reglas (etiqueta visible) y mostrar que la selección por reglas consulta el catálogo real |
| 2:35–3:15 | Carrito → checkout → «Crear pedido pendiente de pago» | Importes reconstruidos en servidor; pago honesto pendiente de verificación; enlace privado al pedido |
| 3:15–3:45 | Panel `/negocio/wiener-kingdom/`: pedido nuevo, verificar pago (transición), estados separados | Operación real con auditoría (actor registrado) |
| 3:45–4:20 | Estudio Nube Demo: catálogo distinto + intento de abrir panel ajeno con staff de Nube → 403 | Aislamiento entre tiendas |
| 4:20–4:45 | `/para-negocios/`: tarifas marcadas como hipótesis del piloto | Modelo de negocio sin vender humo |
| 4:45–5:00 | Cierre: «Wiener Kingdom es nuestro primer reino» | Visión Reino Commerce |

**Contingencia:** si falla internet o la IA, la tienda sigue operando (reglas etiquetadas);
NUNCA sustituir una falla de IA con una respuesta simulada sin avisar. Datos de prueba
rotulados («Tienda demo» en Estudio Nube; pedidos de ensayo visibles en panel).

## Roadmap por condiciones (resumen del diseño)

- **Año 1:** esta build + piloto con comercios invitados. Condición: pedidos satisfechos,
  aislamiento probado, coste IA medido.
- **Año 2:** onboarding/CSV, branding por tienda, 1–2 categorías más, pasarela regional.
- **Año 3:** marketplace público por región (pagos/contratos/logística verificados).
- **Años 4–5:** agentes delegados con autorización por alcance; expansión selectiva.

## Limitaciones honestas de esta entrega

1. IA real: **implementada, pendiente de clave** (puerta §2 no cerrada). El modo reglas
   está etiquetado y no cuenta como IA.
2. Pagos: manual + Bitcoin manual; **sin pasarela electrónica** (elegibilidad SV por confirmar).
3. Concurrencia probada en SQLite; PostgreSQL/RLS en staging pendiente.
4. Editor de catálogo y alta de comercio guiada: P1 (alta P0 por seed/invitación).
5. Capturas: ver STATUS.md; auditoría de accesibilidad manual pendiente.
6. Tarifa de envío San Salvador $3.50: hipótesis pendiente de aprobación del negocio.
