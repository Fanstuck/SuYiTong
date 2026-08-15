# PACM-SW 方法设计基线

- 文档状态：真实产物已生成，待人工质量门确认
- 方法工作名：PACM-SW
- 方法运行：`1dca6adf-b44a-410f-8999-47a75e462845`
- 上游文献运行：`03870aec-7c86-4fb3-b34c-1a60e96f9e5e`
- 生成模型：`deepseek-v4-flash`

## 1. 方法目标

PACM-SW 将多智能体科研写作中的外部信息管理建模为“分层记忆 + 溯源契约 + 组合检索 + 预算化装配 + 交接门控”。它不修改基础 LLM，而是在有限上下文预算中选择能够回指来源、适合当前任务角色并保持跨版本一致性的记忆记录。

方法设计阶段只冻结可实现契约和可证伪实验草案，不预设 PACM-SW 优于基线。所有权重、阈值、统计检验和结果结论必须在实验阶段确定。

## 2. 问题形式化

给定科研任务 `T`、文献集合 `D`、历史产物版本 `v1...vt`、分层记忆 `M`、检索候选 `R_t`、上下文装配策略 `A_t` 和 Token 预算 `B`，目标是在溯源契约约束下提升生成质量并控制上下文成本：

```text
argmax Q(f_LLM(A_t(M, R_t, q_t)))
s.t. cost(A_t) <= B
and every external claim has a reachable provenance path in G_M
```

这里的质量 `Q` 必须拆分为引用有效性、Claim 支持率、实验—论文一致性、决策保持率等可计算维度，不能使用单一主观总分替代。

## 3. 六个核心组件

| ID | 组件 | 职责 |
|---|---|---|
| C1 | 分层记忆索引器 | 从文献、实验和写作产物构建四层记忆与溯源图 |
| C2 | 溯源契约校验器 | 校验 Claim、Evidence、版本和来源字段，显式暴露缺失与冲突 |
| C3 | 候选召回器 | 执行向量、BM25、图邻接与约束层多路召回 |
| C4 | 组合排序器 | 计算相关性、溯源、角色、图连接、时效、冲突和冗余信号 |
| C5 | 预算化上下文装配器 | 在 Token 预算内保留不可驱逐约束和高价值证据 |
| C6 | 多智能体协调器 | 管理交接物、失败门控写入、冲突仲裁和审计日志 |

## 4. 四层记忆

| 层 | 主要内容 | 写入原则 | 检索角色 |
|---|---|---|---|
| 约束层 K | 任务要求、质量规则、禁止事项、固定决策 | 显式更新、不可被低优先级内容覆盖 | 不可驱逐，始终参与装配 |
| 程序层 P | 方法步骤、实验协议、分析流程 | 验证成功后版本化追加 | 方法和实验任务优先 |
| 情节层 E | 运行记录、数值结果、事件、版本变化 | 追加写入，失败记录保留但标记 | 结果讨论、复现和冲突检查 |
| 语义层 S | 概念、定义、综述论断、跨文档聚合 | 聚合节点必须回指原始来源 | 默认查询入口与图扩展起点 |

## 5. Provenance Contract

核心实体包括 `Document`、`Page`、`Paragraph`、`Version`、`Claim`、`EvidenceNode`、`ExperimentRun` 和 `TaskArtifact`。关键关系包括 `supported_by`、`contradicts`、`derives_from` 和 `supersedes`。

每个证据节点至少保存：

```text
source_document_id
source_page_id
source_paragraph_id
version_id
timestamp
collection_id
extractor_id
memory_layer
contradiction_status
```

核心不变量：外部 Claim 必须有可达证据路径；矛盾证据不得静默合并；历史版本不得原地删除；违反契约的记忆写入必须整体拒绝并返回可修复错误。

## 6. 组合检索目标

```text
Score(c) = w_rel  * Rel(q,c)
         + w_prov * Prov(c)
         + w_role * RoleMatch(c, role, layer)
         + w_graph * GraphConn(c, selected)
         + w_time * Freshness(c,t)
         - w_conf * ConflictPenalty(c, selected)
         - w_red  * RedundancyPenalty(c, selected)
```

所有信号需要先归一化。权重非负，只能在开发集和验证集上确定；冻结测试集不得用于调参。同分时依次按溯源完整度、版本时效、图连接和原始召回分确定，最后使用候选 ID 保证确定性。

## 7. 多智能体协议

推荐角色链：

```text
Planner
  -> Evidence Verifier
  -> Method / Experiment Agent
  -> Writer
  -> Reviewer
```

每次交接生成 `handoff_id`，携带任务契约、已批准决策、证据包、冲突列表、版本和接受标准。接收方先运行 provenance contract；失败产物进入待审查队列，不能直接污染共享记忆。

## 8. 实验与消融

方法运行已经形成四个实验草案：

1. EXP1：引用有效性、虚假引用率和 Claim 支持率。
2. EXP2：角色感知上下文选择的质量—Token 成本曲线。
3. EXP3：Claim-Evidence-Experiment 关系对阶段一致性的贡献。
4. EXP4：各方法组件的必要性与消融贡献。

基线保持 B0 Single-Agent、B1 Multi-Agent Chat、B2 Flat Vector RAG、B3 Hybrid Retrieval 和 Ours PACM-SW。六个单变量消融分别移除 provenance、时效/版本、冲突检测、图连接、角色匹配和溯源契约写入门控。

## 9. 证据边界

- 上游 30 个 PAPER 编号作为方法运行的冻结白名单。
- PAPER-017/PAPER-018 可能是同一工作的不同版本，不得当作两个独立验证。
- PAPER-016 等题录级记录只能支持结构动机，不能支持定量性能结论。
- H3 仍为证据不足的待验证命题，不构成已确认的新颖性结论。
- PACM-SW 只控制外部上下文和引用边界，不能保证基础模型绝不生成内部知识幻觉。

## 10. METHOD 质量门

人工确认前应检查：

1. 四层记忆划分是否存在重叠，能否写成确定性分类规则。
2. Provenance Contract 字段是否能从 OpenAlex、PDF 解析器、实验日志和写作版本中真实获得。
3. 组合评分的每个信号是否可计算、可记录、可单独消融。
4. B0–B3 是否使用相同模型、任务、文献集合和预算规则。
5. 主指标是否有确定性计算或稳定的人工标注协议。
6. 实验成本是否满足比赛时间与第三方 API 预算。
7. 方法工作名是否完成重名检查；未检查前仍视为工作名。

质量门确认后，项目进入 `experiment`。确认只代表方法可进入实现与实验，不代表方法有效或论文结论成立。

