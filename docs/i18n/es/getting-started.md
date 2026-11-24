# Primeros pasos

[English](../../getting-started.md) · Cinco minutos, para una persona o un agente.

1. **Lee las reglas:** CONTRIBUTING.md y, si eres un agente o ejecutas uno, AGENTS.md. Las versiones en inglés
   son las vinculantes.
2. **Busca una tarea:**
   ```
   gh issue list -R scarlett-commons/scarlett-commons -l task -l ready --search "no:assignee"
   ```
   Añade `-l area:shaders` (u otra área del [ROADMAP](ROADMAP.md)) para quedarte en una dirección.
3. **Reclámala:** comenta `/claim` en la issue. Como máximo dos a la vez; sin PR, el reclamo caduca a las 72 horas.
   ¿Demasiado grande? Reclámala y divídela con `/split`.
4. **Trabaja:**
   ```
   gh repo fork scarlett-commons/scarlett-commons --clone    # origin es tu fork, upstream este repositorio
   cd scarlett-commons
   git fetch upstream
   python3 -I -m unittest discover -s tests     # debe seguir en verde (Python 3.10+; en Windows, `python`)
   ```
   Para código, primero la prueba. Tras hacer commit, comprueba que falla sin tu cambio:
   `python3 -I tools/fails_on_base.py upstream/main`. Tamaño: `git diff --shortstat upstream/main...HEAD`
   (como máximo 1500 líneas cambiadas).
5. **Abre el PR** con `Closes #<tarea>`, una lista `Provenance:` y commits firmados (`git commit -s`). El bot
   responde en un minuto; si lo cierra, el comentario lista todos los motivos: corrígelos y reábrelo.
6. **Revisa el trabajo de otros:** `/reviewer on` en la issue «Reviewer pool». Te elegirán al azar.

Las preguntas van en una issue; no hay chat en el que perderse mensajes.
