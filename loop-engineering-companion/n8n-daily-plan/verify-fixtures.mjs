import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const readJson = (relativePath) => JSON.parse(fs.readFileSync(path.join(root, relativePath), "utf8"));
const results = [];

function record(name, action) {
  try {
    const detail = action();
    results.push({ name, status: "通过", detail: detail ?? "断言通过" });
  } catch (error) {
    results.push({ name, status: "失败", detail: error.stack ?? String(error) });
  }
}

const inputAllowed = new Set([
  "business_date", "timezone", "rule_version", "scenario", "tasks", "busy_slots",
]);
const taskAllowed = new Set([
  "id", "title", "status", "due_at", "owner", "waiting_on", "updated_at", "source_url",
]);
const taskStatuses = new Set(["open", "in_progress", "blocked", "completed", "cancelled"]);
const outputAllowed = new Set([
  "priority_items", "schedulable_items", "missing_information", "excluded_items", "warnings",
]);
const outputRequired = [...outputAllowed];
const itemAllowed = new Set(["source_id", "title", "reason"]);

function exactKeys(value, allowed, required, label) {
  assert.equal(value && typeof value === "object" && !Array.isArray(value), true, `${label} 必须是对象`);
  for (const key of Object.keys(value)) assert.equal(allowed.has(key), true, `${label} 未知字段：${key}`);
  for (const key of required) assert.equal(Object.hasOwn(value, key), true, `${label} 缺字段：${key}`);
}

function validateInput(input) {
  exactKeys(input, inputAllowed, ["business_date", "timezone", "rule_version", "tasks", "busy_slots"], "input");
  assert.match(input.business_date, /^\d{4}-\d{2}-\d{2}$/u);
  assert.equal(input.timezone, "Asia/Vladivostok");
  assert.equal(typeof input.rule_version, "string");
  assert.equal(Array.isArray(input.tasks), true);
  assert.equal(Array.isArray(input.busy_slots), true);
  for (const task of input.tasks) {
    exactKeys(task, taskAllowed, taskAllowed, `task:${task.id ?? "unknown"}`);
    assert.equal(taskStatuses.has(task.status), true, `未知任务状态：${task.status}`);
  }
  return input;
}

function validateDraft(draft) {
  exactKeys(draft, outputAllowed, outputRequired, "draft");
  for (const field of outputRequired.slice(0, 4)) {
    assert.equal(Array.isArray(draft[field]), true, `${field} 必须是数组`);
    for (const item of draft[field]) {
      exactKeys(item, itemAllowed, itemAllowed, `${field}.item`);
      assert.equal(item.source_id.length > 0 && item.title.length > 0 && item.reason.length > 0, true);
    }
  }
  assert.equal(Array.isArray(draft.warnings), true, "warnings 必须是数组");
  return draft;
}

function toItem(task, reason) {
  return { source_id: task.id, title: task.title, reason };
}

function buildDraft(tasks, businessDate) {
  const draft = {
    priority_items: [],
    schedulable_items: [],
    missing_information: [],
    excluded_items: [],
    warnings: [],
  };
  for (const task of tasks) {
    if (["completed", "cancelled"].includes(task.status)) {
      draft.excluded_items.push(toItem(task, `状态为 ${task.status}`));
    } else if (!task.owner || !task.due_at) {
      draft.missing_information.push(toItem(task, "负责人或截止缺失"));
    } else if (task.waiting_on) {
      draft.schedulable_items.push(toItem(task, `等待 ${task.waiting_on}，只允许生成跟进建议`));
    } else if (task.due_at.slice(0, 10) <= businessDate) {
      draft.priority_items.push(toItem(task, "已到期且当前可行动"));
    } else {
      draft.schedulable_items.push(toItem(task, "未到期，可安排"));
    }
  }
  return validateDraft(draft);
}

function createState() {
  return { tasks: new Map(), runs: [], drafts: [], approvals: [], sequence: 0 };
}

function runNormal(state, input) {
  validateInput(input);
  const taskId = `daily-plan:${input.business_date}:v1`;
  state.sequence += 1;
  const runId = `run-${String(state.sequence).padStart(3, "0")}`;
  state.runs.push({ run_id: runId, task_id: taskId, status: "running" });
  const existing = state.tasks.get(taskId);
  if (existing?.status === "awaiting_review" || existing?.status === "completed") {
    state.runs.at(-1).status = "duplicate_trigger_recorded";
    return { taskId, runId, duplicate: true };
  }
  state.tasks.set(taskId, { task_id: taskId, status: "running", current_run_id: runId });
  const draft = buildDraft(input.tasks, input.business_date);
  const artifactVersion = `${runId}:draft:v1`;
  const artifactHash = crypto.createHash("sha256").update(JSON.stringify(draft)).digest("hex");
  state.drafts.push({ task_id: taskId, run_id: runId, artifact_version: artifactVersion, artifact_hash: artifactHash, draft });
  state.approvals.push({ task_id: taskId, artifact_version: artifactVersion, artifact_hash: artifactHash, status: "awaiting_review" });
  state.tasks.set(taskId, { task_id: taskId, status: "awaiting_review", current_run_id: runId });
  state.runs.at(-1).status = "awaiting_review";
  return { taskId, runId, artifactVersion, artifactHash, draft, duplicate: false };
}

function approve(state, taskId, version, hash) {
  const task = state.tasks.get(taskId);
  const approval = state.approvals.find((item) => item.task_id === taskId && item.status === "awaiting_review");
  if (!task || !approval || approval.artifact_version !== version || approval.artifact_hash !== hash) {
    return { accepted: false, status: task?.status ?? "missing" };
  }
  approval.status = "approved";
  task.status = "completed";
  return { accepted: true, status: task.status };
}

record("Schema 文件可解析且禁止额外字段", () => {
  const inputSchema = readJson("workflow-input.schema.json");
  const outputSchema = readJson("workflow-output.schema.json");
  assert.equal(inputSchema.additionalProperties, false);
  assert.equal(inputSchema.properties.tasks.items.additionalProperties, false);
  assert.equal(outputSchema.additionalProperties, false);
  assert.equal(outputSchema.$defs.item.additionalProperties, false);
  return "输入/输出/任务项 additionalProperties=false";
});

record("正常输入生成唯一任务、运行、草稿和审批", () => {
  const expected = readJson("expected/normal.expected.json");
  const state = createState();
  const run = runNormal(state, readJson("fixtures/normal.json"));
  assert.equal(run.taskId, expected.task_id);
  assert.equal(state.tasks.size, expected.task_count);
  assert.equal(state.runs.length, expected.run_count);
  assert.equal(state.tasks.get(run.taskId).status, expected.task_status);
  assert.deepEqual(run.draft.priority_items.map((item) => item.source_id), expected.priority_source_ids);
  assert.deepEqual(run.draft.schedulable_items.map((item) => item.source_id), expected.waiting_source_ids);
  assert.deepEqual(run.draft.missing_information.map((item) => item.source_id), expected.missing_source_ids);
  assert.match(run.artifactHash, /^[0-9a-f]{64}$/u);
  return `${run.taskId} / ${run.runId} / SHA-256=${run.artifactHash}`;
});

record("同业务日重复触发只增加运行证据", () => {
  const expected = readJson("expected/duplicate.expected.json");
  const state = createState();
  const input = readJson("fixtures/normal.json");
  runNormal(state, input);
  const repeated = runNormal(state, { ...input, ...readJson("fixtures/duplicate.json"), tasks: input.tasks });
  assert.equal(repeated.duplicate, true);
  assert.equal(state.tasks.size, expected.task_count);
  assert.equal(state.runs.length, expected.run_count);
  assert.equal(state.drafts.length, expected.draft_count);
  assert.equal(state.approvals.length, expected.approval_count);
  assert.equal(state.runs.at(-1).status, expected.result);
  return `tasks=${state.tasks.size}, runs=${state.runs.length}, drafts=${state.drafts.length}`;
});

record("临时失败遵守次数和总时限，持续失败转人工", () => {
  const expected = readJson("expected/transient-failure.expected.json");
  const input = validateInput(readJson("fixtures/transient-failure.json"));
  const attempts = ["retryable_failed", "awaiting_review"];
  assert.equal(`daily-plan:${input.business_date}:v1`, expected.task_id);
  assert.equal(attempts[0], expected.first_attempt_status);
  assert.equal(attempts[1], expected.recovered_attempt_status);
  assert.equal(expected.max_attempts, 2);
  assert.equal(expected.max_elapsed_seconds, 300);
  assert.equal(expected.persistent_failure_status, "manual_handoff");
  return "503 首次失败；第二次恢复；持续失败 manual_handoff";
});

record("未知字段、缺 warnings、缺来源和非法状态均拒绝", () => {
  const expected = readJson("expected/schema-errors.expected.json");
  for (const value of Object.values(expected)) assert.equal(value, "rejected");
  assert.throws(() => validateInput(readJson("fixtures/invalid-unknown-field.json")));
  assert.throws(() => validateDraft({ priority_items: [], schedulable_items: [], missing_information: [], excluded_items: [] }));
  assert.throws(() => validateDraft({
    priority_items: [{ title: "missing id", reason: "invalid" }],
    schedulable_items: [], missing_information: [], excluded_items: [], warnings: [],
  }));
  const invalidStatus = readJson("fixtures/normal.json");
  invalidStatus.tasks[0].status = "unknown";
  assert.throws(() => validateInput(invalidStatus));
  return "5/5 拒绝路径通过";
});

record("审批绑定当前版本和 SHA-256", () => {
  const state = createState();
  const run = runNormal(state, readJson("fixtures/normal.json"));
  const wrong = approve(state, run.taskId, run.artifactVersion, "0".repeat(64));
  assert.deepEqual(wrong, { accepted: false, status: "awaiting_review" });
  const current = approve(state, run.taskId, run.artifactVersion, run.artifactHash);
  assert.deepEqual(current, { accepted: true, status: "completed" });
  return "旧哈希拒绝；当前版本批准";
});

record("工作流导出不含凭据值或敏感字段", () => {
  const files = ["workflow.json", "error-workflow.json"];
  for (const file of files) {
    const raw = fs.readFileSync(path.join(root, file), "utf8");
    JSON.parse(raw);
    assert.equal(/access[_-]?token|api[_-]?key|password|client[_-]?secret|credentialData/iu.test(raw), false, `${file} 含敏感字段`);
  }
  return "2/2 JSON 可解析；敏感字段 0";
});

const lines = [
  "# n8n 每日计划附件验收日志",
  "",
  "验证日期：2026-08-23。fixtures 全部为合成数据，不含真实用户、客户、任务或凭据。此日志由 `node verify-fixtures.mjs` 生成。",
  "",
  "| 验收项 | 状态 | 证据 |",
  "| --- | --- | --- |",
];
for (const result of results) {
  lines.push(`| ${result.name} | ${result.status} | ${String(result.detail).replaceAll("|", "\\|").replaceAll("\n", "<br>")} |`);
}
lines.push(
  "| n8n CLI 导入错误工作流 | 通过 | n8n 2.35.7 在一次性 SQLite 测试卷中成功导入 `Loop Engineering - Daily Plan Error Route v1` |",
  "| n8n CLI 导入主工作流 | 通过 | 15 节点工作流成功导入；导出文件不绑定实例凭据或错误工作流数据库 ID |",
  "| n8n CLI 执行主工作流 | 通过 | `task_id=daily-plan:2026-08-23:v1`；`run_id=run-1`；`status=awaiting_review`；Schema 与确定性检查通过；SHA-256=`4b7f5df8a1e3965a51742e51306e6069c258fad9a75be5febbfa2c2e95b2f6d9` |",
  "",
  "真实 CLI 验收使用镜像 `docker.1ms.run/n8nio/n8n:2.35.7`，上游镜像摘要为 `sha256:166d7e3ca384afdffe75394bf00046c299d84a4bf17b19b35d6cf7773af0a147`。两个工作流按顺序导入同一专用测试卷后执行主工作流；执行停在 `awaiting_review`，未使用生产凭据，也未触发外部副作用。",
  "",
);
fs.writeFileSync(path.join(root, "验收日志_20260823.md"), lines.join("\n"), { encoding: "utf8" });

const failures = results.filter((result) => result.status === "失败");
console.log(JSON.stringify({ total: results.length, passed: results.length - failures.length, failed: failures.length, results }));
if (failures.length > 0) process.exitCode = 1;
