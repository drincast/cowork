# Manual — Empaquetar e instalar una herramienta CLI en Python

Guía práctica y reutilizable para convertir un script/proyecto Python en un
paquete **instalable**, de modo que quede un comando disponible en el sistema
(ej. `mitool ...`). Basada en el empaquetado de cowork; sirve para cualquier
proyecto. Sustituye `<...>` por tus valores.

---

## 1. Qué vas a lograr

Pasar de "ejecutar `python script.py`" a "tener un comando global" que se
instala una vez y se invoca desde cualquier carpeta. La vía recomendada para
herramientas de línea de comandos es **pipx**.

## 2. Conceptos en 1 minuto

| Pieza | Qué es |
|---|---|
| `pyproject.toml` | Ficha técnica del paquete: nombre, versión, qué comando crea. |
| **Build backend** | Herramienta que construye el paquete (aquí `setuptools`). |
| **wheel / sdist** | El paquete construido: `.whl` (listo para instalar) y `.tar.gz` (fuente). |
| **entry point** | Línea que crea el comando: `micmd = "modulo:funcion"`. |
| **pipx** | Instala apps CLI cada una en su propio entorno aislado (venv). |

**Cajones de instalación de paquetes** (importante):

- **Sistema/global:** dentro de la instalación de Python; afecta a todos, a veces pide admin.
- **Usuario (`--user`):** carpeta tuya; solo tu cuenta, sin admin, disponible en todas tus terminales.
- **venv:** aislado por proyecto.

pipx usa lo mejor de ambos: él vive en tu cajón de usuario, pero **cada app que
instala va a su propio venv aislado**, así no se mezclan dependencias.

## 3. Requisitos

- Python 3.8+ (`python --version`).
- Acceso a internet la primera vez (para descargar el build backend y pipx).

---

## 4. Paso a paso

### 4.1. Estructura mínima del proyecto

Para un proyecto de **un solo archivo** (`mytool.py` con una función `main()`):

```
mi-proyecto/
├── mytool.py          # tiene una función main()
├── pyproject.toml     # lo creas en el siguiente paso
└── README.md
```

> Si tu proyecto es un **paquete con carpetas** (`mypkg/__init__.py`, etc.), el
> `pyproject.toml` cambia un poco (ver nota al final del paso 4.2).

### 4.2. Crear `pyproject.toml`

Plantilla comentada para **un solo módulo**:

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "<mi-paquete>"
version = "0.1.0"                 # versionado semántico MAYOR.MENOR.PARCHE
description = "<descripción corta>"
readme = "README.md"
requires-python = ">=3.8"
license = { text = "MIT" }
authors = [{ name = "<Tu Nombre>", email = "<tu@correo>" }]

# Crea el comando: <micomando> ejecuta la función main() del módulo <mytool>.
[project.scripts]
<micomando> = "<mytool>:main"

# El proyecto es un único archivo <mytool>.py (sin carpetas de paquete).
[tool.setuptools]
py-modules = ["<mytool>"]
```

> **Si es un paquete con carpetas**, en vez de `py-modules` usa el
> descubrimiento automático (borra el bloque `[tool.setuptools]` o usa
> `[tool.setuptools.packages.find]`), y el entry point apunta al submódulo:
> `<micomando> = "<mypkg>.cli:main"`.

**Versionado semántico (semver):** `MAYOR.MENOR.PARCHE`.
- `PARCHE` (0.1.0 → 0.1.1): correcciones.
- `MENOR` (0.1.0 → 0.2.0): funciones nuevas compatibles.
- `MAYOR` (0.1.0 → 1.0.0): cambios que rompen compatibilidad.
- `0.x` indica "aún evolucionando / API no estable".

### 4.3. Probar el build en un entorno aislado (sin ensuciar nada)

Antes de instalar en el sistema, verifica que el paquete se construye e instala
en un venv desechable:

**Windows (PowerShell):**

```powershell
python -m venv $env:TEMP\pkgtest
& "$env:TEMP\pkgtest\Scripts\python.exe" -m pip install .
& "$env:TEMP\pkgtest\Scripts\<micomando>.exe" --help
Remove-Item -Recurse -Force $env:TEMP\pkgtest
```

**Linux/macOS (bash):**

```bash
python3 -m venv /tmp/pkgtest
/tmp/pkgtest/bin/pip install .
/tmp/pkgtest/bin/<micomando> --help
rm -rf /tmp/pkgtest
```

Si `--help` responde, el empaquetado está bien.

### 4.4. Instalar de verdad con pipx

**a) Instalar pipx (una sola vez por equipo):**

```bash
python -m pip install --user pipx
python -m pipx ensurepath
```

`ensurepath` agrega al PATH la carpeta donde pipx deja los comandos. Se puede
correr desde cualquier ruta. **Cierra y abre una terminal nueva** para que el
PATH se actualice. Verifica:

```bash
pipx --version
```

**b) Instalar tu herramienta** (parado en la carpeta del proyecto):

```bash
pipx install .
```

Resultado: `installed package <mi-paquete> ... These apps are now globally
available - <micomando>`. Ya puedes ejecutar `<micomando>` desde cualquier
carpeta.

### 4.5. Actualizar y desinstalar

```bash
pipx install . --force     # reinstala tras cambios en el código
pipx uninstall <mi-paquete>
pipx list                  # ver lo instalado por pipx
```

---

## 5. Verificación final

```bash
<micomando> --help         # responde desde cualquier carpeta
```

---

## 6. Problemas comunes

- **WARNING: "... Scripts is not on PATH"** al instalar con `--user`. Lo
  resuelve `python -m pipx ensurepath` + terminal nueva. Si varios warnings
  citan la **misma** carpeta, es una sola ruta, no varias.
- **WARNING: "Skipping setuptools as it is not installed"** al hacer
  `pipx install`. Es inofensivo: el build trae setuptools en aislamiento.
- **Artefactos de build** (`build/`, `dist/`, `*.egg-info/`) aparecen tras
  construir. Agrégalos al `.gitignore`; son regenerables.
- **Lanzadores shell (Linux/macOS) que fallan:** si un script `bin/...` tiene
  saltos de línea CRLF, el `#!/usr/bin/env bash` se rompe. Fuerza LF con un
  `.gitattributes`: `bin/* text eol=lf`.
- **Dos veces el mismo comando:** si además tienes un lanzador en el PATH, tras
  `pipx install` el comando existirá por dos vías. No es error; gana el que
  aparezca primero en el PATH.

---

## 7. (Opcional) Publicar en PyPI

Para que cualquiera haga `pipx install <mi-paquete>` desde internet:

```bash
python -m pip install --user build twine
python -m build                              # genera dist/ (sdist + wheel)
python -m twine upload --repository testpypi dist/*   # ensayo en TestPyPI
python -m twine upload dist/*                # publicación real en PyPI
```

Requiere cuenta en PyPI (y TestPyPI) con token de API, y que el **nombre esté
disponible**.

> **Cuidado:** una versión publicada en PyPI **no se puede sobrescribir ni
> reutilizar**. Es pública y permanente. Para corregir, se sube una versión
> nueva (sube el número en `pyproject.toml`).

---

## 8. Referencia rápida (cheat sheet)

```bash
# Construir y probar aislado
python -m venv .venv && .venv/bin/pip install .   # (Windows: .venv\Scripts\)

# Instalar como herramienta global
python -m pip install --user pipx
python -m pipx ensurepath        # + terminal nueva
pipx install .                   # desde la carpeta del proyecto
pipx install . --force           # actualizar
pipx uninstall <mi-paquete>      # quitar

# Publicar (opcional)
python -m build
python -m twine upload dist/*
```
