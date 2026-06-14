"""
cowork — registro de sesiones de trabajo humano + IA.
Solo biblioteca estándar de Python. Sin dependencias externas.
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Resolución de la carpeta de datos
# ---------------------------------------------------------------------------

def get_data_dir() -> Path:
    env = os.environ.get("WORKLOG_HOME")
    if env:
        return Path(env)
    return Path.home() / ".worklog"


def get_db_path() -> Path:
    return get_data_dir() / "worklog.db"


# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------

def open_db() -> sqlite3.Connection:
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(get_db_path())
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


def get_or_create_project(conn: sqlite3.Connection, path: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM projects WHERE path = ?", (path,)
    ).fetchone()
    if row:
        return row
    name = Path(path).name
    conn.execute(
        "INSERT INTO projects (path, name, created_at) VALUES (?, ?, ?)",
        (path, name, now_iso()),
    )
    conn.commit()
    return conn.execute(
        "SELECT * FROM projects WHERE path = ?", (path,)
    ).fetchone()


def get_open_session(conn: sqlite3.Connection, project_id: int):
    return conn.execute(
        "SELECT * FROM sessions WHERE project_id = ? AND end_at IS NULL",
        (project_id,),
    ).fetchone()


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------

def cmd_init(args) -> None:
    path = current_path()
    with open_db() as conn:
        existing = conn.execute(
            "SELECT * FROM projects WHERE path = ?", (path,)
        ).fetchone()
        if existing:
            old_name = existing["name"]
            new_name = args.nombre or old_name
            conn.execute(
                "UPDATE projects SET name = ? WHERE path = ?", (new_name, path)
            )
            conn.commit()
            if new_name != old_name:
                print(f"Proyecto renombrado: '{old_name}' → '{new_name}'")
            else:
                print(f"Proyecto ya registrado: '{old_name}' ({path})")
        else:
            name = args.nombre or Path(path).name
            conn.execute(
                "INSERT INTO projects (path, name, created_at) VALUES (?, ?, ?)",
                (path, name, now_iso()),
            )
            conn.commit()
            print(f"Proyecto registrado: '{name}' ({path})")


def cmd_start(args) -> None:
    path = current_path()
    with open_db() as conn:
        project = get_or_create_project(conn, path)
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


def cmd_end(args) -> None:
    path = current_path()
    with open_db() as conn:
        project = conn.execute(
            "SELECT * FROM projects WHERE path = ?", (path,)
        ).fetchone()
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
    path = current_path()
    with open_db() as conn:
        project = conn.execute(
            "SELECT * FROM projects WHERE path = ?", (path,)
        ).fetchone()
        if not project:
            print("No hay proyecto registrado en esta ruta.")
            return

        open_sess = get_open_session(conn, project["id"])
        if not open_sess:
            print(f"Proyecto : {project['name']}\nNo hay sesión abierta.")
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cowork",
        description="Registro de sesiones de trabajo humano + IA.",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    # init
    p_init = sub.add_parser("init", help="Registra o renombra el proyecto actual.")
    p_init.add_argument("nombre", nargs="?", default=None, help="Nombre del proyecto.")
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

    return parser


def main() -> None:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
