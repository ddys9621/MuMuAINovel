-- 为剧情卡片表添加章纲关联字段
-- 执行时间：2025-11-17
-- 说明：支持剧情卡片与章纲的数据绑定，便于按章筛选和展示

-- 添加 chapter_outline_id 字段
ALTER TABLE plot_cards 
ADD COLUMN chapter_outline_id VARCHAR(36) NULL 
COMMENT '关联的章纲ID';

-- 添加外键约束
ALTER TABLE plot_cards 
ADD CONSTRAINT fk_plot_cards_chapter_outline 
FOREIGN KEY (chapter_outline_id) 
REFERENCES chapter_outlines (id) 
ON DELETE SET NULL;

-- 添加索引以提升查询性能
CREATE INDEX idx_plot_cards_chapter_outline_id 
ON plot_cards (chapter_outline_id);

-- 验证迁移结果
SELECT 
    COLUMN_NAME, 
    DATA_TYPE, 
    IS_NULLABLE, 
    COLUMN_COMMENT 
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_NAME = 'plot_cards' 
AND COLUMN_NAME = 'chapter_outline_id';
