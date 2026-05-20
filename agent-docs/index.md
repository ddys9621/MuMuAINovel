# Agent 文档索引

本目录用于沉淀 MuMuAINovel 项目中具有跨文件约束、关键决策、可复用模式或长期有效价值的事实。
局部实现细节请就近写到代码注释或对应任务文档，不要写回这里。

## 全局关键事实

- **项目定位**：从 0 到 1 的 AI 网文创作工具（角色管理 / 剧情规划 / 章节生成 / 记忆系统 / MCP 插件）。
- **许可证**：本项目 GPL-3.0；引入第三方代码时需确认协议兼容性，AGPL 代码不可直接复制。
- **数据库迁移机制**：`@backend/app/migrations/auto_migrator.py` 在启动时执行幂等迁移；新建表通过 `Base.metadata.create_all` 自动创建，但需要在 `@backend/app/database.py` 顶部 `# noqa: F401` 导入新模型。
- **异步任务范本**：`@backend/app/models/analysis_task.py` 是任务跟踪的标准范式（`pending → running → completed/failed`，`progress 0-100`）。
- **路由注册位置**：所有 API router 在 `@backend/app/main.py:216-251` 集中注册，统一加 `/api` 前缀。
- **AI 服务统一入口**：`@backend/app/services/ai_service.py` 已封装 OpenAI / Anthropic / Custom 三类 provider 调用，新功能不要绕过。
- **章节级分析能力**：`@backend/app/services/plot_analyzer.py` 已实现单章实体提取与剧情结构分析，可复用为子能力。

## 任务文档

### features/

| 文档 | 状态 | 说明 |
|---|---|---|
| `features/book_dissect_mvp.md` | V1 完成（功能闭环） | 拆书 V1：采样式 5 段抽取 → 一键创建新项目。功能可用，但底层范式存在主角漏检 / 角色重复 / 跨章不一致等问题 |
| `features/book_dissect_e2e_checklist.md` | 进行中 | 拆书 V1 真机演练步骤、异常路径、LLM 质量评估清单 |
| `features/book_dissect_v2_design.md` | 抽数层有效 / 应用层被 V3 取代 | 拆书 V2 重构：逐章抽取 + 全书聚合的抽数能力（EntityScanner/Classifier/ChapterFactExtractor/Aggregators 等）仍是 V3 底层。但 V2 的 SynopsisGenerator + apply_to_wizard 走"复刻原书"错路，已被 V3 推翻 |
| `features/book_dissect_v3_imitation_design.md` | R5+R6 完成 | V3 仿写重构：把"复刻原书内容到新项目"改为"参考包(独立资料库)+多项目挂载+作者主导一键仿写"。R5 已实现一键仿写：`imitation_service` 拼装服务 + `POST /api/projects/{id}/imitate-chapter-{preview,stream}` 端点 + 章节编辑器内「一键仿写」弹板。R6 已彻底废弃 `apply_to_wizard` 错路：后端端点返 410 Gone 携带迁移指引、`apply_service.py` 与 `ApplyToWizardRequest/Response` schema 全部移除、前端「一键创建项目」按钮替换为引导卡片 |
| `features/book_dissect_v31_quality_optimization.md` | V3.1.1 / V3.1.2 / V3.1.3 / V3.1.4 / V3.1.5 全部完成 ✅ | V3.1 质量优化：联网检索后识别 4 项 P0 优化 + 1 项死代码清理。已分 5 期落地：聚合冲突 LLM 仲裁（Verification Pass）/ 长上下文兜底（≤128k 一次抽，含路由器 + 抽取器 + DB schema 扩展）/ 灵感语料 BM25 + 1-hop relation 扩展（手写 BM25 不引入依赖）/ 章节切分 LLM fallback / 清理 SynopsisGenerator。拆书 + 仿写相关 382 项单测全 PASS |
| `features/dissect_to_creation_pipeline.md` | **设计稿（待审阅）** | 把拆书 V3 的 10 维产物系统化注入到 11 个生成场景（故事大纲 / 章纲 / 章节正文 / 场景 / 重生成 / 角色 / 关系 / 世界观 / 写作风格 / 灵感 / 一键仿写）。核心抽象 `ReferencePackInjector` 复用 `imitation_service` 已有的强度档位 + 维度组装 + prompt 拼装。含场景×维度矩阵、各场景 prompt 改造点、前端组件 `ReferencePackSelector` 设计、R1-R9 落地路线图（建议最小可用路径 R1+R2+R3+R5+R8 ≈ 8-10h）|

## 编写约定

- 文档与代码同步更新，废弃功能的文档需要同步删除或标记。
- 新增文档必须登记到本索引，标注状态（**进行中** / **已完成** / **已废弃**）。
- 文档采用 Markdown，引用代码时使用 `@<绝对路径>:<行号>` 格式。
