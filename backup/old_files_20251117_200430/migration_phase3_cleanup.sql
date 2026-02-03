-- ============================================
-- Phase 3: 清理冗余字段
-- 注意：仅在数据验证通过后执行！
-- ============================================

-- 备份提示
SELECT '⚠️  警告：执行前请确保已备份数据库！' AS warning;
SELECT '⚠️  建议先在测试环境验证迁移结果！' AS warning;

-- 1. 删除 plot_lines.outline_id（已迁移到 story_outline_id）
-- ALTER TABLE plot_lines DROP FOREIGN KEY fk_plot_line_outline;  -- 如果存在外键约束
-- ALTER TABLE plot_lines DROP COLUMN outline_id;

-- 2. 删除 chapter_outlines.plot_line_id（已迁移到关联表）
-- ALTER TABLE chapter_outlines DROP FOREIGN KEY fk_chapter_outline_plot_line;  -- 如果存在外键约束
-- ALTER TABLE chapter_outlines DROP COLUMN plot_line_id;

-- 3. 删除 plot_cards.outline_id（已迁移到关联表）
-- ALTER TABLE plot_cards DROP FOREIGN KEY fk_plot_card_outline;  -- 如果存在外键约束
-- ALTER TABLE plot_cards DROP COLUMN outline_id;

-- 4. 删除 plot_cards.chapter_outline_id（已迁移到关联表）
-- ALTER TABLE plot_cards DROP FOREIGN KEY fk_plot_card_chapter_outline;  -- 如果存在外键约束
-- ALTER TABLE plot_cards DROP COLUMN chapter_outline_id;

-- ============================================
-- 验证清理结果
-- ============================================
SELECT 
    TABLE_NAME,
    COLUMN_NAME,
    DATA_TYPE
FROM 
    INFORMATION_SCHEMA.COLUMNS
WHERE 
    TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME IN ('plot_lines', 'chapter_outlines', 'plot_cards')
ORDER BY 
    TABLE_NAME, ORDINAL_POSITION;

-- ============================================
-- 回滚脚本（如需恢复旧字段）
-- ============================================
/*
-- 恢复 plot_lines.outline_id
ALTER TABLE plot_lines 
ADD COLUMN outline_id VARCHAR(36) COMMENT '关联的大纲ID（已废弃）' AFTER project_id;

-- 恢复 chapter_outlines.plot_line_id
ALTER TABLE chapter_outlines 
ADD COLUMN plot_line_id VARCHAR(36) COMMENT '关联的剧情线ID（已废弃）' AFTER project_id;

-- 恢复 plot_cards.outline_id
ALTER TABLE plot_cards 
ADD COLUMN outline_id VARCHAR(36) COMMENT '关联的大纲ID（已废弃）' AFTER project_id;

-- 恢复 plot_cards.chapter_outline_id
ALTER TABLE plot_cards 
ADD COLUMN chapter_outline_id VARCHAR(36) COMMENT '关联的章纲ID（已废弃）' AFTER outline_id;
*/
