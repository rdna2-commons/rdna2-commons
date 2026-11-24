# Как начать

[English](../../getting-started.md) · Пять минут — для человека или агента.

1. **Прочитайте правила:** [CONTRIBUTING.md](CONTRIBUTING.md) и [AGENTS.md](AGENTS.md), если вы агент или
   запускаете агента. Обязательны английские оригиналы; переводы — для удобства.
2. **Найдите задачу:**
   ```
   gh issue list -R scarlett-commons/scarlett-commons -l task -l ready --search "no:assignee"
   ```
   Добавьте `-l area:shaders` (или другое направление из [ROADMAP](ROADMAP.md)), чтобы не распыляться.
3. **Займите её:** комментарий `/claim` в задаче. Одновременно — не больше двух; без PR claim сгорает через
   72 часа. Задача слишком большая — займите и разбейте: `/split`.
4. **Работайте:**
   ```
   gh repo fork scarlett-commons/scarlett-commons --clone    # origin — ваш форк, upstream — этот репозиторий
   cd scarlett-commons
   git fetch upstream
   python3 -I -m unittest discover -s tests     # должно оставаться зелёным (Python 3.10+; в Windows — `python`)
   ```
   Для кода сначала тест. После коммита проверьте, что тест падает без вашего изменения:
   `python3 -I tools/fails_on_base.py upstream/main`. Размер: `git diff --shortstat upstream/main...HEAD`
   (не больше 1500 изменённых строк).
5. **Откройте PR** с `Closes #<задача>`, списком `Provenance:` и подписанными коммитами (`git commit -s`).
   Бот ответит в течение минуты. Закрыл — в комментарии все причины: исправьте и откройте заново.
6. **Проверяйте чужое:** `/reviewer on` в issue «Reviewer pool». Вас будут выбирать случайно.

Вопросы — в issue; чата, который можно пропустить, нет.
