# Phase 0 — Cherry-pick 执行计划

> **目的**：从 commit `2ac6b50` 恢复被 revert 的拆书系统，作为 V4.4 实施基础  
> **风险评估**：commit 是 23 秒紧急误推回滚，**代码本身无质量问题**  
> **范围**：82 个新增文件 + ~30 个修改文件  
> **预估工时**：1-2 天（含 P0-1 到 P0-4）

---

## 1. 准备工作

### 1.1 操作环境

- **工作分支**：`feat/v4-phase0-restore`（从 master HEAD 开新分支）
- **避免污染 master**：所有操作在 feature 分支
- **回滚方案**：随时 `git checkout master` 即可恢复

### 1.2 不动 18abca5

commit `18abca5`（"本次修复同时覆盖首次创建与重抽卡"）改了 `wizard_stream.py` 和 `json_cleaner.py` 修一个具体 bug，**必须保留**。我们的 cherry-pick **不能覆盖这两个文件**的相关修复。

---

## 2. 文件分类与 cherry-pick 决策

### 2.1 ✅ 必须恢复（V4 基础设施，82 个新增文件中的 ~60 个）

#### A. 文档（7 个）

```
agent-docs/features/book_dissect_e2e_checklist.md
agent-docs/features/book_dissect_mvp.md
agent-docs/features/book_dissect_v2_design.md
agent-docs/features/book_dissect_v31_quality_optimization.md
agent-docs/features/book_dissect_v3_imitation_design.md
agent-docs/features/dissect_to_creation_pipeline.md
agent-docs/index.md
```

**操作**：`git checkout 2ac6b50 -- <files>` 全部恢复

#### B. 后端 Models（8 个）

```
backend/app/models/book_dissect_task.py
backend/app/models/book_dissect_chapter_fact.py
backend/app/models/book_dissect_dictionary.py
backend/app/models/book_dissect_entity.py
backend/app/models/book_dissect_event.py
backend/app/models/book_dissect_relation.py
backend/app/models/reference_pack.py
backend/app/models/project_reference_pack.py
```

**操作**：全部 cherry-pick

#### C. 后端 Schemas（3 个）

```
backend/app/schemas/book_dissect.py
backend/app/schemas/reference_pack.py
backend/app/schemas/imitation.py
```

**操作**：全部 cherry-pick

#### D. 后端 Services - book_dissect 拆书引擎（25 个）

```
backend/app/services/book_dissect/__init__.py
backend/app/services/book_dissect/alias_resolver.py
backend/app/services/book_dissect/archetype_generator.py
backend/app/services/book_dissect/chapter_fact_extractor.py
backend/app/services/book_dissect/chapter_splitter.py
backend/app/services/book_dissect/dictionary_classifier.py
backend/app/services/book_dissect/entity_aggregator.py
backend/app/services/book_dissect/entity_scanner.py
backend/app/services/book_dissect/event_timeline_builder.py
backend/app/services/book_dissect/extractor_v2.py
backend/app/services/book_dissect/fact_validator.py
backend/app/services/book_dissect/llm_chapter_splitter.py
backend/app/services/book_dissect/location_hierarchy.py
backend/app/services/book_dissect/long_context_extractor.py
backend/app/services/book_dissect/long_context_router.py
backend/app/services/book_dissect/methodology_generator.py
backend/app/services/book_dissect/pattern_generators.py
backend/app/services/book_dissect/prompts.py
backend/app/services/book_dissect/relation_aggregator.py
backend/app/services/book_dissect/structure_generator.py
backend/app/services/book_dissect/style_generator.py
backend/app/services/book_dissect/summary_builder.py
backend/app/services/book_dissect/synopsis_generator.py
backend/app/services/book_dissect/v2_types.py
backend/app/services/book_dissect/verification_pass.py
backend/app/services/book_dissect/worldbuilding_generator.py
```

**操作**：全部 cherry-pick（已被 cache 残留过证明对项目结构兼容）

#### E. 后端 Services - 注入与仿写（4 个）

```
backend/app/services/reference_pack_injector.py    # V4 要改造，先恢复 v3 版作为基础
backend/app/services/imitation_corpus.py           # BM25 检索基础设施，V4 复用
backend/app/services/imitation_service.py          # V4.4 P4 仿写按钮共存策略
backend/app/services/scene_generation_service.py   # 仅恢复 §A.3 增加的 R5-S4 注入调用
```

**操作**：恢复，注意 `scene_generation_service.py` 当前 master 可能已有版本 → 用 3-way merge

#### F. 后端 API（3 个）

```
backend/app/api/book_dissect.py       # 拆书 API（740 行）
backend/app/api/reference_pack.py     # 参考包管理 API（465 行）
backend/app/api/imitation.py          # 一键仿写 API（233 行）
```

**操作**：全部 cherry-pick

#### G. Migration（1 个）

```
backend/app/migrations/reference_pack_synopsis_migration.sql
```

#### H. 后端单测（V4.1 P0-6 要新增 BridgeDetector 单测，先把已有的恢复）

```
backend/tests/test_book_dissect_*.py  (16 个)
backend/tests/test_reference_pack_*.py
backend/tests/test_imitation_*.py
```

**操作**：全部 cherry-pick，保留作为回归基线

#### I. 前端核心页面（拆书 + 参考包管理）

```
frontend/src/pages/BookDissect.tsx         # 拆书页主入口
frontend/src/pages/BookDissectV2View.tsx   # V2 拆书结果视图
frontend/src/pages/ReferencePackDetail.tsx # 参考包详情页
frontend/src/pages/ProjectReferencePacks.tsx # 项目挂载页
frontend/src/services/bookDissectApi.ts
frontend/src/services/referencePackApi.ts
```

**操作**：cherry-pick（V4 用户必须能完整访问拆书流程）

---

### 2.2 ⚠️ 修改的文件 — 需手工 3-way merge

这些文件 commit 2ac6b50 改过、当前 master 也改过、且 18abca5 还动过。**不能直接 cherry-pick，要逐处对比**。

```
backend/app/api/chapters.py          # +91 行：注入器调用
backend/app/api/characters.py        # +66 行：注入器调用
backend/app/api/plot_cards.py        # +7 行：注入器调用
backend/app/api/plot_lines.py        # +7 行：注入器调用
backend/app/api/scene_generation.py  # +9 行：注入器调用
backend/app/api/wizard_stream.py     # ⚠️ 18abca5 修过，注意冲突
backend/app/api/chapter_outlines.py  # +6 行
backend/app/api/inspiration.py       # +113 行
backend/app/services/chapter_regenerator.py  # +21 行
backend/app/services/plot_generation_service.py  # +171 行
backend/app/services/prompt_service.py  # +14 行
backend/app/services/import_export_service.py  # +4 行
backend/app/main.py                   # +13 行：注册 API router
backend/app/database.py               # +8 行：注册新模型
backend/app/migrations/auto_migrator.py  # +102 行：新模型 migration
backend/app/schemas/regeneration.py   # +7 行
backend/app/schemas/chapter.py        # +4 行
backend/app/schemas/character.py      # +4 行
backend/app/schemas/chapter_outline.py  # +4 行
backend/app/schemas/plot_card.py      # +4 行
backend/app/schemas/plot_line.py      # +5 行
backend/app/schemas/project.py        # +5 行
backend/app/models/__init__.py        # +16 行：导出新 models
backend/app/models/project.py         # +3 行：关系字段
```

**处理策略**：

1. 用 `git show 2ac6b50 -- <file>` 看 commit 改了什么
2. 用 `git diff f71892a..HEAD -- <file>` 看 revert 后 master 改了什么（重点关注 18abca5）
3. 手工合并：
   - **保留** master 的修改（特别是 18abca5 的 bug 修复）
   - **追加** 2ac6b50 中拆书相关的新代码
   - **跳过** R8 用户选维度参数（pack_ids/dimensions/strength），V4 不要

---

### 2.3 ❌ 不恢复（K1 决策：用户不选维度）

这些前端组件是 v3 R8 让用户选维度的 UI，V4 不要：

```
frontend/src/components/ReferencePackSelector.tsx
```

**操作**：跳过，不 cherry-pick

```
frontend/src/pages/Outline.tsx       # 内含 ReferencePackSelector 调用
frontend/src/pages/Chapters.tsx      # 同上
frontend/src/pages/Characters.tsx    # 同上
frontend/src/pages/WorldSetting.tsx  # 同上
frontend/src/components/SceneGenerator.tsx  # 同上
frontend/src/services/api.ts         # 内含 pack_ids/dimensions/strength 字段
frontend/src/types/index.ts          # 同上
```

**处理策略**：这些文件**仅 cherry-pick 与拆书无关的修改**（如果有），**不 cherry-pick** R8 相关组件调用。Phase 1 重写挂载 UI 时再清理。

---

## 3. 执行步骤（按 P0-1 → P0-4 顺序）

### 步骤 1：创建工作分支

```powershell
git checkout master
git pull
git checkout -b feat/v4-phase0-restore
```

### 步骤 2：备份关键 master 文件（防误覆盖）

```powershell
# 备份 18abca5 修复的 2 个文件
git show HEAD:backend/app/api/wizard_stream.py > C:\Temp\wizard_stream_master.py
git show HEAD:backend/app/utils/json_cleaner.py > C:\Temp\json_cleaner_master.py
```

### 步骤 3：批量 checkout 必须恢复的文件（2.1 节）

```powershell
# 文档
git checkout 2ac6b50 -- agent-docs/features/book_dissect_e2e_checklist.md `
                         agent-docs/features/book_dissect_mvp.md `
                         agent-docs/features/book_dissect_v2_design.md `
                         agent-docs/features/book_dissect_v31_quality_optimization.md `
                         agent-docs/features/book_dissect_v3_imitation_design.md `
                         agent-docs/features/dissect_to_creation_pipeline.md `
                         agent-docs/index.md

# Models
git checkout 2ac6b50 -- backend/app/models/book_dissect_task.py `
                         backend/app/models/book_dissect_chapter_fact.py `
                         backend/app/models/book_dissect_dictionary.py `
                         backend/app/models/book_dissect_entity.py `
                         backend/app/models/book_dissect_event.py `
                         backend/app/models/book_dissect_relation.py `
                         backend/app/models/reference_pack.py `
                         backend/app/models/project_reference_pack.py

# Schemas
git checkout 2ac6b50 -- backend/app/schemas/book_dissect.py `
                         backend/app/schemas/reference_pack.py `
                         backend/app/schemas/imitation.py

# 拆书引擎服务
git checkout 2ac6b50 -- backend/app/services/book_dissect/

# 注入器与仿写
git checkout 2ac6b50 -- backend/app/services/reference_pack_injector.py `
                         backend/app/services/imitation_corpus.py `
                         backend/app/services/imitation_service.py

# API
git checkout 2ac6b50 -- backend/app/api/book_dissect.py `
                         backend/app/api/reference_pack.py `
                         backend/app/api/imitation.py

# Migration
git checkout 2ac6b50 -- backend/app/migrations/reference_pack_synopsis_migration.sql

# 单测
git checkout 2ac6b50 -- backend/tests/test_book_dissect_*.py `
                         backend/tests/test_reference_pack_*.py `
                         backend/tests/test_imitation_*.py
```

### 步骤 4：手工合并的文件（2.2 节）

逐个处理：

```powershell
# 对每个文件，先查看 2ac6b50 的版本
git show 2ac6b50:backend/app/api/chapters.py > C:\Temp\chapters_2ac6b50.py
# 对比当前 master 版本
diff C:\Temp\chapters_2ac6b50.py backend/app/api/chapters.py

# 手工合并（用编辑器或 P4Merge）
# 关键：只取拆书相关的新代码，跳过 R8 选维度参数
```

**重点关注 `wizard_stream.py`**：
- master 上有 18abca5 的修复（首次创建 + 重抽卡 + json_cleaner 增强）
- 2ac6b50 加了拆书 reference_pack 注入调用
- **必须保留 master 的修复**，**追加** 2ac6b50 的注入代码

### 步骤 5：models/__init__.py 手工添加新模型导出

```python
# 在 backend/app/models/__init__.py 追加
from app.models.book_dissect_task import BookDissectTask
from app.models.book_dissect_chapter_fact import BookDissectChapterFact
from app.models.book_dissect_dictionary import BookDissectDictionary
from app.models.book_dissect_entity import BookDissectEntity
from app.models.book_dissect_event import BookDissectEvent
from app.models.book_dissect_relation import BookDissectRelation
from app.models.reference_pack import ReferencePack
from app.models.project_reference_pack import ProjectReferencePack

# 在 __all__ 追加
__all__ = [
    # ... 现有
    "BookDissectTask",
    "BookDissectChapterFact",
    "BookDissectDictionary",
    "BookDissectEntity",
    "BookDissectEvent",
    "BookDissectRelation",
    "ReferencePack",
    "ProjectReferencePack",
]
```

### 步骤 6：main.py 注册新 router

```python
# backend/app/main.py 追加
from app.api import book_dissect, reference_pack, imitation

app.include_router(book_dissect.router, prefix="/api/book-dissect", tags=["book_dissect"])
app.include_router(reference_pack.router, prefix="/api/reference-packs", tags=["reference_pack"])
app.include_router(imitation.router, prefix="/api/imitation", tags=["imitation"])
```

### 步骤 7：数据库 migration

```powershell
cd backend
# 跑 auto_migrator 自动创建新表
python -c "from app.migrations.auto_migrator import run_migrations; run_migrations()"

# 跑特定 migration
python -c "import sqlite3; sqlite3.connect('data/mumuai.db').executescript(open('app/migrations/reference_pack_synopsis_migration.sql').read())"
```

### 步骤 8：验证编译

```powershell
cd backend
python -m pytest tests/ -k "book_dissect or reference_pack or imitation" -x --tb=short
```

**目标**：所有 cherry-pick 来的单测通过。

### 步骤 9：手工 smoke test

启动 backend + 前端，测试以下流程：

1. 进入拆书页 → 上传一本小说 → 跑完拆书 → 看到 7 维参考包
2. 进入项目 → 挂载参考包 → 看到挂载成功
3. 生成章节 → 后端日志看到 `📚 [R5-章节正文]` 类的注入提示

### 步骤 10：提交分支

```powershell
git add .
git commit -m "feat(book_dissect): Phase 0 P0-1 to P0-4: restore from 2ac6b50

- Cherry-pick 拆书引擎核心（book_dissect services + 8 models + 3 API）
- Cherry-pick ReferencePack 模型 + 关联表 + 注入器
- Cherry-pick 前端拆书页 + 参考包管理页
- 跳过 v3 R8 ReferencePackSelector 用户选维度组件（K1 决策）
- 跑通拆书全流程 smoke test

V4 设计书：agent-docs/features/book_dissect_v4_design.md"
```

---

## 4. P0-5/6/7/8 后续准备

cherry-pick 完成后，P0-5/6/7/8 是新代码（不是恢复），按 §10.1 / §11 设计书实现：

- P0-5：拆书 7 维度加 3 档预压缩字段（先动 ReferencePack 模型，再写生成器）
- P0-6：BridgeDetector（新文件 `services/book_dissect/bridge_detector.py`）
- P0-7：BridgePatternAggregator（新文件 `services/book_dissect/bridge_pattern_aggregator.py`）
- P0-8：CharacterArchiveBuilder（新文件 `services/book_dissect/character_archive_builder.py`）

---

## 5. 风险与回滚

### 5.1 主要风险

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| wizard_stream.py 手工合并冲突搞错 | 中 | 高 | step 2 备份，必要时回滚到备份 |
| auto_migrator 跑挂 | 中 | 中 | 先备份 `data/mumuai.db`，跑失败回滚 |
| 部分单测失败（依赖项不全） | 高 | 低 | 接受 5% 内的失败率，重点保证拆书+注入器单测全过 |
| ReferencePackInjector v3 API 与当前 master 不兼容 | 中 | 中 | Phase 1 重写为 V4 API，不依赖 v3 API 稳定 |

### 5.2 回滚

任意时刻：

```powershell
git checkout master           # 直接放弃所有 cherry-pick
git branch -D feat/v4-phase0-restore  # 删除工作分支
```

数据库回滚：

```powershell
Copy-Item backend\data\mumuai.db.backup backend\data\mumuai.db -Force
```

---

## 6. 完成标志

Phase 0 P0-1 到 P0-4 完成的标志：

- ✅ `feat/v4-phase0-restore` 分支创建并 push
- ✅ 后端单测：`pytest tests/ -k "book_dissect or reference_pack or imitation"` 全过
- ✅ Smoke test：上传一本小说能跑通完整拆书流程
- ✅ 项目能挂载参考包，章节生成日志能看到注入信息
- ✅ master 上 18abca5 的修复未被覆盖

完成后进入 P0-5 到 P0-8（新代码实现），最后整个 Phase 0 一起 PR。

---

**END OF Phase 0 Cherry-pick Plan**
