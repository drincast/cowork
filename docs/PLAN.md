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
- [x] **Fase 5** — Portabilidad inicial de la BD + campos opcionales · completada en sesión 9 (2026-07-05)
- [x] **Fase 6** — Mejoras de Status y Reporte de Proyecto · completada en sesión 10 (2026-07-30)
- [x] **Fase 7** — Sistema de pausas · completada en sesión 12 (2026-09-18)
- [x] **Fase 8** — Versión visible de cowork (`--version`, `-h` y `status`) · completada en sesión 13 (2026-09-21)
- [ ] **Fase 9** — Registro estructurado de agentes/modelos por sesión (multi-agente)
- [ ] **Fase 10** — Edición de sesión abierta
- [ ] **Fase 11** — Pruebas automatizadas
- [ ] **Fase 12** — Normalización de agentes y modelos (tablas + FK)
- [ ] **Fase 13** — Extras
- [ ] **Fase 14** — Publicación en PyPI (final)

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

## Fase 5 — Portabilidad inicial de la BD + campos opcionales

**Estado:** ✅ Completada (sesión 9 · 2026-07-05) — Etapas A y B

**Objetivo:** dar el primer paso hacia trabajar el mismo proyecto desde varios equipos
sin que se cree una BD vacía "fantasma" en cada uno. La estrategia inicial es **manual y
explícita**: llevar la BD en un disco externo (EHD/USB) y que cada equipo apunte a esa
ruta vía `config.json`. En paralelo, habilitar trabajo individual (humano solo) haciendo
opcionales los campos `agent`/`model`.

> **Meta a futuro (no en esta fase):** sincronización automática de la BD entre equipos.
> Aún sin diseño; por ahora la portabilidad es manual mediante disco externo + `config set-db`.

### Etapa A — Portabilidad inicial de la BD (idea 1)

**Estado:** ✅ Completada (sesión 9 · 2026-07-05)

- [x] **Resumen al ejecutar `init` y `start`:** indican si el proyecto es nuevo o existente,
      la ruta efectiva de la BD y su fuente (`--db` / `WORKLOG_HOME` / `config.json` / default).
      `status` también muestra la ruta de la BD.
- [x] **No crear BD "fantasma":** `open_db()` valida existencia del archivo. Con `create=False`
      (todos los comandos salvo `init`), si la ruta resuelta **no existe** → **avisa y para**
      con mensaje guía (`cowork config set-db <ruta>` / `cowork init`). Solo `init` crea la BD
      intencionalmente (`create=True`), distinguiendo "crear por primera vez" de "ruta ausente".
- [x] **La ruta de la BD vive en `config.json` local**, no en el `.cowork` versionado. Se añadió
      la **validación de existencia** antes de operar. Nuevo `init --db-path <ruta>` persiste esa
      ruta en `config.json` (equivale a `config set-db`) y crea la BD ahí en un solo paso.
- [x] **Sin** detección automática de unidades ni etiquetas de volumen en esta fase
      (anotado para más adelante; ver "Pendientes anotados").

### Etapa B — Campos opcionales: trabajo individual (avance parcial de idea 2)

**Estado:** ✅ Completada (sesión 9 · 2026-07-05)

- [x] **Esquema:** `sessions.agent` pasa de `NOT NULL` a **nullable**. BDs nuevas ya nacen así;
      las existentes se migran de forma idempotente reconstruyendo la tabla (SQLite no permite
      quitar `NOT NULL` con `ALTER`). Sin tablas nuevas todavía. `model` ya era nullable.
- [x] **`start` con agente opcional:** el agente posicional pasa a `nargs="?"`; `cowork start`
      sin argumentos abre una sesión solo-humano (individual). No rompe `cowork start <agente> [modelo]`.
- [x] **Formateo de salida tolerante a NULL:** helper `fmt_agent()` muestra `individual` cuando
      `agent` es NULL en `list`, `status`, `export`, `end` y los mensajes de `start`.
      **El SQL de `report` no cambia** (no agrupa por agente; `model` ya tolera NULL).

**Criterio de aceptación:** (a) con la BD en un disco externo desconectado, `cowork start`
avisa y no crea una BD vacía; (b) `cowork start` sin agente registra una sesión individual
y `list`/`export` la muestran sin imprimir `None`.

### Pendientes anotados (futuro, fuera de esta fase)

- [ ] **Multiplataforma:** la ruta por defecto `[UNIDAD]:\Users\[USUARIO]\.worklog\` es
      solo-Windows. Definir comportamiento en Linux / macOS / Android.
- [ ] **Identificación de unidad por etiqueta de volumen:** resolver la letra de unidad a
      partir del nombre del volumen (ej. `COWORK_USB`), para que la ruta no dependa de la
      letra asignada por el SO.
- [ ] **Sincronización automática** de la BD entre equipos (meta de largo plazo).

---

## Fase 6 — Mejoras de Status y Reporte de Proyecto

**Estado:** ✅ Completada (sesión 10 · 2026-07-30)

**Objetivo:** Mejorar la visibilidad de la actividad reciente en el proyecto y proporcionar un reporte detallado y rápido del estado acumulado del proyecto actual.

Checklist de tareas:

- [x] Modificar `cowork status` para mostrar la fecha y duración de la última sesión cerrada si no hay una sesión abierta.
- [x] Agregar flag `--this` al comando `report` para generar un resumen específico del proyecto actual.
- [x] El reporte `--this` debe incluir: total de sesiones, minutos totales, horas totales, fecha del primer y último registro, y datos de la última sesión cerrada.
- [x] Actualizar documentación y verificar funcionamiento con instalación via pipx.

**Criterio de aceptación:** `cowork status` informa sobre la última sesión cuando no hay actividad actual; `cowork report --this` muestra la estadística completa del proyecto sin necesidad de flags de agrupación global.

---

## Fase 7 — Sistema de pausas

**Estado:** ✅ Completada (sesión 12 · 2026-09-18)

**Objetivo:** permitir pausar y reanudar una sesión abierta sin cerrarla, para reflejar
interrupciones reales del trabajo (atender algo distinto un rato) sin fragmentar el
registro en varias sesiones sueltas.

Checklist de tareas:

- [x] Tabla nueva `session_pauses(id, session_id, pause_at, resume_at NULL, motivo)`.
      Se prefiere tabla sobre columnas simples en `sessions` porque permite varias pausas
      por sesión y guardar el motivo de cada una.
- [x] Regla: solo una pausa activa (`resume_at IS NULL`) por sesión; solo se puede pausar
      una sesión abierta y que no esté ya pausada.
- [x] Comando `cowork pause [motivo]`: abre una pausa en la sesión activa.
- [x] Comando `cowork resume`: cierra la pausa activa.
- [x] `status` muestra si la sesión está en pausa (desde cuándo, motivo) y el tiempo
      pausado acumulado.
- [x] `duration_minutes()` pasa a calcular **tiempo neto** = `(end_at - start_at) -
      Σ(resume_at - pause_at)` de las pausas cerradas de esa sesión. Sesiones históricas
      sin filas en `session_pauses` no cambian su duración calculada.
- [x] Decidir y documentar el comportamiento de `end` con una pausa activa sin resolver
      (auto-cerrarla en ese instante, de forma que el tiempo pausado hasta ahí no cuente
      como trabajado). **Decidido:** `end` y `start --force` cierran la pausa activa en
      `end_at` y avisan en pantalla.
- [x] Decidir si `report`/`export` muestran el tiempo pausado como columna informativa
      aparte del tiempo neto. **Decidido:** `report`/`export` usan siempre tiempo neto; el pausado
      se muestra solo en `report --this` ("Tiempo pausado") y en `export` por sesión si > 0.

**Criterio de aceptación:** una sesión con una o más pausas registra duración neta
correcta (excluye el tiempo pausado); sesiones sin pausas no cambian de comportamiento;
`status` refleja el estado de pausa.

---

## Fase 8 — Versión visible de cowork

**Estado:** ✅ Completada (sesión 13 · 2026-09-21) · sin cambios de esquema ni de datos (riesgo nulo para la BD).

**Objetivo:** que se vea qué versión de cowork se está ejecutando. Hoy hay dos rutas en el
PATH (lanzador `bin/` del repo y `cowork.exe` de pipx) y no hay forma de distinguirlas.

Checklist de tareas:

- [x] Constante única `__version__ = "0.2.0"` en `cowork.py`; `pyproject.toml` pasa a versión
      dinámica (`dynamic = ["version"]` + `[tool.setuptools.dynamic] version = {attr = "cowork.__version__"}`,
      quitando el `version =` estático). Una sola fuente de verdad, válida con pipx y con
      `python cowork.py` (`importlib.metadata` no sirve: falla fuera de la instalación pipx).
- [x] Flag global `cowork --version` (`argparse action="version"`).
- [x] `cowork -h`: primera línea `cowork version x.y.z` (argparse imprime `usage:` primero; se
      resuelve sobreescribiendo `print_help` del parser raíz). Solo el `-h` raíz.
- [x] `cowork status`: primera línea `cowork version x.y.z` en **todas** las ramas (sin
      proyecto, sin sesión, abierta, en pausa). Validado: ningún script parsea la salida de `status`.
- [x] Se sube a `0.2.0`: hubo cambios de esquema y funcionalidad real en Fases 5-7
      (pausas, campos opcionales, migraciones) desde `0.1.0`; no es solo un parche.
- [x] Documentado en README/USAGE la salida nueva y la regla de release (se edita solo `__version__`).

**Criterio de aceptación:** `cowork --version`, `cowork -h` y `cowork status` muestran la misma
versión con `cowork.exe` de pipx y con `python cowork.py`; tras cambiar `__version__` y
reinstalar, el paquete instalado refleja el nuevo número.

---

## Fase 9 — Registro estructurado de agentes y modelos por sesión (multi-agente)

**Estado:** ⬜ Pendiente · **cambio grande** (toca esquema, migración de datos reales y varias consultas)

**Objetivo:** reemplazar el emparejamiento manual por posición que se usa hoy para
sesiones con varios agentes/modelos (`agent = "claude ai, openai, brave ai"`,
`model = "[claude-sonnet-5], [openai-luna], [ai-grounding]"`, con la correspondencia
implícita por orden) por una relación explícita agente↔modelo, sin depender de que las
dos listas queden bien alineadas.

Checklist de tareas:

- [ ] Tabla nueva `session_agents(id, session_id, agent, model, posicion, added_at)`.
- [ ] `sessions.agent`/`model` quedan como histórico de solo lectura (no se eliminan:
      sirven de respaldo crudo para auditar la migración).
- [ ] **Migración de datos históricos** (idempotente, revisable con `--dry-run` antes de
      aplicar, no automática al abrir la BD):
      1. `agent`/`model` NULL → no genera filas (sesión individual).
      2. Sesión "simple" (sin coma en `agent`, sin formato de lista en `model`) → una
         fila en `session_agents` con posición 1, valores tal cual.
      3. Sesión "multi" (agent con comas y model en formato `[m1], [m2], ...`) → separar
         ambas listas y emparejar por posición, generando una fila por par.
      4. Casos ambiguos (conteo de agentes ≠ conteo de modelos, o formato no reconocido)
         → no migrar automáticamente; reportar al final la lista de sesiones que
         requieren revisión manual.
- [ ] `start` sigue aceptando opcionalmente el primer agente/modelo (crea la fila de
      posición 1 en `session_agents`).
- [ ] `list`, `status`, `export` y `report --model` pasan a leer de `session_agents` vía
      JOIN en vez de las columnas de texto de `sessions`.
- [ ] Decidir cómo se reparte/cuenta el tiempo de la sesión cuando tiene varios modelos
      en `report --model` (¿tiempo completo por cada modelo usado, o repartido?).

**Nota:** la Fase 12 (normalización con catálogo `agents`/`models` + FK) pasa a operar
sobre `session_agents.agent`/`model` en vez de `sessions.agent`/`model`, ya que esta fase
es la que se vuelve fuente de verdad del dato crudo.

**Criterio de aceptación:** todas las sesiones históricas quedan migradas a
`session_agents` o explícitamente listadas como pendientes de revisión manual;
`report --model` sobre datos migrados da totales coherentes con lo que se esperaría
sumando manualmente.

---

## Fase 10 — Edición de sesión abierta

**Estado:** ⬜ Pendiente · depende de la Fase 9 (`session_agents`)

**Objetivo:** permitir agregar o corregir agente/modelo de la sesión activa cuando se
suma un participante a mitad de camino, sin cerrar y reabrir sesión. Alcance: **solo la
sesión abierta actual**, no sesiones ya cerradas.

Checklist de tareas:

- [ ] Comando `cowork agent add <agente> [modelo]`: agrega la siguiente posición a
      `session_agents` de la sesión abierta.
- [ ] Comando `cowork agent list`: muestra los pares agente/modelo actuales de la sesión
      abierta, con su posición.
- [ ] Evaluar si además se ofrece corregir/eliminar un par ya agregado por error (ej.
      `cowork agent remove <posicion>`).

**Criterio de aceptación:** se puede agregar un agente/modelo a mitad de una sesión
abierta y queda reflejado correctamente en `session_agents` y en `status`.

---

## Fase 11 — Pruebas automatizadas

**Estado:** ⬜ Pendiente

**Objetivo:** blindar el core antes de seguir agregando funcionalidad. Tras las Fases 5,
7 y 9 (migraciones y cambios de esquema), conviene tener una red de seguridad.

Checklist de tareas:

- [ ] Suite con `unittest` o `pytest` en `tests/`, ejecutable sobre una BD temporal aislada.
- [ ] Cubrir el ciclo `start`/`end`/`status`, cálculo de duración, resolución de BD por capas
      y resolución de identidad (`.cowork` / remoto git / ruta).
- [ ] Cubrir los casos de Fase 5: BD ausente (avisar y parar) y sesión individual (agente null).
- [ ] Cubrir pausas (Fase 7) y registro multi-agente (Fase 9), incluyendo la migración.
- [ ] Cubrir `--version` y la línea de versión en `status` (Fase 8).

---

## Fase 12 — Normalización de agentes y modelos (tablas + FK)

**Estado:** ⬜ Pendiente · **cambio grande** (toca esquema, migración y varias consultas)

**Objetivo:** completar la idea 2. Pasar de texto libre a un catálogo normalizado, para
integridad referencial, evitar typos y reutilizar identificadores de modelo.

Checklist de tareas:

- [ ] Tablas nuevas `agents(id, name)` y `models(id, name[, agent_id])`.
- [ ] `session_agents.agent`/`model` (texto) → `session_agents.agent_id`/`model_id`
      (**FK nullable**).
- [ ] **Migración idempotente** que pueble `agents`/`models` con los valores de texto
      distintos ya existentes y reconecte cada fila de `session_agents` a su FK.
- [ ] `report`, `list`, `export` y `status` pasan a hacer **JOIN** en vez de leer la columna.
- [ ] Posibles comandos de catálogo (`agents`/`models` para listar/renombrar) — a evaluar.

**Criterio de aceptación:** las sesiones existentes quedan reconectadas a sus agentes/modelos
por FK; `report --model` sigue dando los mismos totales que antes de la migración.

---

## Fase 13 — Extras (futuro)

**Estado:** ⬜ Pendiente

Checklist de tareas candidatas:

- [ ] **Import del histórico:** parsear el `WORKLOG.md` actual (3 sesiones) y cargarlo en SQLite, para no perder el registro previo.
- [ ] Binario standalone con PyInstaller para máquinas sin Python.
- [ ] Export adicional a CSV/JSON para análisis externo.

---

## Fase 14 — Publicación en PyPI (final)

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
