"""
cowork — registro de sesiones de trabajo humano + IA.
Solo biblioteca estándar de Python. Sin dependencias externas.
"""

import argparse
import os
import sqlite3
import sys
from collections import defaultdict
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


def cmd_list(args) -> None:
    path = current_path()
    with open_db() as conn:
        project = conn.execute(
            "SELECT * FROM projects WHERE path = ?", (path,)
        ).fetchone()
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
        project = conn.execute(
            "SELECT * FROM projects WHERE path = ?", (path,)
        ).fetchone()
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
