# DEVLOG — cowork CLI

Registro diario de desarrollo, decisiones tomadas y progreso.
Archivo muestra lo más actual al inicio.

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
