# 书外资料

> 《循环工程》改版（17 章 → 9 章 + 结语）时从正文外移的模板、完整清单、演练、样例、附录与完整来源说明。目录按**新章号**组织；本目录内容不计入书稿字数，方法与术语以正文为准，仓库内容随工具变化更新。书中链接以 `配套资料 <companion-repo-url>/书外资料/…` 形式指向本目录（占位，公开方式出版前确认）。

## 目录结构

```text
书外资料/
  ch01/…ch09/            按新章号外移的章内资料（模板、练习、演练、外移正文）
  epilogue/              结语外移件（三条路线、迁移预案、证据日志模板）
  self-assessment/       循环成熟度自测表（原第 16 章），含样例/
  appendix/
    A_工具箱/            原附录 A，每个模板一个文件（A.1 使用方式为 README）
    B_30个执行日实施手册.md
    C_故障排查手册.md
    D_术语与字段字典.md
    E_评测样本库/        主文件 + 安全与异常样本（原第 12 章表 12-7 收编）
  sources/               来源说明与参考资料（完整版）
```

## 新旧章号对照

| 原章 | 新位置 | 原章 | 新位置 |
|------|--------|------|--------|
| 第 1、2 章 | 第 1 章 | 第 11 章 | 第 7 章 |
| 第 3 章 | 第 2 章 | 第 12、13 章 | 第 8 章 |
| 第 4 章 | 第 3 章 | 第 14、15 章 | 第 9 章 |
| 第 5 章 | 第 4 章 | 第 16 章 | 配套 `self-assessment/`（成熟度自测表） |
| 第 6 章 | 第 5 章 | 第 17 章 | 结语 |
| 第 7–10 章 | 第 6 章 | 附录 A–E | 配套 `appendix/` |
| — | — | 来源说明 | 书末精简版 + 配套 `sources/` 完整版 |

外移的章内小节随所在章进入 `ch01`…`ch09`；原 12.19 并入附录 A.15，原 13.21 并入 A.16，原 15.7 并入 A.18，原 15.20 并入 A.19，原 12.20 表 12-7 并入附录 E；附录 B 吸收了原 15.21 的组织 90 天提示；来源说明第七节承接原表 12-3 与表 14-8 外移的工具候选。

## 最先用到的三个入口

1. [循环设计单](ch05/templates/design-sheet.md)（第 5 章）
2. [循环成熟度自测表](self-assessment/循环成熟度自测表.md)
3. [附录 C 故障排查手册](appendix/C_故障排查手册.md)

## 各章外移文件

按新章号列出，每行为"文件 — 对应正文小节"；对应小节不明确的只列文件名。清单扫描于 2026-11-07，各章仍可能增补。

### 第 1 章（`ch01/`）

- [任务卡.md](ch01/任务卡.md) — 第 1 章"跟着一项工作走到底"
- [工作影随访谈问题.md](ch01/工作影随访谈问题.md) — 第 1 章"跟着一项工作走到底"
- [手动操作需求整理表.md](ch01/手动操作需求整理表.md) — 第 1 章"跟着一项工作走到底"
- [候选池练习.md](ch01/候选池练习.md) — 第 1 章"哪些任务适合做第一条循环"
- [岗位拆任务示例.md](ch01/岗位拆任务示例.md) — 第 1 章"只自动化中间，把任务和岗位分开"
- [循环合同模板.md](ch01/循环合同模板.md) — 第 1 章"循环合同、停止条件与结束方式"
- [循环退役检查表.md](ch01/循环退役检查表.md) — 第 1 章"循环合同、停止条件与结束方式"
- [任务评审会议程.md](ch01/任务评审会议程.md)
- [循环边界工作坊.md](ch01/循环边界工作坊.md)
- [手动循环观察周.md](ch01/手动循环观察周.md)

### 第 2 章（`ch02/`）

- [四层指标与误读.md](ch02/四层指标与误读.md) — 2.6
- [四层评审追问表.md](ch02/四层评审追问表.md) — 2.7
- [模型升级四层检查表.md](ch02/模型升级四层检查表.md) — 2.9
- [四层自测清单.md](ch02/四层自测清单.md) — 2.10
- [四层剖面练习.md](ch02/四层剖面练习.md)
- [四层故障卡.md](ch02/四层故障卡.md)

### 第 3 章（`ch03/`）

- [事故后规则升级流程.md](ch03/事故后规则升级流程.md) — 3.5
- [邮件循环验收指标算例.md](ch03/邮件循环验收指标算例.md) — 3.7
- [五步设计十问.md](ch03/五步设计十问.md) — 3.10
- [五步设计评审议程.md](ch03/五步设计评审议程.md) — 3.10
- [五步证据包模板.md](ch03/五步证据包模板.md) — 3.10
- [跨轮次改进闭环.md](ch03/跨轮次改进闭环.md)

### 第 4 章（`ch04/`）

- [沙箱资源边界清单.md](ch04/沙箱资源边界清单.md) — 4.5
- [六项责任草图.md](ch04/六项责任草图.md) — 4.9
- [六类设施故障注入表.md](ch04/六类设施故障注入表.md) — 4.10
- [基础设施评审记录模板.md](ch04/基础设施评审记录模板.md) — 4.10
- [三种规模参考链路.md](ch04/三种规模参考链路.md) — 4.11
- [表格迁移数据库清单.md](ch04/表格迁移数据库清单.md) — 4.11
- [最小服务目标示例.md](ch04/最小服务目标示例.md) — 4.12

### 第 5 章（`ch05/`）

目录说明见 [ch05/README.md](ch05/README.md)。

- [templates/design-sheet.md](ch05/templates/design-sheet.md) — 5.4
- [templates/task-run-tables.md](ch05/templates/task-run-tables.md) — 5.5
- [floatboat-practice.md](ch05/floatboat-practice.md) — 5.10
- [python-daily-plan/](ch05/python-daily-plan/README.md)（README.md、main.py、tasks.json） — 5.10
- [templates/input-fields.md](ch05/templates/input-fields.md) — 5.11
- [eval-matrix.md](ch05/eval-matrix.md) — 5.12
- [go-live-gates.md](ch05/go-live-gates.md) — 5.13
- [acceptance-checklist.md](ch05/acceptance-checklist.md) — 5.13
- [trial-kit/](ch05/trial-kit/)（00-loop-contract.md … 07-change-log.md，共 8 个） — 5.13
- [approval-diff-view.md](ch05/approval-diff-view.md) — 5.14
- [drills/rollback-handoff.md](ch05/drills/rollback-handoff.md) — 5.14
- [maintenance.md](ch05/maintenance.md) — 5.14

### 第 6 章（`ch06/`）

- [checklists/content-fault-drills.md](ch06/checklists/content-fault-drills.md) — 6.1
- [cases/email-four-weeks.md](ch06/cases/email-four-weeks.md) — 6.2
- [templates/solo-customer-followup.md](ch06/templates/solo-customer-followup.md) — 6.2
- [templates/office-calendar-precheck.md](ch06/templates/office-calendar-precheck.md) — 6.3
- [templates/solo-ops-review.md](ch06/templates/solo-ops-review.md) — 6.4
- [templates/solo-weekly-console.md](ch06/templates/solo-weekly-console.md) — 6.4
- [workbench-studio-ledger/README.md](ch06/workbench-studio-ledger/README.md) — 6.4
- [workbench-studio-ledger/samples/sample-data.md](ch06/workbench-studio-ledger/samples/sample-data.md) — 6.4
- [cases/column-first-review.md](ch06/cases/column-first-review.md) — 6.5
- [cases/cs-shared-events.md](ch06/cases/cs-shared-events.md) — 6.5
- [cases/next-day-delivery-incident.md](ch06/cases/next-day-delivery-incident.md) — 6.5
- [cases/photographer.md](ch06/cases/photographer.md) — 6.5
- [checklists/content-license-fields.md](ch06/checklists/content-license-fields.md) — 6.5
- [combo/make-column-combo.md](ch06/combo/make-column-combo.md) — 6.5
- [combo/use-existing-combo-weekly-report.md](ch06/combo/use-existing-combo-weekly-report.md) — 6.5
- [templates/ecom-decision-pack.md](ch06/templates/ecom-decision-pack.md) — 6.7
- [templates/ecom-price-monitor.md](ch06/templates/ecom-price-monitor.md) — 6.7
- [checklists/rollout-stages.md](ch06/checklists/rollout-stages.md) — 6.8
- [cases/solo-quarter-roi.md](ch06/cases/solo-quarter-roi.md)
- [checklists/content-metrics.md](ch06/checklists/content-metrics.md)
- [checklists/content-prepublish-onepager.md](ch06/checklists/content-prepublish-onepager.md)
- [checklists/office-review-card.md](ch06/checklists/office-review-card.md)
- [checklists/solo-continuity-and-recovery.md](ch06/checklists/solo-continuity-and-recovery.md)
- [checklists/solo-data-partitions.md](ch06/checklists/solo-data-partitions.md)
- [prompts/email-folder-check.md](ch06/prompts/email-folder-check.md)
- [runbooks/content-on-call.md](ch06/runbooks/content-on-call.md)
- [runbooks/cs-shift.md](ch06/runbooks/cs-shift.md)
- [templates/cs-faq-update.md](ch06/templates/cs-faq-update.md)
- [templates/cs-feedback.md](ch06/templates/cs-feedback.md)
- [templates/ecom-returns-refunds.md](ch06/templates/ecom-returns-refunds.md)
- [templates/office-project-inspection.md](ch06/templates/office-project-inspection.md)
- [templates/office-report-approval.md](ch06/templates/office-report-approval.md)
- [templates/office-weekly-report.md](ch06/templates/office-weekly-report.md)

### 第 7 章（`ch07/`）

目录说明见 [ch07/README.md](ch07/README.md)。

- [ci-repair-runbook.md](ch07/ci-repair-runbook.md) — 7.3
- [templates/ci-repair-pr-description.md](ch07/templates/ci-repair-pr-description.md) — 7.3
- [test-log-report-skill/README.md](ch07/test-log-report-skill/README.md) — 7.4
- [pr-review-publish-rules.md](ch07/pr-review-publish-rules.md) — 7.6
- [cases/http-client-upgrade-regression.md](ch07/cases/http-client-upgrade-regression.md) — 7.8
- [templates/handoff-package.md](ch07/templates/handoff-package.md) — 7.9
- [templates/release-gate-checklist.md](ch07/templates/release-gate-checklist.md) — 7.10
- [coding-tools/product-notes.md](ch07/coding-tools/product-notes.md) — 7.11
- [coding-tools/migration-checklist.md](ch07/coding-tools/migration-checklist.md) — 7.11
- [drills/workflow-file-and-registry-timeout.md](ch07/drills/workflow-file-and-registry-timeout.md)
- [reviews/weekly-ops-review.md](ch07/reviews/weekly-ops-review.md)

### 第 8 章（`ch08/`）

- [独立验证_工具候选与验收证据.md](ch08/独立验证_工具候选与验收证据.md) — 8.2
- [安全上线评审清单.md](ch08/安全上线评审清单.md) — 8.3
- [破窗授权字段.md](ch08/破窗授权字段.md) — 8.3
- [练习_回查前文产物的安全边界.md](ch08/练习_回查前文产物的安全边界.md) — 8.4
- [安全控制退化指标.md](ch08/安全控制退化指标.md) — 8.5
- [桌面演练_重复退款.md](ch08/桌面演练_重复退款.md) — 8.6
- [近失事件记录示例.md](ch08/近失事件记录示例.md) — 8.6
- [事故复盘_跨客户摘要.md](ch08/事故复盘_跨客户摘要.md) — 8.7
- [威胁建模示例_退款循环.md](ch08/威胁建模示例_退款循环.md) — 8.7
- [安全控制测试矩阵.md](ch08/安全控制测试矩阵.md) — 8.7
- [单任务成本账_合成示例.md](ch08/单任务成本账_合成示例.md) — 8.8、8.9
- [Workflow_固化确定步骤.md](ch08/Workflow_固化确定步骤.md) — 8.9
- [降本实验卡.md](ch08/降本实验卡.md) — 8.9
- [重试风暴_修复步骤.md](ch08/重试风暴_修复步骤.md) — 8.10
- [成本评审表.md](ch08/成本评审表.md) — 8.11
- [练习_用实战记录验收预算.md](ch08/练习_用实战记录验收预算.md) — 8.11
- [预算告警示例.md](ch08/预算告警示例.md) — 8.11
- [案例_账单上涨一倍.md](ch08/案例_账单上涨一倍.md) — 8.12
- [自建总拥有成本清单.md](ch08/自建总拥有成本清单.md)

### 第 9 章（`ch09/`）

- [影子自动化普查表.md](ch09/影子自动化普查表.md) — 9.2
- [P-42_三循环冲突与恢复.md](ch09/P-42_三循环冲突与恢复.md) — 9.7
- [多循环协调_组件候选与验收样例.md](ch09/多循环协调_组件候选与验收样例.md) — 9.7
- [多循环混沌演练.md](ch09/多循环混沌演练.md) — 9.7
- [连接合同测试样例.md](ch09/连接合同测试样例.md) — 9.7
- [连接评审卡.md](ch09/连接评审卡.md) — 9.7
- [演练_关键负责人缺席.md](ch09/演练_关键负责人缺席.md) — 9.8、9.13
- [跨部门交接包.md](ch09/跨部门交接包.md) — 9.10
- [生产变更记录.md](ch09/生产变更记录.md) — 9.11
- [供应商采购评审表.md](ch09/供应商采购评审表.md) — 9.11
- [供应商迁移演练.md](ch09/供应商迁移演练.md) — 9.11
- [组织上线检查表.md](ch09/组织上线检查表.md) — 9.11
- [练习_在工作台中看等待与冲突.md](ch09/练习_在工作台中看等待与冲突.md) — 9.12
- [统一动作门禁_请求结构.json](ch09/统一动作门禁_请求结构.json) — 9.6

### 结语（`epilogue/`）

- [个人_团队_平台三条路线.md](epilogue/个人_团队_平台三条路线.md)
- [能力跃升与平台消失时的迁移.md](epilogue/能力跃升与平台消失时的迁移.md)
- [未来判断证据日志模板.md](epilogue/未来判断证据日志模板.md)
