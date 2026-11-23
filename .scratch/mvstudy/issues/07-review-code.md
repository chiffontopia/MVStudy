# 07 — 从已有工作台定位裸 except 与未定义名称

**Parent:** [7 号 Spec](../../../docs/task-07-spec.md) · [共享契约与关闭规则](../../../docs/development.md)

**What to build:** 在已合入的 Vue/Flask 粘贴评审路径上补全规则分类、规则版本与空结果展示。继续使用 review_source 和原有端点。

**Blocked by:** None — can start immediately

**Status:** done

- [x] 分别输入裸 except、未定义名称、超长行及干净代码；展示对应类别、1 起算行号、理由与建议，干净代码返回 []。
- [x] 带 print 的文本仅被解析；保留原型响应字段、512 KiB 请求上限和既有语言的行长检查。

**验收证据：** 实现提交 `a9d1198` 已随 [PR #5](https://github.com/chiffontopia/MVStudy/pull/5) 合入 `main`，并确认该提交包含在 `ff181a9` 的历史中。PR 实现分支验收：`python -m unittest mvstudy.domains.review.test_static_review`（`PYTHONPATH=backend`，3 项通过）、`python -m unittest discover -s tests`（4 项通过）、`npm --prefix frontend run build`（通过）；当前上游基线 `python tools/check_layout.py` 通过。
