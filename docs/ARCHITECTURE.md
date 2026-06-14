# Arquitectura — Sistema de registro de sesiones de trabajo humano + IA

> Proyecto: herramienta CLI para registrar sesiones de trabajo colaborativo entre una persona y agentes/chats de IA.
> Autor de referencia: **drincast** (Rubén Orozco).
> Estado: documento de diseño para iniciar implementación con un agente de código.

---

## 1. Objetivo

Crear una herramienta de línea de comandos, **externa a los proyectos**, que registre sesiones de trabajo identificando:

- Tiempo invertido (minutos y horas).
- Autores que participaron (persona + agente de IA).
- Nombre del chat/agente de IA y el modelo usado.
- Fecha y hora de inicio.
- Fecha y hora de fin.

Restricciones de diseño:

- **No debe consumir tokens de modelos de IA.** Todo el procesamiento es local. El agente solo invoca comandos de terminal (igual que `git commit`), no procesa nada con un modelo.
- **El estado vive fuera del proyecto** (base de datos central en el home del usuario). El proyecto no se contamina con scripts ni lógica.
- **Opcionalmente** se puede exportar una vista legible (`WORKLOG.md`) dentro del repo para que quede versionada en GitHub.
- **Implementación inicial:** un único script Python con biblioteca estándar (sin dependencias externas). Evolución posterior a paquete instalable (`pipx`).

### Decisiones confirmadas

- **Nombre del comando:** `cowork`. La carpeta de datos (`~/.worklog/`), la BD (`worklog.db`), el export (`WORKLOG.md`) y la variable (`WORKLOG_HOME`) conservan "worklog" porque nombran el *registro*; `cowork` nombra la *acción*.
- **Sesión huérfana:** ambos comportamientos disponibles. Por defecto avisa y para; con `--force` auto-cierra la previa y abre la nueva.
- **Export:** a demanda únicamente (`cowork export`). Nunca automático.

---

## 2. Decisión de diseño: manejo de tiempo

**No se usa UTC puro.** Se almacena el **instante absoluto con offset explícito** en formato ISO 8601 completo:

```
2026-06-13T10:28:00-05:00
```

Razones:

- El usuario opera en una sola zona horaria (Colombia, `-05:00`, sin horario de verano). UTC puro obligaría a convertir en cada lectura, introduciendo riesgo de error sin beneficio real.
- El formato ISO 8601 con offset es **inequívoco** (identifica el instante exacto como lo haría UTC) pero **conserva la hora local real** sin conversiones mentales.
- SQLite ordena correctamente estos strings cronológicamente.
- Si en el futuro hay colaboradores en otras zonas o el usuario viaja, el offset explícito permite comparar y sumar tiempos de forma fiable.

Regla: **almacenar el momento con su offset, nunca convertir a UTC para guardar.** Para mostrar, se usa la parte local tal cual.

---

## 3. Arquitectura de capas

```
┌─────────────────────────────────────────────────┐
│  Agente IA / Usuario (terminal)                  │
│  cowork start · end · status · report · export   │
└────────────────────┬────────────────────────────┘
                     │ invoca (cero tokens IA)
                     ▼
┌─────────────────────────────────────────────────┐
│  worklog.py  (Python stdlib: sqlite3,            │
│              argparse, datetime, pathlib)        │
│  · resolución de proyecto por ruta               │
│  · manejo de sesión abierta / huérfana           │
│  · cálculo de duración con ISO 8601 + offset     │
└──────────┬───────────────────────┬───────────────┘
           │                       │
           ▼                       ▼
┌──────────────────────┐   ┌──────────────────────┐
│ ~/.worklog/          │   │ <proyecto>/WORKLOG.md│
│   worklog.db (SQLite)│   │  (export opcional,    │
│   FUENTE DE VERDAD   │   │   solo lectura)       │
└──────────────────────┘   └──────────────────────┘
```

La **fuente de verdad** es siempre la base SQLite. El `WORKLOG.md` es una proyección de solo lectura que se regenera con `export`; nunca se edita a mano.

---

## 4. Ubicación del estado

Resolución de la carpeta de datos, cross-platform:

1. Si la variable de entorno `WORKLOG_HOME` está definida, se usa esa ruta.
2. Si no, se usa `~/.worklog/` (Linux/macOS) o `%USERPROFILE%\.worklog\` (Windows).

Dentro de esa carpeta:

- `worklog.db` — base de datos SQLite (única fuente de verdad).
- `config.toml` — (fase futura) configuración opcional: autor por defecto, auto-export, etc.

Nada se escribe en el proyecto salvo que se invoque `export`.

---

## 5. Esquema de la base de datos

Dos tablas. Separar proyectos de sesiones evita repetir metadatos y permite renombrar un proyecto sin tocar su historial.

```sql
CREATE TABLE projects (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    path         TEXT UNIQUE NOT NULL,   -- ruta absoluta; identifica el proyecto
    name         TEXT NOT NULL,          -- nombre legible (editable)
    created_at   TEXT NOT NULL,          -- ISO 8601 con offset
	description  TEXT 				     -- descripción del proyecto
);

CREATE TABLE sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   INTEGER NOT NULL REFERENCES projects(id),
    author       TEXT NOT NULL DEFAULT 'drincast',
    agent        TEXT NOT NULL,          -- "Claude Code", "Antigravity", "Cursor"...
    model        TEXT,                   -- "claude-opus-4-8" (puede ser NULL)
    start_at     TEXT NOT NULL,          -- ISO 8601 con offset
    end_at       TEXT,                   -- NULL = sesión abierta
    summary      TEXT
);

CREATE INDEX idx_sessions_project ON sessions(project_id);
CREATE INDEX idx_sessions_open    ON sessions(project_id, end_at);
```

Decisiones clave:

- **Sin columna de duración:** se calcula al vuelo desde `start_at` y `end_at`. Evita inconsistencias.
- **Sin totales acumulados almacenados:** los agregados se obtienen con SQL (`SUM`, `GROUP BY`). Esto elimina por completo la fragilidad de re-parsear y reescribir totales que tiene el sistema actual basado en Markdown.
- **Sesión abierta = `end_at IS NULL`.** Solo puede haber una abierta por proyecto.
- `model` es nullable porque no siempre se conoce el ID exacto del modelo.

---

## 6. Regla: una sesión abierta por proyecto

Antes de `start`, se consulta si ya existe una sesión con `end_at IS NULL` en el proyecto actual.

Manejo de **sesión huérfana** (el usuario olvidó cerrar). El comportamiento lo decide quien ejecuta `start`, mediante flag:

- **Por defecto (avisar y parar):** `start` detecta la sesión abierta previa, **avisa y no abre** la nueva. El usuario decide qué hacer (cerrar la anterior con `end`, o forzar).
- **`start --force`:** auto-cierra la sesión previa (calculando su duración hasta ese momento) y abre la nueva en un solo paso.
- `end` sin sesión abierta da un **error claro** ("no hay sesión abierta en este proyecto"), nunca corrompe datos.

Esto resuelve el escenario que en el sistema Markdown actual produciría duraciones corruptas.

---

## 7. Comandos

| Comando | Comportamiento |
|---|---|
| `cowork init [nombre]` | Registra/renombra el proyecto de la ruta actual. Opcional. |
| `cowork start <agente> [modelo]` | Resuelve/crea proyecto por ruta actual y abre sesión. Si hay una abierta, avisa y para. |
| `cowork start <agente> [modelo] --force` | Auto-cierra la sesión abierta previa y abre la nueva. |
| `cowork end [resumen]` | Cierra la sesión abierta del proyecto actual y calcula duración. |
| `cowork status` | Muestra la sesión abierta (si hay) y el tiempo transcurrido en vivo. |
| `cowork list [-n N]` | Últimas N sesiones del proyecto actual. |
| `cowork report [--project] [--month] [--model]` | Agregados de tiempo por proyecto, modelo y/o mes. |
| `cowork export [--md] [--path RUTA]` | Genera `WORKLOG.md` en el proyecto desde la BD. A demanda. |

Notas de comportamiento:

- `start` funciona **sin `init` previo**: en una ruta nueva crea el proyecto automáticamente usando el nombre del directorio. `init` solo sirve para asignar un nombre distinto al del directorio.
- El proyecto se identifica por la **ruta absoluta** desde donde se ejecuta el comando.
- El autor por defecto es **drincast** (configurable en fase futura).

---

## 8. Export a Markdown

`export` regenera un `WORKLOG.md` con el mismo espíritu del formato actual del usuario:

- Encabezado con totales (sesiones, minutos, horas, última fecha).
- Sesiones en **orden descendente** (más reciente primero).
- Por sesión: agente, modelo, inicio, fin, duración, resumen.

Diferencia esencial: el Markdown es **derivado de SQLite**, no editado a mano. La BD central permite además consultas que el Markdown nunca pudo dar (tiempo por modelo, por mes, por proyecto).

El export es **a demanda**: se ejecuta solo cuando el usuario lo requiere con `cowork export`. Nunca automático tras `end`. La base SQLite es siempre la fuente de verdad; el `WORKLOG.md` se genera cuando se quiere una vista versionable en el repo.

---

## 9. Compatibilidad

- **Python 3.8+** con biblioteca estándar únicamente (`sqlite3`, `argparse`, `datetime`, `pathlib`, `os`). Sin dependencias que instalar.
- **Windows, Linux y macOS.** Una sola implementación en Python reemplaza los dos scripts (`.ps1` + `.sh`) actuales, eliminando el riesgo de que diverjan.
- El comando `cowork` se hace invocable globalmente añadiéndolo al PATH (fase 3) o instalándolo con `pipx` (fase 4). El script principal puede llamarse `cowork.py`.

---

## 10. Migración desde el sistema actual

El `WORKLOG.md` existente contiene 3 sesiones. En la fase de extras se incluye un import one-shot que parsea ese Markdown y carga las sesiones históricas en SQLite, para no perder el registro previo.
