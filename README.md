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
- Consultas de tiempo por proyecto, modelo y mes (`report`) y listado de sesiones (`list`).
- Export opcional a `WORKLOG.md` versionable en el repo (`export`).
- Ubicación de la BD configurable: comando `config`, variable `WORKLOG_HOME` o flag `--db`.
- Identidad de proyecto portable entre equipos, discos y usuarios (marcador `.cowork` o remoto git), no atada a la ruta.

---

## Instalación

Requiere **Python 3.8+**. Sin dependencias externas.

```bash
# Clona el repo
git clone https://github.com/drincastX/cowork.git

# Úsalo directamente
python cowork.py start "Claude Code" "claude-opus-4-8"
```

### Opción recomendada: instalar con pipx

[pipx](https://pipx.pypa.io) instala la herramienta en un entorno aislado y crea el comando `cowork` en el sistema. Una vez instalado pipx:

```bash
# Instala pipx una sola vez (si no lo tienes)
python -m pip install --user pipx
python -m pipx ensurepath        # abre una terminal nueva después

# Desde la carpeta del repo
pipx install .
```

A partir de ahí, `cowork ...` funciona desde cualquier carpeta. Para actualizar tras cambios: `pipx install . --force`.

### Alternativa sin pipx: lanzadores en `bin/`

Si prefieres no usar pipx, el repo trae lanzadores en `bin/`. Agrega esa carpeta `bin/` al PATH **una sola vez** por equipo.

**Windows** (PowerShell, persistente para tu usuario; reemplaza la ruta):

```powershell
[Environment]::SetEnvironmentVariable(
  "Path", $env:Path + ";C:\ruta\a\cowork\bin", "User")
```

Abre una terminal nueva y ya puedes ejecutar `cowork ...` desde cualquier carpeta.

**Linux / macOS** (bash o zsh; reemplaza la ruta):

```bash
chmod +x /ruta/a/cowork/bin/cowork
echo 'export PATH="$PATH:/ruta/a/cowork/bin"' >> ~/.bashrc   # o ~/.zshrc
source ~/.bashrc
```

Verifica desde cualquier carpeta:

```bash
cowork status
```

> Los lanzadores conservan tu carpeta actual: cowork identifica el proyecto por **dónde estás parado**, no por dónde vive el script.

### Mover la base de datos (`WORKLOG_HOME`)

Por defecto la BD vive en `~/.worklog/worklog.db`. Si quieres llevarla en un disco externo o carpeta sincronizada (para usarla desde varios equipos), define la variable `WORKLOG_HOME` apuntando a esa carpeta, o fija la ruta con `cowork config set-db <ruta>`. Ver la sección **Configuración e identidad**.

---

## Uso

```bash
python cowork.py init "Nombre del proyecto"         # registra o renombra el proyecto actual
python cowork.py start "Claude Code" "claude-opus-4-8"  # abre sesión
python cowork.py status                             # muestra sesión activa y tiempo transcurrido
python cowork.py end "resumen de lo trabajado"      # cierra y calcula duración
```

Consultas y export:

```bash
python cowork.py list -n 10                          # últimas sesiones del proyecto
python cowork.py report --model                      # tiempo agregado por modelo (o --project / --month)
python cowork.py export                              # genera WORKLOG.md desde la BD
```

Si olvidaste cerrar una sesión anterior:

```bash
python cowork.py start "Claude Code" --force        # auto-cierra la anterior y abre la nueva
```

---

## Configuración e identidad

**¿Dónde vive la base de datos?** Se resuelve por capas (gana la primera): flag `--db <ruta>` → variable `WORKLOG_HOME` → `config.json` → por defecto `~/.worklog/worklog.db`.

```bash
python cowork.py config                              # muestra la ruta efectiva de la BD y de qué fuente salió
python cowork.py config set-db "D:\datos\worklog.db" # fija la ruta en config.json
```

**¿Cómo se identifica un proyecto?** No por la ruta (que cambia entre equipos o discos), sino por un identificador estable resuelto por capas: marcador `.cowork` → URL del remoto git → ruta (último recurso). La primera vez, `init`/`start` crean un archivo `.cowork` con un `id` y un `name`.

> **Commitea el archivo `.cowork`.** Es una etiqueta de identidad (como `.git`), no guarda datos de sesiones. Versionarlo hace que el mismo proyecto cuente igual desde cualquier equipo, disco o usuario. Si dos proyectos comparten nombre, `init` avisa y puedes asociarlos con `cowork init --link <uid>`.

---

## Documentación

- [`USAGE.md`](USAGE.md) — guía breve para registrar el tiempo con cowork (para el agente).
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — diseño del sistema y decisiones técnicas.
- [`docs/PLAN.md`](docs/PLAN.md) — plan de ejecución por fases con checklist de progreso.
- [`docs/manual-tests/`](docs/manual-tests/) — guías de prueba manual en entorno aislado.
- [`AGENTS.md`](AGENTS.md) — instrucciones para el agente de código.
- [`DEVLOG.md`](DEVLOG.md) — registro de desarrollo sesión a sesión.

---

## Estado

- **Fase 1 completada** — `init`, `start`, `end`, `status` con SQLite.
- **Fase 2 completada** — `list`, `report`, `export`.
- **Fase 2.5 completada** — configuración de la BD (`config`) e identidad de proyecto portable (`.cowork` / remoto git).
- **Fase 3 completada** — `cowork` invocable desde cualquier carpeta (lanzadores en `bin/` + PATH) y guía de uso para el agente.
- **Fase 4 completada** — empaquetado con `pyproject.toml`, instalable con `pipx install .` (versión 0.1.0).
- Siguiente: Fase 5 (extras) y Fase 6 (publicación en PyPI).

---

## Licencia

MIT © 2026 Rubén Orozco (drincastX). Ver [`LICENSE`](LICENSE).
