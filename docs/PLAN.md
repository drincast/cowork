# Plan de ejecución — Sistema de registro de sesiones (worklog)

> Plan por fases para implementar con un agente de código.
> Cada fase es entregable e independiente: al terminar la Fase 1 ya reemplaza al sistema actual.

---

## Estado de fases

- [x] **Fase 1** — Núcleo funcional (MVP) · completada en sesión 2 (2026-06-14)
- [x] **Fase 2** — Consultas y export · completada en sesión 3 (2026-06-15)
- [x] **Fase 2.5** — Configuración e identidad portable · completada en sesión 5 (2026-06-15)
- [x] **Fase 3** — Ergonomía de instalación · completada en sesión 6 (2026-06-15)
- [x] **Fase 4** — Empaquetado pip (instalación local) · completada en sesión 7 (2026-06-15)
- [ ] **Fase 5** — Extras
- [ ] **Fase 6** — Publicación en PyPI (final)

> Leyenda: `[x]` completada · `[ ]` pendiente. El detalle de tareas de cada fase está en su checklist más abajo.

---

## Fase 1 — Núcleo funcional (MVP)

**Estado:** ✅ Completada (sesión 2 · 2026-06-14)

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

**Estado:** ✅ Completada (sesión 3 · 2026-06-15)

**Objetivo:** sacar valor de tener los datos en SQLite. Supera lo que el sistema Markdown nunca pudo hacer.

Checklist de tareas:

- [x] Comando `list [-n N]`: últimas N sesiones del proyecto actual, formateadas en tabla legible.
- [x] Comando `report`: agregados de tiempo. Flags `--project`, `--month`, `--model`. Totales por dimensión (agregación en Python reutilizando `duration_minutes`; ver nota abajo).
- [x] Comando `export --md [--path]`: genera `WORKLOG.md` desde la BD con el formato del sistema actual (totales arriba, sesiones en orden descendente).

**Criterio de aceptación:** `report --model` muestra minutos totales agrupados por modelo; `export` produce un `WORKLOG.md` equivalente al formato actual.

> Nota de diseño (sesión 3): la agregación de `report` se hace en Python, no con `SUM`/`GROUP BY` en SQL. La duración no se almacena (se calcula de `start_at`/`end_at`), y restar timestamps ISO 8601 con offset en SQL (`julianday`) es frágil. Se reutiliza el helper `duration_minutes()` ya probado; el volumen de datos es mínimo. `report` opera sobre **todos los proyectos** (alcance global) y solo sobre **sesiones cerradas**.

---

## Fase 2.5 — Configuración e identidad portable

**Estado:** ✅ Completada (análisis sesión 4, implementación sesión 5 · 2026-06-15)

**Objetivo:** que la herramienta funcione igual desde cualquier equipo, disco o usuario. Separa dos preguntas que hoy dependen del entorno: *dónde viven los datos* (almacenamiento) y *quién es el proyecto* (identidad). Diseño completo en `ARCHITECTURE.md` §11.

> Esta fase tiene dos etapas: **análisis** (esta sesión, ya documentado) e **implementación** (pendiente).

### Etapa A — Análisis (completada)

- [x] Detectar que identidad por ruta absoluta falla con disco externo / otro equipo / otro usuario / otro SO.
- [x] Decidir resolución por capas para almacenamiento e identidad.
- [x] Decidir formato de configuración: **JSON** (stdlib lee y escribe; gestionable por comandos).
- [x] Decidir identidad: `uid` (UUID4 completo, se muestra prefijo corto) + `name` (repetible) + `path` (informativo).
- [x] Precisar la regla "no escribir estado en el proyecto": el marcador `.cowork` (solo `id` + `name`) es etiqueta de identidad, no estado de sesiones; permitido y versionable.
- [x] Documentar el diseño en `ARCHITECTURE.md` §11.

### Etapa B — Implementación (completada · sesión 5)

- [x] **Config JSON** en `~/.worklog/config.json` (o `WORKLOG_HOME`): clave `db_path`. Se crea con `config set-db` (no se auto-escribe al leer, para evitar escrituras sorpresa).
- [x] **Resolución de BD por capas:** `--db` → `WORKLOG_HOME` → `config.json` → default `~/.worklog/worklog.db`.
- [x] **Comando `config`:** muestra la ruta efectiva de la BD y de qué fuente salió; `config set-db <ruta>` la cambia.
- [x] **Esquema:** añadido `uid TEXT` (UUID4) con índice único y `git_remote TEXT`; `path` pasa a informativo. Migración idempotente que rellena `uid` a proyectos existentes.
- [x] **Marcador `.cowork`** (JSON con `id` + `name`): lo crean `init`/`start`; se busca subiendo directorios.
- [x] **Resolución de identidad por capas:** `.cowork` → URL del remoto git (https/ssh normalizadas) → ruta. Lectura con `find_project`, creación con `ensure_project`.
- [x] **Detección de duplicados:** `init` avisa si el `name` ya existe con otro `uid`; opción `--link <uid>` para asociar (acepta prefijo corto del uid).
- [x] Actualizado `AGENTS.md` (reglas 1, 2, 4, 5) y `README.md` (config e identidad).

**Criterio de aceptación:** registrar sesiones del mismo proyecto desde dos rutas/letras de unidad distintas y que cuenten como **un solo** proyecto; `cowork config` muestra claramente dónde está la BD.

---

## Fase 3 — Ergonomía de instalación

**Estado:** ✅ Completada (sesión 6 · 2026-06-15)

**Objetivo:** que `cowork` sea invocable globalmente y que el agente sepa usarlo.

Checklist de tareas:

- [x] Lanzadores `bin/cowork.cmd` (Windows) y `bin/cowork` (POSIX) que conservan la carpeta actual; instrucciones de PATH para Windows, Linux y macOS en el README (script directo, sin paquete).
- [x] Guía breve para el agente (`USAGE.md`, sucesor de `COWORK.md`): cuándo correr `start`/`end`, con ejemplos.
- [x] Soporte de la variable `WORKLOG_HOME` documentado (README, sección de instalación y de configuración).

**Criterio de aceptación:** desde cualquier carpeta, `cowork status` funciona sin ruta completa al script.

---

## Fase 4 — Empaquetado pip (instalación local)

**Estado:** ✅ Completada (sesión 7 · 2026-06-15)

**Objetivo:** instalación local reproducible con `pipx install .`. (La publicación en PyPI se separó a la Fase 6.)

Checklist de tareas:

- [x] `pyproject.toml` con entry point de consola `cowork` (backend `setuptools`, módulo único `cowork.py`).
- [x] Construible/instalable: verificado con `pip install .` en venv aislado (genera `cowork-0.1.0-py3-none-any.whl` y el comando `cowork`). `pipx install .` requiere que el usuario tenga `pipx`.
- [x] Versionado semántico: arranca en `0.1.0`.
- [x] Configuración: ya resuelta en Fase 2.5 con `config.json` (capas `--db`/`WORKLOG_HOME`/`config.json`); no se usa `config.toml`.
- [x] `.gitignore` con artefactos de build (`build/`, `dist/`, `*.egg-info/`).

**Nota:** la instalación con pipx coexiste con los lanzadores `bin/` de la Fase 3; pipx es la vía recomendada, `bin/` el respaldo sin herramientas de empaquetado.

**Criterio de aceptación:** `pipx install .` deja el comando `cowork` disponible (cumplido a nivel de paquete; el usuario instala `pipx` una vez).

---

## Fase 5 — Extras (futuro)

**Estado:** ⬜ Pendiente

Checklist de tareas candidatas:

- [ ] **Import del histórico:** parsear el `WORKLOG.md` actual (3 sesiones) y cargarlo en SQLite, para no perder el registro previo.
- [ ] Pruebas automatizadas (`unittest` o `pytest`) en `tests/`.
- [ ] Binario standalone con PyInstaller para máquinas sin Python.
- [ ] Export adicional a CSV/JSON para análisis externo.

---

## Fase 6 — Publicación en PyPI (final)

**Estado:** ⬜ Pendiente

**Objetivo:** que cualquiera pueda `pipx install cowork` desde internet.

Checklist de tareas:

- [ ] Verificar que el nombre `cowork` esté disponible en PyPI (si no, elegir alternativa).
- [ ] Cuenta en PyPI (y TestPyPI para ensayar) con token de API.
- [ ] Construir artefactos: `python -m build` (genera `sdist` + `wheel` en `dist/`).
- [ ] Subir con `twine upload` (primero a TestPyPI, luego a PyPI).
- [ ] Completar metadatos para la ficha pública (descripción larga = README, clasificadores, URLs).

**Criterio de aceptación:** `pipx install cowork` funciona en una máquina limpia con acceso a internet.

> Es una acción **pública y permanente**: una versión publicada no se puede sobrescribir. Se hace solo cuando se decida liberar.

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
