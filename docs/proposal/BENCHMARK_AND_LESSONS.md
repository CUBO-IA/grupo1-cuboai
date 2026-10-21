# Benchmark técnico y de diseño — investigación documental

## 1. dataMiner — Mario Marroquín

Referencia: https://github.com/mariomarroquin3/dataMiner

**Lo que se observa en código y README:** motor de equipo multiagente BoxLang AI, coordinador, analistas especializados, ingestión de datos, soporte SQL/MCP en lectura, verificador de afirmaciones y respuestas estructuradas con hechos respaldados, separación de interpretaciones, trazas de la actividad, interfaz visual con microinteracciones, datasets de prueba y alternativas mock. Documenta un modo compacto que afirma reducir llamadas LLM respecto al equipo completo; no he reproducido esa medición.

**Aplicación para Wiener Kingdom:**
- **Sales Mission Control:** panel de pedidos, márgenes, incidencias y alertas con origen de cada dato.
- **Specialized agents:** un agente de pedidos, uno de catálogo, otro de analítica, otro de soporte, con revisión independiente.
- **Evidence first:** toda predicción marcada como hipótesis; el sistema no debe confundir datos reales con demostrativos.
- **Cost discipline:** usar reglas deterministas y modelos pequeños donde funcionen; limitar llamadas IA y conservar trazas.
- **Visual:** inspiración en un dashboard de alta calidad con bento grids y motion sutil, NO copiar CSS, composición, marca ni activos.

**Límites documentados:** README dice que en su entorno aún no probó un LLM real (estado 10/10/2026), y parte de pruebas de Kaggle son con servidor simulado. No asumir cobertura en producción.

## 2. Second Brain — Out of the Box

Referencia: https://github.com/CUBO-IA/boxlang-second-brain

**Lo verificado por los autores:** autenticación con permisos por espacio, separaciones de backend/frontend, documentación por fases, RAG con fuentes e inferencias citadas, pruebas automatizadas y aceptación sintética de proveedor registrada para fase 03 (alcance acotado). Sus documentos excluyen expresamente despliegue remoto acreditado y seguridad absoluta ante prompt injection.

**Aplicación:**
- Documentar cada fase con alcance, pruebas, aceptación y límites.
- Separar contexto y archivos por tienda, rol y proyecto.
- Handoff IA → humano documentado, con evidencias y controles.
- Test mocks sin costo, además de prueba opt-in con proveedor real, con techo definido.
- Preservar decisiones en Git, no únicamente en el chat.

## 3. ¿Por qué ganaron?

La persona que solicita este documento afirma que Second Brain ganó el hackathon. **Los repositorios revisados no permiten demostrar causalmente los criterios del jurado ni atribuir una razón oficial del premio.** Desde el código se pueden inferir puntos fuertes de demostrabilidad y rigor, pero hay que solicitar rúbrica, resultados o acta oficial antes de afirmar por qué obtuvo la victoria.

## 4. Límites de inspiración

Aprender principios técnicos y visuales, pero desarrollar componentes originales; respetar licencias antes de reutilizar código, fuentes, archivos y recursos gráficos.
