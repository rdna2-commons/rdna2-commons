# The plan, without jargon

**English** · [Русский](i18n/ru/plan-explained.md) · [简体中文](i18n/zh-CN/plan-explained.md) · [Español](i18n/es/plan-explained.md)

**The problem.** A console game is a program written for the console's processor, graphics chip and system.
The processor in an Xbox Series is the same kind a PC has, so most of the program could run on a PC as is.
Two things stop it: the small programs that draw the picture (shaders) are written for the console's AMD graphics
chip, and the system functions the game calls (memory, files, sound, controllers) do not exist on Windows.
Every compatibility project has to translate both, and every one of them is doing it alone.

**What we do instead.** We write down, as tests, exactly what the console does: "this instruction with these
inputs gives these outputs". Several people run the tests on real hardware, and a result counts only when they
agree. Then any project can run the tests against its translator and see, line by line, what it gets wrong.

**The phases**

0. **Foundation** — the rules, the bot that checks every contribution, the documentation. Finished when a
   newcomer, person or AI, can take a task and get it accepted without anyone's help.
1. **Shared knowledge** — the tests themselves, area by area: graphics instructions, memory, sound, storage,
   controllers. Finished when every test has a result confirmed by two independent people.
2. **Adapters** — small connectors that run other projects' translators against our tests, and a public table
   of who passes what.
3. **Upstream fixes** — when the table shows a bug in another project, we offer that project a fix.
4. **Shared components** — pieces several projects need and none has yet, built here as libraries.

From phase 1 on, everything runs in parallel: each task only waits for the tasks it depends on.

**What we never do:** share anything from any game (files, code, pictures, sounds), break protections, or link
to leaks. Everything we test is written by hand for the purpose.

**How to follow along:** the [progress page](https://github.com/scarlett-commons/scarlett-commons/blob/status/PROGRESS.md) updates itself every six hours. Each task is an issue
on GitHub; anyone can take one.
