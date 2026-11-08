# Loop Engineering Companion

这份配套项目对应《循环工程》第 5 章（你的第一个循环）和配套的"循环成熟度自测表"。运行时为 Python 3.12，依赖由 `uv.lock` 固定。

## 第 5 章：每日计划循环

代码类型：可执行 Python。它读取本地 JSON，生成待审草稿，保存任务与运行状态，不调用模型或外部业务动作。

安装并执行一次固定业务日期的样例：

```powershell
uv sync --locked --dev
uv run daily-plan-loop run `
  --input examples/tasks.json `
  --database loop.db `
  --artifacts artifacts `
  --business-date 2026-08-15
```

命令输出当前 `artifact_version` 和 `artifact_hash`。批准时把这两个值原样带回，并使用带时区的未来有效期：

```powershell
uv run daily-plan-loop approve "daily-plan:2026-08-15:v1" `
  --database loop.db `
  --artifact-version "<current version>" `
  --artifact-hash "<current sha256>" `
  --approver "reviewer-01" `
  --reason "已核对任务来源、日期和排除项" `
  --valid-until "2026-08-16T09:00:00+10:00"
```

这是教学用状态与审批合同，不是生产部署模板。SQLite 适合单用户试点；多人并发、细粒度权限和事务型外部动作需要另行设计。示例表结构仍完整保存书中要求的业务日期、规则版本、当前运行、输入哈希、反馈版本、重试预算、下一次重试时间、验证结果和成本字段，未发生的模型或平台费用显式记为 0。

同一业务任务只有三类恢复信号能创建新运行：`needs_input` 收到不同的输入哈希，`retryable_failed` 到达重试时间且仍有次数与总时限预算，`rejected` 收到新的反馈版本。其余重复触发只追加到 `loop_events`，不写入 `loop_runs`。要求修改时，先把当前产物和新反馈绑定到拒绝记录；下一次 `run` 会消费该反馈版本：

```powershell
uv run daily-plan-loop reject "daily-plan:2026-08-15:v1" `
  --database loop.db `
  --artifact-version "<current version>" `
  --artifact-hash "<current sha256>" `
  --feedback-version "feedback-v1" `
  --reviewer "reviewer-01" `
  --reason "回查 T-104 的截止日期"
```

## 循环成熟度自测表：真实 PostgreSQL 夹具

代码类型：PostgreSQL DDL、参数化查询和可执行 pytest。`tests/test_maturity_postgres.py` 创建独立临时 schema，验证旧评审或旧系统版本的 L3/L4 证据不会污染当前评审、当前系统版本的 L1 结果。

本机已有可用 PostgreSQL 时，直接设置测试 DSN：

```powershell
$env:TEST_POSTGRES_DSN = 'postgresql://loop_test:loop_test@127.0.0.1:55432/loop_engineering'
uv run pytest tests/test_maturity_postgres.py -q
Remove-Item Env:TEST_POSTGRES_DSN
```

仓库也提供只用于测试的 `compose.yaml`。它把数据库目录放在容器 `tmpfs` 中，不保存业务数据：

```powershell
docker compose up -d --wait postgres
$env:TEST_POSTGRES_DSN = 'postgresql://loop_test:loop_test@127.0.0.1:55432/loop_engineering'
uv run pytest -q
Remove-Item Env:TEST_POSTGRES_DSN
docker compose down
```

## 验收范围

`uv run pytest -q` 检查：

- `Draft` 保留 `warnings` 并拒绝未知字段；
- 缺输入、权限、瞬时依赖错误和未知错误进入不同状态；
- 未变化输入、未到期或超预算重试、无新反馈的重做都不创建运行，并保留重复到达证据；
- 批准绑定当前版本、SHA-256、批准人、理由和有效期；
- 任务表与运行表保存完整审计合同；
- 提供 `TEST_POSTGRES_DSN` 时，在真实 PostgreSQL 引擎上验证评审与系统版本隔离。

没有设置 `TEST_POSTGRES_DSN` 时，只有 PostgreSQL 测试会显示为跳过；这不能作为成熟度自测表数据库语义已经验证的证据。
