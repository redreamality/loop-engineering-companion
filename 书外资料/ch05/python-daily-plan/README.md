# ch05 Python 每日计划循环（书中原版清单）

本目录保存《循环工程》第 5 章（原第 6 章）"方案三"的书中原版 `main.py`、样例输入 `tasks.json`，以及运行、审批与回归说明。它是教学阅读用的单文件版本；要复制运行、跑测试或接真实数据，请优先使用配套仓库的主项目 [`loop-engineering-companion/`](../../../loop-engineering-companion/README.md)。

## 与配套仓库版的差异

两版业务逻辑同源，但有以下实质差异：

| 方面 | 书中原版（本目录） | 配套仓库版 |
|------|--------------------|------------|
| `task_id` 构成 | `daily-plan:<业务日期>`，规则版本只存 `rule_version` 字段，不进任务身份 | `daily-plan:<业务日期>:v1`，`make_task_id` 把规则版本后缀写进了 `task_id` |
| 输入模型 | `Item.status` 为 `Literal` 枚举，`due_at` 为 `date` | 两者均放宽为 `str` |
| 程序结构 | 固定路径的单文件脚本（读当前目录 `tasks.json`） | `run_once` / `build_draft` / `stage_draft` / `record_failure` 拆分，数据库、输入、产物路径与业务日期为命令参数 |
| 报错方式 | `SystemExit` | `ApprovalRejected` 异常，配套 pytest 回归 |
| 数据库 | 建表即用 | 另有 `ensure_column` 迁移，兼容旧库 |

注意第一点与正文的教学原则相关：正文要求"规则版本绑定在任务上，不写进任务身份"，规则升级应在同一任务下用新版本重新运行。仓库版把版本后缀放进 `task_id`，规则升级会生成新的任务身份，与该原则不一致；以正文为准的话，应在仓库版中去掉该后缀，改用 `rule_version` 字段记录。

## 安装

```powershell
uv init --python 3.12 daily-plan-loop
Set-Location daily-plan-loop
uv add pydantic tzdata
```

把本目录 `main.py` 与 `tasks.json` 放进项目目录。这份样例按业务日期 2026-08-15 解读：`T-104` 今天截止；`T-207` 的原截止是 2026-08-14、已逾期且在等待客户 A；`T-301` 既没有截止日期也没有负责人。`owner` 表示任务负责人，空值表示尚未指定；`due_at` 为 ISO 日期，接入含时分秒的来源时先按业务时区归一化。

## 运行

`uv run main.py` 会按 `Asia/Vladivostok` 计算业务日期，创建 `loop.db` 和 `artifacts/<run_id>-draft.json`，并打印待审产物的版本和 SHA-256。任务表保存业务日期、规则版本、当前运行、输入哈希、反馈版本、重试预算和最近验证；运行表通过外键关联任务并保存同一输入哈希、验证器版本、验证结果和费用（未发生的费用显式记为 0）。事件表以追加记录保存每次领取、失败、拒绝和重复到达的原因。草稿仍处"等待审核"时再次执行，会命中同一个 `task_id`，追加 `duplicate_arrival` 后退出，不创建 `run_id`，也不覆盖待审产物。示例 `task_id` 省略了设计单中的用户段，只适用于单用户试点；多个使用者共用同一套系统时，必须把用户或租户标识写进身份。

## 审批

审批前先打开实际待审文件核对内容，并重新计算该文件的 SHA-256，与台账中当前产物的哈希比较。`approve` 不重读文件，只检查提交的版本和哈希是否匹配数据库；复制生成时打印的旧哈希，不能证明文件后来没有被改过。本练习要求待审产物不被原地修改。需要改稿时，先拒绝旧候选、记录新反馈，再生成新版本并重新验证；文件已被改且无法确认原版本时，停止批准，保留差异供核查。

```powershell
$validUntil = (Get-Date).AddHours(4).ToString("o")
uv run main.py approve "daily-plan:2026-08-15" `
  --artifact-version "run-替换为实际值:draft:v1" `
  --artifact-hash "替换为终端打印的SHA-256" `
  --approver "reviewer-01" `
  --reason "已核对任务来源、日期和排除项" `
  --valid-until $validUntil
```

要求修改时，同样绑定当前产物，并提交一个尚未用于重做的反馈版本：

```powershell
uv run main.py reject "daily-plan:2026-08-15" `
  --artifact-version "run-替换为实际值:draft:v1" `
  --artifact-hash "替换为终端打印的SHA-256" `
  --feedback-version "feedback-v1" `
  --reviewer "reviewer-01" `
  --reason "T-104 的截止日期需回查来源"
```

版本或哈希与台账不一致时条件更新失败；已过期的有效期、空的批准人或理由在更新前被拒绝；反馈版本为空或与上次已用于重做的版本相同，也不能再次允许重做。这些情况下待审产物保持不变。本只读每日计划以"有明确审核人完成审核"为完成条件；若后续增加标签、排期或发送动作，应把 `approved` 与 `completed` 分开。

## 接入模型

骨架用固定规则生成分组。接入模型时只替换 `draft = Draft(...)` 这一段：把 `eligible` 和任务包交给选定的 Agent 或模型适配器，再用 `Draft.model_validate(...)` 检查回传。`Draft` 要求输出包含 `warnings` 并用 `extra="forbid"` 拒绝未知字段。`model_validate` 只完成五层检查中的字段检查；集合覆盖、事实核对、重复与超量检查必须补在写入 `passed` 之前，由检查结果决定能否进入待审。

## 失败分类与回归输入对照表

只有能确认属于暂时故障的连接超时和数据库忙碌记为 `retryable_failed`；缺文件、非法 JSON、编码或字段验证问题进 `needs_input`；权限拒绝和路径类型错误进 `failed_permanent`；未知异常进 `manual_handoff` 并停止自动推进。下一次运行仍沿用原 `task_id`，但 `needs_input` 只有在输入摘要变化后才能新建 `run_id`；`retryable_failed` 必须同时满足重试次数未耗尽、总时限未耗尽且 `next_retry_at` 已到；`rejected` 必须存在尚未用于重做的新反馈版本。

| 回归输入 | 预期任务状态 | 下一步 |
|----------|--------------|--------|
| `tasks.json` 缺失、非法 JSON 或字段不合 Schema | `needs_input` | 补齐或修正输入后再运行 |
| `needs_input` 后输入摘要未变化 | 仍为 `needs_input` | 追加 `input_digest_unchanged` 证据，不创建运行 |
| 文件无读取/写入权限，或路径类型错误 | `failed_permanent` | 修正授权或路径，不能原样重试 |
| 连接超时，或 SQLite 明确返回 locked/busy | `retryable_failed` | 等 `next_retry_at` 到期后，在次数和总时限预算内新建运行 |
| 重试尚未到期 | 仍为 `retryable_failed` | 追加 `next_retry_at_not_due` 证据，不创建运行 |
| 重试次数或总时限耗尽 | `manual_handoff` | 追加预算耗尽证据并转人工，不创建运行 |
| 拒绝后沿用旧反馈版本 | 仍为 `rejected` | 追加 `feedback_version_unchanged` 证据，不创建运行 |
| 拒绝后提交新反馈版本 | `running` | 根据该反馈版本新建一次运行，并将反馈标记为已使用 |
| 未分类的编程错误或数据库错误 | `manual_handoff` | 告警、保留证据并由人判断 |
| 批准使用旧版本、旧哈希或过期时间 | 仍为 `awaiting_review` | 重新读取当前产物，不覆盖状态 |

成对的条件适合一起测试：先让输入缺失，确认进入 `needs_input`；原样再触发，应只增加重复证据；补齐输入后才允许新建运行。表中数据库错误还要单独检查发生位置：`open_db()` 和 `claim_task()` 位于业务异常处理之前，这些位置失败时可能只有进程退出，没有失败状态或下次重试时间；即使异常进入分类处理，数据库持续不可写也会使故障记账失败。退出报错不能等同于已登记 `retryable_failed`；入口与记账故障需要数据库之外的运行记录、退出码监测和通知机制接手。检查时同时核对任务状态、运行数量和事件原因。

## 并发与上线前补项

`BEGIN IMMEDIATE` 把"检查状态、创建 run、领取任务"放在同一个 SQLite 写事务中，两个同时启动的进程不能都领取同一业务任务；`INSERT OR IGNORE` 只负责稳定创建记录，本身不提供互斥。操作系统定时任务最终只需执行 `uv run main.py`，但上线前还要增加进程超时、卡在 `running` 的租约恢复、失败通知和文件权限测试。SQLite 适合单用户试点；出现多人并发领取、细粒度权限或事务型外部动作后，应按第 4 章的证据迁移数据库，不要把示例数据库当成生产建议。

## 与字段合同的差距

正文表 5-3、表 5-4 是应满足的完整要求，本骨架只自动检查其中一部分：

1. **批准不重读文件。** `approve` 只比较提交参数与数据库中的版本、哈希；文件是否仍与记录一致，需审批人另行核对或扩展检查。
2. **`input_hash` 两种口径。** 读取成功时是输入字节的内容哈希；读取失败时是 `unreadable:异常类型:异常内容` 的 SHA-256，只用于识别失败是否重复。缺文件与非法 JSON 都进入 `needs_input`，留下的证据却不同；不能只看状态或哈希是否非空。扩展实现应另设摘要类型或分开存储两种值。
3. **规则版本没有按运行保存。** 骨架的运行表没有按次运行保存规则版本，领取时也不比较版本；要让规则升级后"在同一任务下用新版本重新运行并记录版本变化"可回查，需要为每次运行补记所用版本。
4. **输入快照需人工另存。** 骨架不自动另存输入快照。运行者须在读取前固定并另存输入，获知 `run_id` 后保存到 `source-snapshots/<run_id>/tasks.json`，并在运行记录中写明路径、读取结果和内容哈希；保存的字节应与本次 `input_hash` 核对一致。读取失败时不能补造快照。完整字段合同见 [`../templates/task-run-tables.md`](../templates/task-run-tables.md)。
