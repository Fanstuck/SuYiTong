# 14 开发环境与启动指南

## 1. 当前实现状态

截至 2026-08-16：

- JiuwenSwarm 官方标签：`JiuwenSwarm0.2.2`；
- 锁定提交：`d7c2ab2f299cd2c73201afb41ebb8b9c00cc7015`；
- 上游目录：`vendor/jiuwenswarm`；
- 二开分支：`suiyitong/0.1-lite`；
- Python：3.11 项目虚拟环境 `.venv`；
- JiuwenSwarm 数据：`runtime/.jiuwenswarm`；
- 速易通数据：`runtime/suyitong`；
- 模型方式：第三方 API；
- 交互渠道：仅本地 Web。
- 速易通垂直链路：选题、文献、方法、实验协议、真实检索、qrels 与 B0/B1 调度均已接通；
- 自动测试：12 项通过；
- 正式效果门：等待人工 qrels、可用生成模型端点与完整统计审计。

## 2. 首次部署

在项目根目录执行：

```powershell
.\scripts\setup.ps1
```

脚本会校验 v0.2.2 提交、应用轻量补丁、安装 Python 依赖、构建 Web 前端并初始化隔离运行目录。若前端已经构建且只需刷新 Python 环境：

```powershell
.\scripts\setup.ps1 -SkipFrontend
```

脚本可重复执行；检测到现有 `runtime/.jiuwenswarm/config/config.yaml` 时会保留整个工作区，不触发覆盖式初始化。

## 3. 配置第三方模型

参考 `config/jiuwenswarm.env.example`，修改本机文件：

```text
runtime/.jiuwenswarm/config/.env
```

必填项：

```dotenv
API_BASE=https://provider.example/v1
API_KEY=真实密钥
MODEL_NAME=模型 ID
MODEL_PROVIDER=OpenAI
SUYITONG_LITE_MODE=true
```

要求：默认模型必须支持多轮对话和 Function Calling。密钥文件位于 `runtime/`，已被根目录 `.gitignore` 排除。

## 4. 启动

终端一：

```powershell
.\scripts\start-jiuwenswarm.ps1
```

终端二：

```powershell
.\scripts\start-api.ps1
```

服务地址：

| 服务 | 地址 |
|---|---|
| JiuwenSwarm Web | `http://127.0.0.1:5173` |
| AgentServer | `127.0.0.1:18092` |
| WebChannel | `127.0.0.1:19000` |
| Gateway | `127.0.0.1:19001` |
| 速易通 API | `http://127.0.0.1:8000` |
| OpenAPI | `http://127.0.0.1:8000/docs` |

两个启动脚本以前台方式运行，按 `Ctrl+C` 停止。当前上游 Windows 默认实例的 `--stop default` 存在进程识别不稳定问题，因此开发期不使用后台常驻。

## 5. 验证

两个服务启动后：

```powershell
.\scripts\smoke-test.ps1
.\.venv\Scripts\python.exe -m pytest
```

已验证结果：

- JiuwenSwarm 四个端口可用；
- Web 返回 HTTP 200；
- 外部渠道 SDK 卸载后仍可启动；
- 速易通 `/health` 返回 `ok`；
- `/api/v1/system/capabilities` 返回第三方 API、无需本地模型、仅 Web；
- 项目可创建、查询并按顺序推进阶段；
- 不允许跳过中间质量门。

## 6. 当前 API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 服务健康检查 |
| GET | `/api/v1/system/capabilities` | 模型、渠道和 JiuwenSwarm 状态 |
| POST | `/api/v1/projects` | 创建科研项目 |
| GET | `/api/v1/projects` | 项目列表 |
| GET | `/api/v1/projects/{id}` | 项目详情 |
| POST | `/api/v1/projects/{id}/transitions` | 推进一个科研阶段 |
| POST | `/api/v1/projects/{id}/topic-framing/runs` | 运行选题拆解 |
| POST | `/api/v1/projects/{id}/literature-review/runs` | 运行文献调研 |
| POST | `/api/v1/projects/{id}/method-design/runs` | 运行方法设计 |
| POST | `/api/v1/projects/{id}/experiments/runs` | 生成实验协议 |
| POST | `/api/v1/projects/{id}/experiments/retrieval-runs` | 运行真实检索/消融矩阵 |
| POST | `/api/v1/projects/{id}/experiments/qrels` | 创建盲化人工 qrels |
| POST | `/api/v1/projects/{id}/experiments/generation-runs` | 运行 B0/B1 生成批量 |

## 7. 尚未完成

- 独立人工 qrels 标注与冻结；
- 可用生成模型端点下的 B0/B1 正式四任务三种子批量；
- B2/B3/Ours 生成系统同任务对比和人工写作质量评审；
- 统计重建、Claim Ledger、ICLR LaTeX/PDF 与最终交付包；
- HarmonyOS、移动端和端侧推理（不在当前比赛原型范围）。
