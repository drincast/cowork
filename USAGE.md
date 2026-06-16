# Cómo registrar el tiempo con cowork (guía para el agente)

Guía breve para un agente de IA (o una persona) que trabaja en **cualquier**
proyecto y quiere dejar registrado el tiempo invertido. Estos comandos son
locales y **no consumen tokens**; se ejecutan como cualquier comando de
terminal.

Requisito: tener `cowork` invocable (ver "Invocar cowork desde cualquier
carpeta" en el README). Si no, usa `python /ruta/a/cowork.py` en su lugar.

## Flujo de cada sesión

1. **Al empezar**, parado en la carpeta del proyecto:

   ```bash
   cowork start "Claude Code" "claude-opus-4-8"
   ```

   El agente es el nombre de quien trabaja (ej. `"Claude Code"`, `"Cursor"`);
   el segundo argumento es el modelo (opcional).

2. **Mientras trabajas**, para ver la sesión activa y el tiempo transcurrido:

   ```bash
   cowork status
   ```

3. **Al terminar**, cierra con un resumen breve de lo hecho:

   ```bash
   cowork end "implementacion del login y pruebas"
   ```

## Reglas útiles

- **Una sola sesión abierta por proyecto.** Si olvidaste cerrar una anterior,
  `cowork start ... --force` la cierra y abre la nueva.
- El proyecto se identifica solo (por marcador `.cowork`, remoto git o ruta);
  no necesitas configurar nada para empezar.
- Consultas cuando quieras: `cowork list` (últimas sesiones),
  `cowork report --model` (tiempo por modelo/proyecto/mes),
  `cowork export` (genera `WORKLOG.md` versionable).

## Recomendación para el agente

Si trabajas con un agente de IA, pídele que ejecute `cowork start` al iniciar y
`cowork end "<resumen>"` al cerrar. Así el registro queda casi automático sin
esfuerzo manual.
