# V4 Phase 1 P1-2：8 个挂载点接入手册

> **状态**：v4_compat.build_v4_dissect_segment 适配器已实现，8 个挂载点改造一行代码即可  
> **目标**：让现有的章节/角色/世界观/章纲/场景生成调用链路无缝接入 V4 PromptAssembler  
> **零破坏**：现有 prompt_service 不变，只在调用方加一行装配

---

## 1. 接入模式（统一）

```python
from app.services.reference_pack import build_v4_dissect_segment

# 在你原有 prompt 拼装代码 之前 加 1 行：
v4_segment = await build_v4_dissect_segment(
    db, project_id=project.id,
    scene="<场景名>",                    # 见下表
    model_name=request.model,            # 'deepseek-v3' 等
    # 各场景可选参数：
    chapter_outline_id=chapter_outline.id if chapter_outline else None,
    target_word_count=request.target_word_count or 3000,
    bridge_position=chapter_outline.bridge_position if chapter_outline else None,
    bridge_context={                     # K2 桥段上下文（仅 chapter_content 用）
        "title": bridge.title,
        "goal": bridge.goal,
        "showoff_point": bridge.showoff_point,
        "next_bridge_goal": next_bridge.goal if next_bridge else "",
    } if bridge else None,
)

# 把 v4_segment 拼到现有 mcp_references 字段
mcp_reference_materials = (
    (mcp_reference_materials or "") + ("\n\n" + v4_segment if v4_segment else "")
)

# 现有 prompt_service 调用 不动
prompt = prompt_service.get_chapter_generation_with_context_prompt(
    ...,
    mcp_references=mcp_reference_materials,  # ← V4 内容随 mcp_references 自然进 prompt
)
```

---

## 2. 8 个挂载点对应的 scene 值

| # | 业务场景 | 文件位置 | scene 值 | 关键参数 |
|---|---|---|---|---|
| 1 | 世界观生成 | `wizard_stream.py:worldview_generator` | `world_building` | - |
| 2 | 角色生成（向导）| `wizard_stream.py:characters_generator` | `character` | `role_type` |
| 2b | 角色生成（API）| `api/characters.py:generate_character` | `character` | `role_type` / `user_input` |
| 3 | 故事大纲 | `wizard_stream.py:outline_generator` | `story_outline` | `description`/`theme`/`genre` |
| 4 | 章纲批量 | `services/plot_generation_service.py` | `chapter_outline` | - |
| **5a** | **章节正文** | `api/chapters.py:1865,3035` + `services/scene_generation_service.py:231` | `chapter_content` | `chapter_outline_id` + `bridge_position` + `bridge_context` |
| 5b | 场景生成 | `services/scene_generation_service.py:253` | `scene_generation` | `plot_card_id` |
| 5c | 章节重生成 | `services/chapter_regenerator.py` | `chapter_regenerate` | + `modification_instructions` |

---

## 3. 改造示例：章节正文（最高频）

### 3.1 chapters.py:1865 改造前

```python
prompt = prompt_service.get_chapter_generation_with_context_prompt(
    title=project.title,
    ...,
    mcp_references=mcp_reference_materials,
)
```

### 3.2 改造后

```python
# 🆕 V4 装配拆书参考块
v4_seg = await build_v4_dissect_segment(
    db_session, project.id,
    scene="chapter_content",
    model_name=request.model or "deepseek-v3",
    chapter_outline_id=current_outline.id if current_outline else None,
    target_word_count=current_chapter.target_word_count or 3000,
    bridge_position=current_outline.bridge_position if current_outline else None,
    bridge_context=_make_bridge_context(current_outline, db_session) if current_outline and current_outline.bridge_id else None,
)
mcp_with_v4 = (mcp_reference_materials or "") + ("\n\n" + v4_seg if v4_seg else "")

prompt = prompt_service.get_chapter_generation_with_context_prompt(
    title=project.title,
    ...,
    mcp_references=mcp_with_v4,  # ← 改这一处
)


async def _make_bridge_context(co, db) -> dict | None:
    if not co.bridge_id:
        return None
    from app.models.plot_bridge import PlotBridge
    bridge = (await db.execute(select(PlotBridge).where(PlotBridge.id == co.bridge_id))).scalar_one_or_none()
    if not bridge:
        return None
    next_bridge = (await db.execute(
        select(PlotBridge)
        .where(PlotBridge.project_id == co.project_id)
        .where(PlotBridge.bridge_number == bridge.bridge_number + 1)
    )).scalar_one_or_none()
    return {
        "title": bridge.title,
        "goal": bridge.goal,
        "showoff_point": bridge.showoff_point,
        "next_bridge_goal": next_bridge.goal if next_bridge else "（下一桥段未设定）",
    }
```

---

## 4. 各挂载点接入要点

### 4.1 世界观生成（wizard_stream.py）

```python
v4_seg = await build_v4_dissect_segment(
    db, project_id=project.id,
    scene="world_building",
    model_name=model,
)
# 拼到 final_prompt 末尾
final_prompt = f"{base_prompt}\n\n{v4_seg}" if v4_seg else base_prompt
```

### 4.2 角色生成（characters.py / wizard_stream.py）

```python
v4_seg = await build_v4_dissect_segment(
    db, project_id=project.id,
    scene="character",
    model_name=model,
)
```

### 4.3 故事大纲

```python
v4_seg = await build_v4_dissect_segment(
    db, project_id=project.id,
    scene="story_outline",
    model_name=model,
)
```

### 4.4 章纲批量

```python
v4_seg = await build_v4_dissect_segment(
    db, project_id=project.id,
    scene="chapter_outline",
    model_name=model,
)
```

### 4.5 场景生成

```python
v4_seg = await build_v4_dissect_segment(
    db, project_id=project.id,
    scene="scene_generation",
    model_name=model,
    extra={"plot_card_id": plot_card.id},
)
```

### 4.6 章节重生成

```python
v4_seg = await build_v4_dissect_segment(
    db, project_id=project.id,
    scene="chapter_regenerate",
    model_name=model,
    chapter_outline_id=chapter_outline.id,
)
```

---

## 5. 验证方式

### 5.1 单元层（已有）

```bash
cd backend
python -m pytest tests/test_blueprint_safety.py -v
```

### 5.2 E2E（手动）

```bash
cd backend
python -m tests.manual.test_e2e_assemble
# 看 dissect_methodology / dissect_structure 等是否被填充
```

### 5.3 集成层（推荐 Phase 4 P3 Eval Harness）

跑 30 个 Gold Test Case，对比改造前后的章节质量分。

---

## 6. 注意事项

1. **降级**：`build_v4_dissect_segment` 永不抛异常。项目没挂载参考包 / 场景未注册 / DB 错 → 返回 `""`
2. **零破坏**：现有 `prompt_service.get_chapter_generation_*` 不动，旧 prompt 模板保持。V4 内容**仅追加到 `mcp_references` 字段**
3. **Cache 友好**（V4.4 K5 P1 完成后）：建议把 V4 适配器的输出**单独发给 AI**，让 prompt caching 命中静态前缀
4. **bridge_context 是关键**：传给 build_v4_dissect_segment 才能拿到 K2 桥段位置约束。无桥段的章节 → 跳过即可

---

## 7. Phase 1 P1-2 完成清单

按以下顺序改造（每个 1-2 小时）：

- [ ] api/chapters.py 1865 行（章节生成主入口）
- [ ] api/chapters.py 3035 行（章节生成另一处）
- [ ] services/scene_generation_service.py 231/253 行
- [ ] services/chapter_regenerator.py（重生成）
- [ ] services/plot_generation_service.py（章纲批量）
- [ ] wizard_stream.py worldview_generator（世界观）
- [ ] wizard_stream.py characters_generator + api/characters.py（角色）
- [ ] wizard_stream.py outline_generator（故事大纲）

每改完一个，跑 `python -m tests.manual.test_e2e_assemble` 验证。

---

**END**
