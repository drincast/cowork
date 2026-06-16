# Prueba manual — Identidad portable y configuración de la BD

**Propósito:** verificar que la ubicación de la base de datos se resuelve por
capas y que un proyecto se reconoce por su identidad (no por su ruta), de modo
que el mismo proyecto cuente igual desde rutas, discos o equipos distintos.

**Alcance:** comando `config`, capas de resolución de la BD (`--db` >
`WORKLOG_HOME` > `config.json` > default) e identidad por capas (marcador
`.cowork` → remoto git → ruta), más la detección de duplicados y `init --link`.

**Fuera de alcance:** NO valida el cálculo de duraciones, `report`, `export` ni
el manejo de sesiones huérfanas. NO es una suite completa: que esto pase no
significa que toda la app funcione.

**Requisitos:** Python 3.8+, git y PowerShell (Windows). En Linux/macOS el
concepto es el mismo cambiando la sintaxis (`export WORKLOG_HOME=...` en bash).

**Por qué un entorno aislado:** la línea `$env:WORKLOG_HOME = ...` hace que
cowork use una base de datos temporal y separada. Esa variable solo vive en la
ventana de PowerShell actual; al cerrarla, vuelves a tu entorno real. Así, tu
`~/.worklog/worklog.db` real nunca se modifica.

---

## Cómo ejecutar

Ejecuta los bloques en orden, en la **misma** ventana de PowerShell.

### 1. Aislar el entorno

```powershell
$lab    = Join-Path $env:TEMP "cowork_lab"
$env:WORKLOG_HOME = Join-Path $lab "db"
$script = "D:\Desarrollo\RepoGit\github\cowork\cowork.py"

python $script config
```

**Resultado esperado:** `Fuente : WORKLOG_HOME` y la BD apuntando dentro de
`cowork_lab`. Si dice `default`, DETENTE: estarías sobre tu BD real.

### 2. Capa "marcador": mismo proyecto, dos rutas

```powershell
$A = Join-Path $lab "diskD\myapp"
$B = Join-Path $lab "diskE\myapp"
New-Item -ItemType Directory -Force $A,$B | Out-Null

Set-Location $A
python $script init "My App"        # crea el proyecto y su .cowork
Get-Content .\.cowork               # muestra { id, name }

Copy-Item "$A\.cowork" "$B\.cowork" # simula que el marcador viaja con el repo
Set-Location $B
python $script status               # otra ruta, mismo proyecto
```

**Resultado esperado:** en el paso final, `Proyecto : My App`. El nombre del
archivo copiado debe ser exactamente `.cowork` (cowork lo busca por ese nombre).

### 3. Capa "remoto git": mismo repo, https vs ssh, sin marcador

```powershell
$C = Join-Path $lab "repoC"
$D = Join-Path $lab "repoD"
New-Item -ItemType Directory -Force $C,$D | Out-Null

Set-Location $C
git init -q
git remote add origin https://github.com/demo/example.git
python $script init "Example"
Remove-Item .\.cowork               # se borra el marcador a propósito

Set-Location $D
git init -q
git remote add origin git@github.com:demo/example.git  # mismo repo, forma ssh
python $script status               # sin marcador, resuelve por el remoto
```

**Resultado esperado:** `Proyecto : Example`. Demuestra que las formas `https`
y `ssh` del mismo remoto se normalizan al mismo identificador.

### 4. Detección de duplicados y enlace manual

```powershell
Set-Location $D
python $script init "My App"        # nombre ya usado por otro uid -> aviso
```

**Resultado esperado:** un aviso de que ya existe otro proyecto con ese nombre
y la sugerencia de usar `cowork init --link <uid>`.

### 5. Limpieza

```powershell
Set-Location "D:\Desarrollo\RepoGit\github\cowork"
Remove-Item Env:WORKLOG_HOME        # restaura el entorno real en esta ventana
Remove-Item -Recurse -Force $lab
python $script config               # Fuente vuelve a 'default'
```

**Resultado esperado:** `Fuente : default` y tu BD real intacta.

---

## Si algo sale mal

Cierra la ventana de PowerShell y abre una nueva: la variable `WORKLOG_HOME`
desaparece con la ventana y vuelves a tu entorno real automáticamente. La base
de datos real nunca se tocó durante la prueba.
