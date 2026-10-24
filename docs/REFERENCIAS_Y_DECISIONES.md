# Referencias y decisiones de implementación

Fecha de consulta: 2026-10-22/23 (sandbox Fluso).

## Fuentes del documento de diseño (R1–R15) y su aplicación real

| Ref | Uso en esta build |
|---|---|
| R1 OpenAI function calling | `reino/ai/schemas.py`: especificaciones de herramientas; orquestador con rondas acotadas |
| R2 Django QuerySet API | `select_for_update` en `services_commerce` (transacciones cortas, orden estable) |
| R3 PostgreSQL RLS | **Planificado para staging** (documentado en 02/05); no activado en SQLite |
| R4 WCAG 2.2 | Criterios aplicados en CSS/markup; auditoría manual pendiente (declarado) |
| R5 Core Web Vitals | Umbrales citados como objetivo; no medidos en sandbox |
| R6 BTCPay | Referencia para F8; no integrado (P1) |
| R7/R8 Stripe availability/Connect | Elegibilidad SV **pendiente**; ningún cobro electrónico habilitado |
| R9 Shippo capabilities | Sin integración logística; matriz de zonas manual P0 |
| R10 Merchant listing | Datos estructurados: pendiente P1 (URLs estables ya existen) |
| R11/R12 Apple/Linear | Referencia estructural de mensajes breves; composición y textos originales |
| R13–R15 Shopify/WooCommerce/Tiendanube | «Tenemos IA» no se presenta como diferenciador; la prueba es el tiempo hasta una variante compatible explicada |

## Licencias de tipografía (verificado al incluir)

- **Fraunces** (titulares): SIL Open Font License 1.1 — familia variable de Undercasetype,
  distribuida por Google Fonts. Subconjuntos latin vendorados en `static/reino/fonts/`.
- **Manrope** (texto/UI): SIL Open Font License 1.1 — de Michael Sharanda, Google Fonts.
- Ambas permiten uso comercial y redistribución con licencia incluida; se recomienda
  copiar el texto OFL en `static/reino/fonts/OFL.txt` al desplegar (tarea registrada en STATUS).
- Respaldo declarado en CSS: Georgia/serif y stack de sistema.

## Imágenes

- Wiener Kingdom: fotografías reales ya presentes en el repositorio (`static/tienda/img/`),
  origen registrado en `ProductMedia.source` = «fotografía real del repositorio».
- Estudio Nube Demo: 7 imágenes generadas con IA para esta demo
  (`static/reino/img/nube/`), marcadas en `source` = «imagen generada — contenido de
  demostración» y en la UI («Tienda demo»). No representan productos reales en venta.
- Política de marca respetada: ninguna caricatura canina; el diagrama Smart Fit es SVG
  geométrico original.

## Decisiones técnicas registradas (resumen; detalle en 01/02)

1. Base = `feature/homepage-premium` (PR #2 integrado); PR #1 (docs) incorporado en `docs/proposal/`.
2. Una app nueva `reino` con servicios en vez de doce apps (permitido por el diseño).
3. `/` se conserva para la home histórica (suite legacy intacta); la plataforma vive en
   `/tiendas/` y `/s/<slug>/`. Adaptación mínima que no rompe pruebas.
4. Catálogo nuevo en DB + flujo Smart Quote legacy preservado como «hecho a medida» (S11).
5. Cuenta comprador por sesión en P0 (invitados); login de compradores = P1.
6. Reserva de 10 min; envío «por calcular» hasta cotizar zona; tarifa SV $3.50 = hipótesis.
7. Proveedor IA: adaptador OpenAI-compatible configurable (`REINO_AI_*`); modelo exacto =
   configuración tras evaluación con la batería preparada (80 casos), no una afirmación previa.
8. SQLite local con `transaction_mode=IMMEDIATE`; PostgreSQL objetivo staging/producción.
9. Fraunces+Manrope (OFL) vendoradas localmente tras verificar licencia — sin CDN en runtime.
10. Ninguna dependencia nueva en `requirements.txt` para la IA (urllib estándar): superficie
    de instalación idéntica a la histórica.
