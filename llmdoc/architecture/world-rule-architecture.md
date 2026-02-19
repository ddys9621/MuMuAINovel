# 世界规则系统架构

## 1. 身份

- **是什么：** 小说世界观设定的结构化规则管理系统
- **目的：** 将世界观从项目简介中独立出来，以细粒度的规则条目管理力量体系、社会结构等设定

## 2. 核心组件

- `backend/app/models/world_rule.py` (WorldRule): 世界规则数据模型（类别、标题、内容、排序、启用状态）
- `backend/app/services/world_rule_service.py` (WorldRuleService): 规则 CRUD + 语义检索 + 规则合并
- `backend/app/api/world_rules.py`: 世界规则 API
- `frontend/src/pages/WorldRules.tsx`: 规则管理页面
- `frontend/src/pages/WorldSetting.tsx`: 世界观总体设定页面

## 3. 执行流程

- **1. 规则创建：** 用户按类别（力量体系、社会结构、地理环境等）创建世界规则条目
- **2. 规则增强：** `PlotGenerationService._enhance_world_rules()` 在生成时合并项目基础 world_rules 与规则明细
- **3. 语义检索：** WorldRuleService 支持按 query 语义检索最相关的规则条目
- **4. 上下文注入：** 合并后的世界规则文本注入到剧情生成和章节生成的 Prompt 中

## 4. 设计原理

- **结构化管理**：每条规则有独立的类别、标题和内容，而非一大段世界观文本
- **启用/禁用**：支持单条规则启用/禁用，灵活控制哪些规则参与生成
- **双层规则**：项目级 `world_rules` 字段（粗略描述）+ WorldRule 表（详细条目），生成时自动合并

