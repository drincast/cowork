# cowork

Herramienta CLI para registrar sesiones de trabajo colaborativo entre una persona y agentes/chats de IA. Registra tiempo, autores, agente, modelo, e inicio/fin de cada sesión, en una base de datos central fuera de tus proyectos.

> **No consume tokens de IA.** El agente solo invoca comandos de terminal; todo el procesamiento es local.

---

## Autor

Creado por **Rubén Orozco** ([@drincastX](https://github.com/drincastX)).

Si usas o adaptas este proyecto, se agradece mantener el crédito de autoría conforme a la licencia MIT incluida.

---

## Características

- Estado central en SQLite (`~/.worklog/worklog.db`), no contamina tus repos.
- Un solo script Python con biblioteca estándar. Sin dependencias externas.
- Multiplataforma: Windows, Linux, macOS.
- Consultas de tiempo por proyecto, modelo y mes (Fase 2).
- Export opcional a `WORKLOG.md` versionable en el repo (Fase 2).

---

## Instalación

Requiere **Python 3.8+**. Sin dependencias externas.

```bash
# Clona el repo
git clone https://github.com/drincastX/cowork.git

# Úsalo directamente
python cowork.py start "Claude Code" "claude-opus-4-8"
```

Para invocarlo como `cowork` desde cualquier carpeta, consulta la Fase 3 en `docs/PLAN.md`.

---

## Uso

```bash
python cowork.py init "Nombre del proyecto"         # registra o renombra el proyecto actual
python cowork.py start "Claude Code" "claude-opus-4-8"  # abre sesión
python cowork.py status                             # muestra sesión activa y tiempo transcurrido
python cowork.py end "resumen de lo trabajado"      # cierra y calcula duración
```

Si olvidaste cerrar una sesión anterior:

```bash
python cowork.py start "Claude Code" --force        # auto-cierra la anterior y abre la nueva
```

---

## Documentación

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — diseño del sistema y decisiones técnicas.
- [`docs/PLAN.md`](docs/PLAN.md) — plan de ejecución por fases con checklist de progreso.
- [`AGENTS.md`](AGENTS.md) — instrucciones para el agente de código.
- [`DEVLOG.md`](DEVLOG.md) — registro de desarrollo sesión a sesión.

---

## Estado

**Fase 1 completada** — `init`, `start`, `end`, `status` funcionando con SQLite.
Fase 2 en camino: `list`, `report`, `export`.

---

## Licencia

MIT © 2026 Rubén Orozco (drincastX). Ver [`LICENSE`](LICENSE).
