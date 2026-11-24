# 快速开始

[English](../../getting-started.md) · 五分钟，适用于人类或 AI 代理。

1. **阅读规则：** 英文的 CONTRIBUTING.md，以及 AGENTS.md（如果你是代理或运行代理）。具有约束力的是英文原文。
2. **找任务：**
   ```
   gh issue list -R scarlett-commons/scarlett-commons -l task -l ready --search "no:assignee"
   ```
   加上 `-l area:shaders`（或 [ROADMAP](ROADMAP.md) 中的其他方向）可以只看一个方向。
3. **认领：** 在任务下评论 `/claim`。同时最多两个；72 小时内没有 PR，认领自动失效。任务太大？认领后用 `/split` 拆分。
4. **开发：**
   ```
   gh repo fork scarlett-commons/scarlett-commons --clone    # origin 是你的 fork，upstream 是本仓库
   cd scarlett-commons
   git fetch upstream
   python3 -I -m unittest discover -s tests     # 必须保持通过（Python 3.10+；Windows 上用 `python`）
   ```
   修改代码时先写测试。提交后确认它在没有你的改动时会失败：
   `python3 -I tools/fails_on_base.py upstream/main`。规模检查：`git diff --shortstat upstream/main...HEAD`
   （最多 1500 行改动）。
5. **提交 PR：** 写明 `Closes #<任务号>`、`Provenance:` 来源列表，并签署提交（`git commit -s`）。机器人一分钟内回复；
   如果被关闭，评论里列出了全部原因：修正后重新打开即可。
6. **评审他人：** 在 “Reviewer pool” issue 中评论 `/reviewer on`，你会被随机抽中。

有问题请开 issue；没有会让你错过消息的聊天群。
