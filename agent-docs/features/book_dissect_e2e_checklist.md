# 拆书 MVP 端到端演练清单

本文档是 S6 阶段的**真机演练步骤**，需要本地启动 backend + frontend 联调。

## 前置条件

- [ ] 已配置 AI Provider（OpenAI / Anthropic / Custom 任一），并在 `Settings` 页面填入 API Key
- [ ] Python 依赖已装（`pip install -r requirements.txt`）
- [ ] 前端依赖已装（`npm install` 在 `frontend/`）
- [ ] 准备一份测试用的 txt 小说，文件大小 ≤ 10 MB，至少含 5 章

## 启动步骤

### 1. 启动 backend

```powershell
# 根目录启动（会自动加载 .env）
python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

健康检查：浏览器访问 `http://localhost:8000/docs` 应能看到 Swagger UI，并能在路径列表中找到 `/api/book-dissect/*` 系列。

### 2. 启动 frontend

```powershell
# 在 frontend/ 目录下
npm run dev
```

访问 `http://localhost:5173`，登录后从左侧栏进入「拆书参考」页面。

## 演练用例

### Case 1：基础闭环（happy path）

1. **上传**：上传一本 txt 小说，预期看到「✅ 上传成功，识别到 X 章」+ 章节预览列表
2. **启动抽取**：点「启动抽取」按钮，预期 stage 在 `queued → extract_project → extract_world → extract_characters → extract_outlines → extract_style → done` 之间渐进切换，progress 5→20→35→55→80→100
3. **查看结果**：抽取完成后，详情面板应渲染：
   - 项目骨架卡片（蓝色，左下绿色 selling_points/main_tropes pills）
   - 世界观卡片（紫色，4 字段）
   - 主要角色卡片（紫红色 grid）
   - 章纲样本卡片（橙色折叠列表）
   - 文风样本卡片（粉色，含一键复制按钮）
4. **一键创建项目**：点绿色「一键创建项目」按钮 → 确认弹窗 → toast 显示创建结果摘要 → 自动跳转到 `/project/<新 project_id>`
5. **进项目验证**：在新项目详情页看到：
   - 项目标题、世界观四字段已填
   - 角色页有 N 个角色（含别名拼接到背景）
   - 章纲页有 5 条章纲（含 key_events JSON 解析后渲染）
   - 写作设置页默认风格为「参考书文风」（自定义风格）

### Case 2：异常路径

1. **上传超大文件**：上传 > 10 MB 的文件，预期 413 + 前端 toast「文件过大」
2. **上传非 txt**：上传 .pdf，预期 400 + toast「仅支持 .txt/.md/.markdown」
3. **重复启动抽取**：在 running 状态再点「启动抽取」，预期按钮 disabled / 409 拦截
4. **未登录调 apply**：登出后直接 curl `POST /book-dissect/{id}/apply-to-wizard`，预期 401
5. **无 result 时尝试 apply**：刚上传未抽取的任务，预期按钮 disabled（hover 提示「需先完成抽取」）
6. **拆解任务进行中再删除**：删除 running 状态的任务，确认是否符合预期（删 DB + 删磁盘 + 卡片消失）

### Case 3：质量检查（人工评估）

抽取结果由 LLM 输出，质量需要人工评估：

- [ ] **项目骨架**：premise 是否准确概括全文？卖点 / 套路 / 金手指是否合理？
- [ ] **世界观**：四字段是否独立非冗余？rules 是否切实归纳了世界规则而非堆设定？
- [ ] **角色**：主角识别是否正确？关键配角是否覆盖？别名是否正确归属？
- [ ] **章纲**：章节号 / 标题是否对应原文？key_events 是否抓住章末钩子？
- [ ] **文风**：prompt_content 是否能让其他 AI 模仿原作风格？

如某项 LLM 输出质量明显有问题，需要回到 `prompts.py` 微调对应 prompt（注意只调 prompt，不要动业务逻辑）。

## 已知边界

- LLM 调用失败 / 超时：单阶段失败不阻断后续阶段，最终 task.error_message 记录最后一条失败原因；至少一项成功才标 completed。
- 章节切分误判：如果切分把序章 / 尾声拆成"第 0 章"，会被 ChapterOutline 跳过（`chapter_number > 0`）。
- 大型小说（200 万字+）：采样后的 prompt 输入仍可能超长，受 max_tokens 限制；目前 P3 / P4 设了较高 max_tokens（4096+）。
- 一键创建后的项目 `wizard_status=incomplete`，用户可继续走向导补全；也可以直接进入项目主页正常使用。

## 验收 checklist

- [ ] Case 1 全部步骤通过
- [ ] Case 2 至少 4/6 异常路径符合预期
- [ ] Case 3 LLM 输出质量人工评分 ≥ 中等可用
- [ ] backend logs 无未捕获 exception
- [ ] frontend 控制台无未捕获错误

完成后将本文件 `## 验收 checklist` 部分勾选，并把 `book_dissect_mvp.md` 中 S6.1 标 [x]。

## 故障排查

| 现象 | 可能原因 | 排查 |
|---|---|---|
| 上传 500 | 磁盘写入失败 / 数据库表未建 | 看 backend logs，确认 `data/book_dissect_uploads/` 可写 |
| 抽取卡在 queued | BackgroundTasks 没起来 / AI service 配置错 | 看 backend logs 是否有 `LLM 调用失败` |
| stage = extract_xxx 但 progress 不动 | LLM 长时间无响应 | 检查 AI Provider 配置 + 网络 |
| apply-to-wizard 500 | 字段映射异常 / 外键失败 | 看 logs；如频发，复查 result_json 结构 |
| 创建后项目角色 / 章纲为空 | LLM 抽取就是空 | 看 task.result_json 是否含对应字段 |
