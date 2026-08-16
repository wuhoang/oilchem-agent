# OilChem Agent 开发规范

## 代码变更收尾工作流

每次完成代码修改、功能新增或 Bug 修复后，**必须**执行以下操作：

### 1. 更新 CHANGELOG.md
- 在 `CHANGELOG.md` 中追加新版本条目
- 按 Added / Changed / Fixed 分类记录
- 包含日期和版本号

### 2. 统一版本号
检查并更新以下文件中的版本号，确保全部一致：
- `backend/pyproject.toml` → `version = "X.Y.Z"`
- `frontend/package.json` → `"version": "X.Y.Z"`
- `frontend/package-lock.json` → `"version": "X.Y.Z"`
- `backend/app/core/config.py` → `version: str = Field(default="X.Y.Z")`
- `docs/api.md` → `"version": "X.Y.Z"`

### 3. 更新技术文档
如涉及架构变化或新功能，同步更新：
- `docs/PROJECT_STATUS.md`（技术状态文档）
- `docs/architecture.md`（架构文档）
- `docs/api.md`（API 文档）

### 4. 验证
- 重启后端，访问 `/health` 确认返回正确版本号
- 运行核心测试用例
- 前端构建（如涉及前端变更）

---

## 版本号约定

遵循 [Semantic Versioning](https://semver.org/)：
- **MAJOR**：不兼容的 API 变更
- **MINOR**：向后兼容的功能新增
- **PATCH**：向后兼容的问题修复

### 当前版本：1.3.2

---

## 项目结构

参见 `docs/PROJECT_STATUS.md` 获取完整的项目技术架构说明。
