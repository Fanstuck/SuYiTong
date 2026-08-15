# PACM-SW 需求澄清与选题拆解垂直链路

- 状态：已实现、待人工质量门确认
- 提示词版本：`pacm-sw-topic-framing-v1`
- 首次真实运行：2026-08-15
- 模型栈：JiuwenSwarm / openJiuwen → OpenAI 兼容第三方 API

## 1. 核心技术方向

速易通将“可溯源上下文记忆”作为首篇论文和产品中台的共同主方向，把上下文工程与记忆引擎统一起来；自演进保留为平台扩展能力，不作为首篇论文的主要结论。

工作名：

> **Provenance-Aware Context Memory for Multi-Agent Scientific Writing**  
> 面向多智能体科研写作的可溯源上下文记忆方法

暂定方法名为 **PACM-SW**。该名称、研究空白和新颖性都必须经过下一阶段的相关工作检索，当前不得表述为已被证实。

## 2. 已实现链路

```text
项目输入
  → 汇集带来源类型和 checksum 的上下文
  → JiuwenSwarm 模型栈结构化生成
  → Pydantic Schema 校验
  → 来源 ID 白名单校验
  → 保存候选题目、研究问题、贡献假设和检索式
  → 页面审阅与候选方案选择
  → 人工确认质量门
  → 进入文献调研
```

点击质量门不再直接修改阶段。只有生成成功且人工选择候选题目后，项目才能进入 `literature_review`。

## 3. 可追溯上下文

首期固定汇集以下输入：

| Context ID | 类型 | 内容 |
|---|---|---|
| `CTX-PROJECT-001` | project | 用户暂定题目 |
| `CTX-PROJECT-002` | project | 用户填写的研究方向 |
| `CTX-CORE-001` | product_core | PACM-SW 核心技术定位 |
| `CTX-RULE-001` | quality_rule | 禁止虚构引用、实验和新颖性结论 |
| `CTX-DELIVERY-001` | delivery_constraint | Agent Short Paper 与 ICLR 交付约束 |

每条上下文保存 SHA-256 截断摘要。模型产物中的 `provenance_map` 只能引用本次运行实际存在的 Context ID；未知 ID 会被移除。

## 4. 结构化产物

一次成功运行保存：

- 需求澄清摘要；
- 3 个中英文候选题目及各自聚焦点；
- 问题陈述与待验证研究空白；
- 可实验验证的研究问题；
- 待验证贡献假设；
- 方法定位、核心模块和明确非目标；
- 中英文关键词与下一阶段检索式；
- 新颖性风险和证据边界；
- 来源映射、执行轨迹、模型名称和提示词版本；
- 人工选择结果、审核意见与确认时间。

运行记录保存在 SQLite 表 `topic_framing_runs`。失败运行同样保留错误与执行轨迹，不覆盖历史记录。

## 5. 证据边界

当前阶段只允许以下两类状态：

- `context_supported`：可由用户输入、产品决策或交付规则直接支持；
- `pending_literature_verification`：涉及现有工作、研究空白、新颖性或效果，必须等待文献调研。

页面展示“可审计执行轨迹”，不保存或展示模型内部思维链。

## 6. API

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/v1/projects/{id}/topic-framing/runs` | 执行真实结构化选题拆解 |
| GET | `/api/v1/projects/{id}/topic-framing/runs/latest` | 读取最新运行与产物 |
| POST | `/api/v1/projects/{id}/topic-framing/confirm` | 选择候选题目并确认质量门 |

## 7. 下一步

下一条垂直链路是文献调研：把检索式交给文献检索工具，建立可去重的文献记录、引用元数据、主张—证据关系和研究空白验证报告。只有通过文献质量门后，PACM-SW 名称、相关工作定位和贡献声明才能逐步冻结。
