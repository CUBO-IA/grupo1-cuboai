# Tipografías de la Home

| Elemento | Fuente pedida | Estado en el proyecto |
|---|---|---|
| Título y párrafo | Spartan MB | Solo instalada en el equipo del diseñador (`local()`); alternativa: League Spartan, Montserrat, Arial |
| Texto final (cursiva) | Calibri | Fuente de Microsoft instalada en Windows; alternativa: Carlito, Segoe UI, Arial |

El proyecto **no incluye archivos de fuente**, así que otros dispositivos verán la alternativa. El CSS ya está preparado
(`@font-face` "Spartan MB Web" y "Calibri Web" y las variables `--font-spartan` y `--font-calibri` en `static/tienda/css/style.css`).

## Cómo incorporarlas para todos los visitantes
1. **Spartan MB**: confirmar que su licencia permite uso web/redistribución. Si lo permite, convertir los `.otf` Regular y Bold a `.woff2`
   y copiarlos a `web/static/tienda/fonts/`. Si no, usar **League Spartan** (licencia OFL, libre para web), muy similar.
2. **Calibri**: su licencia no permite redistribuirla en un sitio web. Usar **Carlito** (licencia OFL, métricamente compatible), o licenciar Calibri para web.
3. En `style.css` añadir a cada `@font-face` una línea `url("../fonts/archivo.woff2") format("woff2")` después de los `local(...)`.
