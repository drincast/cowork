# DEVLOG — cowork CLI

Registro diario de desarrollo, decisiones tomadas y progreso.
Archivo muestra lo más actual al inicio.

---

## 2026-07-05 | Sesión 9 | Fase 5 Etapa A — Portabilidad inicial de la BD

### Tareas realizadas

- **Validación de existencia de la BD (fin de la "BD fantasma").**
  `open_db()` recibe un parámetro `create`. Con `create=False` (todos los comandos salvo
  `init`), si la ruta de BD resuelta no existe **avisa y para** con mensaje guía en vez de
  crear una BD vacía. Solo `init` la crea intencionalmente (`create=True`). Así se distingue
  "crear por primera vez" de "ruta ausente inesperada" (disco desconectado).

- **Resumen de BD en `init`, `start` y `status`.**
  Nuevo helper `db_summary_line()` imprime la ruta efectiva de la BD y su fuente
  (`--db` / `WORKLOG_HOME` / `config.json` / default). `init` además indica si el proyecto
  es nuevo o existente.

- **`init --db-path <ruta>`.**
  Persiste la ubicación de la BD en `config.json` (equivale a `config set-db`) y la crea ahí
  en un solo paso, pensado para elegir un disco externo en un equipo nuevo. Avisa si
  `WORKLOG_HOME` está activo (tiene prioridad y anula esa ruta).

### Verificación (sandbox aislado con WORKLOG_HOME temporal)

- `status`/`start` con BD inexistente → avisan y paran (exit 1), sin crear archivo.
- `init` → crea la BD, muestra estado "nuevo" y la ruta/fuente.
- `start`/`status`/`end` con BD existente → funcionan y muestran la ruta.
- BD renombrada (simula disco desconectado) → `start` avisa y **no** recrea BD fantasma.
- `init --db-path` → escribe `db_path` en `config.json`.
- BD real intacta: `cowork config` sigue resolviendo `~/.worklog/worklog.db` (fuente default).

### Nota de diseño

- **`init` es el único punto de creación intencional** de la BD (decisión del usuario).
  El resto de comandos asume que la BD ya existe. Bajo `WORKLOG_HOME`, la capa `config.json`
  se ignora por las reglas de capas de Fase 2.5 (comportamiento esperado y avisado).

### Pendiente para próxima sesión

- Fase 5 Etapa B: `sessions.agent` nullable + `start` con agente opcional (trabajo solo-humano)
  + formateo tolerante a NULL en `list`/`status`/`export`/`end`.
- Commit de la Etapa A (cowork.py + PLAN + DEVLOG).

---

## 2026-06-30 | Sesión 8 | Planeación — Replanificación de fases 5 a 9 (sin implementación)

### Naturaleza de la sesión

Sesión **solo de análisis y planeación**. No se tocó `cowork.py` ni el core; el objetivo fue
encaminar dos inconvenientes/ideas del usuario y dejar el plan reorganizado antes de implementar.

### Contexto: dos ideas a analizar

1. **Portabilidad de la BD** entre equipos. El problema observado: en cada PC se crea una BD
   "fantasma" vacía en la ruta por defecto (`[UNIDAD]:\Users\[USUARIO]\.worklog\worklog.db`),
   sin los registros previos. La meta a futuro es sincronización automática (aún sin diseño);
   el paso inicial acordado es manual: llevar la BD en un disco externo y apuntar cada equipo
   a esa ruta vía `config.json`.
2. **Estructura de agentes/modelos:** pasar de texto libre a tablas normalizadas con FK
   nullable, para habilitar trabajo individual (humano solo) sin agente/modelo.

### Decisiones tomadas

- **Idea 1 → Fase 5 (Etapa A).** Enfoque manual y explícito, sin que la app detecte unidades:
  - `init`/`start` mostrarán un **resumen** (proyecto nuevo o no, ruta efectiva de la BD y su fuente).
  - **No crear BD "fantasma":** si la ruta resuelta no existe (disco desconectado o proyecto
    nuevo sin ruta), **avisar y parar** con mensaje guía que incluye el comando de ejemplo
    `cowork config set-db <ruta>`. Sin prompt interactivo.
  - La ruta de la BD vive en **`config.json` local**, NO en el `.cowork` versionado
    (se respetó la regla de Fase 2.5: `.cowork` es identidad, no estado per-máquina; meterle
    la ruta causaría conflictos de merge entre equipos).
- **Avance parcial de Idea 2 → Fase 5 (Etapa B).** Hacer `sessions.agent` **nullable**
  (migración idempotente, sin tablas nuevas todavía) y `start` con agente opcional. El SQL de
  `report` **no cambia** (no agrupa por agente; `model` ya tolera NULL); solo se ajusta el
  formateo de salida en `list`/`status`/`export`/`end` para mostrar `—` en vez de `None`.
- **Idea 2 completa → Fase 7.** Normalización con tablas `agents`/`models`, FK nullable,
  migración del texto a IDs y JOINs. Se reconoce como cambio grande y se separa para mantener
  el core estable.
- **Reordenamiento de fases:** 5 = portabilidad inicial + campos opcionales · 6 = pruebas
  automatizadas (antes "extras") · 7 = normalización agentes/modelos · 8 = extras restantes
  (import histórico, PyInstaller, export CSV/JSON) · 9 = publicación PyPI (final).

### Hallazgo verificado

- `config.json` es código real (`load_config`/`save_config`/`cmd_config`) pero **el archivo no
  existe** en la máquina del usuario: solo se crea al ejecutar `cowork config set-db`. Se revisó
  `~/.worklog/` y solo contiene `worklog.db`. Es comportamiento intencional de Fase 2.5
  (no auto-escribir al leer), no un bug.

### Pendientes anotados (futuro, fuera de fase asignada)

- **Multiplataforma:** la ruta por defecto es solo-Windows; definir comportamiento en
  Linux / macOS / Android.
- **Identificación de unidad por etiqueta de volumen:** resolver la letra a partir del nombre
  del volumen (ej. `COWORK_USB`) para no depender de la letra que asigne el SO. Se explicó el
  concepto al usuario; se aplaza.
- **Sincronización automática** de la BD entre equipos (meta de largo plazo, sin diseño).

### Archivos modificados

- `docs/PLAN.md`: reorganización de fases 5 a 9 con sus checklists y criterios de aceptación.
- `DEVLOG.md`: esta entrada.

### Pendiente para próxima sesión

- Implementar Fase 5 (Etapa A portabilidad + Etapa B campos opcionales).
- Commit de la replanificación (PLAN + DEVLOG).

---

## 2026-06-15 | Sesión 7 | Fase 4 — Empaquetado (instalación local)

### Tareas realizadas

- **`pyproject.toml`**
  Backend `setuptools`, módulo único (`py-modules = ["cowork"]`), entry point `cowork = "cowork:main"` y versión `0.1.0`. Sin dependencias de ejecución (solo build).

- **Verificación en venv aislado**
  `pip install .` construyó `cowork-0.1.0-py3-none-any.whl` y creó el comando `cowork`; `cowork --help` y `cowork config` corrieron correctamente. La instalación no tocó el Python global ni la BD real.

- **`.gitignore`**
  Se ignoran artefactos de build (`build/`, `dist/`, `*.egg-info/`).

- **Documentación**
  README con sección de `pipx install .` (vía recomendada) y los lanzadores `bin/` como alternativa. PLAN: Fase 4 completada.

- **Decisión: publicación en PyPI a una fase aparte**
  Se separó la publicación pública a una nueva **Fase 6** (final), dejando la Fase 4 acotada a instalación local. Versión semántica inicial `0.1.0`.

- **Aclaración Fase 3 vs Fase 4**
  No se solapan en vano: los lanzadores `bin/` (Fase 3) son el respaldo sin herramientas de empaquetado; pipx (Fase 4) es la vía recomendada. Conviven.

### Pendiente para próxima sesión

- El usuario debe instalar `pipx` (no estaba) y ejecutar `pipx install .` para tener el comando global por esa vía.
- Commit y push de Fase 4.
- Fase 5 (extras) o Fase 6 (PyPI) cuando se decida.

---

## 2026-06-15 | Sesión 6 | Fase 3 — Ergonomía + guía de pruebas

### Tareas realizadas

- **Invocación global de `cowork`**
  Lanzadores `bin/cowork.cmd` (Windows) y `bin/cowork` (Linux/macOS) que llaman a `cowork.py` conservando la carpeta actual. Instrucciones de PATH para los tres sistemas en el README. Verificado: `cowork status` funciona desde cualquier carpeta.

- **Guía para el agente (`USAGE.md`)**
  Sucesor de `COWORK.md`: explica de forma breve cuándo correr `start`/`end`, con ejemplos. Pensada para minimizar lectura del agente.

- **Refuerzo de `WORKLOG_HOME`**
  Documentado en el README (instalación y configuración) para llevar la BD a un disco externo o carpeta sincronizada.

- **Guías de prueba manual (`docs/manual-tests/`)**
  `README.md` (índice + propósito) y `portable-identity.md` (con encabezado de alcance: propósito, alcance, fuera de alcance). Aclara que NO son la suite automatizada (esa será de Fase 5, en `tests/`).

- **Dogfooding: `.cowork` del propio repo**
  Al iniciar la sesión, `cowork start` creó el marcador `.cowork` del repo y fijó su `git_remote`.

- **Convención de nombres confirmada**
  Carpetas y archivos en inglés; código fuente en inglés; comentarios de código en español; contenido de documentos en español.

### Pendiente para próxima sesión

- **Push** del commit de Fase 2.5 (`1775e92`) y de los de esta sesión a `origin/main`.
- Iniciar Fase 4: empaquetado con `pipx` (`pyproject.toml` con entry point `cowork`).

---

## 2026-06-15 | Sesión 5 | Fase 2.5 Etapa B — Implementación

### Tareas realizadas

- **Almacenamiento configurable**
  `config.json` (gestionado por comandos, no auto-escrito al leer) y resolución de la BD por capas: `--db` → `WORKLOG_HOME` → `config.json` → default. Nuevo comando `config` (muestra ruta efectiva + fuente) y `config set-db <ruta>`. Flag global `--db`.

- **Identidad de proyecto portable**
  Esquema migrado idempotente: `uid` (UUID4) con índice único + `git_remote`; `path` pasa a informativo. Resolución por capas: marcador `.cowork` → URL del remoto git (https/ssh normalizadas) → ruta. `find_project` (lectura) y `ensure_project` (creación + escribe marcador). Detección de duplicados de nombre e `init --link <uid>`.

- **Comandos adaptados**
  `start`, `end`, `status`, `list`, `export` resuelven el proyecto por identidad, ya no por ruta.

- **Documentación**
  `AGENTS.md` (reglas 1, 2, 4, 5), `README.md` (config e identidad) y `docs/PLAN.md` (Fase 2.5 completada).

- **Pruebas manuales en sandbox aislado**
  Con `WORKLOG_HOME` temporal y proyectos falsos se verificaron las 3 capas de identidad, normalización https/ssh, detección de duplicados y `--link`. La migración de la BD real no perdió datos.

### Pendiente para próxima sesión

- Decidir nombre/ubicación de una guía de pruebas manuales (propuesta: `docs/pruebas/identidad-portable.md` con encabezado de alcance).
- Generar el `.cowork` del propio repo (dogfooding, previsto para Fase 3).
- Iniciar Fase 3: `cowork` invocable desde cualquier carpeta.

---

## 2026-06-15 | Sesión 4 | Fase 2.5 Etapa A — Análisis y diseño

### Tareas realizadas

- **Diagnóstico de portabilidad**
  Se identificó que identificar el proyecto por la ruta absoluta falla con disco externo (cambia la letra), otro equipo u otro usuario.

- **Diseño por capas**
  Se separó "dónde viven los datos" (config) de "quién es el proyecto" (identidad). Decisiones: config en JSON; identidad por `uid` estable (UUID4) resuelto por capas; el marcador `.cowork` (solo `id` + `name`) es etiqueta de identidad versionable, no estado.

- **Documentación del diseño**
  Nueva sección `ARCHITECTURE.md` §11 y `docs/PLAN.md` (Fase 2.5 con etapas de análisis e implementación). Se corrigió además el mensaje corrupto del commit de Fase 2 (amend) y se commiteó la documentación.

---

## 2026-06-15 | Sesión 3 | Fase 2 — Consultas y export

### Tareas realizadas

- **Comando `list [-n N]`**
  Lista las últimas N sesiones (default 10) del proyecto actual en tabla legible: ID, agente, modelo, inicio, fin y duración. La sesión abierta se muestra con duración en vivo y "— (abierta)" en Fin.

- **Comando `report [--project] [--month] [--model]`**
  Agregados de tiempo (sesiones, minutos, horas) con flags combinables; orden por minutos desc y fila TOTAL. Decisión: la agregación se hace en Python reutilizando `duration_minutes()`, no con `SUM`/`GROUP BY` en SQL, porque la duración no se almacena y restar timestamps ISO 8601 con offset en SQL es frágil. `report` tiene alcance global (todos los proyectos) y solo cuenta sesiones cerradas.

- **Comando `export [--md] [--path]`**
  Genera `WORKLOG.md` del proyecto actual desde la BD: encabezado con totales (sesiones, minutos, horas, última sesión) y sesiones en orden descendente con agente, modelo, inicio, fin, duración y resumen. Es la única escritura autorizada dentro del repo; vista derivada, no se edita a mano. Se generó el `WORKLOG.md` inicial del proyecto.

- **Helper `fmt_duration` extraído**
  Formateo de minutos a `Xh YYm` reutilizado por `list` y `export`.

- **Corrección en `docs/PLAN.md`**
  Se detectó que la línea `**Estado:**` se repetía idéntica en las 5 fases (`[ ] Pendiente / [x] Completada`), haciendo parecer que todas estaban completadas. Se añadió una sección "Estado de fases" como lista de overview y se dejó un estado real único por fase (solo Fase 1 y 2 completadas).

### Pendiente para próxima sesión

- Retomar el análisis de **identidad portable del proyecto** (ruta absoluta falla con disco externo, otro equipo u otro usuario). El usuario tiene una propuesta propia por revisar.
- Iniciar Fase 3: añadir `cowork` al PATH y guía breve para el agente.

---

## 2026-06-14 | Sesión 2 | Subida a GitHub y licencia MIT

### Tareas realizadas

- **Licencia MIT agregada**
  Archivo `LICENSE` con copyright a nombre de Rubén Orozco (drincastX). Decisión: MIT por ser permisiva y requerir que se mantenga el aviso de autoría en cualquier copia o uso del código.

- **README actualizado**
  Se agregó sección de autor con enlace al perfil de GitHub, instrucciones de instalación, uso con los comandos reales de Fase 1, estado de fases y referencia a la licencia.

- **Repositorio subido a GitHub**
  Repo público en `https://github.com/drincast/cowork`. Se corrigió la URL del remote (nombre de usuario `drincast`, no `drincastX`).

- **Registro de sesión en BD**
  Primera sesión registrada con `cowork` en producción: 23 minutos, agente Claude Code (claude-sonnet-4-6).

### Pendiente para próxima sesión

- Iniciar Fase 2: comandos `list`, `report` y `export`.

---

## 2026-06-14 | Sesión 1 | Implementación Fase 1 — Núcleo funcional

### Tareas realizadas

- **Git init y configuración base del repositorio**
  Se inicializó el repositorio local (`git init`) con rama `main`. Se configuró identidad de git para el repo (`drincastX`, `drincast@gmail.com`). El repositorio aún es solo local; se subirá a GitHub una vez se revise y apruebe el estado actual.

- **Creación de `.gitignore`**
  Incluye `venv/`, `*.db`, `__pycache__/`, `*.pyc` y `.env`. Garantiza que la base de datos SQLite y los ambientes virtuales nunca se versionen.

- **Regla de ambiente virtual agregada a `AGENTS.md`**
  Se añadió la Regla 8: el proyecto es Python y se debe usar siempre un ambiente virtual (`venv`) para no instalar nada en el Python global del sistema. El directorio `venv/` va en `.gitignore`.

- **Checklists de fases en `docs/PLAN.md`**
  Cada fase ahora tiene un estado (`Pendiente` / `Completada`) y una lista de tareas con casillas Markdown (`- [ ]` / `- [x]`). La Fase 1 quedó completamente marcada como hecha.

- **Implementación de `cowork.py` — Fase 1 completa**
  Script principal con solo biblioteca estándar de Python (3.14.5). Implementa:
  - `cowork init [nombre]` — registra o renombra el proyecto actual por ruta absoluta.
  - `cowork start <agente> [modelo] [--force]` — abre sesión con timestamp ISO 8601 + offset local (`-05:00`). Detecta sesión huérfana: avisa y para por defecto; `--force` la auto-cierra y abre la nueva.
  - `cowork end [resumen]` — cierra la sesión abierta, calcula duración en minutos. Error claro si no hay sesión.
  - `cowork status` — muestra sesión activa y tiempo transcurrido en vivo.
  - Auto-creación del esquema SQLite si la BD no existe (idempotente).
  - Corrección de encoding UTF-8 para consola Windows.

- **Verificación en dos proyectos**
  Se probaron los cuatro comandos en `cowork` y en `iachatexporter-extension` de forma independiente. La BD en `~\.worklog\worklog.db` quedó con datos correctos: dos proyectos separados, timestamps con offset `-05:00`, sin mezcla de sesiones.

- **Decisiones de diseño confirmadas (no repreguntar)**
  - La BD y la carpeta de datos usan "worklog" (`~/.worklog/worklog.db`); el comando usa "cowork".
  - No se convierte a UTC; se almacena la hora local con offset explícito.
  - Sin columna de duración en la BD; se calcula al vuelo.
  - Export a demanda únicamente (`cowork export`, Fase 2).

- **Commit inicial creado**
  `42c942e — feat(fase1): implementacion completa del nucleo funcional cowork`

### Pendiente para próxima sesión

- Subir a GitHub: crear repo remoto → `git remote add origin` → `git push`.
- Iniciar Fase 2: comandos `list`, `report` y `export`.
- Evaluar si agregar `cowork` al PATH de Windows antes de la Fase 2 (para no escribir la ruta completa al script en cada llamada).
