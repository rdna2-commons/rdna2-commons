<p align="center"><img src="../../images/banner.svg" alt="Scarlett Commons" width="100%"></p>

<p align="center"><img src="https://raw.githubusercontent.com/scarlett-commons/scarlett-commons/status/badges/phase.svg" alt="phase"> <img src="https://raw.githubusercontent.com/scarlett-commons/scarlett-commons/status/badges/tasks.svg" alt="tasks"> <img src="https://raw.githubusercontent.com/scarlett-commons/scarlett-commons/status/badges/cases.svg" alt="cases"> <img src="https://raw.githubusercontent.com/scarlett-commons/scarlett-commons/status/badges/results.svg" alt="results"></p>

# Scarlett Commons (русский)

[English](../../../README.md) · [Русский](../ru/README.md) · [简体中文](../zh-CN/README.md) · [Español](../es/README.md)

**Документы на русском:** [План простыми словами](plan-explained.md) · [План работ](ROADMAP.md) · [Как начать](getting-started.md) · [Для ИИ-агентов](AGENTS.md) · [Как внести вклад](CONTRIBUTING.md)

> Перевод для удобства. Обязательные правила — английские файлы в корне: CONTRIBUTING.md, AGENTS.md,
> GOVERNANCE.md. Если перевод с ними расходится, верна английская версия.

Открытый проект сообщества: запуск программ Xbox Series X|S (Scarlett) на ПК. Вместо шестнадцатого проекта с
нуля мы собираем и проверяем общие части: тесты семантики шейдеров RDNA2, описания поведения системных API и
результаты на реальном железе. Ими может пользоваться любой проект.

Почти всю рутину делает бот: раздаёт задачи, закрывает PR, нарушающие правила, и сливает те, что прошли тесты
и независимое ревью. Работают люди и ИИ-агенты на равных; мейнтейнеры только присматривают.

## Главные правила

- **Никаких игровых данных.** Ни архивов, ни исполняемых файлов, ни шейдеров, текстур, моделей, звука, видео,
  ни логов с их содержимым. Бот проверяет каждый PR.
- **Никаких ключей, расшифровки и обхода защиты**, никаких ссылок на утечки.
- **Лицензия GPL-3.0-or-later.** Чужой код — только под совместимой лицензией и с указанием источника.
  Переписанный несовместимый код — тоже копия.
- **Ты не прав только потому, что сам это написал.** Тест должен падать без изменения; ревью — вслепую, по
  задаче, а не по описанию автора.

## Как начать (5 минут)

1. Прочитайте CONTRIBUTING.md и AGENTS.md (для агентов).
2. Найдите задачу: `gh issue list -R scarlett-commons/scarlett-commons -l task -l ready --search "no:assignee"`
3. Напишите в задаче `/claim`. Слишком большая — `/split`.
4. Сначала тест, который падает без вашего изменения: `python3 -I tools/fails_on_base.py upstream/main`.
5. PR с `Closes #<задача>`, списком `Provenance:` и подписанными коммитами (`git commit -s`).
6. Хотите проверять чужое — `/reviewer on` в issue «Reviewer pool».

План работ — [ROADMAP](ROADMAP.md), прогресс — [страница прогресса](https://github.com/scarlett-commons/scarlett-commons/blob/status/PROGRESS.md).

## Движок

В `engine/` — гибридный рекомпилятор: код игры выполняется напрямую на процессоре ПК, консольные функции заменены, а важные функции параллельно перекомпилируются статически. Как собирать и тестировать — [docs/engine-dev.md](../../engine-dev.md) (англ.), план — [docs/engine-plan.md](../../engine-plan.md).

> Переводы могут отставать от английского оригинала.
