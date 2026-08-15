# 06 数据、上下文与记忆设计

## 1. 设计目标

数据与记忆设计需要解决：

- 研究事实与 Agent 自然语言记忆混淆；
- 不同阶段需要的上下文不同；
- 文献、论点和实验之间缺少可追溯关系；
- 错误或过期信息被长期召回；
- 多 Agent 交接丢失决策原因；
- 无法回放某篇论文的生成过程。

## 2. 三类数据边界

### 2.1 业务事实数据

由速易通控制中台维护，包括：

- Project、Stage、StageRun；
- Approval、Task、Event；
- Artifact、ArtifactVersion；
- AgentRun、ToolCall；
- QualityGateRun、Delivery。

这些数据是项目状态的权威来源，Agent 不能直接篡改。

### 2.2 研究知识数据

包括：

- ResearchGoal；
- Evidence；
- Claim；
- ExperimentPlan、ExperimentRun、Metric；
- Decision；
- Limitation；
- Conflict；
- ReviewIssue。

这些数据构成项目的可溯源研究图。

### 2.3 Agent 记忆数据

包括：

- 会话摘要；
- 角色工作偏好；
- 团队协作经验；
- 工具故障经验；
- Skill 演进候选；
- 非权威的工作笔记。

Agent 记忆可以帮助执行，但不能覆盖业务事实和研究知识。

## 3. 核心实体

### 3.1 Project

关键字段：

```yaml
project_id: prj_xxx
title: "..."
status: active
automation_mode: full | partial | review
research_direction: context_engineering | memory | evolution
language: en
venue_profile: iclr_short_paper
page_budget: 6
deadline: "..."
compute_budget: {}
current_stage: literature
created_at: "..."
```

### 3.2 Artifact 与 ArtifactVersion

所有重要文件作为 Artifact 管理，每次修改生成新版本。

```yaml
artifact_id: art_xxx
project_id: prj_xxx
type: evidence_ledger
current_version: 4
versions:
  - version: 4
    path: artifacts/evidence/v4.jsonl
    sha256: "..."
    created_by: agent_run_xxx
    derived_from: [art_query_v2]
    status: approved
```

禁止在原路径静默覆盖已批准产物。

### 3.3 Evidence

```json
{
  "evidence_id": "ev_xxx",
  "work_id": "https://openalex.org/W...",
  "doi": "10....",
  "arxiv_id": "...",
  "title": "...",
  "authors": [],
  "year": 2026,
  "source_type": "paper",
  "source_url": "...",
  "location": {"page": 4, "section": "3.2"},
  "span": "authorized excerpt or structured summary",
  "supports": ["claim_xxx"],
  "contradicts": [],
  "retrieved_at": "...",
  "verification": {
    "metadata": "verified",
    "fulltext": "available",
    "retraction_status": "checked"
  },
  "license": "...",
  "confidence": 0.92
}
```

Evidence 必须区分元数据、摘要、全文证据和模型总结，不能混为同一置信等级。

### 3.4 Claim

```json
{
  "claim_id": "clm_xxx",
  "text": "...",
  "claim_type": "experimental_result",
  "scope": "under the evaluated tasks and model settings",
  "supporting_evidence": ["ev_xxx"],
  "supporting_experiments": ["run_xxx"],
  "counter_evidence": [],
  "strength": "moderate",
  "allowed_language": "improves / is associated with",
  "forbidden_language": "proves / universally solves",
  "status": "approved",
  "used_in": ["paper:results:paragraph_3"]
}
```

### 3.5 ExperimentRun

```yaml
experiment_run_id: run_xxx
plan_version: 3
code_commit: abc123
container_digest: sha256:...
dataset_checksums: {}
model_config_hash: sha256:...
seed: 42
started_at: "..."
finished_at: "..."
exit_code: 0
status: completed
metrics_path: runs/run_xxx/metrics.json
stdout_path: runs/run_xxx/stdout.log
stderr_path: runs/run_xxx/stderr.log
resource_usage: {}
```

### 3.6 Decision

Decision 保存“为什么选择”，避免团队只记住结果：

```yaml
decision_id: dec_xxx
question: "选择何种记忆基线？"
options: ["vector-only", "hybrid", "graph-memory"]
selected: "hybrid"
rationale: "..."
evidence: [ev_xxx]
approved_by: user_xxx
valid_from: "..."
supersedes: null
```

## 4. 研究关系图

主要关系：

```text
ResearchGoal
  ├─ decomposed_into → ResearchQuestion
  ├─ constrained_by → Decision
  └─ evaluated_by → ExperimentPlan

Evidence
  ├─ supports/contradicts → Claim
  ├─ describes → Method/Baseline/Dataset
  └─ motivates → ResearchGap

ExperimentRun
  ├─ implements → ExperimentPlan
  ├─ produces → Metric
  └─ supports/contradicts → Claim

Claim
  ├─ used_in → PaperSection
  ├─ limited_by → Limitation
  └─ challenged_by → ReviewIssue
```

首期不要求独立图数据库。关系可以先存 PostgreSQL 关系表或 JSONB，并提供图查询接口。

## 5. 上下文分层

### 5.1 常驻上下文

每次调用均包含，严格控制长度：

- 当前项目目标；
- 当前阶段与输出契约；
- 硬性安全和质量规则；
- 当前角色职责；
- 已批准的范围和关键决策。

### 5.2 按任务召回上下文

根据任务动态获取：

- 相关 Claim/Evidence/Experiment；
- 相关论文段落；
- 冲突和限制；
- 最近一次失败和人工反馈；
- 相关 Skill 经验。

### 5.3 冷存储上下文

不直接放入模型：

- 原始全文；
- 完整日志；
- 旧版本草稿；
- 大型数据和代码；
- 与当前任务弱相关的历史对话。

Agent 通过索引和按需读取访问冷存储。

## 6. 记忆层次

| 层次 | 内容 | 生命周期 | 权威性 |
|---|---|---|---|
| 会话工作记忆 | 当前执行步骤和临时观察 | 单次 AgentRun | 低 |
| Agent 个人记忆 | 角色经验、工具注意事项 | 跨会话 | 低 |
| 团队记忆 | 共同决策、经验教训、分工 | 跨 round/项目可配置 | 中低 |
| 项目研究记忆 | Evidence/Claim/Experiment/Decision | 项目全周期 | 高 |
| 全局 Skill 经验 | 经验证的可复用方法 | 跨项目版本化 | 中 |

项目研究记忆不依赖 JiuwenSwarm 的 Markdown 记忆是否启用，二者通过适配层同步必要摘要。

## 7. 混合检索

检索流程：

1. 根据角色、阶段和任务生成检索意图；
2. BM25/全文检索召回精确术语；
3. 向量检索召回语义相关内容；
4. 图邻接扩展与当前 Claim/Decision 直接相关的节点；
5. 应用项目、权限、版本和状态过滤；
6. 去重、冲突标注和预算化排序；
7. 生成带来源标识的 Context Pack。

Context Pack 示例：

```json
{
  "task": "write_results_section",
  "role": "paper_writer",
  "token_budget": 12000,
  "items": [
    {"id": "clm_1", "type": "claim", "tokens": 120},
    {"id": "run_7", "type": "experiment", "tokens": 540},
    {"id": "ev_9", "type": "evidence", "tokens": 260}
  ],
  "excluded": [
    {"id": "ev_old", "reason": "superseded"}
  ],
  "conflicts": []
}
```

## 8. 溯源置信度

Provenance confidence 可综合：

- 标识符是否经官方元数据源验证；
- 是否获得原始全文或仅有二手摘要；
- 证据位置是否精确；
- 是否存在撤稿、更正或元数据冲突；
- Evidence 是否被独立来源支持；
- 实验结果是否来自成功且可复现的运行；
- 产物是否经过人工批准。

置信度用于排序和警告，不应伪装成统计概率。

## 9. 冲突与失效

- Evidence 之间冲突：同时保留并创建 Conflict。
- 新实验推翻旧 Claim：旧 Claim 标为 superseded，不删除。
- 方法或计划改变：关联新的版本，旧运行保持原计划版本。
- 文献撤稿或更正：传播影响到所有关联 Claim 和论文段落。
- 人工驳回：保留记录并从默认上下文排除。

## 10. 敏感信息与保留策略

- API Key、密码、个人身份信息不得写入 Agent 记忆。
- 未公开草稿默认仅项目可见。
- 无权分发的全文只保存授权范围内的本地副本，不进入交付包。
- 日志在写入前脱敏；必要的原始日志单独加权限。
- 项目删除采用明确审批和可恢复策略；首期不实现自动清理。

