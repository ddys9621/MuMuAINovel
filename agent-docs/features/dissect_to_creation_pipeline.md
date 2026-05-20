# 拆书产物 → 全场景生成参考：注入设计

**状态**：R1-R9 + V3.2 全部落地 ✅
**作者**：Cascade（INTJ 风格架构）
**前置文档**：`@/agent-docs/features/book_dissect_v3_imitation_design.md`（一键仿写已实现，是本设计的标杆）

## 实施进度

| R | 状态 | 完成时间 | 备注 |
|---|---|---|---|
| R1 写作风格导入 | ✅ 已落地 | 2026-05-07 | 见下方 §A.1 |
| R2 ReferencePackInjector 抽取 | ✅ 已落地 | 2026-05-07 | 见下方 §A.2 |
| R3 故事大纲生成接入 | ✅ 已落地 | 2026-05-07 | 自动模式 + R8 显式模式；见 §A.3 |
| R4 章纲生成接入 | ✅ 已落地 | 2026-05-07 | 自动模式 + R8 显式模式；见 §A.3 |
| R5 章节正文/场景/重生成接入 | ✅ 已落地 | 2026-05-07 | 3 个子场景均含 R8 显式模式；见 §A.3 |
| R6 角色生成接入 | ✅ 已落地 | 2026-05-07 | 单条+向导批量+显式模式；见 §A.3 |
| R7 世界观生成接入 | ✅ 已落地 | 2026-05-07 | R8 显式模式已接入；灵感生成仍待 |
| R8 前端 ReferencePackSelector + 全入口接入 | ✅ 已落地 | 2026-05-07 | 通用组件 + 6/6 入口 + 30s TTL 缓存；见 §A.5 |
| R9 V2 视图 CTA 横条 | ✅ 已落地 | 2026-05-07 | 见下方 §A.4 |
| P2 性能优化 | ✅ 已落地 | 2026-05-07 | 前端挂载列表 TTL 缓存 + 后端 injector 分段耗时日志；见 §A.6 |
| **V3.2 synopsis 维度复活**（Story Bible 层全局引导） | ✅ 已落地 | 2026-05-07 | 见 §A.7 |
| **V3.2-A 拆书页跳转创建项目** + ?pack_task_id 预选 | ✅ 已落地 | 2026-05-07 | 见 §A.8 |
| **V3.2-B 灵感入口/向导无 projectId 选包** + 项目创建后自动挂载 | ✅ 已落地 | 2026-05-07 | 见 §A.8 |
| **V3.2-P2 entities/relations/events 模式三维度**（聚合统计） | ✅ 已落地 | 2026-05-07 | 见 §A.9 |

## 附录 A 实施备注

### A.1 R1 写作风格导入（已落地）

**改动范围**：仅前端 1 文件 `@frontend/src/pages/ReferencePackDetail.tsx`，零后端改动。

**实现要点**：

- `StyleTab` 签名增加 `sourceBookTitle: string`，由父组件传入 `pack.source_book_title`
- StyleTab 在「复制」按钮旁追加「导入到项目写作风格库」按钮（仅在 `data.prompt_content` 存在时显示）
- 新增 `ImportStyleDialog` 组件，含：
  - 通过 `projectApi.getProjects()` 拉取用户项目列表，自动选中第一个
  - 风格名输入框默认值 = `${style.name} · 拆书：${sourceBookTitle}`，用户可改
  - prompt_content 只读预览块（max-height 32 + scroll）
  - 提交调用 `writingStyleApi.createStyle({ project_id, name, description, prompt_content, style_type: 'custom' })`
  - 提交成功后切换为"成功视图"，提供「去查看 →」链接跳转 `/project/:projectId/writing-styles`
- 新增 `DialogShell` 通用弹窗壳（含标题栏 + X 关闭按钮 + 内容容器）

**验证结果**：

- TypeScript: `npx tsc -b --noEmit` → 0 错
- ESLint（针对改动文件）: `npx eslint src/pages/ReferencePackDetail.tsx --max-warnings 0` → 0 错 0 警告
- 后端单测：`pytest tests/ -k "book_dissect or imitation or writing_style"` → 349 PASS（R1 零后端改动，单测仅作回归基线）

**用户验证步骤**：

1. 完成一次拆书，等参考包 status=ready
2. 进入 `/reference-packs/:packId`，切到「文风范本」tab
3. 看到 prompt_content 下方有蓝色「导入到项目写作风格库」按钮
4. 点击 → 选目标项目 → 改名（可选）→ 确认导入
5. 跳转到 `/project/:projectId/writing-styles` 应能看到新条目
6. 在该项目编辑章节时，写作风格选择器中选这个条目，章节生成立刻应用拆书的笔法

### A.2 R2 ReferencePackInjector 抽取（已落地）

**改动范围**：

- 新增 `@backend/app/services/reference_pack_injector.py`（611 行）
- 重构 `@backend/app/services/imitation_service.py`（881 → 502 行，-379 行）
- 新增 `@backend/tests/test_reference_pack_injector.py`（19 单测）

**实现要点**：

- `ReferencePackInjector` 持有所有"参考资料组装"逻辑，无状态，可全局复用：
  - 强度档位 `StrengthProfile.for_strength(light/medium/deep)`（与原 imitation_service 行为字节级一致）
  - `_ResolvedPack` 数据载体（pack + 挂载关系合并快照）
  - 输入归一化：`resolve_packs / resolve_dimensions / resolve_strength`
  - 维度组装：`_format_methodology / _format_structure / _format_archetypes / _format_worldbuilding / _format_dimension_section / _format_corpus / _format_style_system_prompt`
  - 工具函数：`_safe_json / _truncate / _dedup_keep_order / _serialize_dimension / _serialize_style`
- 新增高层 API `build_reference_block(scene, dimensions?, strength?, pack_ids?, anchor_query?)`：
  - 一次返回 `ReferenceBlock` 数据类，含 `user_segment / system_segment / user_sections / used_packs / used_dimensions / used_strength / debug_meta`
  - `style` 维度走 `system_segment`；其余 5 维 + corpus 走 `user_segment`
  - 多 pack 自动并集合并；维度过滤考虑实际 `generated_dimensions`
- `imitation_service.py` 改造为薄上层：
  - `__init__` 中 `self.injector = ReferencePackInjector(ai_service)`
  - `resolve_packs / resolve_dimensions / resolve_strength` 改为代理调用
  - `assemble_prompt` 内部 `_format_*` 调用全部替换为 `self.injector._format_*`
  - 保留 `_ProjectContext / load_project_context / _format_project_state / _format_user_intent`（仿写专用）
  - 保留 `_STOPWORDS / _tokenize_keywords / _score_text`（V3.1.3 升级 BM25 前的 token 工具，仍被测试用）
- **对外 API 100% 向下兼容**：测试与下游代码继续 `from app.services.imitation_service import StrengthProfile, _ResolvedPack, _score_text, _tokenize_keywords` 不需改动（通过 `# noqa: F401  re-export`）

**验证结果**：

- TypeScript: `npx tsc -b --noEmit` → 0 错（前端无改动）
- R2 自身单测：`pytest tests/test_reference_pack_injector.py` → **19 PASS**
  - StrengthProfile 档位（3 测试）
  - resolve_dimensions（6 测试，覆盖显式/隐式/fallback/corpus 兜底）
  - resolve_strength（4 测试）
  - build_reference_block 集成（6 测试，含 DB seed）
- R5 仿写回归：`pytest tests/test_book_dissect_v3_r5_imitation.py` → **28 PASS**（零回归）
- 拆书+仿写+参考包全套：`pytest tests/ -k "book_dissect or imitation or reference_pack or writing_style"` → **349 PASS**
- 项目全套：`pytest tests/` → 402 passed / 1 failed（fail 是 `test_narrative_state_service.py:: test_build_generation_context_contains_new_sections`，已用 `git stash` 验证为 R1+R2 之前就存在的预存 bug，与本次改动无关）

**对 R3-R7 的接入约定**：

各场景在自己的生成 service 中按下面模式调用 injector：

```python
from app.services.reference_pack_injector import ReferencePackInjector

injector = ReferencePackInjector()  # 或全局单例
try:
    block = await injector.build_reference_block(
        db, project_id,
        scene="story_outline",  # / "chapter_outline" / "chapter_content" / ...
        anchor_query=user_question_or_outline_text,
    )
    # 把 block.user_segment 拼到自家 prompt 的 {mcp_references} 段
    # 把 block.system_segment（如果有）拼到 system prompt
except ValueError:
    # 项目未挂载参考包等情况，优雅降级，跳过参考资料注入
    pass
```

### A.3 R3-R7 各生成场景接入（已落地）

**统一改造模式**：所有生成场景在 prompt 构建处调用 `ReferencePackInjector.build_reference_block(...)`，把 `user_segment` 拼到 user prompt（与 MCP 资料并存或合并），`system_segment`（style 维度）拼到 style_content 或 system prompt。`ValueError` 兜底跳过（未挂载参考包），其他异常打 warning 不阻塞主流程。

**改动清单**：

| R | 场景 | 文件 / 行号 | anchor_query 选择 | 推荐维度 |
|---|---|---|---|---|
| R3 | 故事大纲（向导/灵感模式） | `@backend/app/api/wizard_stream.py:1386`（`mcp_references=combined_references`） | `theme + genre + description` | 默认全维度（按挂载 default_dimensions） |
| R4 | 章纲生成 | `@backend/app/services/plot_generation_service.py:1697`（MCP 段后追加拆书参考块） | `plot_line_content[:300] + story_premise[:300]` | structure / methodology / corpus |
| R5-S3 | 章节正文流式生成 | `@backend/app/api/chapters.py:1818`（MCP 收集后） | `chapter_title + outline[:300]` | style / methodology / corpus |
| R5-S4 | 场景生成（plot_card） | `@backend/app/services/scene_generation_service.py:187`（构 prompt 前） | `plot_card.title + plot_card.content[:300]` | style / corpus |
| R5-S5 | 章节重生成 | `@backend/app/api/chapters.py:3193`（构 project_context 后） + `@backend/app/services/chapter_regenerator.py:209`（_build_regeneration_prompt 内读取） | `chapter.title + outline.summary[:300]` | style / methodology / corpus |
| R6 | 单角色生成（同步+流式） | `@backend/app/api/characters.py:516, 985` | `request.role_type + user_input` | archetypes / corpus（fallback） |
| R6 扩展 | 向导批量角色生成 | `@backend/app/api/wizard_stream.py:734` | `theme + genre + 角色塑造` | archetypes / corpus（fallback） |
| R7 | 世界观生成（仅 update 模式） | `@backend/app/api/wizard_stream.py:252`（final_prompt 决定后） | `theme + genre` | worldbuilding（fallback） |

**不落地的**：

- **灵感生成**（`@backend/app/api/inspiration.py`）：用户在创建项目"前"用，无 project_id 自然无挂载关系。需要 R8 让用户在 UI 里显式选某个参考包，再传 `pack_ids` 走显式参数路径。
- **关系/组织/世界规则单条生成**：项目里没有独立的 LLM 单条生成端点（这些都是从 generate_character / world rules 服务批生成出来的），R6/R7 已覆盖。

**验证结果**：

- 后端单测：`pytest tests/ --ignore=tests/test_narrative_state_service.py` → **400 PASS**（R3-R7 改动零后端单测回归）
- 前端 TypeScript：`npx tsc -b --noEmit` → 0 错（仅 R9 涉及前端，其余纯后端）

**用户验证流程**（至少跑一遍 e2e）：

1. 完成一次拆书 → 进 `/reference-packs/:packId` → 把这个 pack 挂载到目标项目（用 `/project/:id/reference-packs` 已有页面，或 §A.1 的「导入到写作风格库」快捷入口）
2. 在该项目内：
   - **故事大纲**：进项目 → 大纲页 → 「AI 生成」→ 服务端会自动注入拆书参考（看后端日志 `📚 [R3-故事大纲]`）
   - **章纲**：项目 → 章节大纲页 → 生成章纲 → 服务端日志 `📚 [R4-章纲]`
   - **章节正文**：项目 → 章节页 → 编辑章 → 一键生成 → 前端 SSE 会显示「📚 已注入拆书参考包（...）」
   - **场景**：项目 → 章纲 → 关联剧情卡 → 生成场景 → 后端日志 `📚 [R5-场景生成]`
   - **章节重生成**：编辑章 → 分析章节后 → 「重生成」 → 后端日志 `📚 [R5-章节重生成]`
   - **角色**：项目 → 角色页 → 「AI 生成角色」 → 后端日志 `📚 [R6-角色]`
   - **世界观**：项目 → 世界观设定 → AI 生成 → 后端日志 `📚 [R7-世界观]`

### A.4 R9 V2 视图 CTA 横条（已落地）

**改动范围**：仅前端 1 文件 `@frontend/src/pages/BookDissectV2View.tsx`，零后端改动。

**实现要点**：

- 新增 `ApplyToCreationBar({ taskId })` 组件，仅在 `status === 'completed'` 时渲染（`@frontend/src/pages/BookDissectV2View.tsx:98`）
- 内部通过 `referencePackApi.list()` 拉用户所有参考包，本地匹配 `task_id === taskId` 找到本次拆书对应的 pack（避免新建后端端点）
- 4 种状态展示：
  - **loading**：「正在关联参考包…」灰色 spinner
  - **未找到 pack**（generating/failed）：黄色提示「参考包尚未生成或已失败」
  - **partial**（部分维度未生成）：完整 CTA + 「部分维度未生成」chip 提示
  - **ready**：完整 CTA（橙→绿渐变背景 + 标题《某书》+ 2 个按钮）
- 2 个 Link 按钮：
  - 【查看参考包】 → `/reference-packs/{packId}`（用户在那能看 5 维 + 用 R1 导入文风）
  - 【去项目挂载】（主按钮，brand 色）→ `/projects`（用户选项目后用现有的 `/project/:id/reference-packs` 页面挂载）

**验证结果**：

- TypeScript：`npx tsc -b --noEmit` → 0 错
- ESLint（针对改动文件）：`npx eslint src/pages/BookDissectV2View.tsx --max-warnings 0` → 0 错 0 警告

**故意不做的**（避免设计膨胀）：

- 不做内嵌「挂载到项目」对话框：现有 `/project/:id/reference-packs` 已是完整页面，跳过去更轻量。R8 完成后可整合在 `ReferencePackSelector` 组件里。
- 不做「去某项目仿写」直接跳：依赖用户先选项目，弹 dialog 选项目体验割裂；让用户经过 `/projects` → 进项目 → 章节页用现有「一键仿写」按钮，路径更自然。

### A.5 R8 前端 ReferencePackSelector（部分落地）

**改动范围**：

- 新增通用组件 `@frontend/src/components/ReferencePackSelector.tsx`（约 305 行）
- 故事大纲生成入口接入：`@frontend/src/pages/Outline.tsx`（4 处改动）+ `@frontend/src/services/api.ts`（payload 类型扩展）
- 后端 outline_generator 透传：`@backend/app/api/wizard_stream.py`（2 处：函数顶部读 R8 字段 + 注入处传给 build_reference_block）

**通用组件能力**（`ReferencePackSelector`）：

- 4 种状态：未启用（默认折叠 + "启用" 按钮）/ 加载中 / 项目未挂载任何包（提示+跳转链接）/ 启用就绪（完整面板）
- 启用就绪时含 3 段控件：
  - **参考包多选**（chip）：空选表示用项目所有挂载的 ready/partial pack
  - **维度多选**（chip）：根据所选 packs 的 `generated_dimensions` 并集动态启用/禁用；空选表示用挂载的 default_dimensions
  - **强度切换**（light/medium/deep）：每档配字符预算说明
- 接口：
  ```ts
  interface ReferencePackSelectorValue {
    enabled: boolean;
    packIds: string[];
    dimensions: ReferenceDimension[];
    strength: ReferenceStrength;
  }
  ```
- 默认值常量 `DEFAULT_SELECTOR_VALUE`（`enabled=false` + 空数组 + medium）

**已接入的入口（6/6 完整）**：

| 场景 | 前端入口 | 后端字段读取 |
|---|---|---|
| 故事大纲 | `@frontend/src/pages/Outline.tsx` OutlinesView GenModal | `wizard_stream.py` outline_generator `data.get("pack_ids"/...)` |
| 章纲生成 | `@frontend/src/pages/Outline.tsx` ChapterOutlinesView GenModal | `plot_generation_service.generate_chapter_outlines(..., pack_ids, dimensions, strength)` 形参 |
| 章节正文 + 章节重生成 | `@frontend/src/pages/Chapters.tsx` 共用 GenModal（`genTarget.isRegenerate` 区分） | S3：`generate_request.pack_ids` 等；S5：`regenerate_request.pack_ids` 等 |
| 场景生成 | `@frontend/src/components/SceneGenerator.tsx` 弹框顶部（所有卡片共用配置） | `scene_generation_service.generate_scene_direct(..., pack_ids, dimensions, strength)` 形参 |
| 角色生成（单条） | `@frontend/src/pages/Characters.tsx` AI 生成对话框 | `request.pack_ids` 等（`CharacterGenerateRequest` 字段） |
| 世界观重生成 | `@frontend/src/pages/WorldSetting.tsx` 重生成对话框 | `wizard_stream.py` worldview_generator `data.get("pack_ids"/...)` |

**Schema/Service 层级改动**（5 文件）：

- `@backend/app/schemas/chapter_outline.py` `ChapterOutlineGenerateRequest` 加 `pack_ids/dimensions/strength`
- `@backend/app/schemas/chapter.py` `ChapterGenerateRequest` 加同 3 字段
- `@backend/app/schemas/regeneration.py` `ChapterRegenerateRequest` 加同 3 字段
- `@backend/app/schemas/character.py` `CharacterGenerateRequest` 加同 3 字段
- `@backend/app/api/scene_generation.py` inline `DirectGenerateRequest` 加同 3 字段

**前端类型层**（2 文件）：

- `@frontend/src/types/index.ts` `ChapterGenerateRequest` / `GenerateCharacterRequest` / `ChapterOutlineGenerateRequest` 加 R8 字段
- `@frontend/src/services/api.ts` `generateCompleteOutlineStream` / `regenerateWorldBuildingStream` / `generateSceneStream` / `generateCharactersStream` 四个 inline payload 加 R8 字段

**扩展通用模板**（前端 + 后端）：

```tsx
// 前端：Modal/Dialog 内部加 state
const [refPack, setRefPack] = useState<ReferencePackSelectorValue>(DEFAULT_SELECTOR_VALUE);

// Modal body 加（建议放在 MCPSelector 之后）
{projectId && (
  <ReferencePackSelector
    projectId={projectId}
    value={refPack}
    onChange={setRefPack}
    hint="..."
    disabledTitle="使用拆书参考包作为对标"
  />
)}

// 提交时：仅 enabled 时透传
await someApi.generate({
  ...existingPayload,
  ...(refPack.enabled ? {
    pack_ids: refPack.packIds.length > 0 ? refPack.packIds : undefined,
    dimensions: refPack.dimensions.length > 0 ? refPack.dimensions : undefined,
    strength: refPack.strength,
  } : {}),
});
```

```python
# 后端 service：从 request/data 读取 R8 字段
explicit_pack_ids = data.get("pack_ids")
explicit_dimensions = data.get("dimensions")
explicit_strength = data.get("strength")

# 调用 injector 时传给 build_reference_block
block = await injector.build_reference_block(
    db, project_id,
    scene="<场景名>",
    pack_ids=explicit_pack_ids,
    dimensions=explicit_dimensions,
    strength=explicit_strength,
    anchor_query=...,
)
```

**验证结果**：

- TypeScript：`npx tsc -b --noEmit` → 0 错
- ESLint（所有 R8 改动文件）：`npx eslint src/components/ReferencePackSelector.tsx src/pages/Outline.tsx src/pages/Chapters.tsx src/pages/Characters.tsx src/pages/WorldSetting.tsx src/pages/ProjectReferencePacks.tsx src/components/SceneGenerator.tsx --max-warnings 0` → 0 错 0 警告
- 后端单测：`pytest tests/ -k "not test_build_generation_context_contains_new_sections"` → **402 PASS**（R8 后端零回归）

### A.6 P2 性能优化（已落地）

**P2-1 前端：挂载列表模块级 TTL 缓存**

**改动文件**：

- `@frontend/src/components/ReferencePackSelector.tsx`：增加模块级 Map 缓存（30 秒 TTL）
- `@frontend/src/pages/ProjectReferencePacks.tsx`：在 `attach / detach / updateAttachment` 成功后调用 `invalidateAttachmentsCache(projectId)` 主动清除

**动机**：

用户日常写作会反复打开多个生成对话框（故事大纲 → 章纲 → 章节正文 → 场景 → 角色 …），每次都去拉 `GET /projects/{id}/reference-packs` 太浪费。优化后同一项目下 30s 窗口内只请求一次，命中缓存直接填充 UI（无请求等待）。

**代码要点**：

```ts
const CACHE_TTL_MS = 30 * 1000;
const _attachmentsCache = new Map<string, { items: ProjectReferencePackItem[]; expireAt: number }>();

// 对外失效函数：挂载/卸载/更新后调用
export function invalidateAttachmentsCache(projectId?: string): void {
  if (projectId) _attachmentsCache.delete(projectId);
  else _attachmentsCache.clear();
}
```

**效果预估**：

- 用户一次写作流程（5+ 次对话框开合）的网络请求数从 5+ 降到 1
- 对话框打开延迟从 ~100-500ms（取决于网络）降到 0ms

**P2-2 后端：build_reference_block 分段耗时日志 + 超阈值告警**

**改动文件**：

- `@backend/app/services/reference_pack_injector.py`：`build_reference_block` 内部加 `time.perf_counter()` 分段测量

**能力**：

- 分段记录 4 个时间点：`packs`（加载参考包 DB）/ `dims_5`（5 维组装）/ `corpus`（BM25 检索）/ `total`
- 每次调用日志 INFO 级输出完整耗时：
  ```
  [Injector] scene=story_outline project=proj-1 strength=medium dims=['methodology','style','corpus']
  user=1800 sys=400 | timings packs=42ms dims=5ms corpus=380ms total=427ms
  ```
- `ms_total > 1500` 时升级 WARNING 告警，便于运维或后续用户反馈"生成卡顿"时快速定位瓶颈
- `debug_meta.timings_ms` 字典也带出去（前端可通过 `/imitate-chapter-preview` 等调试端点读取展示）

**典型性能画像**（本地基线，仅作参考，实际依 DB 大小和 corpus 大小）：

- `packs`: ~20-80ms（1-2 个挂载包 + 小型 SQLite）
- `dims_5`: ~0-5ms（纯 Python 字符串拼接）
- `corpus`: ~100-500ms（BM25 + 1-hop 检索，随 chapter_facts 条数增长）
- `total`: ~150-600ms

**未来瓶颈预警**：

- 若单个项目挂载了 10+ 参考包且 corpus 总量超大，`corpus` 阶段可能冲破 1500ms → 日志会自动告警
- 后续可考虑引入 per-task BM25 索引内存缓存（LRU）进一步优化，但当前性能充足不必做

### A.7 V3.2 synopsis 维度复活（Story Bible 层）

**动机**：

行业最佳实践（NovelAI Lorebook / Sudowrite Story Bible / 主流 Hierarchical RAG）普遍把"故事类型骨架"作为粗粒度全局引导（写作 RAG 第 1 层）。V2 时代的 SynopsisGenerator 因走"复刻原书"错路被 V3 废弃；V3.2 重新定义为"抽类型骨架"——`genre/premise/golden_finger/power_system/...` 的抽象描述，**禁止出现具体专有名词**。

**改动文件**：

- `@backend/app/services/book_dissect/synopsis_generator.py`（新建）：145 行；prompt 含「禁复刻具体名词」严格指令，输出 8 字段抽象骨架
- `@backend/app/services/book_dissect/prompts.py`：增加 `SYNOPSIS_PROMPT`（V3.2 复活版）
- `@backend/app/models/reference_pack.py`：增加 `synopsis_json` 列
- `@backend/app/migrations/auto_migrator.py`：`ensure_reference_pack_v32_columns` 自动迁移
- `@backend/app/services/book_dissect/extractor_v2.py`：并行 6 个 generator（5 核心 + 1 synopsis），synopsis 失败不拉低主状态
- `@backend/app/services/reference_pack_injector.py`：增加 `_format_synopsis` 方法，build_reference_block 把 synopsis 放最前（Hierarchical RAG 顺序），`StrengthProfile.synopsis_chars` 三档预算
- `@backend/app/schemas/reference_pack.py`：`ReferenceDimension` 增加 `synopsis`；`ReferencePackDetail` 增加可选 `synopsis` 字段
- `@frontend/src/types/reference_pack.ts`：同步类型扩展
- `@frontend/src/components/ReferencePackSelector.tsx` / `ImitationDialog.tsx` / `ProjectReferencePacks.tsx`：DIMENSION_LABELS 加 `synopsis: '故事梗概'`

**单测**：`@backend/tests/test_book_dissect_v3_generators.py` 加 6 个 SynopsisGenerator 测试；`@backend/tests/test_reference_pack_injector.py` 加 SynopsisFormat / SynopsisStrengthProfile 共 10 个测试。

### A.8 V3.2-A/B 入口产品逻辑闭环

**动机**：

灵感模式与项目创建向导历来在 **项目创建之前** 没有 selector 入口，用户必须先创建项目、再去项目设置挂载参考包。流程割裂。V3.2 闭环：

- **V3.2-A**：在拆书页（`@frontend/src/pages/BookDissect.tsx`）的「抽取完成」横条加「以本书作参考创建项目」按钮 → 跳转 `/projects?wizard=1&pack_task_id=xxx`，自动开 wizard 并预选本书 pack
- **V3.2-B**：让 `ReferencePackSelector` 支持 `projectId` 可选；项目未创建时拉用户全部 pack 列表（包装成虚拟 attachment）；用户选好的 pack 在项目创建第一步（world-building create）后由后端 `_auto_attach_packs_to_project` 自动挂载，让后续 characters/outline 步骤无缝继承

**改动文件**：

- `@frontend/src/components/ReferencePackSelector.tsx`：`projectId?: string`；增加用户级 TTL 缓存（key=`__user_packs__`）；`_wrapAsAttachment` 把 ReferencePackSummary 包成虚拟挂载项；空态文案根据有/无 projectId 区分
- `@frontend/src/components/inspiration/useProjectGeneration.ts`：hook 增加 `refPackSettings?: ReferencePackSelectorValue` 参数；`_r8Payload` 把 selector 值映射成 R8 字段；3 个 wizardStream API 都展开透传
- `@frontend/src/components/inspiration/InspirationDrawer.tsx`：高级设置面板加 `<ReferencePackSelector>`，`refPackSettings` 状态传给 hook，reset 时一并清空
- `@frontend/src/pages/ProjectList.tsx`：`WizardModal` 接 selector + `r8Payload`；监听 `?wizard=1&pack_task_id=xxx` URL 参数自动开 wizard，参数读完即清掉避免刷新重复弹出；`initialPackTaskId` prop 在 mount 时拉 `referencePackApi.list()` 找匹配 pack 自动预选
- `@frontend/src/services/api.ts`：`generateWorldBuildingStream` 加 R8 字段
- `@backend/app/api/wizard_stream.py`：新增 `_auto_attach_packs_to_project` helper（不复用 reference_pack.py 的 attach API，简化路径）；world-building create 模式 project 创建+设置默认风格之后、世界规则生成之前调用，失败容错不阻断主流程

**用户路径**：

| 路径 | 入口 | 选包时机 | 自动挂载 |
|---|---|---|---|
| 1 | 拆书页 → 「以本书作参考创建项目」 | 跳转后向导预选 | ✅ project 创建后 |
| 2 | 项目列表 → 「新建项目」 → 向导弹窗 | 表单底部 selector | ✅ project 创建后 |
| 3 | 项目列表 → 「灵感模式」抽屉 → 高级设置 | 抽屉内 selector | ✅ project 创建后 |

### A.9 V3.2-P2 entities/relations/events 模式三维度

**动机**：

V2 已 LLM 抽好 entities/relations/events 完整数据，但其原始数据**含具体专有名词**——直接喂给生成 LLM 会引导复刻原书人/物/事，违反 V3「学方法不学内容」哲学。V3.2-P2 增加 3 个**纯聚合统计**维度，输出**类型分布 / 命名风格信号 / 节奏模式**等抽象特征：

- `entities`：实体类型分布、角色档位分布、命名风格信号（长度分布/中文占比/首字多样性）、主线主角数
- `relations`：关系类别分布、高频关系类型（不含具体角色对）、平均跨章节强度
- `events`：事件类型分布、重要性分布、高重要性事件章节密度

**关键决策**：不调 LLM——纯 SQL 聚合 + Python `Counter`，秒级返回，零 token 消耗。

**改动文件**：

- `@backend/app/services/book_dissect/pattern_generators.py`（新建）：3 个聚合 generator + `build_pattern_dimensions` 一站式接口
- `@backend/app/models/reference_pack.py`：增加 `entities_json` / `relations_json` / `events_json` 三列
- `@backend/app/migrations/auto_migrator.py`：`ensure_reference_pack_v32_columns` 一并增加三列迁移
- `@backend/app/services/book_dissect/extractor_v2.py`：6 个 LLM generator 完成后调 `build_pattern_dimensions` 做纯统计聚合，加入 `generated_dims`
- `@backend/app/services/reference_pack_injector.py`：`StrengthProfile` 增加 `entities_chars/relations_chars/events_chars`；`_ResolvedPack` 加 3 个字段；`resolve_packs` 加载 3 列；`_format_entities/_format_relations/_format_events` 三个格式化方法（含「禁复刻」声明）；`build_reference_block` 在 synopsis 之后、5 手法之前装配；`_build_used_packs_meta` 同步识别新维度
- `@backend/app/schemas/reference_pack.py`：`ReferenceDimension` 加 3 个字面量；`ReferencePackDetail` 加可选字段
- `@backend/app/api/reference_pack.py`：`_detail_from` 转换；`_infer_default_dimensions` 与前端对齐：medium 加 `synopsis`，deep 加 `synopsis + entities + relations + events`
- `@backend/app/api/wizard_stream.py`：`_wizard_infer_default_dimensions` 同步对齐
- `@frontend/src/types/reference_pack.ts`：`ReferenceDimension` 加 3 项；`ReferencePackDetail` 加 3 字段
- `@frontend/src/components/ReferencePackSelector.tsx` / `ImitationDialog.tsx` / `pages/ProjectReferencePacks.tsx`：DIMENSION_LABELS 加 `entities/relations/events` → `实体分布/关系频谱/事件节奏`；`inferDefaultDimensions` 与后端对齐

**Hierarchical RAG 维度装配顺序**（最终）：

```
synopsis（Story Bible，最粗）
→ entities / relations / events（模式分布，粗+中）
→ methodology / structure / archetypes / worldbuilding（手法，中）
→ style（system_segment，单独）
→ corpus（BM25+1-hop，最细）
```

**单测**：

- `@backend/tests/test_book_dissect_pattern_generators.py`（新建，18 个测试）：覆盖 3 个 generator 的正常/空数据/异常路径，`build_pattern_dimensions` 一站式 + 异常容错
- `@backend/tests/test_reference_pack_injector.py`：追加 `TestPatternStrengthProfile / TestEntitiesFormat / TestRelationsFormat / TestEventsFormat / TestPatternResolveDimensions` 共 9 个测试
- 全后端跑 `441 passed`（除 1 pre-existing 失败 `test_build_generation_context_contains_new_sections`）

## 1. 目标

把拆书产物（V2/V3 共 10 个维度）系统地接入现有的 11 个 LLM 生成场景，让用户每次写作都能"自动参考想对标的那本书"，而不是只在「一键仿写」一个入口能用上。

价值路径：

```
用户上传想对标的书 → 拆书 → 自动产出 ReferencePack
   ↓ 挂载到自己的项目（一次性配置）
   ↓
全部生成场景（大纲 / 章纲 / 正文 / 角色 / 世界观 / 灵感 / ...）
   都自动按"配置好的维度+强度"注入参考资料
```

**不是要让所有生成都强制依赖拆书**，而是让"参考资料注入"成为统一的可选能力，用户哪个场景想参考、参考哪本、参考多深，全部可控。

## 2. 现状盘点

### 2.1 拆书产物的 10 个维度

| # | 维度 | 类型 | 来源表 | 描述 |
|---|---|---|---|---|
| A | `methodology` | "怎么写" | `reference_packs.methodology_json` | 金手指模式 / 钩子套路 / 打脸节奏 / 升级颗粒度 / 爽点密度 |
| B | `style` | "怎么写" | `reference_packs.style_json` | 文风 prompt_content + traits（笔调/句式/常用修辞） |
| C | `structure` | "怎么写" | `reference_packs.structure_json` | 开篇钩 / 中段冲突升级 / 结尾钩 + 原书案例引用 |
| D | `archetypes` | "怎么写" | `reference_packs.archetypes_json` | 主角/配角/反派的塑造模式 + 案例 |
| E | `worldbuilding` | "怎么写" | `reference_packs.worldbuilding_json` | 时代设计 / 地点层级 / 规则平衡的建模思路 + 案例 |
| F | `synopsis` | "是什么" | `book_dissect_tasks.result_json.synopsis` | 标题、premise、金手指、力量体系、终极目标、开篇钩子、题材、卖点、标签 |
| G | `corpus` | "语料" | `book_dissect_v2_chapter_facts` | 原书章节级事实清单（few-shot 示例） |
| H | `entities` | "是什么" | `book_dissect_v2_entities` + `dictionary` | 人物/地点/物品/组织/概念实体图 |
| I | `relations` | "是什么" | `book_dissect_v2_relations` | 人际/势力/隶属关系 |
| J | `events` | "是什么" | `book_dissect_v2_events` | 章节事件时间线 |

A-E 五维已经组装到 `ReferencePack`；F-J 五维存在拆书原始表里，可用 task_id 反查。

### 2.2 现有生成场景

| # | 场景 | 入口 service | Prompt 模板/服务 | 现状是否接入参考资料 |
|---|---|---|---|---|
| S1 | 故事大纲（synopsis 级） | `plot_generation_service.generate_complete_outline` | `plot_prompts.PlotPromptTemplates.COMPLETE_OUTLINE_GENERATION` | ❌ 仅有 `mcp_references`（搜索工具结果），未接拆书 |
| S2 | 章纲生成（chapter_outline） | `plot_generation_service.generate_chapter_outlines` | `plot_prompts.get_chapter_outline_prompt` | ❌ 同上 |
| S3 | 章节正文 | `prompt_service.get_chapter_generation_prompt` | 同名方法 | ⚠️ `style_content` 占位已有，但只挂"写作风格"表的条目，未对接拆书的 `style` 维度 |
| S4 | 场景生成 | `scene_generation_service.generate_scene_direct` | 复用 S3 同 prompt | 同 S3 |
| S5 | 章节重生成 | `chapter_regenerator` | 自有 prompt | ❌ 未接 |
| S6 | 角色生成 | `api/characters.py:generate_character{,_stream}` | 内联 prompt | ❌ 未接 |
| S7 | 关系/组织生成 | 同 S6 | 同 S6 | ❌ 未接 |
| S8 | 世界观/规则/地点 | `world_rules` / 项目设定 | 项目设定字段直填 | ❌ 未接 |
| S9 | 写作风格条目（writing_styles） | `api/writing_styles.py` | 用户手填 prompt_content | ❌ 未接（拆书已生成现成 style，但需手动复制） |
| S10 | 灵感生成 | `inspiration_service` | 自有 prompt | ❌ 未接 |
| S11 | **一键仿写** ✅ | `imitation_service.imitate_chapter` | 完整组装 | ✅ **已支持全维度，是本设计的标杆** |

### 2.3 已有的注入基础设施（标杆：imitation_service）

- 强度档位 `StrengthProfile.for_strength('light/medium/deep')`：每维 600/1500/3500 字符预算 + corpus top 1/2/3
- 包归一化 `_ResolvedPack`：聚合 `ReferencePack` + `ProjectReferencePack` 挂载关系
- 维度过滤 `resolve_dimensions(packs, explicit)`：用户显式 / 挂载默认 / DEFAULT_DIMENSION_FALLBACK 三级回退
- 维度组装 `_format_methodology / _format_style / _format_structure / _format_archetypes / _format_worldbuilding / _format_corpus`
- 拼装顺序：`[项目当前状态] + [作者本次创作意图] + [参考方法论] + [参考结构] + [参考角色塑造] + [参考世界观] + [参考语料] + [文风注入 system_prompt]`

## 3. 设计原则

1. **复用，不重写**。`imitation_service` 已经把"维度选择 + 强度组装 + prompt 拼装"做完了。把它的核心抽出来作为通用 `ReferencePackInjector`，其它场景直接调用。
2. **三类映射，明确职责**：
   - **"怎么写"**（A/B/C/D/E）→ 创作向场景（S1-S5/S10/S11）注入"笔法范本"段
   - **"是什么"**（F/H/I/J）→ 内容向场景（S6/S7/S8）注入"对标素材"段
   - **"语料"**（G）→ 任何场景都可作为 few-shot 兜底
3. **维度 ↔ 场景映射可配置**，不写死。每个生成场景在前端 UI 给用户暴露"勾选参考包+维度+强度"的入口，**默认值**遵循矩阵建议；用户可覆盖。
4. **零侵入扩展**。所有 prompt 模板已有的 `{mcp_references}` / `style_content` 占位符**继续保留**，新引入的拆书参考作为**新段**追加，不破坏现有 MCP 检索功能或写作风格选择。
5. **失败优雅降级**。任何拆书数据缺失 / pack 未就绪 / 维度未生成都不阻塞主流程，跳过该段并打日志即可。

## 4. 核心抽象：`ReferencePackInjector`

新增 `@/backend/app/services/reference_pack_injector.py`，把 `imitation_service` 中可复用的注入能力提取出来。

### 4.1 接口设计

```python
class ReferencePackInjector:
    """统一的拆书参考注入服务。所有生成场景共享。"""

    def __init__(self, ai_service: AIService | None = None):
        # ai_service 可选：仅 corpus 维度的 retriever 需要
        ...

    async def build_reference_block(
        self,
        db: AsyncSession,
        project_id: str,
        scene: str,                          # "story_outline" / "chapter_outline" / ... 用于 telemetry
        dimensions: list[str] | None = None, # 显式覆盖；None 则取项目挂载默认
        strength: str | None = None,         # 显式覆盖；None 则取项目挂载默认
        pack_ids: list[str] | None = None,   # 显式覆盖；None 则取项目挂载所有 ready pack
        anchor_query: str | None = None,     # 用于 corpus 检索的查询锚点（章纲/正文场景必传）
    ) -> ReferenceBlock:
        """组装可注入的参考资料块。返回值含：
        - user_segment: str  # 注入到 user prompt 的段（"参考方法论..." 等）
        - system_segment: str  # 注入到 system prompt 的段（仅 style 维度走 system）
        - debug_meta: dict  # 实际生效的 packs/dimensions/strength/字符数等，便于前端显示
        """
        ...

    async def get_attached_packs(
        self, db, project_id, only_ready: bool = True,
    ) -> list[ProjectReferencePackItem]:
        """前端弹板取已挂载列表用。"""
        ...
```

### 4.2 与 `imitation_service` 的关系

- `imitation_service` 保留为"专用上层"（带 SSE 流式 + 项目状态 + 用户意图三段），不变
- `imitation_service` 内部把 `_format_methodology` 等方法**改为委托** `ReferencePackInjector`，避免双源维护
- 其他生成场景调用 `ReferencePackInjector.build_reference_block(...)` 拿到 `ReferenceBlock`，自行决定塞到自家 prompt 哪段

## 5. 场景 × 维度 注入矩阵

### 5.1 默认配置矩阵

| # | 场景 | 必选维度（默认勾选） | 可选维度 | 注入到 prompt 哪段 | 默认强度 |
|---|---|---|---|---|---|
| S1 | 故事大纲 | `methodology` `structure` `worldbuilding` `archetypes` | `synopsis`(对标骨架) | 替换 `{mcp_references}` 占位（或并存） | medium |
| S2 | 章纲生成 | `structure` `methodology` | `corpus`(原书章节切分作对照) `archetypes` | 同 S1，复用 `{mcp_references}` 占位 | medium |
| S3 | 章节正文 | `style` `methodology` | `corpus`(few-shot) `structure` | `style` 进 system_prompt（同 imitation 思路）；`methodology+structure+corpus` 进 user prompt 新段 | medium |
| S4 | 场景生成 | `style` | `corpus` | 同 S3 | light |
| S5 | 章节重生成 | `style` | `corpus` `methodology` | 同 S3 | medium |
| S6 | 角色生成 | `archetypes` | `entities`(同类型样本) `relations` | 内联 prompt 加「角色塑造手法参考」段 | medium |
| S7 | 关系/组织生成 | `archetypes` | `entities` `relations` | 「人物关系图谱参考」段 | medium |
| S8 | 世界观/规则/地点 | `worldbuilding` | `entities`(location/org) | 「世界观建模参考」段 | medium |
| S9 | 写作风格条目导入 | — | — | **不走注入**：直接拷贝 `style.prompt_content` 到 `writing_styles` 表 | — |
| S10 | 灵感生成 | `methodology` `synopsis`(对标卖点) | `structure` | 「对标爆款骨架」段 | light |
| S11 | 一键仿写 | 用户勾选（默认全勾） | — | 已实现 | medium |

### 5.2 各场景具体改造点

#### S1 故事大纲生成

**现状** `@backend/app/services/plot_prompts.py:316-336`：
```
## 背景参考
- 初始想法：{description}
...

{mcp_references}

## 其他要求
{requirements}
```

**改造**：
- 在 `plot_generation_service.generate_complete_outline` 调用前组装参考块
- 把 `ReferenceBlock.user_segment` 注入到 `mcp_references` 之后（保留 MCP 不动）

```python
# plot_generation_service.generate_complete_outline 内部：
ref_block = await injector.build_reference_block(
    db, project_id, scene="story_outline",
    anchor_query=story_premise or theme,
)
# 把 ref_block.user_segment 拼接到 mcp_references 之后
mcp_text_combined = f"{mcp_text}\n\n{ref_block.user_segment}".strip()
```

模板无需改动，只是 `{mcp_references}` 占位的输入更丰富了。

#### S2 章纲生成

类似 S1，但 `anchor_query` 用当前章纲段的 `plot_line_content` 或 `chapter_outline.title`，使 corpus 检索更精准。

#### S3 / S4 / S5 章节正文 / 场景 / 重生成

**现状** `@backend/app/services/prompt_service.py:1078-1093`：
- `mcp_references` 塞到 `memory_text` 之后；
- `style_content` 通过 `WritingStyleManager.apply_style_to_prompt(base_prompt, style_content)` 追加到末尾。

**改造**：
- 取消"只能用 writing_styles 表条目"的耦合，改为：
  1. 优先用拆书 `style.prompt_content`（如果用户在 UI 选了拆书 style 维度）
  2. 否则用 writing_styles 表条目
  3. 都没有则跳过
- `methodology + structure + corpus` 通过 `ReferencePackInjector` 取出，塞到 `mcp_references` 段下面

```python
# scene_generation_service.generate_scene_direct 内部：
ref_block = await injector.build_reference_block(
    db, project_id, scene="scene_generation",
    anchor_query=plot_card.title + "\n" + (plot_card.content or ""),
)
# style_content 传 ref_block.system_segment（如果 style 维度被勾选）
# 否则传写作风格表的内容
style_for_prompt = ref_block.system_segment or writing_style_content
mcp_text_combined = f"{mcp_text}\n\n{ref_block.user_segment}".strip()
```

#### S6 角色生成

**现状**：`api/characters.py:generate_character` 内联 prompt，未支持参考。

**改造**：
- 调用 `ReferencePackInjector.build_reference_block(scene="character_generation", dimensions=["archetypes"])`
- 在角色生成 prompt 末尾追加 `### 角色塑造手法参考\n{archetypes_segment}`
- 可选：再注入 `entities` 维度同类型角色样本（如生成"反派"则取拆书原书"反派"实体的 traits/profile 作为对标）

#### S7 关系/组织生成

同 S6，注入 `archetypes`（特别是反派/势力部分）+ `relations`（原书人物势力图）。

#### S8 世界观 / 规则 / 地点

同 S6，注入 `worldbuilding`，特别是 `location_tree`（地点层级）和 `rule_clues`（规则平衡线索）。

#### S9 写作风格导入

**特例：不走注入，走"一键导入"**。

- 在参考包详情页 `style` tab 加按钮「导入到本项目写作风格库」
- 后端新增 `POST /api/projects/{project_id}/writing-styles/import-from-pack`：
  - 入参：`{ pack_id }`
  - 行为：从 `reference_packs.style_json` 取 `prompt_content` / `name` / `description` / `traits`，拷贝为新 `writing_styles` 条目
- ROI 最高（不需要改任何 prompt 拼装代码就能立刻生效）

#### S10 灵感生成

**改造**：
- 注入 `methodology`（爽点节奏）+ `synopsis`（金手指/题材/卖点对标）
- 灵感场景对话窗里给一行小字："本次灵感参考自《某某书》的方法论与卖点定位"

## 6. 前端 UI 升级点

### 6.1 全局：参考包选择器组件

新增 `@/frontend/src/components/ReferencePackSelector.tsx`，复用 `ImitationDialog` 已有的"包/维度/强度"三段交互模式。**所有生成场景共用**。

接口：
```ts
interface Props {
  projectId: string;
  scene: 'story_outline' | 'chapter_outline' | 'chapter_content' | 'scene' | 'character' | 'world' | 'inspiration';
  defaultDimensions?: ReferenceDimension[]; // 来自矩阵 5.1
  defaultStrength?: ReferenceStrength;
  value: { packIds: string[]; dimensions: ReferenceDimension[]; strength: ReferenceStrength } | null;
  onChange: (v: ...) => void;
  compact?: boolean; // true 时只显示 chip 摘要，点击展开抽屉
}
```

### 6.2 各生成入口的接入

- **S1 故事大纲对话框**：在「类型/视角/字数」选项后追加 `<ReferencePackSelector compact />`
- **S2 章纲生成对话框**：同上
- **S3-S5 章节正文/场景/重生成**：编辑器右侧"创作设置"面板加一行"参考自：xxx 书 · 文风+方法论"
- **S6-S8 角色/关系/世界观生成对话框**：同 S1
- **S10 灵感**：同 S1（compact 模式）
- **S9 写作风格库**：在 `WritingStyles` 页加「从参考包导入」按钮

### 6.3 V2 视图加 CTA

在 `BookDissectV2View` 顶部加「应用到创作」横条（呼应上次 UI 讨论的 A 选项），3 个按钮：
- 【查看参考包】跳 `/reference-packs/:packId`
- 【挂载到项目】弹挂载对话框（可一次选多个项目）
- 【去某项目仿写】跳目标项目章节页

## 7. 落地路线图

按 ROI 优先级排序，每个 R 是独立可交付增量。

| R | 工作 | 影响场景 | 预估工时 | 依赖 |
|---|---|---|---|---|
| **R1** | 写作风格导入（S9） | S3/S4/S5 立刻生效 | 30min | — |
| **R2** | 抽出 `ReferencePackInjector` 通用服务 | 所有 | 2-3h | — |
| **R3** | 接入 S1 故事大纲 | S1 | 1h | R2 |
| **R4** | 接入 S2 章纲生成 | S2 | 1h | R2 |
| **R5** | 接入 S3-S5 章节正文/场景/重生成 | S3/S4/S5 | 2-3h | R2 |
| **R6** | 接入 S6/S7 角色/关系生成 | S6/S7 | 2h | R2 |
| **R7** | 接入 S8/S10 世界观/灵感生成 | S8/S10 | 1.5h | R2 |
| **R8** | 前端 `ReferencePackSelector` 组件 + 各入口接入 | 全部前端 | 3-4h | R3-R7 |
| **R9** | V2 视图 CTA 横条 | 入口可见性 | 30min | — |

**最小可用路径** = R1 + R2 + R3 + R5 + R8（约 8-10h），其余作为后续增量。

### 7.1 验收标准

- 后端：
  - 每个 R 完成后跑全套 `pytest tests/`，**回归 0 失败**
  - `ReferencePackInjector` 自身单测覆盖：维度过滤 / 强度档位 / 缺失维度降级 / corpus 检索 4 类
  - 端到端：选 1 本拆书包 + 挂载到测试项目，跑 S1/S3/S6 各一次，确认 prompt 里能看到注入段
- 前端：
  - `ReferencePackSelector` 单测：勾选/取消/强度切换/默认值回填
  - TS 严格 0 错；ESLint 0 警告
- 文档：
  - `agent-docs/index.md` 登记本文档（已加）
  - 每个 R 完成后回填本文档"实现备注"段

## 8. 边界与不做的事

**做**：
- 已挂载到项目的参考包，自动作为各场景默认参考源
- 所有现有 prompt 模板**不破坏**，新参考通过新段追加
- corpus 检索复用 `imitation_corpus.ImitationCorpusRetriever`（BM25 + 1-hop relation 扩展，已实现）

**不做**（避免设计膨胀）：
- 不做"跨参考包智能融合"——多个 pack 的同维度并列拼接，不做摘要/裁剪
- 不做"实时拆书"——参考包必须是已就绪状态（status=ready/partial）
- 不做"参考包版本管理"——同一拆书任务的多次重抽直接覆盖（沿用 `_write_reference_pack` 现有 upsert 逻辑）
- 不动 MCP 检索 / 写作风格 / 智能记忆这三个已有体系——它们与本设计正交，并存即可

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| Prompt 长度爆炸（多维 + corpus + 已有 MCP + 记忆） | `StrengthProfile` 已有字符预算；新增统一打日志，超 8000 字提醒用户降强度 |
| 用户不知道哪个场景用了哪本书参考 | 每次生成在响应里带 `debug_meta`（packs/dimensions/strength），前端在生成结果旁显示一行小字"本次参考：xxx 书 · 文风+方法论 · medium" |
| 拆书包就绪时间不确定 | 仅显示 status=ready/partial 的包；generating 状态不暴露给生成场景选择 |
| `ReferencePackInjector` 抽取后 `imitation_service` 行为漂移 | 抽取后立刻跑 imitation 全套单测；保留 imitation_service 现有 API 100% 兼容 |

## 10. 附录：关键代码定位

- 标杆服务：`@backend/app/services/imitation_service.py`（特别是 `StrengthProfile`、`_format_*` 系列）
- 现有 prompt 模板入口：
  - `@backend/app/services/plot_prompts.py:316`（COMPLETE_OUTLINE_GENERATION）
  - `@backend/app/services/plot_prompts.py:783`（chapter_outline_prompt）
  - `@backend/app/services/prompt_service.py:982`（get_chapter_generation_prompt）
- 拆书产物模型：
  - `@backend/app/models/reference_pack.py`（5 维 JSON 字段）
  - `@backend/app/models/project_reference_pack.py`（多对多挂载）
  - `@backend/app/models/book_dissect_task.py`（chapter_facts/entities/relations/events 关联）
- corpus 检索：`@backend/app/services/imitation_corpus.py`（已实现 BM25 + 1-hop）
- 前端标杆组件：`@frontend/src/components/ImitationDialog.tsx`

---

**审阅指引**：

1. 先看 §5 矩阵：每个场景的维度是否合你预期？哪些不合理？
2. 再看 §7 路线图：R1-R9 是否合理？哪些 R 优先级你想调？
3. 最后看 §8 边界：是否有你想做但被我标"不做"的？或者反之？
