# Handoff — OilChem Agent 阶段交接

> 日期：2026-08-16
> 当前版本：1.3.1（develop 分支，已推送到 origin）
> 状态：一个大演进刚收尾，进入「调整完善」的规划期

---

## 一句话现状

**实验域闭环 + 用户认证都走通了，骨架完整；下一阶段的核心矛盾是「质量债」（测试少）和「真实硬件通信」（仍是 Mock）。**

## 刚完成的演进（本次阶段做了什么）

| 版本 | 内容 |
|---|---|
| 1.2.0 | 实验审核（待审核/通过/驳回 + 审核人选择） |
| 1.3.0 | 用户认证（JWT 登录 + RBAC + 前端登录页） |
| 1.3.1 | 清理（删死代码/修文档/消警告）+ 语义化版本管理细则 |

关键点：
- 1.3.0 的认证是 opencode 写的，我 review 后发现并修了 6 处 bug，**核心一个是「前端冷启动不跳登录页」**（`/auth/me` 原本在未登录时返回 401，导致前端永远进不了登录页）。已端到端验证。
- 版本管理从此规范：**功能走 MINOR，修复/清理走 PATCH**（之前 patch 位一直空转，已纠正，细则在 CLAUDE.md）。

## 能力全景

| 状态 | 模块 |
|---|---|
| ✅ 可用 | 对话（function calling + SSE）、Guardrails、DB（ORM）、Playwright 网页工具、实验域 M1-M7 闭环、用户认证（JWT + RBAC） |
| ⚠️ Mock | 硬件设备（MockDriver 模拟器，指令模拟下发，无真实通信） |
| 🔌 预留 | MCP 客户端（写了没接）、真实硬件通信（RS232/USB/GPIB） |

## 待办技术债（下一步的候选方向）

**质量类（见效快，推荐优先）**
- 测试严重不足：仅 2 个 smoke test + 7 个 auth test，无集成测试
- `datetime.utcnow()` 26 处弃用警告（换 timezone-aware 会牵扯 SQLite 存储格式，需单独规划，别随手改）

**架构类**
- 旧 Planner→Executor 链路未清理（与 function calling 主链路并存，代码重复）
- 全局单例泛滥（无 DI 容器）
- MemoryManager 纯内存（重启丢失，目前是设计如此）

**功能/工程类**
- 真实硬件通信（RS232/USB/GPIB）—— 用户最懂硬件，可能是重头戏
- MCP 接入
- 无 Docker、无限流/并发控制

## 下一步讨论的两个最可能方向

1. **补测试**（质量债最痛、见效最快、风险最低）
2. **真实硬件通信**（用户最有发言权、最能体现「中间层」价值，但工作量和硬件条件未知）

## 接手者必读

- **LLM 是 DeepSeek**（不是本地小模型），配置在 `backend/.env`（gitignore），别假设用 Ollama/qwen
- **硬件驱动仍是 Mock**，`send_hardware_command` 走 `DriverRegistry` 取 `MockDriver`，无真实通信
- **`init_db()` 三阶段**（Alembic → create_all → seed），别回退成早 return
- **Playwright 走后台线程**（`_SyncBrowserManager`），别改成 async（Windows greenlet 跨线程错误）
- **版本管理**：改代码涉及版本就按 CLAUDE.md 的 MAJOR/MINOR/PATCH 细则 bump，并同步 9 处版本号 + CHANGELOG + DEVELOPMENT_LOG
- **技能约定**：加功能先 brainstorming、声称完成先 verification-before-completion、排查 bug 用 systematic-debugging（详见 CLAUDE.md）

## 常用命令

```bash
# 后端
cd backend && .venv/Scripts/python.exe -m uvicorn app.main:app --port 8000 --reload
# 前端
cd frontend && npm run dev
# 测试
cd backend && .venv/Scripts/python.exe -m pytest tests/test_auth.py tests/test_bootstrap.py -v
```

---

详细逐模块状态见 `docs/PROJECT_STATUS.md`，完整变更见 `CHANGELOG.md` / `DEVELOPMENT_LOG.md`。
