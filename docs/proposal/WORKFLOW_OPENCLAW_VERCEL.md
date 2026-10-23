# Herramientas: cómo se conectan OpenClaw y Vercel

**OpenClaw = coordinación/desarrollo, no hosting de una tienda.** Orquesta agentes autorizados, lee requisitos, asigna tareas, propone PRs, ejecuta tests en entorno local aislado si tiene permisos. Mantener accesos limitados y secretos fuera del repositorio.

**GitHub = fuente de verdad.** Repositorio, ramas, code review, CI y auditoría. La cuenta conectada hoy NO tiene `push` al repositorio objetivo.

**Vercel = hosting, despliegues y previews de aplicaciones compatibles.** Puede ser apropiado para la demo estática o frontend separado, pero no sustituye automáticamente el stack Django+BD. No publicar nada hasta seleccionar cuenta, entorno y permisos. Vercel Hobby tiene restricciones para uso comercial: revisar plan antes de producción.

**DeepSeek Pro / ChatGPT = motores intercambiables para análisis/código.** Toda decisión crítica vive en `docs/`, issues y PR, para cambiar de modelo sin perder contexto. Ningún modelo conoce el workspace local por arte de magia; se le proporcionan recursos y accesos explícitos.

## Ciclo propuesto

1. Equipo define necesidad → issue en GitHub.
2. Coordinador autorizado desglosa y asigna agente.
3. Agente consulta requisitos y modifica exclusivamente su rama.
4. QA independiente revisa código, seguridad, Django `manage.py test` y UX.
5. PR en borrador con resumen y evidencias; aprobación humana.
6. Tras aprobación: merge, staging; preview en Vercel solo si la arquitectura y plan lo permiten.
7. Monitoreo de pedidos y soporte en backend Django; operaciones reales solo cuando habilitadas.
8. Registrar handoff a otro modelo en `AI_HANDOFF.md` y conservar contexto.

**No existe ningún despliegue ni integración activa de OpenClaw creada por estos documentos.**
