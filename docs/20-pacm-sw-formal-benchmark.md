# PACM-SW 正式基线、人工 Qrels 与消融批量运行

状态：执行框架已完成，正式效果验证等待人工 qrels 与生成模型连通  
版本：v0.1  
日期：2026-08-16

## 1. 本阶段交付

本阶段在真实 B2/B3/PACM-SW 检索层上补齐四类能力：

1. B0 Single-Agent 与 B1 Multi-Agent Chat 生成任务运行器；
2. 与检索系统隔离的盲化人工 qrels 标注、完整性检查和冻结；
3. PACM-SW R1–R6 单变量消融与 seeds 13/37/73 批量调度；
4. 逐智能体回合、逐实验单元和逐查询 JSONL 审计记录。

实现完成不等于效果结论成立。正式运行必须通过人工 qrels 门；生成模型失败、未标注候选和不完整实验单元都会保留，不允许用自动标签或补造结果绕过质量门。

## 2. B0/B1 生成任务运行器

| 系统 | 定义 | 每个 task × seed 的调用数 |
|---|---|---:|
| B0 | 单一智能体一次性接收任务与冻结语料，不调用检索、记忆或其他智能体 | 1 |
| B1 | Planner 生成计划，Writer 依据计划写作，Reviewer 在相同冻结语料上审阅并形成最终产物 | 3 |

两个系统使用相同任务、相同冻结语料、相同 token 预算和相同模型配置。运行器检查：

- 引用是否严格使用 `[PAPER-###]`；
- 引用是否存在于冻结语料；
- task 要求的证据 ID 覆盖率；
- B1 最终产物对 Planner 决策的保留情况；
- 成功/失败单元、输出长度和实际模型调用轨迹。

当前冻结任务矩阵包含 Related Work、Method Design、Experiment Analysis 和 Short Paper Synthesis 四类任务。完整的 B0/B1 三种子矩阵会产生 12 个 B0 单元和 12 个 B1 单元，即 48 次第三方模型调用。

第三方供应商的 `seed` 能力尚未验证，因此 `provider_seed_enforced=false`。当前 seeds 只作为冻结任务顺序、运行标签和分组字段，不能声称模型输出具有供应商级随机复现性。

## 3. 独立人工 Qrels

qrels 候选池从最近一次检索 JSONL 中读取，按 query 合并所有系统的 top-depth 候选、去重并稳定打乱。标注界面只显示 query、论文 ID、题名、摘要、年份和 DOI，不显示来源系统、原始排名或分数。

相关性采用四级标注：

| 等级 | 定义 |
|---:|---|
| 0 | 与查询无关 |
| 1 | 弱相关，只提供背景或词项重合 |
| 2 | 相关，可直接支持该查询的研究问题 |
| 3 | 高度相关，是该查询的核心证据 |

冻结条件为：所有候选均由登记的 assessor 完成判断，并且每条 query 至少存在一个 `relevance >= 2` 的候选。冻结后对 labels 计算 SHA-256；draft 不会进入 formal 检索或 formal 生成批量。系统没有模型自动标注接口，现有 `literature.matched_query` 只可用于 engineering 调试。

## 4. R1–R6 消融

| ID | 单变量移除项 | 其余部分 |
|---|---|---|
| R1 | provenance score | 保持不变 |
| R2 | freshness score | 保持不变 |
| R3 | conflict penalty | 保持不变 |
| R4 | graph connection score | 保持不变 |
| R5 | role-aware layer weighting | 改为层间等权，其余保持不变 |
| R6 | provenance contract | provenance 权重归零并排除 constraint nodes，其余保持不变 |

正式矩阵由 B2、B3、Ours、R1–R6 共 9 个配置组成。检索执行器本身是确定性的，三 seed 只控制完全同分候选的稳定打破顺序；因此三 seed 可检查排序稳定性，但不能被描述为独立随机训练重复。

## 5. API

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/v1/projects/{project_id}/experiments/qrels/latest` | 获取最近 qrels |
| POST | `/api/v1/projects/{project_id}/experiments/qrels` | 创建盲化候选池 |
| PUT | `/api/v1/projects/{project_id}/experiments/qrels/{qrels_id}/judgments` | 保存人工判断 |
| POST | `/api/v1/projects/{project_id}/experiments/qrels/{qrels_id}/freeze` | 完整性检查并冻结 |
| POST | `/api/v1/projects/{project_id}/experiments/retrieval-runs` | 运行普通或 R1–R6 三种子检索矩阵 |
| GET | `/api/v1/projects/{project_id}/experiments/generation-runs/latest` | 获取最近 B0/B1 批量 |
| POST | `/api/v1/projects/{project_id}/experiments/generation-runs` | 运行 B0/B1 工程抽样或正式批量 |
| GET | `/api/v1/projects/{project_id}/experiments/generation-runs/{run_id}/log` | 下载生成 JSONL |

正式检索请求：

```json
{
  "role": "researcher",
  "top_k": 5,
  "context_budget_tokens": 6000,
  "seeds": [13, 37, 73],
  "include_ablations": true,
  "evaluation_mode": "formal"
}
```

正式生成请求：

```json
{
  "seeds": [13, 37, 73],
  "task_limit": 4,
  "context_budget_tokens": 6000,
  "mode": "formal"
}
```

## 6. 本轮真实验收记录

工程消融运行 `aabbc98a-954f-4d9b-9ec9-2f0395e1c80a` 已完成 9 配置 × 6 query × 3 seeds：

- Embedding：`qwen3.7-text-embedding`，1024 维；
- 缓存：106/106 命中，外部 Embedding 调用 0；
- JSONL：164 条；
- SHA-256：`11997d1911825460fd7589641be93a10dd707a45b5586746aa73cc7dcbe06b31`；
- 模式：`engineering`；
- 效果主张：禁止。

B0/B1 工程抽样 `9f7ee340-d567-4f0e-b533-e6a21f9a5907` 已按真实链路发起 2 个实验单元。两个单元均因当前生成模型端 `ConnectError` 失败，4 条 JSONL 完整保留 header、两个 failed cell 和 footer；SHA-256 为 `0b4ee2d3f3e1c84c3d301eb6e35cc299d3cdd26f8575f9dc4014ae832ab42235`。两个失败单元均准确记录为一次实际调用尝试，未把 B1 计划中的三次调用误记为已执行。独立的 `/api/v1/system/model/test` 同样返回连接失败，因此问题不属于 B0/B1 任务调度或结果解析。

自动测试为 12/12 通过，前端 JavaScript 语法检查通过；未冻结 qrels 时，formal 检索和 formal 生成均返回 HTTP 409。

## 7. 当前质量门

正式效果实验仍处于阻断状态，必须依次完成：

1. 在页面填写真实人工标注者 ID，创建并完成盲化 qrels；
2. 冻结 qrels，保存 labels SHA-256；
3. 修正并通过生成模型连通性测试；
4. 运行正式 R1–R6 三种子检索矩阵；
5. 运行 B0/B1 四任务三种子生成矩阵；
6. 将 B2/B3/Ours 的生成系统纳入相同任务矩阵；
7. 完成人工写作质量评审、统计重建和失败样本审计。

上述条件完成前，`efficacy_claim_allowed` 必须保持 `false`。
