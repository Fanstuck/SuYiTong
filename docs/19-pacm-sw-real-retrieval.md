# PACM-SW 真实检索执行器与 JSONL 记录层

状态：工程验证已完成，论文效果验证待完成  
版本：v0.1  
日期：2026-08-15

## 1. 实现范围

本模块把 EXPERIMENT 中的元数据 proxy 替换为三个真实执行器，并将每个候选的分数组件、预算决策和运行指标写入不可变 JSONL：

| 系统 | 实现 |
|---|---|
| B2 | 第三方 Embedding API + cosine 的 Flat Vector Retrieval |
| B3 | BM25（k1=1.5，b=0.75）与 dense rank 的 RRF（k=60）融合 |
| Ours | PACM-SW 四层记忆 + provenance、freshness、role、graph、conflict、redundancy 与预算组装 |

系统不依赖本地模型、GPU 或外部向量数据库。Embedding 向量来自用户配置的 OpenAI-compatible API；向量按模型和文本 SHA-256 缓存在本地 SQLite，相同冻结输入复跑不重复调用第三方接口。

## 2. PACM-SW 四层记忆

- `semantic`：论文标题和摘要；
- `episodic`：文献被哪条查询检索、来源、年份和 venue；
- `procedural`：METHOD 组件、算法步骤和 evidence-design link；
- `constraint`：DOI、来源记录、provenance 必填字段、不变量和质量门。

每个节点包含 `paper_id`、来源字段和图连接。当前真实项目构建出 semantic 30、episodic 30、constraint 30、procedural 10 个节点；procedural 不覆盖没有 METHOD 证据映射的论文，避免补造方法关系。

PACM-SW 使用固定、版本化的分数组合：

```text
Score = 0.55 Relevance
      + 0.15 Provenance
      + 0.08 Freshness
      + 0.08 RoleMatch
      + 0.10 GraphConnection
      - 0.02 ConflictPenalty
      - 0.04 RedundancyPenalty
```

`Relevance` 由角色感知的四层 dense 相似度和归一化 BM25 构成。角色可选 researcher、planner、writer、reviewer；各角色的层级权重固定写入 JSONL header。候选按 token 估算逐个装入上下文，超过预算的候选被跳过。

## 3. JSONL 审计契约

每个 retrieval run 生成独立文件：

```text
runtime/suyitong/experiments/{project_id}/{retrieval_run_id}/retrieval.jsonl
```

记录类型包括：

1. `run_header`：冻结的上游 ID、模型、评分器版本、角色、预算、权重和层数；
2. `query_execution`：系统、查询、qrels 来源、全部候选、所有分数组件、选择结果、token 与指标；
3. `run_footer`：运行状态和系统汇总；
4. `run_error`：失败阶段、错误和已产生的部分轨迹。

成功后计算整个文件的 SHA-256，manifest 保存 schema、相对路径、哈希、记录数、模型、向量维度和语料规模。JSONL 不保存 API Key、Authorization header 或其他密钥。

## 4. API

| 方法 | 路径 | 作用 |
|---|---|---|
| POST | `/api/v1/system/embedding/test` | 真实调用一个测试文本并返回模型、维度和延迟 |
| GET | `/api/v1/projects/{project_id}/experiments/retrieval-runs/latest` | 获取最近真实检索运行 |
| POST | `/api/v1/projects/{project_id}/experiments/retrieval-runs` | 按角色、Top-K 和预算执行三个检索器 |
| GET | `/api/v1/projects/{project_id}/experiments/retrieval-runs/{run_id}/log` | 下载该项目下的 JSONL |

POST 请求示例：

```json
{
  "role": "researcher",
  "top_k": 5,
  "context_budget_tokens": 6000
}
```

## 5. 首次真实运行

运行 `d468f614-8745-42a9-ae86-0f8f5a04c747` 使用：

- 模型：`qwen3.7-text-embedding`；
- 向量维度：1024；
- 语料：30 篇；
- 查询：6 条；
- 外部调用：7 批；
- JSONL：20 条，约 324 KB；
- JSONL SHA-256：`81effaca03b7057e8bc99d106666f93eb21809691223f445a9de1963d65e978f`。

相同输入第二次运行命中 106/106 个缓存项，Embedding API 调用为 0。

工程 qrels 下得到混合结果：B3 的 Recall 高于 PACM-SW，PACM-SW 的 provenance coverage 更高。这些数值被保留用于调试，但 `qrels_source=literature.matched_query_engineering_only`，不得作为论文效果结论。

## 6. 质量边界

真实检索层完成后仍保持：

```json
{
  "benchmark_status": "retrieval_engines_implemented_formal_benchmark_pending",
  "efficacy_claim_allowed": false
}
```

后续的 B0/B1 生成任务、独立人工 qrels、冻结测试集、R1-R6 消融、三种子调度和失败样本保留层已经实现，详见 [正式基线、人工 Qrels 与消融批量运行](20-pacm-sw-formal-benchmark.md)。正式效果阶段仍需真实人工标注、完整批次与统计审计。当前 conflict detector 是明确记录的词项启发式，正式实验前应替换为冻结的 claim-level 检测器。
