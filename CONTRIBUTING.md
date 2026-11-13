# Cómo trabajamos en este repositorio

## Ramas

| Rama | Para qué | Quién la actualiza |
| --- | --- | --- |
| `main` | Versión aprobada. Lo que está aquí es lo que se presenta. | Solo con un pull request desde `develop`, aprobado por ambos integrantes. |
| `develop` | Integración: funcionalidades terminadas y probadas, pendientes de aprobación final. | Pull requests desde ramas `feature/*`. |
| `feature/<nombre>` | Una funcionalidad o un cambio concreto. | Quien la desarrolla. |
| `fix/<nombre>` | Corrección de un error. | Quien lo corrige. |

Nunca se hace `push` directo a `main` ni a `develop`.

## Paso a paso

1. Actualizar `develop` y crear la rama:
   ```bash
   git checkout develop
   git pull
   git checkout -b feature/panel-por-etapa
   ```
2. Trabajar con commits pequeños y mensajes claros en español (ver abajo).
3. Correr las pruebas antes de subir: `pytest`.
4. Subir la rama y abrir un pull request hacia `develop`.
5. El otro integrante revisa. Si se aprueba, se fusiona en `develop`.
6. Cuando `develop` tenga un conjunto de cambios aprobados por ambos (por ejemplo, el cierre de una iteración), se abre un pull request de `develop` a `main`.

## Mensajes de commit

Formato: `tipo: descripción corta en minúscula`

| Tipo | Uso |
| --- | --- |
| `feat` | Funcionalidad nueva |
| `fix` | Corrección de un error |
| `docs` | Solo documentación |
| `test` | Pruebas |
| `refactor` | Cambio interno sin cambiar el comportamiento |
| `chore` | Configuración, dependencias, herramientas |

Ejemplo: `feat: alerta por temperatura de secado`.

## Proteger `main` en GitHub

En el repositorio: **Settings → Branches → Add branch ruleset** (o *Add rule*) para `main` y para `develop`:

- Exigir pull request antes de fusionar.
- Exigir 1 aprobación.
- Exigir que pasen las pruebas (el flujo `Pruebas` de GitHub Actions).
- Bloquear los *force push*.
