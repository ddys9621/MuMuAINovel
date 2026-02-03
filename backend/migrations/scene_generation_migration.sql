-- =====================================================
-- 场景级创作循环功能 - 数据库迁移脚本
-- 版本: 1.0
-- 日期: 2025-01-20
-- 说明: 添加章节生成会话表和剧情卡片场景生成字段
-- =====================================================

-- 1. 创建章节生成会话表
CREATE TABLE IF NOT EXISTS chapter_generation_sessions (
    id VARCHAR(36) PRIMARY KEY,
    chapter_outline_id VARCHAR(36) NOT NULL REFERENCES chapter_outlines(id) ON DELETE CASCADE,
    user_id VARCHAR(100) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    base_context JSONB,
    generated_scenes JSONB DEFAULT '[]'::jsonb,
    status VARCHAR(20) DEFAULT 'active',
    provider VARCHAR(50),
    model VARCHAR(100),
    enable_mcp VARCHAR(10) DEFAULT 'false',
    selected_plugins JSONB DEFAULT '[]'::jsonb,
    writing_style_id VARCHAR(36),
    target_word_count VARCHAR(20) DEFAULT '3000',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_cgs_chapter_outline_id ON chapter_generation_sessions(chapter_outline_id);
CREATE INDEX IF NOT EXISTS idx_cgs_user_id ON chapter_generation_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_cgs_status ON chapter_generation_sessions(status);

-- 添加注释
COMMENT ON TABLE chapter_generation_sessions IS '章节生成会话表 - 用于场景级创作循环';
COMMENT ON COLUMN chapter_generation_sessions.base_context IS '缓存的基础上下文（JSON格式）';
COMMENT ON COLUMN chapter_generation_sessions.generated_scenes IS '已生成的场景列表（JSON格式）';
COMMENT ON COLUMN chapter_generation_sessions.status IS '会话状态: active/completed/expired/cancelled';

-- 2. 为 plot_cards 表添加场景生成相关字段
-- 添加 generation_status 字段
ALTER TABLE plot_cards 
ADD COLUMN IF NOT EXISTS generation_status VARCHAR(20) DEFAULT 'pending';
COMMENT ON COLUMN plot_cards.generation_status IS '场景生成状态: pending/generating/completed/rejected';

-- 添加 generated_content 字段
ALTER TABLE plot_cards 
ADD COLUMN IF NOT EXISTS generated_content TEXT;
COMMENT ON COLUMN plot_cards.generated_content IS '该场景生成的正文内容';

-- 添加 word_count_target 字段
ALTER TABLE plot_cards 
ADD COLUMN IF NOT EXISTS word_count_target INTEGER DEFAULT 500;
COMMENT ON COLUMN plot_cards.word_count_target IS '目标字数';

-- 添加 word_count_actual 字段
ALTER TABLE plot_cards 
ADD COLUMN IF NOT EXISTS word_count_actual INTEGER DEFAULT 0;
COMMENT ON COLUMN plot_cards.word_count_actual IS '实际生成字数';

-- 添加 generation_order 字段
ALTER TABLE plot_cards 
ADD COLUMN IF NOT EXISTS generation_order INTEGER DEFAULT 0;
COMMENT ON COLUMN plot_cards.generation_order IS '在章节中的生成顺序';

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_plot_cards_generation_status ON plot_cards(generation_status);
CREATE INDEX IF NOT EXISTS idx_plot_cards_generation_order ON plot_cards(generation_order);

-- =====================================================
-- 迁移完成
-- =====================================================

