# AGENTS — Instrucciones para el agente de código

> Lee este archivo antes de empezar a implementar. Define el alcance, las reglas y lo que NO debes hacer.

---

## Qué vas a construir

Una herramienta CLI en **Python (solo biblioteca estándar)** que registra sesiones de trabajo entre una persona y agentes de IA. Lee `docs/ARCHITECTURE.md` para el diseño completo y `docs/PLAN.md` para las fases.

Empieza por la **Fase 1**.

---

## Reglas no negociables

1. **Solo biblioteca estándar de Python.** Permitido: `sqlite3`, `argparse`, `datetime`, `pathlib`, `os`, `sys`, `json`, `uuid`, `subprocess`. Prohibido añadir dependencias externas.
2. **La fuente de verdad es SQLite.** Su ubicación se resuelve por capas (Fase 2.5): `--db` → `WORKLOG_HOME` → `config.json` → por defecto `~/.worklog/worklog.db`. Nunca escribas **estado de sesiones** en el proyecto salvo con `export`. **Excepción:** el marcador `.cowork` (solo `id` + `name`) sí se escribe en el proyecto; es una etiqueta de identidad, no estado, y es versionable.
3. **Tiempos en ISO 8601 con offset** (`2026-06-13T10:28:00-05:00`). No conviertas a UTC para almacenar. Usa `datetime.now().astimezone()` para obtener el offset local.
4. **El esquema se auto-crea** si la BD no existe, y se **migra de forma idempotente** (p.ej. añadir `uid`). Operaciones idempotentes.
5. **El proyecto se identifica por un `uid` estable**, resuelto por capas (Fase 2.5): marcador `.cowork` → URL del remoto git → ruta absoluta (último recurso). La ruta dejó de ser la clave.
6. **Una sola sesión abierta por proyecto** (`end_at IS NULL`). Ante sesión huérfana: `start` avisa y para; `start --force` auto-cierra la previa y abre la nueva.
7. **Cero llamadas de red, cero IA.** La herramienta es 100% local.
8. **El proyecto es Python. Nunca instales paquetes en el Python global del sistema.** Usa siempre un ambiente virtual (`venv`) aislado: crea `venv/` en la raíz del repo con `python -m venv venv` y actívalo antes de instalar cualquier dependencia. El directorio `venv/` debe estar en `.gitignore`. Si en una fase futura se requieren dependencias externas, documenta el comando de instalación en el README pero nunca ejecutes `pip install` fuera del ambiente virtual.

---

## Estilo

- Código claro y legible por encima de clever.
- Mensajes de salida en español, concisos.
- Manejo de errores explícito: si no hay sesión abierta y se llama `end`, mensaje claro, no excepción cruda.
- Autor por defecto: `drincast`.

---

## Decisiones ya confirmadas (no preguntes)

1. **Comando:** `cowork`. Script principal: `cowork.py`. La carpeta de datos (`~/.worklog/`), la BD (`worklog.db`), el export (`WORKLOG.md`) y la variable (`WORKLOG_HOME`) conservan "worklog".
2. **Sesión huérfana:** ambas. Por defecto avisa y para; `--force` auto-cierra la previa y abre la nueva.
3. **Export:** a demanda únicamente (`cowork export`). Nunca automático tras `end`.

---

## Criterio de "hecho" para Fase 1

- `cowork start "Claude Code" "claude-opus-4-8"` abre sesión.
- `cowork status` muestra la sesión abierta y el tiempo transcurrido.
- `cowork end "resumen"` cierra y calcula duración correcta.
- Funciona en dos proyectos distintos sin mezclar sesiones.
- La BD queda en `~/.worklog/worklog.db` con datos correctos.
