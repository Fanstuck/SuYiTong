# 09 JiuwenSwarm 集成与二次开发边界

## 1. 集成目标

在不把业务系统深度绑定到 JiuwenSwarm 内部实现的前提下，复用其多 Agent 协作、Skill、工具调用、记忆、权限、自演进和人机中断能力。

## 2. 版本策略

- 比赛开发基线：JiuwenSwarm v0.2.2。
- 运行环境与源码必须锁定同一版本。
- `develop` 分支文档只用于了解后续能力，不作为 v0.2.2 配置事实源。
- 版本标签、配置 schema、命令和存储路径在技术验证阶段重新核对。
- 依赖锁文件、源码提交和前端构建产物进入项目 manifest。

当前官方 `develop` 文档中的自演进配置字段与较早配置说明存在变化，因此不得复制最新示例后假定 v0.2.2 可直接使用。

## 3. 能力映射

| 速易通需要的能力 | JiuwenSwarm 能力 | 速易通补充 |
|---|---|---|
| 多角色协作 | Swarm/Team、Leader 分解 | 固定研究角色、阶段输入输出契约 |
| 长流程 | Swarmflow、人机中断/状态 | 项目级状态机、审批与产物准入 |
| 工具调用 | 内置工具/MCP/Function Calling | 科研工具网关、schema、幂等与审计 |
| 记忆 | 内置/外接记忆、团队记忆 | Project Research Graph 与权威数据边界 |
| 上下文管理 | 上下文压缩和按需召回 | 角色感知 Context Pack、预算与溯源 |
| Skill | Skill 加载、检索、编排 | 科研 Skills、版本、回放集和质量标准 |
| 自演进 | 信号检测、evolutions 经验 | 评测、审批、发布和回滚治理 |
| 工具安全 | allow/ask/deny 权限 | 项目策略、高成本实验审批和沙箱 |
| 多模型 | 多供应商/OpenAI 兼容接口 | 模型注册、项目固定和公平评测 |
| 运行界面 | Web/TUI/Desktop | 独立速易通研究工作台 |

## 4. 推荐集成方式

采用“外部控制中台 + JiuwenSwarm 适配器 + Skills/Tools 扩展”的轻量 Fork 方式。

```text
SuYiTong Control Plane
        │ stable adapter contract
        ▼
JiuwenSwarm Adapter
        │
        ├── create/run/pause/resume team
        ├── provide Context Pack
        ├── register Skills and Tools
        ├── collect trace and artifacts
        └── receive evolution signals
```

### 4.1 尽量不修改 JiuwenSwarm 的内容

- 研究业务数据模型；
- Evidence/Claim/Experiment Ledger；
- 项目状态机；
- 质量门；
- LaTeX 和交付打包；
- 评测任务集和统计分析；
- 速易通 Web 工作台。

这些内容独立放在速易通仓库中。

### 4.2 可能需要 Fork 的内容

只有无法通过公开扩展接口完成时才修改：

- 阶段级运行事件与 trace 导出；
- 稳定的暂停、恢复和取消钩子；
- 人工审批请求转发；
- Agent/Tool 调用与项目 `run_id` 关联；
- 项目 Context Pack 注入；
- 结构化输出失败的拦截；
- 速易通工具权限策略桥接。

每项 Fork 修改必须：

- 独立提交；
- 说明上游缺口；
- 提供自动测试；
- 避免改变无关默认行为；
- 记录未来回归上游或适配新版本的方法。

## 5. 适配器契约

### 5.1 输入

```json
{
  "project_id": "prj_xxx",
  "stage_run_id": "sr_xxx",
  "agent_profile": "literature_scout",
  "task": {},
  "context_pack": {},
  "allowed_skills": [],
  "allowed_tools": [],
  "permission_policy": {},
  "model_profile": {},
  "output_schema": {}
}
```

### 5.2 输出

```json
{
  "agent_run_id": "ar_xxx",
  "status": "completed",
  "structured_output": {},
  "artifacts": [],
  "tool_calls": [],
  "usage": {},
  "warnings": [],
  "evolution_signals": [],
  "trace_path": "..."
}
```

JiuwenSwarm 的原始消息和事件可保留为 trace，但上层只依赖稳定契约。

## 6. Skill 接入策略

速易通 Skills 保存在自身仓库，构建或启动时同步到 JiuwenSwarm 工作空间，不直接手工维护两份副本。

同步时记录：

- Skill ID 和语义版本；
- 源文件哈希；
- 兼容的 JiuwenSwarm 版本；
- 允许角色；
- 依赖工具；
- 回放测试结果；
- 当前发布状态。

生产运行只加载已发布 Skill；草案和演进候选使用隔离测试空间。

## 7. 记忆接入策略

JiuwenSwarm 内置/团队记忆用于：

- 会话连续性；
- Agent 角色经验；
- 团队决策摘要；
- 工具与 Skill 使用经验。

速易通项目数据库用于：

- Evidence、Claim、Experiment、Decision；
- 项目和阶段状态；
- 审批与质量门；
- 产物和交付 manifest。

适配器在每次 Agent 调用前，从速易通数据构建只读 Context Pack；Agent 的建议先写候选产物，通过状态机后再进入权威数据。

## 8. 自演进接入策略

可接收的信号：

- 工具错误和超时；
- schema 验证失败；
- 用户纠正；
- Reviewer 重复问题；
- 质量门失败；
- 实验回放失败；
- 上下文召回遗漏。

发布链路：

```text
JiuwenSwarm evolution signal
  → SuYiTong Evolution Candidate
  → root-cause classification
  → candidate patch
  → regression replay
  → metric comparison
  → human approval
  → new Skill/Prompt version
```

首期 `auto_save` 或等价自动发布行为保持关闭。

## 9. 工具安全桥接

速易通为每个阶段计算工具策略，再映射为 JiuwenSwarm 权限配置：

- 文献发现阶段允许只读网络 API；
- 实验设计阶段禁止执行任意代码；
- 实验阶段允许写隔离目录，但不允许写项目源数据；
- 写作阶段只读 Experiment Ledger；
- 交付阶段允许编译和写 delivery 目录；
- 外部发布工具全阶段禁止。

权限决定和用户审批必须回写速易通审计记录。

## 10. 本地验证步骤

正式开发前先完成技术验证，不立即建设完整平台：

1. 安装 Python 3.11、Node.js 18+、Git。
2. 从官方 AtomGit 仓库锁定 `JiuwenSwarm0.2.2`。
3. 校验提交 `d7c2ab2f299cd2c73201afb41ebb8b9c00cc7015`。
4. 按官方源码方式执行 editable install。
5. 构建 `channels/web/frontend` 并验证 Web UI。
6. 配置一个支持工具调用的第三方 API 模型。
7. 运行单 Agent、Swarm/Team、Skill、工具和记忆 smoke test。
8. 验证暂停、恢复、权限审批和演进信号在 v0.2.2 的真实行为。
9. 记录与官方文档不一致项。
10. 再决定需要哪些 Fork 修改。

当前项目统一入口：

```powershell
.\scripts\setup.ps1
.\scripts\start-jiuwenswarm.ps1
```

源码验证：

```powershell
git clone --depth 1 --branch JiuwenSwarm0.2.2 https://atomgit.com/openJiuwen/jiuwenswarm.git vendor/jiuwenswarm
Set-Location vendor/jiuwenswarm
git rev-parse HEAD
# 预期：d7c2ab2f299cd2c73201afb41ebb8b9c00cc7015
```

上述源码部署、Python 依赖、前端构建和四端口启动验证已于 2026-08-14 完成。模型实际对话仍需配置真实第三方 API 后验证。

## 10.1 速易通轻量化边界

当前二开分支为 `suiyitong/0.1-lite`，通过 `SUYITONG_LITE_MODE=true` 强制只启用本地 Web 渠道。已从直接依赖和虚拟环境移除：

- `lark-oapi`；
- `python-telegram-bot`；
- `discord.py`；
- `dingtalk-stream`；
- `wecom-aibot-sdk`；
- `python-socks`。

上游渠道源码暂时保留但运行时不可达，用于降低以后合并安全更新的成本；只有当源码体积成为交付约束时，才执行物理删除。

## 11. 技术验证通过条件

- v0.2.2 能在目标本地环境稳定启动；
- 模型能够完成结构化工具调用；
- 至少两个 Agent 能交接结构化任务；
- Tool 调用能关联项目和运行 ID；
- 记忆能够写入、检索、隔离和禁用；
- 权限策略能阻止未授权写入或执行；
- 失败能够被捕获而不是无限等待；
- trace 可以导出并用于回放；
- 列出需要 Fork 的最小改动清单。
