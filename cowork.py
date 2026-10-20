"""
cowork — registro de sesiones de trabajo humano + IA.
Solo biblioteca estándar de Python. Sin dependencias externas.
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Fuente única de verdad de la versión (Fase 8). pyproject.toml la lee de aquí
# vía version = {attr = "cowork.__version__"}; al liberar una versión nueva
# solo se edita esta línea.
__version__ = "0.3.0"

# Versión del esquema de la BD (Fase 9), guardada en PRAGMA user_version.
# Si la BD trae un esquema más nuevo que este, los comandos que escriben paran.
# 0 = esquema previo a la Fase 9 · 1 = tabla session_agents.
SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# Configuración y resolución de la BD (Fase 2.5)
#
# La carpeta de configuración (donde vive config.json) se resuelve con
# WORKLOG_HOME o, por defecto, ~/.worklog. La ruta de la BD se resuelve por
# capas: --db  >  WORKLOG_HOME  >  config.json[db_path]  >  default.
# ---------------------------------------------------------------------------

# Anulación de la ruta de BD vía flag global --db; la fija main() al arrancar.
_DB_OVERRIDE = None


def get_config_dir() -> Path:
    env = os.environ.get("WORKLOG_HOME")
    return Path(env) if env else Path.home() / ".worklog"


def get_config_path() -> Path:
    return get_config_dir() / "config.json"


def load_config() -> dict:
    p = get_config_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_config(cfg: dict) -> None:
    d = get_config_dir()
    d.mkdir(parents=True, exist_ok=True)
    get_config_path().write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def resolve_db():
    """Devuelve (Path de la BD, fuente) según el orden de capas."""
    if _DB_OVERRIDE:
        return Path(_DB_OVERRIDE).expanduser(), "--db"
    if os.environ.get("WORKLOG_HOME"):
        return get_config_dir() / "worklog.db", "WORKLOG_HOME"
    db_path = load_config().get("db_path")
    if db_path:
        return Path(db_path).expanduser(), "config.json"
    return get_config_dir() / "worklog.db", "default"


def get_db_path() -> Path:
    return resolve_db()[0]


# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------

def _db_unavailable_msg(path: Path, source: str) -> str:
    """Mensaje guía cuando la BD resuelta no existe (Fase 5, Etapa A)."""
    return (
        f"La BD (fuente: {source}) en '{path}' no está disponible.\n"
        f"Puede que el disco esté desconectado o la ruta sea incorrecta.\n"
        f"  · Conéctalo, o corrige la ruta con: cowork config set-db <ruta>\n"
        f"  · Si es un proyecto nuevo, créala con: cowork init"
    )


def open_db(create: bool = False, write: bool = False) -> sqlite3.Connection:
    """Abre la BD resuelta por capas.

    Con create=False (por defecto), si el archivo de BD no existe **avisa y para**
    en vez de crear una BD "fantasma" vacía (Fase 5, Etapa A). Solo `init` la crea
    intencionalmente con create=True.

    Con write=True (comandos que registran datos), si la BD tiene un esquema más
    nuevo del que esta versión conoce, **avisa y para** (Fase 9). Los comandos de
    solo lectura continúan con un aviso.
    """
    db_path, source = resolve_db()
    if not db_path.exists():
        if not create:
            print(_db_unavailable_msg(db_path, source), file=sys.stderr)
            sys.exit(1)
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    db_version = conn.execute("PRAGMA user_version").fetchone()[0]
    if db_version > SCHEMA_VERSION:
        msg = (
            f"La BD usa un esquema más nuevo (v{db_version}) que esta versión de "
            f"cowork ({__version__}, esquema v{SCHEMA_VERSION}).\n"
            f"  Actualiza cowork (p. ej. 'pipx install --force .') antes de registrar sesiones."
        )
        if write:
            print(msg, file=sys.stderr)
            conn.close()
            sys.exit(1)
        print(f"Aviso: {msg}", file=sys.stderr)
        return conn  # no se toca un esquema que no se conoce

    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            path        TEXT UNIQUE NOT NULL,
            name        TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  INTEGER NOT NULL REFERENCES projects(id),
            author      TEXT NOT NULL DEFAULT 'drincast',
            agent       TEXT,
            model       TEXT,
            start_at    TEXT NOT NULL,
            end_at      TEXT,
            summary     TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_sessions_project
            ON sessions(project_id);

        CREATE INDEX IF NOT EXISTS idx_sessions_open
            ON sessions(project_id, end_at);
    """)
    conn.commit()

    # Migración Fase 2.5: identidad portable (uid estable + remoto git).
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(projects)")}
    if "uid" not in cols:
        conn.execute("ALTER TABLE projects ADD COLUMN uid TEXT")
    if "git_remote" not in cols:
        conn.execute("ALTER TABLE projects ADD COLUMN git_remote TEXT")
    for r in conn.execute(
        "SELECT id FROM projects WHERE uid IS NULL OR uid = ''"
    ).fetchall():
        conn.execute(
            "UPDATE projects SET uid = ? WHERE id = ?", (str(uuid.uuid4()), r["id"])
        )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_uid ON projects(uid)"
    )
    conn.commit()

    # Migración Fase 5 (Etapa B): sessions.agent pasa de NOT NULL a nullable,
    # para registrar trabajo solo-humano (sin agente). SQLite no permite quitar
    # NOT NULL con ALTER, así que se reconstruye la tabla de forma idempotente.
    agent_col = next(
        (r for r in conn.execute("PRAGMA table_info(sessions)") if r["name"] == "agent"),
        None,
    )
    if agent_col is not None and agent_col["notnull"] == 1:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.executescript("""
            CREATE TABLE sessions_new (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id  INTEGER NOT NULL REFERENCES projects(id),
                author      TEXT NOT NULL DEFAULT 'drincast',
                agent       TEXT,
                model       TEXT,
                start_at    TEXT NOT NULL,
                end_at      TEXT,
                summary     TEXT
            );
            INSERT INTO sessions_new
                (id, project_id, author, agent, model, start_at, end_at, summary)
            SELECT id, project_id, author, agent, model, start_at, end_at, summary
            FROM sessions;
            DROP TABLE sessions;
            ALTER TABLE sessions_new RENAME TO sessions;
            CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_open ON sessions(project_id, end_at);
        """)
        conn.commit()
        conn.execute("PRAGMA foreign_keys = ON")

    # Fase 7: pausas de sesión. Se crea DESPUÉS de la reconstrucción de `sessions`
    # (Fase 5B) para que su FK no quede apuntando a una tabla reemplazada.
    # El índice único parcial garantiza una sola pausa activa por sesión.
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS session_pauses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  INTEGER NOT NULL REFERENCES sessions(id),
            pause_at    TEXT NOT NULL,
            resume_at   TEXT,
            motivo      TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_pauses_session
            ON session_pauses(session_id);

        CREATE UNIQUE INDEX IF NOT EXISTS idx_pauses_active
            ON session_pauses(session_id) WHERE resume_at IS NULL;
    """)
    conn.commit()

    # Fase 9: participantes de cada sesión, una fila por par agente-modelo.
    # `position` es el orden del agente; se repite si el agente tiene varios
    # modelos (agregadores). Se crea tras la reconstrucción de `sessions` (Fase 5B)
    # por la misma razón que session_pauses.
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS session_agents (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  INTEGER NOT NULL REFERENCES sessions(id),
            agent       TEXT NOT NULL,
            model       TEXT,
            position    INTEGER NOT NULL,
            added_at    TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_session_agents_session
            ON session_agents(session_id);
    """)
    if conn.execute("PRAGMA user_version").fetchone()[0] < SCHEMA_VERSION:
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()


# ---------------------------------------------------------------------------
# Helpers de tiempo
# ---------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def duration_minutes(start: str, end: str) -> float:
    delta = parse_iso(end) - parse_iso(start)
    return delta.total_seconds() / 60


def get_active_pause(conn: sqlite3.Connection, session_id: int):
    return conn.execute(
        "SELECT * FROM session_pauses WHERE session_id = ? AND resume_at IS NULL",
        (session_id,),
    ).fetchone()


def close_active_pause(conn: sqlite3.Connection, session_id: int, ts: str) -> bool:
    """Cierra la pausa activa (si existe) en `ts`. Devuelve True si había una."""
    cur = conn.execute(
        "UPDATE session_pauses SET resume_at = ? "
        "WHERE session_id = ? AND resume_at IS NULL",
        (ts, session_id),
    )
    return cur.rowcount > 0


def paused_minutes(conn: sqlite3.Connection, session_id: int, upto: str = None) -> float:
    """Minutos pausados de una sesión. Una pausa activa cuenta hasta `upto`
    (si se indica); las cerradas cuentan siempre completas."""
    total = 0.0
    for p in conn.execute(
        "SELECT pause_at, resume_at FROM session_pauses WHERE session_id = ?",
        (session_id,),
    ):
        fin = p["resume_at"] or upto
        if fin:
            total += duration_minutes(p["pause_at"], fin)
    return total


def net_minutes(conn: sqlite3.Connection, sess, end: str = None) -> float:
    """Tiempo neto de una sesión = (fin - inicio) - pausas. `end` por defecto es
    sess['end_at']; para sesiones abiertas pasar now_iso(). Sesiones sin pausas
    dan exactamente la duración bruta."""
    fin = end or sess["end_at"]
    bruto = duration_minutes(sess["start_at"], fin)
    return max(0.0, bruto - paused_minutes(conn, sess["id"], upto=fin))


def paused_by_session(conn: sqlite3.Connection) -> dict:
    """{session_id: minutos pausados} para pausas cerradas (evita N+1 en reportes)."""
    out = defaultdict(float)
    for p in conn.execute(
        "SELECT session_id, pause_at, resume_at FROM session_pauses "
        "WHERE resume_at IS NOT NULL"
    ):
        out[p["session_id"]] += duration_minutes(p["pause_at"], p["resume_at"])
    return out


def fmt_duration(mins: float) -> str:
    h, m = divmod(int(mins), 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def elapsed_display(start: str) -> str:
    delta = datetime.now().astimezone() - parse_iso(start)
    total = int(delta.total_seconds())
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


# ---------------------------------------------------------------------------
# Resolución de proyecto
# ---------------------------------------------------------------------------

def current_path() -> str:
    return str(Path.cwd().resolve())


MARKER_NAME = ".cowork"


def short_uid(uid) -> str:
    return (uid or "")[:8]


def find_marker(start: str):
    """Busca .cowork subiendo directorios. Devuelve (datos, ruta) o (None, None)."""
    d = Path(start).resolve()
    for cand in (d, *d.parents):
        m = cand / MARKER_NAME
        if m.is_file():
            try:
                return json.loads(m.read_text(encoding="utf-8")), m
            except (json.JSONDecodeError, OSError):
                return None, None
    return None, None


def write_marker(directory: str, uid: str, name: str) -> Path:
    m = Path(directory) / MARKER_NAME
    m.write_text(
        json.dumps({"id": uid, "name": name}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return m


def normalize_remote(url: str) -> str:
    """Normaliza la URL del remoto para que https y ssh del mismo repo coincidan."""
    u = url.strip()
    if u.endswith(".git"):
        u = u[:-4]
    u = u.rstrip("/")
    if u.startswith("git@"):              # git@host:user/repo
        u = "https://" + u[4:].replace(":", "/", 1)
    elif "://" in u:                      # https://host/... o ssh://...
        u = "https://" + u.split("://", 1)[1]
    return u.lower()


def git_remote(directory: str):
    """URL normalizada del remoto 'origin', o None si no es repo git con remoto."""
    try:
        out = subprocess.run(
            ["git", "-C", str(directory), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    return normalize_remote(out.stdout.strip())


def _project_by_uid(conn, uid):
    return conn.execute("SELECT * FROM projects WHERE uid = ?", (uid,)).fetchone()


def find_project(conn):
    """Resuelve el proyecto actual por capas (marcador → remoto git → ruta).
    Solo lectura: no crea ni escribe marcador."""
    path = current_path()
    data, _ = find_marker(path)
    if data and data.get("id"):
        row = _project_by_uid(conn, data["id"])
        if row:
            return row
    remote = git_remote(path)
    if remote:
        row = conn.execute(
            "SELECT * FROM projects WHERE git_remote = ?", (remote,)
        ).fetchone()
        if row:
            return row
    return conn.execute("SELECT * FROM projects WHERE path = ?", (path,)).fetchone()


def ensure_project(conn):
    """Resuelve o crea el proyecto actual y fija el marcador .cowork.
    Devuelve (row, fuente, marcador_creado)."""
    path = current_path()
    data, _ = find_marker(path)

    # Capa 1: marcador .cowork presente.
    if data and data.get("id"):
        uid = data["id"]
        name = data.get("name") or Path(path).name
        row = _project_by_uid(conn, uid)
        if row:
            conn.execute("UPDATE projects SET path = ? WHERE id = ?", (path, row["id"]))
            conn.commit()
            return _project_by_uid(conn, uid), "marcador", False
        # Marcador sin proyecto en esta BD (p.ej. repo clonado): crear con ese uid.
        remote = git_remote(path)
        conn.execute(
            "INSERT INTO projects (path, name, created_at, uid, git_remote) "
            "VALUES (?, ?, ?, ?, ?)",
            (path, name, now_iso(), uid, remote),
        )
        conn.commit()
        return _project_by_uid(conn, uid), "marcador", False

    # Sin marcador: adoptar por ruta (local/migración), luego por remoto, o crear.
    remote = git_remote(path)
    row = conn.execute("SELECT * FROM projects WHERE path = ?", (path,)).fetchone()
    fuente = "ruta"
    if not row and remote:
        row = conn.execute(
            "SELECT * FROM projects WHERE git_remote = ?", (remote,)
        ).fetchone()
        if row:
            fuente = "remoto git"

    if row:
        uid, name = row["uid"], row["name"]
        if remote and not row["git_remote"]:
            conn.execute(
                "UPDATE projects SET git_remote = ? WHERE id = ?", (remote, row["id"])
            )
        conn.execute("UPDATE projects SET path = ? WHERE id = ?", (path, row["id"]))
        conn.commit()
    else:
        uid = str(uuid.uuid4())
        name = Path(path).name
        fuente = "nuevo"
        conn.execute(
            "INSERT INTO projects (path, name, created_at, uid, git_remote) "
            "VALUES (?, ?, ?, ?, ?)",
            (path, name, now_iso(), uid, remote),
        )
        conn.commit()

    # Fijar identidad portable escribiendo el marcador.
    write_marker(path, uid, name)
    return _project_by_uid(conn, uid), fuente, True


def fmt_agent(agent) -> str:
    """Etiqueta legible del agente; 'individual' cuando es trabajo solo-humano (NULL)."""
    return agent if agent else "individual"


# ---------------------------------------------------------------------------
# Participantes de la sesión: agentes y modelos (Fase 9)
#
# El texto libre de `start` (y el histórico de sessions.agent/model) se
# interpreta así:
#   agente: "Claude ai, Hostgator ai"
#   modelo: "[claude-sonnet-5], [gpt-5.6 Terra, grok-4.6]"
# Cada [...] es el grupo de modelos del agente en esa posición.
# ---------------------------------------------------------------------------

_MODEL_GROUP = re.compile(r"\[([^\[\]]*)\]")

AMBIGUOUS_HELP = (
    "Con varios agentes, indica un grupo de modelos por agente, en el mismo orden:\n"
    '  cowork start "Claude ai, Hostgator ai" "[claude-sonnet-5], [gpt-5.6, grok-4.6]"'
)


def _clean(text: str) -> str:
    """Recorta y colapsa espacios internos ("Calude  ai" → "Calude ai")."""
    return " ".join(text.split())


def _split_list(text: str) -> list:
    """Separa por comas, limpia y descarta vacíos (p. ej. por una coma final)."""
    return [x for x in (_clean(p) for p in text.split(",")) if x]


def parse_participants(agent_text, model_text):
    """Interpreta el texto de agente/modelo. Devuelve (tipo, pares).

    tipo: 'individual' | 'simple' | 'multi' | 'ambiguous'.
    pares: lista de (agente, modelo | None, posición), una por par agente-modelo.

    Reglas:
      · agente y modelo NULL o vacíos → individual, sin pares.
      · modelos con corchetes: cada [...] es el grupo del agente en esa posición;
        corchetes sueltos se ignoran; texto fuera de corchetes → ambiguo.
      · modelos sin corchetes: uno por agente, separados por coma.
      · mismo nº de agentes que de grupos → se emparejan por posición.
      · un solo agente → todos los modelos son suyos.
      · agentes sin modelo → pares con modelo None.
      · cualquier otro caso → ambiguo (no se adivina).
    No corrige mayúsculas ni erratas.
    """
    agents = _split_list(agent_text or "")
    model_text = model_text or ""

    if "[" in model_text or "]" in model_text:
        groups = [_split_list(g) for g in _MODEL_GROUP.findall(model_text)]
        resto = re.sub(r"[\s,\[\]]", "", _MODEL_GROUP.sub("", model_text))
        if resto:
            return "ambiguous", []
    else:
        groups = [[m] for m in _split_list(model_text)]

    if not agents and not any(groups):
        return "individual", []
    if not agents:
        return "ambiguous", []

    if not groups:
        groups = [[] for _ in agents]
    elif len(agents) == 1:
        groups = [[m for g in groups for m in g]]
    elif len(agents) != len(groups):
        return "ambiguous", []

    pairs = []
    for pos, (agent, models) in enumerate(zip(agents, groups), start=1):
        for model in (models or [None]):
            pairs.append((agent, model, pos))
    return ("simple" if len(pairs) == 1 else "multi"), pairs


def fmt_participants(pairs) -> str:
    """'Claude ai (claude-sonnet-5) · Hostgator ai (gpt-5.6, grok-4.6)'."""
    grupos = {}
    for agent, model, pos in pairs:
        modelos = grupos.setdefault((pos, agent), [])
        if model:
            modelos.append(model)
    partes = [
        f"{agent} ({', '.join(modelos)})" if modelos else agent
        for (_, agent), modelos in grupos.items()
    ]
    return " · ".join(partes) if partes else "individual"


def load_participants(conn) -> dict:
    """{session_id: [(agente, modelo, posición), ...]} de session_agents."""
    out = defaultdict(list)
    for r in conn.execute(
        "SELECT session_id, agent, model, position FROM session_agents "
        "ORDER BY session_id, position, id"
    ):
        out[r["session_id"]].append((r["agent"], r["model"], r["position"]))
    return out


def participants_of(conn, session_id: int) -> list:
    return [
        (r["agent"], r["model"], r["position"])
        for r in conn.execute(
            "SELECT agent, model, position FROM session_agents "
            "WHERE session_id = ? ORDER BY position, id",
            (session_id,),
        )
    ]


def add_participants(conn, session_id: int, pairs, added_at: str) -> None:
    conn.executemany(
        "INSERT INTO session_agents (session_id, agent, model, position, added_at) "
        "VALUES (?, ?, ?, ?, ?)",
        [(session_id, a, m, p, added_at) for a, m, p in pairs],
    )


def session_label(sess, pairs) -> str:
    """Etiqueta de participantes de una sesión. Con filas en session_agents usa
    esas; si no (sesión no migrada o creada con una versión anterior), muestra el
    texto crudo de sessions.agent/model (lectura con respaldo)."""
    if pairs:
        return fmt_participants(pairs)
    model = f" ({sess['model']})" if sess["model"] else ""
    return f"{fmt_agent(sess['agent'])}{model}"


def report_models(sess, pairs) -> list:
    """Modelos distintos de una sesión para `report --model`. Sin filas en
    session_agents interpreta el texto crudo; si es ambiguo usa el texto tal cual.
    '—' representa 'sin modelo'."""
    if not pairs:
        kind, pairs = parse_participants(sess["agent"], sess["model"])
        if kind == "ambiguous":
            return [sess["model"] or "—"]
    modelos = []
    for _, model, _ in pairs:
        clave = model or "—"
        if clave not in modelos:
            modelos.append(clave)
    return modelos or ["—"]


def db_summary_line() -> str:
    """Línea de resumen con la ruta efectiva de la BD y su fuente (Fase 5)."""
    path, source = resolve_db()
    return f"  BD: {path} (fuente: {source})"


def get_open_session(conn: sqlite3.Connection, project_id: int):
    return conn.execute(
        "SELECT * FROM sessions WHERE project_id = ? AND end_at IS NULL",
        (project_id,),
    ).fetchone()


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------

def cmd_init(args) -> None:
    # --db-path: persiste la ubicación de la BD en config.json antes de crearla,
    # para elegir dónde vivirá (p. ej. disco externo) en un solo paso.
    if getattr(args, "db_path", None):
        ruta = str(Path(args.db_path).expanduser())
        cfg = load_config()
        cfg["db_path"] = ruta
        save_config(cfg)
        print(f"Ruta de BD guardada en config.json: {ruta}")
        if os.environ.get("WORKLOG_HOME"):
            print(
                "  Aviso: WORKLOG_HOME está activo y tiene prioridad sobre config.json;"
                " la ruta guardada no se usará mientras esa variable esté definida."
            )

    # init es el punto de creación intencional de la BD (create=True).
    with open_db(create=True, write=True) as conn:
        # --link: asocia el directorio actual a un proyecto existente por uid.
        if getattr(args, "link", None):
            target = _project_by_uid(conn, args.link)
            if not target:
                target = conn.execute(
                    "SELECT * FROM projects WHERE uid LIKE ?", (args.link + "%",)
                ).fetchone()
            if not target:
                print(f"No existe ningún proyecto con uid '{args.link}'.")
                sys.exit(1)
            path = current_path()
            conn.execute("UPDATE projects SET path = ? WHERE id = ?", (path, target["id"]))
            conn.commit()
            write_marker(path, target["uid"], target["name"])
            print(
                f"Directorio enlazado al proyecto '{target['name']}' "
                f"(uid {short_uid(target['uid'])}). Marcador {MARKER_NAME} escrito."
            )
            return

        project, fuente, marcador_creado = ensure_project(conn)

        if args.nombre and args.nombre != project["name"]:
            dup = conn.execute(
                "SELECT * FROM projects WHERE name = ? AND uid != ?",
                (args.nombre, project["uid"]),
            ).fetchone()
            if dup:
                print(
                    f"Aviso: ya existe otro proyecto llamado '{args.nombre}' "
                    f"(uid {short_uid(dup['uid'])}). Los nombres pueden repetirse; si es "
                    f"el mismo proyecto, usa 'cowork init --link {short_uid(dup['uid'])}'."
                )
            old = project["name"]
            conn.execute(
                "UPDATE projects SET name = ? WHERE id = ?", (args.nombre, project["id"])
            )
            conn.commit()
            write_marker(current_path(), project["uid"], args.nombre)
            print(
                f"Proyecto renombrado: '{old}' → '{args.nombre}' "
                f"(uid {short_uid(project['uid'])})."
            )
        else:
            print(
                f"Proyecto: '{project['name']}' · uid {short_uid(project['uid'])} "
                f"· identidad por {fuente}."
            )
        estado = "nuevo" if fuente == "nuevo" else "existente"
        print(f"  Estado: proyecto {estado}.")
        print(db_summary_line())
        if marcador_creado:
            print(f"Marcador {MARKER_NAME} creado (versionable).")


def cmd_start(args) -> None:
    agent = args.agente or None
    model = args.modelo or None
    # Se valida antes de tocar la BD (incluido el auto-cierre de --force).
    kind, pairs = parse_participants(agent, model)
    if kind == "ambiguous":
        print(
            f'No se pudo interpretar agente/modelo: "{agent or ""}" / "{model or ""}".\n'
            f"{AMBIGUOUS_HELP}"
        )
        sys.exit(1)

    with open_db(write=True) as conn:
        project, fuente, marcador_creado = ensure_project(conn)
        open_sess = get_open_session(conn, project["id"])

        if open_sess:
            prev_label = session_label(open_sess, participants_of(conn, open_sess["id"]))
            if not args.force:
                started = parse_iso(open_sess["start_at"]).strftime("%Y-%m-%d %H:%M")
                elapsed = elapsed_display(open_sess["start_at"])
                print(
                    f"Ya hay una sesión abierta en este proyecto.\n"
                    f"  Agente : {prev_label}\n"
                    f"  Inicio : {started}\n"
                    f"  Tiempo : {elapsed}\n"
                    f"\nCiérrala con 'cowork end' o usa 'cowork start --force' para auto-cerrarla."
                )
                sys.exit(1)
            else:
                end_ts = now_iso()
                close_active_pause(conn, open_sess["id"], end_ts)
                mins = net_minutes(conn, open_sess, end=end_ts)
                conn.execute(
                    "UPDATE sessions SET end_at = ? WHERE id = ?",
                    (end_ts, open_sess["id"]),
                )
                conn.commit()
                print(f"Sesión anterior auto-cerrada ({mins:.0f} min): {prev_label}.")

        # Doble escritura temporal (Fase 9): el texto crudo en `sessions` para que
        # versiones anteriores sigan mostrando la sesión; los pares en
        # `session_agents`. Se retira en la Fase 12.
        ts = now_iso()
        cur = conn.execute(
            "INSERT INTO sessions (project_id, agent, model, start_at) VALUES (?, ?, ?, ?)",
            (project["id"], agent, model, ts),
        )
        add_participants(conn, cur.lastrowid, pairs, ts)
        conn.commit()
        print(f"Sesión iniciada — {fmt_participants(pairs)} en '{project['name']}'.")
        print(f"  Identidad: uid {short_uid(project['uid'])} (por {fuente}).")
        print(db_summary_line())
        if marcador_creado:
            print(
                f"  Marcador {MARKER_NAME} creado (versionable; "
                f"commitéalo para portar la identidad entre equipos)."
            )


def cmd_end(args) -> None:
    with open_db(write=True) as conn:
        project = find_project(conn)
        if not project:
            print("No hay proyecto registrado en esta ruta. Usa 'cowork start' primero.")
            sys.exit(1)

        open_sess = get_open_session(conn, project["id"])
        if not open_sess:
            print("No hay sesión abierta en este proyecto.")
            sys.exit(1)

        end_ts = now_iso()
        summary = args.resumen or None
        pausa_cerrada = close_active_pause(conn, open_sess["id"], end_ts)
        conn.execute(
            "UPDATE sessions SET end_at = ?, summary = ? WHERE id = ?",
            (end_ts, summary, open_sess["id"]),
        )
        conn.commit()

        mins = net_minutes(conn, open_sess, end=end_ts)
        pausado = paused_minutes(conn, open_sess["id"])
        h, m = divmod(int(mins), 60)
        duracion = f"{h}h {m:02d}m" if h else f"{m}m"
        started = parse_iso(open_sess["start_at"]).strftime("%Y-%m-%d %H:%M")
        label = session_label(open_sess, participants_of(conn, open_sess["id"]))
        print(
            f"Sesión cerrada.\n"
            f"  Agente   : {label}\n"
            f"  Inicio   : {started}\n"
            f"  Duración : {duracion} ({mins:.1f} min)"
        )
        if pausado > 0:
            print(f"  Pausado  : {fmt_duration(pausado)} (no cuenta como trabajado)")
        if pausa_cerrada:
            print("  Aviso    : había una pausa activa; se cerró al terminar la sesión.")
        if summary:
            print(f"  Resumen  : {summary}")


def cmd_pause(args) -> None:
    with open_db(write=True) as conn:
        project = find_project(conn)
        if not project:
            print("No hay proyecto registrado en esta ruta. Usa 'cowork start' primero.")
            sys.exit(1)
        open_sess = get_open_session(conn, project["id"])
        if not open_sess:
            print("No hay sesión abierta en este proyecto; no hay nada que pausar.")
            sys.exit(1)
        pausa = get_active_pause(conn, open_sess["id"])
        if pausa:
            desde = parse_iso(pausa["pause_at"]).strftime("%H:%M")
            print(f"La sesión ya está en pausa desde las {desde}. Usa 'cowork resume'.")
            sys.exit(1)
        ts = now_iso()
        motivo = args.motivo or None
        conn.execute(
            "INSERT INTO session_pauses (session_id, pause_at, motivo) VALUES (?, ?, ?)",
            (open_sess["id"], ts, motivo),
        )
        conn.commit()
        extra = f" — {motivo}" if motivo else ""
        print(f"Sesión en pausa desde las {parse_iso(ts).strftime('%H:%M')}{extra}.")
        print("  Reanúdala con 'cowork resume'.")


def cmd_resume(args) -> None:
    with open_db(write=True) as conn:
        project = find_project(conn)
        if not project:
            print("No hay proyecto registrado en esta ruta. Usa 'cowork start' primero.")
            sys.exit(1)
        open_sess = get_open_session(conn, project["id"])
        if not open_sess:
            print("No hay sesión abierta en este proyecto.")
            sys.exit(1)
        pausa = get_active_pause(conn, open_sess["id"])
        if not pausa:
            print("La sesión no está en pausa.")
            sys.exit(1)
        ts = now_iso()
        close_active_pause(conn, open_sess["id"], ts)
        conn.commit()
        print(
            f"Sesión reanudada. Pausa de {fmt_duration(duration_minutes(pausa['pause_at'], ts))}"
            f" (no cuenta como trabajado)."
        )
        print(f"  Pausado acumulado : {fmt_duration(paused_minutes(conn, open_sess['id']))}")


def cmd_status(args) -> None:
    print(f"cowork version {__version__}")
    with open_db() as conn:
        project = find_project(conn)
        if not project:
            print("No hay proyecto registrado en esta ruta.")
            return

        open_sess = get_open_session(conn, project["id"])
        if not open_sess:
            print(f"Proyecto : {project['name']}\nNo hay sesión abierta.")
            last_sess = conn.execute(
                "SELECT * FROM sessions WHERE project_id = ? AND end_at IS NOT NULL ORDER BY start_at DESC LIMIT 1",
                (project["id"],),
            ).fetchone()
            if last_sess:
                started = parse_iso(last_sess["start_at"]).strftime("%Y-%m-%d %H:%M")
                mins = net_minutes(conn, last_sess)
                print(f"Última sesión: {started} ({mins:.1f} min)")
            print(db_summary_line())
            return

        started = parse_iso(open_sess["start_at"]).strftime("%Y-%m-%d %H:%M")
        ahora = now_iso()
        neto = net_minutes(conn, open_sess, end=ahora)
        pausa = get_active_pause(conn, open_sess["id"])
        label = session_label(open_sess, participants_of(conn, open_sess["id"]))
        estado = "EN PAUSA" if pausa else "ABIERTA"
        print(
            f"Proyecto  : {project['name']}\n"
            f"Sesión    : {estado}\n"
            f"Agente    : {label}\n"
            f"Inicio    : {started}\n"
            f"Transcurrido : {elapsed_display(open_sess['start_at'])} (neto: {fmt_duration(neto)})"
        )
        if pausa:
            desde = parse_iso(pausa["pause_at"]).strftime("%H:%M")
            motivo = f" — {pausa['motivo']}" if pausa["motivo"] else ""
            print(f"Pausa     : desde {desde}{motivo}")
        pausado = paused_minutes(conn, open_sess["id"], upto=ahora)
        if pausado > 0:
            print(f"Pausado acumulado : {fmt_duration(pausado)}")
        print(db_summary_line())


def cmd_list(args) -> None:
    with open_db() as conn:
        project = find_project(conn)
        if not project:
            print("No hay proyecto registrado en esta ruta.")
            return

        rows = conn.execute(
            "SELECT * FROM sessions WHERE project_id = ? "
            "ORDER BY start_at DESC LIMIT ?",
            (project["id"], args.n),
        ).fetchall()
        if not rows:
            print(f"Proyecto : {project['name']}\nSin sesiones registradas.")
            return
        participantes = load_participants(conn)

        print(f"Proyecto : {project['name']}  ·  últimas {len(rows)} sesiones\n")
        # Los participantes van al final y sin truncar: con varios agentes la
        # etiqueta es larga y cortarla ocultaría justo la información nueva.
        header = (
            f"{'ID':>3}  {'Inicio':<16} {'Fin':<16} {'Duración':>9}  Agentes / modelos"
        )
        print(header)
        print("-" * len(header))
        for r in rows:
            inicio = parse_iso(r["start_at"]).strftime("%Y-%m-%d %H:%M")
            if r["end_at"]:
                fin = parse_iso(r["end_at"]).strftime("%Y-%m-%d %H:%M")
                dur = fmt_duration(net_minutes(conn, r))
            else:
                fin = "— (abierta)"
                dur = fmt_duration(net_minutes(conn, r, end=now_iso()))
            label = session_label(r, participantes.get(r["id"]))
            print(f"{r['id']:>3}  {inicio:<16} {fin:<16} {dur:>9}  {label}")


def cmd_report(args) -> None:
    with open_db() as conn:
        if getattr(args, "this", False):
            project = find_project(conn)
            if not project:
                print("No hay proyecto registrado en esta ruta.")
                return

            rows = conn.execute(
                "SELECT s.* FROM sessions s WHERE s.project_id = ? AND s.end_at IS NOT NULL ORDER BY s.start_at ASC",
                (project["id"],),
            ).fetchall()

            if not rows:
                print(f"Proyecto: {project['name']}\nNo hay sesiones cerradas para reportar.")
                return

            total_n = len(rows)
            pausas = paused_by_session(conn)
            total_mins = sum(net_minutes(conn, r) for r in rows)
            total_pausado = sum(pausas.get(r["id"], 0.0) for r in rows)
            first_date = parse_iso(rows[0]["start_at"]).strftime("%Y-%m-%d %H:%M")
            last_sess = rows[-1]
            last_date = parse_iso(last_sess["start_at"]).strftime("%Y-%m-%d %H:%M")
            last_dur = fmt_duration(net_minutes(conn, last_sess))
            last_label = session_label(last_sess, participants_of(conn, last_sess["id"]))

            print(f"Reporte del proyecto: {project['name']} (uid {short_uid(project['uid'])})")
            print(f"  Sesiones totales : {total_n}")
            print(f"  Minutos totales  : {total_mins:.1f}")
            print(f"  Horas totales    : {total_mins / 60:.2f}")
            if total_pausado > 0:
                print(f"  Tiempo pausado   : {total_pausado:.1f} min (excluido del total)")
            print(f"  Primer registro  : {first_date}")
            print(f"  Último registro  : {last_date}")
            print(f"  Última sesión    : {last_label} ({last_dur})")
            return

        rows = conn.execute(
            "SELECT s.id, s.start_at, s.end_at, s.agent, s.model, p.name AS project_name "
            "FROM sessions s JOIN projects p ON p.id = s.project_id "
            "WHERE s.end_at IS NOT NULL"
        ).fetchall()
        pausas = paused_by_session(conn)
        participantes = load_participants(conn)

    if not rows:
        print("No hay sesiones cerradas para reportar.")
        return

    full = getattr(args, "full", False)
    if full and not args.model:
        print("Aviso: --full solo aplica junto con --model; se ignora.", file=sys.stderr)

    # Dimensiones de agrupación según los flags activos. El modelo va siempre
    # al final de la clave porque una sesión puede aportar a varios modelos.
    dims = []
    if args.project:
        dims.append(("Proyecto", lambda r: r["project_name"]))
    if args.month:
        dims.append(("Mes", lambda r: r["start_at"][:7]))  # YYYY-MM
    titles = [t for t, _ in dims] + (["Modelo"] if args.model else [])

    # agg: clave (tupla de dimensiones) -> [num_sesiones, minutos]
    # Con --model, cada sesión aporta a cada uno de sus modelos distintos:
    #   · por defecto, su tiempo neto repartido en partes iguales (la columna
    #     suma el tiempo real);
    #   · con --full, su tiempo neto completo a cada modelo (presencia; la
    #     columna no es sumable).
    agg = defaultdict(lambda: [0, 0.0])
    total_n, total_mins = 0, 0.0
    for r in rows:
        bruto = duration_minutes(r["start_at"], r["end_at"])
        neto = max(0.0, bruto - pausas.get(r["id"], 0.0))
        total_n += 1
        total_mins += neto
        base = tuple(fn(r) for _, fn in dims)
        if args.model:
            modelos = report_models(r, participantes.get(r["id"]))
            parte = neto if full else neto / len(modelos)
            for m in modelos:
                agg[base + (m,)][0] += 1
                agg[base + (m,)][1] += parte
        else:
            agg[base][0] += 1
            agg[base][1] += neto

    # Sin flags: total global.
    if not titles:
        n, mins = agg[()]
        print("Reporte global (solo sesiones cerradas)")
        print(f"  Sesiones : {n}")
        print(f"  Minutos  : {mins:.1f}")
        print(f"  Horas    : {mins / 60:.2f}")
        return

    ordenado = sorted(agg.items(), key=lambda kv: kv[1][1], reverse=True)

    # Ancho de cada columna = el mayor entre el título y los valores reales.
    widths = [len(t) for t in titles]
    for key, _ in agg.items():
        for i, v in enumerate(key):
            widths[i] = max(widths[i], len(str(v)))

    header = "  ".join(f"{t:<{w}}" for t, w in zip(titles, widths))
    header += f"  {'Sesiones':>9} {'Minutos':>9} {'Horas':>7}"
    print(header)
    print("-" * len(header))

    for key, (n, mins) in ordenado:
        cols = "  ".join(f"{str(v):<{w}}" for v, w in zip(key, widths))
        print(f"{cols}  {n:>9} {mins:>9.1f} {mins / 60:>7.2f}")

    # TOTAL = sesiones distintas y tiempo real trabajado, en cualquier modo.
    print("-" * len(header))
    label_w = sum(widths) + 2 * (len(widths) - 1)
    print(f"{'TOTAL':<{label_w}}  {total_n:>9} {total_mins:>9.1f} {total_mins / 60:>7.2f}")
    if args.model and full:
        print(
            "Nota: --full asigna a cada modelo el tiempo completo de sus sesiones; "
            "la columna no es sumable. TOTAL es el tiempo real."
        )
    elif args.model:
        print(
            "Nota: el tiempo de cada sesión se reparte en partes iguales entre sus "
            "modelos. Usa --full para ver el tiempo completo por modelo."
        )


def cmd_export(args) -> None:
    path = current_path()
    with open_db() as conn:
        project = find_project(conn)
        if not project:
            print("No hay proyecto registrado en esta ruta.")
            sys.exit(1)
        sessions = conn.execute(
            "SELECT * FROM sessions WHERE project_id = ? AND end_at IS NOT NULL "
            "ORDER BY start_at DESC",
            (project["id"],),
        ).fetchall()
        # Tiempo neto y pausado por sesión, calculados con la conexión abierta.
        netos = {s["id"]: net_minutes(conn, s) for s in sessions}
        pausas = paused_by_session(conn)
        participantes = load_participants(conn)

    out_path = Path(args.path) if args.path else Path(path) / "WORKLOG.md"

    total_sessions = len(sessions)
    total_mins = sum(netos.values())
    ultima = (
        parse_iso(sessions[0]["start_at"]).strftime("%Y-%m-%d %H:%M")
        if sessions else "—"
    )

    lines = [
        f"# WORKLOG — {project['name']}",
        "",
        f"> Generado por `cowork export` el {now_iso()}.",
        "> Vista derivada de la base de datos; no editar a mano.",
        "",
        "## Totales",
        "",
        f"- Sesiones: {total_sessions}",
        f"- Minutos: {total_mins:.1f}",
        f"- Horas: {total_mins / 60:.2f}",
        f"- Última sesión: {ultima}",
        "",
        "## Sesiones",
        "",
    ]

    if not sessions:
        lines.append("_Sin sesiones cerradas registradas._")
    for s in sessions:
        inicio = parse_iso(s["start_at"]).strftime("%Y-%m-%d %H:%M")
        fin = parse_iso(s["end_at"]).strftime("%Y-%m-%d %H:%M")
        dur = fmt_duration(netos[s["id"]])
        pares = participantes.get(s["id"])
        if pares:
            agentes = ", ".join(dict.fromkeys(a for a, _, _ in pares))
        else:
            agentes = fmt_agent(s["agent"])
        lines.append(f"### {inicio} · {agentes}")
        lines.append("")
        lines.append(f"- Agentes: {session_label(s, pares)}")
        lines.append(f"- Inicio: {inicio}")
        lines.append(f"- Fin: {fin}")
        lines.append(f"- Duración: {dur}")
        if pausas.get(s["id"], 0.0) > 0:
            lines.append(f"- Pausado: {fmt_duration(pausas[s['id']])}")
        if s["summary"]:
            lines.append(f"- Resumen: {s['summary']}")
        lines.append("")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Export generado: {out_path} ({total_sessions} sesiones).")


def backup_db(conn: sqlite3.Connection) -> Path:
    """Copia de seguridad consistente de la BD junto a ella
    (worklog.db.bak-AAAAMMDD-HHMMSS), usando la API de backup de SQLite."""
    db_path = resolve_db()[0]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = db_path.with_name(f"{db_path.name}.bak-{stamp}")
    bak = sqlite3.connect(dest)
    try:
        conn.backup(bak)
    finally:
        bak.close()
    return dest


def _print_values(titulo: str, valores: Counter) -> None:
    """Lista valores distintos ordenados sin distinguir mayúsculas, para que
    variantes como 'Claude ai' / 'claude ai' queden juntas y se vean."""
    print(f"  {titulo}:")
    for v in sorted(valores, key=lambda x: (x.lower(), x)):
        print(f"    {v}  ({valores[v]})")


def cmd_migrate(args) -> None:
    """Fase 9: migra sessions.agent/model (texto) a session_agents.
    Por defecto solo muestra el resultado; con --apply escribe (tras copia de
    seguridad). Idempotente: salta sesiones que ya tienen filas."""
    apply = args.apply
    with open_db(write=apply) as conn:
        ya = conn.execute(
            "SELECT COUNT(DISTINCT session_id) FROM session_agents"
        ).fetchone()[0]
        rows = conn.execute(
            "SELECT s.*, p.name AS project_name FROM sessions s "
            "JOIN projects p ON p.id = s.project_id "
            "WHERE s.id NOT IN (SELECT session_id FROM session_agents) "
            "ORDER BY s.start_at"
        ).fetchall()

        tipos = Counter()
        filas = []        # (session_id, agente, modelo, posición, added_at)
        ambiguas = []
        agentes, modelos = Counter(), Counter()   # nº de sesiones por valor
        for r in rows:
            kind, pairs = parse_participants(r["agent"], r["model"])
            tipos[kind] += 1
            if kind == "ambiguous":
                ambiguas.append(r)
                continue
            for a, m, pos in pairs:
                filas.append((r["id"], a, m, pos, r["start_at"]))
            agentes.update({a for a, _, _ in pairs})
            modelos.update({m for _, m, _ in pairs if m})

        modo = "aplicando" if apply else "vista previa"
        print(f"Migración de agentes/modelos a session_agents ({modo})")
        print(f"  Ya migradas        : {ya} sesiones")
        print(f"  Sin filas todavía  : {len(rows)} sesiones")
        print(f"    · individuales   : {tipos['individual']}  (no generan filas)")
        print(f"    · simples        : {tipos['simple']}")
        print(f"    · multi          : {tipos['multi']}")
        print(f"    · ambiguas       : {tipos['ambiguous']}  (no se migran)")
        print(f"  Filas a crear      : {len(filas)}")

        if agentes or modelos:
            print("\nValores distintos (revisa erratas; su corrección es de la Fase 12):")
            _print_values("Agentes", agentes)
            _print_values("Modelos", modelos)

        if ambiguas:
            print("\nPendientes de revisión manual (corrige el texto y vuelve a ejecutar):")
            for r in ambiguas:
                fecha = parse_iso(r["start_at"]).strftime("%Y-%m-%d %H:%M")
                print(
                    f"  id {r['id']:>4} · {r['project_name']} · {fecha} · "
                    f"agent={r['agent']!r} · model={r['model']!r}"
                )

        if not apply:
            print(
                "\nVista previa: no se escribió nada. "
                "Ejecuta 'cowork migrate agents --apply' para migrar."
            )
            return
        if not filas:
            print("\nNada que migrar.")
            return

        destino = backup_db(conn)
        print(f"\nCopia de seguridad: {destino}")
        conn.executemany(
            "INSERT INTO session_agents (session_id, agent, model, position, added_at) "
            "VALUES (?, ?, ?, ?, ?)",
            filas,
        )
        conn.commit()
        migradas = len({f[0] for f in filas})
        print(f"Migración aplicada: {len(filas)} filas en {migradas} sesiones.")


def cmd_config(args) -> None:
    if getattr(args, "config_cmd", None) == "set-db":
        ruta = str(Path(args.ruta).expanduser())
        cfg = load_config()
        cfg["db_path"] = ruta
        save_config(cfg)
        print(f"Guardado en {get_config_path()}:")
        print(f"  db_path = {ruta}")
        return

    # Sin subacción: mostrar la configuración efectiva.
    db, fuente = resolve_db()
    cfg_path = get_config_path()
    existe_cfg = "" if cfg_path.exists() else "  (no existe aún)"
    print("Configuración de cowork")
    print(f"  Archivo config : {cfg_path}{existe_cfg}")
    print(f"  BD efectiva    : {db}")
    print(f"  Fuente         : {fuente}")
    print(f"  BD existe      : {'sí' if db.exists() else 'no'}")
    if os.environ.get("WORKLOG_HOME"):
        print(f"  WORKLOG_HOME   : {os.environ['WORKLOG_HOME']}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cowork",
        description="Registro de sesiones de trabajo humano + IA.",
    )
    parser.add_argument(
        "--version", action="version", version=f"cowork version {__version__}",
        help="Muestra la versión de cowork y termina.",
    )
    parser.add_argument(
        "--db", default=None,
        help="Ruta explícita a la BD; anula WORKLOG_HOME y config.json.",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    # -h del parser raíz: antepone "cowork version x.y.z" antes del uso normal,
    # para distinguir qué instalación se está ejecutando (bin/ del repo vs.
    # cowork.exe de pipx). Solo afecta a `cowork -h`, no a `cowork <sub> -h`.
    _print_help = parser.print_help

    def _print_help_con_version(file=None):
        (file or sys.stdout).write(f"cowork version {__version__}\n")
        _print_help(file)

    parser.print_help = _print_help_con_version

    # init
    p_init = sub.add_parser("init", help="Registra o renombra el proyecto actual.")
    p_init.add_argument("nombre", nargs="?", default=None, help="Nombre del proyecto.")
    p_init.add_argument("--link", default=None, help="Enlaza el directorio actual a un proyecto existente por uid.")
    p_init.add_argument("--db-path", default=None, help="Persiste en config.json dónde vivirá la BD (p. ej. disco externo) y la crea ahí.")
    p_init.set_defaults(func=cmd_init)

    # start
    p_start = sub.add_parser("start", help="Abre una sesión de trabajo.")
    p_start.add_argument("agente", nargs="?", default=None, help='Agente(s), ej: "Claude Code" o "Claude ai, Hostgator ai". Omítelo para registrar trabajo solo-humano (individual).')
    p_start.add_argument("modelo", nargs="?", default=None, help='Modelo(s), ej: "claude-opus-4-8"; con varios agentes, un grupo por agente: "[m1], [m2, m3]".')
    p_start.add_argument("--force", action="store_true", help="Auto-cierra sesión previa si existe.")
    p_start.set_defaults(func=cmd_start)

    # end
    p_end = sub.add_parser("end", help="Cierra la sesión abierta.")
    p_end.add_argument("resumen", nargs="?", default=None, help="Resumen de lo trabajado.")
    p_end.set_defaults(func=cmd_end)

    # pause / resume
    p_pause = sub.add_parser("pause", help="Pausa la sesión abierta (el tiempo pausado no cuenta).")
    p_pause.add_argument("motivo", nargs="?", default=None, help="Motivo de la pausa (opcional).")
    p_pause.set_defaults(func=cmd_pause)

    p_resume = sub.add_parser("resume", help="Reanuda la sesión pausada.")
    p_resume.set_defaults(func=cmd_resume)

    # status
    p_status = sub.add_parser("status", help="Muestra la sesión abierta y tiempo transcurrido.")
    p_status.set_defaults(func=cmd_status)

    # list
    p_list = sub.add_parser("list", help="Lista las últimas sesiones del proyecto actual.")
    p_list.add_argument("-n", type=int, default=10, help="Número de sesiones a mostrar (default 10).")
    p_list.set_defaults(func=cmd_list)

    # report
    p_report = sub.add_parser("report", help="Agregados de tiempo por proyecto, mes y/o modelo.")
    p_report.add_argument("--project", action="store_true", help="Agrupa por proyecto.")
    p_report.add_argument("--month", action="store_true", help="Agrupa por mes (YYYY-MM).")
    p_report.add_argument("--model", action="store_true", help="Agrupa por modelo (reparte cada sesión en partes iguales entre sus modelos).")
    p_report.add_argument("--full", action="store_true", help="Con --model: tiempo completo de la sesión a cada modelo (no sumable).")
    p_report.add_argument("--this", action="store_true", help="Reporte detallado del proyecto actual.")
    p_report.set_defaults(func=cmd_report)

    # export
    p_export = sub.add_parser("export", help="Genera WORKLOG.md del proyecto actual desde la BD.")
    p_export.add_argument("--md", action="store_true", help="Formato Markdown (por defecto).")
    p_export.add_argument("--path", default=None, help="Ruta de salida (default: <proyecto>/WORKLOG.md).")
    p_export.set_defaults(func=cmd_export)

    # migrate
    p_migrate = sub.add_parser("migrate", help="Migra datos históricos al esquema actual.")
    p_migrate.add_argument("objetivo", choices=["agents"], help="agents: sessions.agent/model → session_agents.")
    p_migrate.add_argument("--apply", action="store_true", help="Escribe los cambios (sin él, solo muestra el resultado). Hace copia de seguridad antes.")
    p_migrate.set_defaults(func=cmd_migrate)

    # config
    p_config = sub.add_parser("config", help="Muestra o cambia la configuración (ubicación de la BD).")
    cfg_sub = p_config.add_subparsers(dest="config_cmd")
    p_setdb = cfg_sub.add_parser("set-db", help="Fija la ruta de la BD en config.json.")
    p_setdb.add_argument("ruta", help="Ruta del archivo de BD.")
    p_config.set_defaults(func=cmd_config)

    return parser


def main() -> None:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args()
    global _DB_OVERRIDE
    _DB_OVERRIDE = args.db
    args.func(args)


if __name__ == "__main__":
    main()
