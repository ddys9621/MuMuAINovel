-- ============================================================
-- V3.2 synopsis 复活：reference_packs 表加 synopsis_json 列
-- ============================================================
-- 背景：行业最佳实践（NovelAI / Sudowrite / Hierarchical RAG）普遍把"故事类型骨架"
--   作为粗粒度全局引导（Story Bible 层）。V2 时代有 SynopsisGenerator，V3 早期被
--   废弃（避免复刻原书内容）；V3.2 重写为"抽类型骨架"作为可选维度复活。
--
-- 兼容性：现有 ReferencePack 行 synopsis_json 默认 NULL，injector 会跳过 synopsis
--   维度（generated_dimensions 不含 'synopsis' 时不注入），完全不影响存量数据。
--
-- 应用方式：
--   sqlite3 path/to/your.db < reference_pack_synopsis_migration.sql
--   （SQLite 直接 ALTER TABLE ADD COLUMN，零停机）
-- ============================================================

ALTER TABLE reference_packs
ADD COLUMN synopsis_json TEXT NULL;

-- 列注释（SQLite 不支持 COMMENT，留作文档）：
-- Tab6 故事类型骨架 JSON：genre_tag / core_premise / golden_finger_concept /
-- power_system_overview / central_conflict / ultimate_goal / selling_points /
-- target_audience_signals。严示「抽类型骨架不复刻内容」。
