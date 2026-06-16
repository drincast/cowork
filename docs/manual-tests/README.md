# Manual tests

Guías de **prueba manual / exploratoria** de cowork. Se ejecutan a mano para
ver el comportamiento real en un entorno aislado.

> **No son la suite automatizada.** Las pruebas automatizadas (con `pytest`,
> previstas en la Fase 5) vivirán en la carpeta `tests/` en la raíz del repo.
> Estas guías de `docs/manual-tests/` son complementarias: sirven para
> entender y verificar a mano, no garantizan que "toda la app funcione".

## Cómo se usan

Cada archivo es una guía independiente con un encabezado que declara su
**alcance** (qué prueba y qué **no** prueba). Lee ese encabezado antes de
ejecutar para no asumir más de lo que cubre.

Todas las guías usan un **entorno aislado**: apuntan la variable
`WORKLOG_HOME` a una carpeta temporal, de modo que crean una base de datos
propia y desechable. Tu base de datos real (`~/.worklog/worklog.db`) nunca se
toca.

## Guías disponibles

- [`portable-identity.md`](portable-identity.md) — resolución de la ubicación
  de la base de datos (capas) e identidad portable del proyecto (marcador
  `.cowork`, remoto git).
