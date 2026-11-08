# 第 5 章 n8n 每日计划循环附件

## 已验证环境

| 项目 | 实测值 |
| --- | --- |
| n8n 版本 | `2.35.7`，由容器内 `n8n --version` 返回 |
| 镜像 | `docker.1ms.run/n8nio/n8n:2.35.7` |
| 上游镜像摘要 | `sha256:166d7e3ca384afdffe75394bf00046c299d84a4bf17b19b35d6cf7773af0a147` |
| 部署方式 | 自托管 Docker；附件验收使用一次性容器和具名测试卷 |
| n8n 数据库 | 附件验收使用 n8n 默认 SQLite；工作流 fixture store 只用于演示，不是生产状态库 |
| 执行模式 | n8n regular 模式；未启用队列执行 |
| 业务时区 | `Asia/Vladivostok`，工作流与触发器均显式设置 |
| 验证日期 | 2026-08-23 |

工作流停在 `awaiting_review`，不修改原任务、不创建日历事件、不发送消息。它包含可执行的合成数据入口和确定性草稿节点，用于验证工作流结构、字段合同和错误路由。接入真实系统时，必须替换两个 `Replace with Read Only Credential` 节点和 `Fixture Store`，并重新执行本页全部验收；导入成功不能证明生产凭据、并发、状态存储或业务审批已经合格。

## 文件

| 文件 | 用途 |
| --- | --- |
| `workflow.json` | 可导入主工作流；15 个节点覆盖触发、任务包、读取、脱敏、去重、运行、草稿、验证、产物、审批包、决策与状态更新 |
| `error-workflow.json` | 独立错误工作流；把输入、权限、瞬时依赖、未分类错误和动作状态未知分路并脱敏 |
| `workflow-input.schema.json` | 脱敏输入合同；任务只允许 8 个字段，未知字段拒绝 |
| `workflow-output.schema.json` | 草稿输出合同；`warnings` 必填，任务项禁止额外字段 |
| `credentials.example.md` | 四类凭据的最小权限与过宽时的停机动作，不包含凭据值 |
| `fixtures/*.json` | 正常、重复、瞬时失败和未知字段合成输入 |
| `expected/*.json` | 各 fixture 的预期任务、运行、错误和批准结果 |
| `verify-fixtures.mjs` | 不依赖 n8n 服务的确定性合同回归，并生成验收日志 |
| `验收日志_20260823.md` | fixtures、Schema、幂等、失败和批准绑定的运行结果 |

## 逐节点配置

| 顺序 | 节点 | 输入与输出 | 失败行为 |
| ---: | --- | --- | --- |
| 1 | `Schedule Trigger 08:30` / `Manual Test Trigger` | 工作日 08:30 或人工验收入口 | 触发配置失败时不创建业务任务 |
| 2 | `Build Envelope` | 计算业务日、时区、规则版本和稳定 `task_id` | 日期或时区不可解析时进入 `needs_input` |
| 3 | `Read Tasks - Replace with Read Only Credential` | 合成任务；生产中替换为专用清单只读节点 | 401/403 永久失败；429/5xx/超时最多 2 次、总时限 5 分钟 |
| 4 | `Read Busy Slots - Replace with Read Only Credential` | 只返回 busy/free 所需字段 | 读取失败进入可重试失败，不用空日历伪装成功 |
| 5 | `Allowlist and Filter` | 只保留 `id/title/status/due_at/owner/waiting_on/updated_at/source_url` | 缺 ID 或状态时停止，Agent 不补字段 |
| 6 | `Atomic Upsert Task - Fixture Store` | 合成状态存储；活动或完成任务记录重复触发并停止 | 生产中必须替换为带唯一约束和条件更新的事务存储 |
| 7 | `New Run ID` | 每次允许执行都创建独立 `run_id` | 无法生成身份时不进入草稿 |
| 8 | `Agent Draft Only - Deterministic Fixture` | 当前为固定规则草稿；生产模型只能接收脱敏任务包 | 模型或解析失败不能归为数据源成功 |
| 9 | `JSON Schema Validate` | 检查必填数组、任务项和额外字段 | 失败记录具体字段并进入 `needs_input`/重做，不放行 |
| 10 | `Deterministic Checks` | 检查任务集合覆盖和来源 ID | 失败保持待人工处理，不用总分覆盖遗漏 |
| 11 | `Save Versioned Artifact` | 生成 `artifact_version` 和 SHA-256 | 保存失败不创建空审批 |
| 12 | `Approval Package - No Auto Approval` | 默认形成绑定当前版本/哈希的待审批包 | 没有具名决定、理由和有效期时不能批准 |
| 13 | `Decision Route` | 批准、拒绝、修改、等待对应不同下一状态 | 旧版本或旧哈希批准抛出 `STALE_APPROVAL` |
| 14 | `Finalize Run and Task` | 保存任务、运行、产物和验证摘要 | 条件更新冲突时转人工，不覆盖新状态 |
| 15 | 独立 `Error Workflow` | 记录节点、执行、任务/运行身份和脱敏错误摘要 | 未分类错误进入 `manual_handoff`；`action_status_unknown` 禁止直接重发 |

## 关键表达式

n8n 2.35.7 的表达式运行时支持 Luxon。若用 Edit Fields 节点替换 `Build Envelope`，按下面两项配置；不要把触发时间放进业务任务身份：

```text
business_date = {{$now.setZone('Asia/Vladivostok').toFormat('yyyy-MM-dd')}}
task_id = {{'daily-plan:' + $json.business_date + ':v1'}}
```

每次尝试使用新的 `run_id`。同一业务日再次触发仍映射到 `daily-plan:<YYYY-MM-DD>:v1`；活动或已完成任务不得产生第二份草稿或审批。

## 导入与执行

在本目录执行以下 PowerShell。测试卷只保存一次性 n8n SQLite 数据；验收后删除卷即可清理。

```powershell
$attachmentDir = (Resolve-Path -LiteralPath '.').Path
$n8nImage = 'docker.1ms.run/n8nio/n8n:2.35.7'
$n8nVolume = 'loop-engineering-n8n-test'

docker volume create $n8nVolume
docker run --rm `
  -e GENERIC_TIMEZONE='Asia/Vladivostok' `
  -e TZ='Asia/Vladivostok' `
  -e NODE_FUNCTION_ALLOW_BUILTIN='crypto' `
  -e N8N_BLOCK_ENV_ACCESS_IN_NODE='false' `
  -v "${attachmentDir}:/files:ro" `
  -v "${n8nVolume}:/home/node/.n8n" `
  $n8nImage import:workflow --input=/files/error-workflow.json

docker run --rm `
  -e GENERIC_TIMEZONE='Asia/Vladivostok' `
  -e TZ='Asia/Vladivostok' `
  -e NODE_FUNCTION_ALLOW_BUILTIN='crypto' `
  -e N8N_BLOCK_ENV_ACCESS_IN_NODE='false' `
  -v "${attachmentDir}:/files:ro" `
  -v "${n8nVolume}:/home/node/.n8n" `
  $n8nImage import:workflow --input=/files/workflow.json

docker run --rm `
  -e GENERIC_TIMEZONE='Asia/Vladivostok' `
  -e TZ='Asia/Vladivostok' `
  -e NODE_FUNCTION_ALLOW_BUILTIN='crypto' `
  -e N8N_BLOCK_ENV_ACCESS_IN_NODE='false' `
  -v "${n8nVolume}:/home/node/.n8n" `
  $n8nImage execute --id=LoopDailyPlanV1 --rawOutput
```

导入主工作流后，在 n8n 设置中把 `Loop Engineering - Daily Plan Error Route v1` 选为错误工作流。导出 JSON 中不预写错误工作流数据库 ID，因为不同实例导入后 ID 可能变化。

本地 fixtures 回归不需要启动 n8n 服务：

```powershell
node verify-fixtures.mjs
```

清理命令必须在确认卷名仍为本页测试卷后执行：

```powershell
docker volume inspect loop-engineering-n8n-test
docker volume rm loop-engineering-n8n-test
```

## 验收合同

1. 正常输入只产生一个业务任务、一个运行、一份通过 Schema 的草稿和一项待审批记录。
2. 同业务日连续触发时沿用 `task_id`，新运行只记录重复证据；草稿与审批仍各一份。
3. 首次 503 可在 2 次、5 分钟预算内恢复；持续失败进入 `manual_handoff`，留下错误证据。
4. 输入未知字段、输出未知字段、缺少 `warnings`、缺来源 ID 和非法状态分别被拒绝。
5. 审批必须绑定当前 `artifact_version` 与 SHA-256；旧哈希拒绝，人工修改后生成新版本并重跑验证。

生产接入还需验证数据库原子唯一约束、并发领取、真实连接器权限、凭据撤销、错误工作流告警接收人、日志保留与删除。附件没有完成这些环境专属决定，因此不得仅凭导入成功开放外部动作。
