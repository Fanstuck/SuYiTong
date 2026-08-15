# PACM-SW 实验验证模块

状态：开发基线（协议与检索 Harness 已实现，正式效果实验待实现）  
版本：v0.1  
日期：2026-08-15

## 1. 模块目标

EXPERIMENT 模块把已确认的 METHOD 产物转换为可执行、可证伪、可审计的实验协议，并在任何论文结果写作前完成质量门检查。

当前实现有意区分两类产物：

1. **协议与工程试运行**：验证数据、接口、指标计算和运行留痕能否贯通；
2. **正式效果实验**：使用真实基线、PACM-SW 执行器、冻结任务和独立标注运行，才可形成论文结论。

任何 proxy、mock、元数据相关性分或自动构造的相关集合都不得进入论文结果表。

## 2. 已实现纵向链路

```text
已确认 METHOD + 已确认文献集
        ↓
模型生成预注册实验协议
        ↓
平台确定性归一化与必填项补全
        ↓
上游/系统/文献/种子/执行器预检
        ↓
3 个代理检索配置 × 6 条查询 smoke test
        ↓
持久化协议、轨迹、指标与解释边界
        ↓
正式执行器缺失 → 质量门阻断，不进入 WRITING
```

实验运行持久化到 SQLite，并关联项目、METHOD 运行和 LITERATURE 运行 ID，避免实验输入发生静默漂移。

## 3. 冻结系统配置

| ID | 配置 | 目的 |
|---|---|---|
| B0 | Single-Agent | 无检索、无持久记忆的单智能体基线 |
| B1 | Multi-Agent Chat | 只有对话历史的多智能体基线 |
| B2 | Flat Vector RAG | 扁平向量检索基线 |
| B3 | Hybrid Retrieval | BM25 与向量融合基线 |
| Ours | PACM-SW | 四层记忆、溯源图、角色感知、冲突与预算组装 |

公平性约束至少包括同一基础模型、语料、任务、输出上限、上下文预算、候选上限、提示词版本和随机种子。协议默认使用种子 `13 / 37 / 73`，每个配置与任务组合至少重复三次。

## 4. 指标与消融契约

核心指标覆盖：

- Fabricated Reference Rate；
- Claim Support Rate；
- Reference Validity；
- Context Token Cost；
- Decision Retention；
- Experiment-Paper Consistency；
- Retrieval Precision@k。

R1-R6 消融依次移除 provenance 排序、时效/版本、冲突检测、图连接、角色匹配和 provenance 写入质量门。正式统计必须在查看结果前冻结，报告原始值、均值、标准差、95% bootstrap 置信区间、配对检验、Holm 校正与效应量，并保留失败、不显著和负向结果。

## 5. 当前 Harness 的准确含义

当前 smoke test 运行 `B2-proxy`、`B3-proxy`、`Ours-proxy` 三种配置，输出 Recall@5、MRR@5、provenance coverage 和 token proxy，用于检查：

- 文献运行能否稳定提供查询和证据 ID；
- 排序器能否生成确定性候选；
- 指标和运行轨迹能否序列化、持久化并展示；
- 质量门能否识别非正式结果。

它不等价于正式实验：B2 尚非向量检索，B3 尚非 BM25+向量融合，Ours 尚未实现完整 provenance 图、角色、冲突和冗余评分；相关集合也来自 `matched_query`，不是独立人工 qrels。因此运行统一标记：

```json
{
  "validation_level": "protocol_and_retrieval_harness_smoke",
  "benchmark_status": "formal_benchmark_pending",
  "efficacy_claim_allowed": false
}
```

## 6. API 与前端

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/v1/projects/{project_id}/experiments/runs/latest` | 获取最近实验运行 |
| POST | `/api/v1/projects/{project_id}/experiments/runs` | 生成协议、预检并运行 harness |
| POST | `/api/v1/projects/{project_id}/experiments/confirm` | 确认正式实验质量门 |

项目页展示预注册目标、B0-Ours 配置、任务、指标、预检、代理试运行、统计与复现清单、执行轨迹及阻断原因。当 `efficacy_claim_allowed=false` 时，确认接口返回 HTTP 409，页面禁用“进入论文写作”。

## 7. 正式实验的完成条件

必须全部满足以下条件，才可把状态改为可确认：

1. 实现 B2 的真实 embedding/vector index；
2. 实现 B3 的 BM25+dense 融合与固定融合参数；
3. 实现 Ours 的四层记忆、provenance 图和完整排序项；
4. 实现 B0/B1 生成任务运行器；
5. 冻结独立开发集、测试集、gold qrels 和提示词；
6. 完成五系统、六消融、三种子运行并保存逐运行 JSONL；
7. 从只读原始记录重建全部主表和统计检验；
8. 完成失败样本、成本、公平性和证据账本人工审计。

真实检索执行器与运行记录层已在 [19-pacm-sw-real-retrieval.md](19-pacm-sw-real-retrieval.md) 实现。下一里程碑是 B0/B1 生成任务、独立 qrels 和正式消融运行，不是直接撰写结果章节。
