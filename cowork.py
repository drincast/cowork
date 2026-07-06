"""
cowork — registro de sesiones de trabajo humano + IA.
Solo biblioteca estándar de Python. Sin dependencias externas.
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


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


def open_db(create: bool = False) -> sqlite3.Connection:
    """Abre la BD resuelta por capas.

    Con create=False (por defecto), si el archivo de BD no existe **avisa y para**
    en vez de crear una BD "fantasma" vacía (Fase 5, Etapa A). Solo `init` la crea
    intencionalmente con create=True.
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
            agent       TEXT NOT NULL,
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
    with open_db(create=True) as conn:
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
    with open_db() as conn:
        project, fuente, marcador_creado = ensure_project(conn)
        open_sess = get_open_session(conn, project["id"])

        if open_sess:
            if not args.force:
                started = parse_iso(open_sess["start_at"]).strftime("%Y-%m-%d %H:%M")
                elapsed = elapsed_display(open_sess["start_at"])
                print(
                    f"Ya hay una sesión abierta en este proyecto.\n"
                    f"  Agente : {open_sess['agent']}\n"
                    f"  Inicio : {started}\n"
                    f"  Tiempo : {elapsed}\n"
                    f"\nCiérrala con 'cowork end' o usa 'cowork start --force' para auto-cerrarla."
                )
                sys.exit(1)
            else:
                end_ts = now_iso()
                mins = duration_minutes(open_sess["start_at"], end_ts)
                conn.execute(
                    "UPDATE sessions SET end_at = ? WHERE id = ?",
                    (end_ts, open_sess["id"]),
                )
                conn.commit()
                print(
                    f"Sesión anterior auto-cerrada ({mins:.0f} min): {open_sess['agent']}."
                )

        model = args.modelo or None
        conn.execute(
            "INSERT INTO sessions (project_id, agent, model, start_at) VALUES (?, ?, ?, ?)",
            (project["id"], args.agente, model, now_iso()),
        )
        conn.commit()
        model_str = f" ({model})" if model else ""
        print(f"Sesión iniciada — {args.agente}{model_str} en '{project['name']}'.")
        print(f"  Identidad: uid {short_uid(project['uid'])} (por {fuente}).")
        print(db_summary_line())
        if marcador_creado:
            print(
                f"  Marcador {MARKER_NAME} creado (versionable; "
                f"commitéalo para portar la identidad entre equipos)."
            )


def cmd_end(args) -> None:
    with open_db() as conn:
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
        conn.execute(
            "UPDATE sessions SET end_at = ?, summary = ? WHERE id = ?",
            (end_ts, summary, open_sess["id"]),
        )
        conn.commit()

        mins = duration_minutes(open_sess["start_at"], end_ts)
        h, m = divmod(int(mins), 60)
        duracion = f"{h}h {m:02d}m" if h else f"{m}m"
        started = parse_iso(open_sess["start_at"]).strftime("%Y-%m-%d %H:%M")
        print(
            f"Sesión cerrada.\n"
            f"  Agente   : {open_sess['agent']}\n"
            f"  Inicio   : {started}\n"
            f"  Duración : {duracion} ({mins:.1f} min)"
        )
        if summary:
            print(f"  Resumen  : {summary}")


def cmd_status(args) -> None:
    with open_db() as conn:
        project = find_project(conn)
        if not project:
            print("No hay proyecto registrado en esta ruta.")
            return

        open_sess = get_open_session(conn, project["id"])
        if not open_sess:
            print(f"Proyecto : {project['name']}\nNo hay sesión abierta.")
            print(db_summary_line())
            return

        started = parse_iso(open_sess["start_at"]).strftime("%Y-%m-%d %H:%M")
        elapsed = elapsed_display(open_sess["start_at"])
        model_str = f" ({open_sess['model']})" if open_sess["model"] else ""
        print(
            f"Proyecto  : {project['name']}\n"
            f"Sesión    : ABIERTA\n"
            f"Agente    : {open_sess['agent']}{model_str}\n"
            f"Inicio    : {started}\n"
            f"Transcurrido : {elapsed}"
        )
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

        print(f"Proyecto : {project['name']}  ·  últimas {len(rows)} sesiones\n")
        header = (
            f"{'ID':>3}  {'Agente':<14} {'Modelo':<20} "
            f"{'Inicio':<16} {'Fin':<16} {'Duración':>9}"
        )
        print(header)
        print("-" * len(header))
        for r in rows:
            inicio = parse_iso(r["start_at"]).strftime("%Y-%m-%d %H:%M")
            if r["end_at"]:
                fin = parse_iso(r["end_at"]).strftime("%Y-%m-%d %H:%M")
                dur = fmt_duration(duration_minutes(r["start_at"], r["end_at"]))
            else:
                fin = "— (abierta)"
                dur = elapsed_display(r["start_at"])
            modelo = r["model"] or "—"
            print(
                f"{r['id']:>3}  {r['agent']:<14.14} {modelo:<20.20} "
                f"{inicio:<16} {fin:<16} {dur:>9}"
            )


def cmd_report(args) -> None:
    with open_db() as conn:
        rows = conn.execute(
            "SELECT s.start_at, s.end_at, s.model, p.name AS project_name "
            "FROM sessions s JOIN projects p ON p.id = s.project_id "
            "WHERE s.end_at IS NOT NULL"
        ).fetchall()

    if not rows:
        print("No hay sesiones cerradas para reportar.")
        return

    # Dimensiones de agrupación según los flags activos.
    dims = []
    if args.project:
        dims.append(("Proyecto", lambda r: r["project_name"]))
    if args.month:
        dims.append(("Mes", lambda r: r["start_at"][:7]))  # YYYY-MM
    if args.model:
        dims.append(("Modelo", lambda r: r["model"] or "—"))

    # agg: clave (tupla de dimensiones) -> [num_sesiones, minutos_totales]
    agg = defaultdict(lambda: [0, 0.0])
    for r in rows:
        key = tuple(fn(r) for _, fn in dims)
        agg[key][0] += 1
        agg[key][1] += duration_minutes(r["start_at"], r["end_at"])

    # Sin flags: total global.
    if not dims:
        n, mins = agg[()]
        print("Reporte global (solo sesiones cerradas)")
        print(f"  Sesiones : {n}")
        print(f"  Minutos  : {mins:.1f}")
        print(f"  Horas    : {mins / 60:.2f}")
        return

    ordenado = sorted(agg.items(), key=lambda kv: kv[1][1], reverse=True)

    # Ancho de cada columna = el mayor entre el título y los valores reales.
    titles = [t for t, _ in dims]
    widths = [len(t) for t in titles]
    for key, _ in agg.items():
        for i, v in enumerate(key):
            widths[i] = max(widths[i], len(str(v)))

    header = "  ".join(f"{t:<{w}}" for t, w in zip(titles, widths))
    header += f"  {'Sesiones':>9} {'Minutos':>9} {'Horas':>7}"
    print(header)
    print("-" * len(header))

    total_n, total_mins = 0, 0.0
    for key, (n, mins) in ordenado:
        cols = "  ".join(f"{str(v):<{w}}" for v, w in zip(key, widths))
        print(f"{cols}  {n:>9} {mins:>9.1f} {mins / 60:>7.2f}")
        total_n += n
        total_mins += mins

    print("-" * len(header))
    label_w = sum(widths) + 2 * (len(widths) - 1)
    print(f"{'TOTAL':<{label_w}}  {total_n:>9} {total_mins:>9.1f} {total_mins / 60:>7.2f}")


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

    out_path = Path(args.path) if args.path else Path(path) / "WORKLOG.md"

    total_sessions = len(sessions)
    total_mins = sum(duration_minutes(s["start_at"], s["end_at"]) for s in sessions)
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
        dur = fmt_duration(duration_minutes(s["start_at"], s["end_at"]))
        modelo = s["model"] or "—"
        lines.append(f"### {inicio} · {s['agent']}")
        lines.append("")
        lines.append(f"- Modelo: {modelo}")
        lines.append(f"- Inicio: {inicio}")
        lines.append(f"- Fin: {fin}")
        lines.append(f"- Duración: {dur}")
        if s["summary"]:
            lines.append(f"- Resumen: {s['summary']}")
        lines.append("")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Export generado: {out_path} ({total_sessions} sesiones).")


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
        "--db", default=None,
        help="Ruta explícita a la BD; anula WORKLOG_HOME y config.json.",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    # init
    p_init = sub.add_parser("init", help="Registra o renombra el proyecto actual.")
    p_init.add_argument("nombre", nargs="?", default=None, help="Nombre del proyecto.")
    p_init.add_argument("--link", default=None, help="Enlaza el directorio actual a un proyecto existente por uid.")
    p_init.add_argument("--db-path", default=None, help="Persiste en config.json dónde vivirá la BD (p. ej. disco externo) y la crea ahí.")
    p_init.set_defaults(func=cmd_init)

    # start
    p_start = sub.add_parser("start", help="Abre una sesión de trabajo.")
    p_start.add_argument("agente", help='Nombre del agente, ej: "Claude Code".')
    p_start.add_argument("modelo", nargs="?", default=None, help='ID del modelo, ej: "claude-opus-4-8".')
    p_start.add_argument("--force", action="store_true", help="Auto-cierra sesión previa si existe.")
    p_start.set_defaults(func=cmd_start)

    # end
    p_end = sub.add_parser("end", help="Cierra la sesión abierta.")
    p_end.add_argument("resumen", nargs="?", default=None, help="Resumen de lo trabajado.")
    p_end.set_defaults(func=cmd_end)

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
    p_report.add_argument("--model", action="store_true", help="Agrupa por modelo.")
    p_report.set_defaults(func=cmd_report)

    # export
    p_export = sub.add_parser("export", help="Genera WORKLOG.md del proyecto actual desde la BD.")
    p_export.add_argument("--md", action="store_true", help="Formato Markdown (por defecto).")
    p_export.add_argument("--path", default=None, help="Ruta de salida (default: <proyecto>/WORKLOG.md).")
    p_export.set_defaults(func=cmd_export)

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
