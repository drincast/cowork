# cowork

Herramienta CLI para registrar sesiones de trabajo colaborativo entre una persona y agentes/chats de IA. Registra tiempo, autores, agente, modelo, e inicio/fin de cada sesión, en una base de datos central fuera de tus proyectos.

> **No consume tokens de IA.** El agente solo invoca comandos de terminal; todo el procesamiento es local.

---

## Características

- Estado central en SQLite (`~/.worklog/worklog.db`), no contamina tus repos.
- Un solo script Python con biblioteca estándar. Sin dependencias.
- Multiplataforma: Windows, Linux, macOS.
- Consultas de tiempo por proyecto, modelo y mes.
- Export opcional a `WORKLOG.md` versionable en el repo.

## Uso (previsto)

```bash
cowork start "Claude Code" "claude-opus-4-8"   # abre sesión en el proyecto actual
cowork status                                   # ¿hay sesión abierta?
cowork end "Implementé el parser de ChatGPT"    # cierra y calcula duración
cowork report --model                           # tiempo total por modelo
cowork export --md                              # genera WORKLOG.md a demanda
```

## Documentación

- `docs/ARCHITECTURE.md` — diseño del sistema y decisiones técnicas.
- `docs/PLAN.md` — plan de ejecución por fases.
- `AGENTS.md` — instrucciones para el agente de código.

## Estado

En diseño. La implementación arranca por la Fase 1 (ver `docs/PLAN.md`).
