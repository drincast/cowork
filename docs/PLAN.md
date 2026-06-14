# Plan de ejecución — Sistema de registro de sesiones (worklog)

> Plan por fases para implementar con un agente de código.
> Cada fase es entregable e independiente: al terminar la Fase 1 ya reemplaza al sistema actual.

---

## Fase 1 — Núcleo funcional (MVP)

**Estado:** `[ ] Pendiente` / `[x] Completada`

**Objetivo:** un `cowork.py` que abra y cierre sesiones contra SQLite. Reemplaza el sistema actual de scripts + Markdown.

Checklist de tareas:

- [x] Crear `cowork.py` con `argparse` y subcomandos.
- [x] Resolución de la carpeta de datos: `WORKLOG_HOME` o `~/.worklog/`.
- [x] Auto-creación del esquema SQLite si la BD no existe (idempotente).
- [x] Resolución de proyecto por ruta absoluta del directorio actual.
- [x] Comando `init [nombre]`: registra o renombra el proyecto actual.
- [x] Comando `start <agente> [modelo]`: crea proyecto si no existe, abre sesión con timestamp ISO 8601 + offset. Si hay sesión huérfana, avisa y para. Con `--force` la auto-cierra y abre la nueva.
- [x] Comando `end [resumen]`: cierra la sesión abierta, calcula duración en minutos. Error claro si no hay sesión abierta.
- [x] Comando `status`: muestra sesión abierta y tiempo transcurrido.
- [x] Git init + primer commit local
- [x] `.gitignore` con `venv/` y `*.db`

**Criterio de aceptación:** iniciar y cerrar una sesión en dos proyectos distintos; verificar en la BD que las sesiones quedan correctas y las duraciones bien calculadas.

---

## Fase 2 — Consultas y export

**Estado:** `[ ] Pendiente` / `[x] Completada`

**Objetivo:** sacar valor de tener los datos en SQLite. Supera lo que el sistema Markdown nunca pudo hacer.

Checklist de tareas:

- [ ] Comando `list [-n N]`: últimas N sesiones del proyecto actual, formateadas en tabla legible.
- [ ] Comando `report`: agregados de tiempo. Flags `--project`, `--month`, `--model`. Totales por dimensión usando SQL (`SUM`, `GROUP BY`).
- [ ] Comando `export --md [--path]`: genera `WORKLOG.md` desde la BD con el formato del sistema actual (totales arriba, sesiones en orden descendente).

**Criterio de aceptación:** `report --model` muestra minutos totales agrupados por modelo; `export` produce un `WORKLOG.md` equivalente al formato actual.

---

## Fase 3 — Ergonomía de instalación

**Estado:** `[ ] Pendiente` / `[x] Completada`

**Objetivo:** que `cowork` sea invocable globalmente y que el agente sepa usarlo.

Checklist de tareas:

- [ ] Instrucciones para añadir `cowork` al PATH en Windows, Linux y macOS (script directo, sin paquete).
- [ ] Reescribir la guía para el agente (sucesor de `COWORK.md`): explica cuándo correr `start` y `end`, con ejemplos. Debe ser breve para minimizar lectura del agente.
- [ ] Soporte de la variable `WORKLOG_HOME` documentado.

**Criterio de aceptación:** desde cualquier carpeta, `cowork status` funciona sin ruta completa al script.

---

## Fase 4 — Empaquetado pip (evolución)

**Estado:** `[ ] Pendiente` / `[x] Completada`

**Objetivo:** instalación profesional reproducible.

Checklist de tareas:

- [ ] `pyproject.toml` con entry point de consola `cowork`.
- [ ] Instalable con `pipx install`.
- [ ] Versionado semántico.
- [ ] Configuración opcional en `~/.worklog/config.toml`: autor por defecto, `auto_export`, formato de fecha.

**Criterio de aceptación:** `pipx install .` deja el comando `cowork` disponible en el sistema.

---

## Fase 5 — Extras (futuro)

**Estado:** `[ ] Pendiente` / `[x] Completada`

Checklist de tareas candidatas:

- [ ] **Import del histórico:** parsear el `WORKLOG.md` actual (3 sesiones) y cargarlo en SQLite, para no perder el registro previo.
- [ ] Pruebas automatizadas (`unittest` o `pytest`).
- [ ] Binario standalone con PyInstaller para máquinas sin Python.
- [ ] Export adicional a CSV/JSON para análisis externo.

---

## Decisiones confirmadas

1. **Nombre del comando:** `cowork`. La carpeta de datos, la BD y el export conservan "worklog".
2. **Sesión huérfana:** ambas opciones. Por defecto avisa y para; `--force` auto-cierra la previa y abre la nueva.
3. **Export:** a demanda únicamente (`cowork export`), nunca automático.

---

## Orden de archivos a crear (para el agente de código)

```
worklog-project/
├── cowork.py               # Fase 1-2: script principal
├── docs/
│   ├── ARCHITECTURE.md     # este diseño
│   └── PLAN.md             # este plan
├── AGENTS.md          # Fase 3: guía breve para el agente (sucesor de COWORK.md)
├── pyproject.toml          # Fase 4: empaquetado
└── README.md               # uso e instalación
```
