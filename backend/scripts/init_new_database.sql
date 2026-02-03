-- ============================================
-- 全新数据库初始化脚本 (PostgreSQL)
-- 用于从零开始创建新的数据库结构
-- ============================================

-- 删除旧表（如果存在）
DROP TABLE IF EXISTS plot_card_chapter_outline_links CASCADE;
DROP TABLE IF EXISTS plot_card_plot_line_links CASCADE;
DROP TABLE IF EXISTS chapter_outline_plot_line_links CASCADE;
DROP TABLE IF EXISTS story_outlines CASCADE;

-- ============================================
-- 1. 创建 story_outlines 表（故事大纲）
-- ============================================
CREATE TABLE story_outlines (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL,
    title VARCHAR(200) NOT NULL,
    content TEXT,
    structure TEXT,
    version INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    order_index INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_story_outline_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX idx_story_outlines_project_id ON story_outlines(project_id);
CREATE INDEX idx_story_outlines_project_active ON story_outlines(project_id, is_active);

COMMENT ON TABLE story_outlines IS '故事大纲表 - 高层故事结构';
COMMENT ON COLUMN story_outlines.title IS '大纲标题';
COMMENT ON COLUMN story_outlines.content IS '大纲内容';
COMMENT ON COLUMN story_outlines.structure IS '结构化大纲数据(JSON)';
COMMENT ON COLUMN story_outlines.version IS '版本号';
COMMENT ON COLUMN story_outlines.is_active IS '是否为当前激活版本';

-- ============================================
-- 2. 创建 chapter_outline_plot_line_links 表
-- ============================================
CREATE TABLE chapter_outline_plot_line_links (
    id VARCHAR(36) PRIMARY KEY,
    chapter_outline_id VARCHAR(36) NOT NULL,
    plot_line_id VARCHAR(36) NOT NULL,
    role VARCHAR(50) DEFAULT 'main',
    order_index INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_copll_chapter_outline FOREIGN KEY (chapter_outline_id) REFERENCES chapter_outlines(id) ON DELETE CASCADE,
    CONSTRAINT fk_copll_plot_line FOREIGN KEY (plot_line_id) REFERENCES plot_lines(id) ON DELETE CASCADE,
    CONSTRAINT uk_chapter_plot UNIQUE (chapter_outline_id, plot_line_id)
);

CREATE INDEX idx_copll_chapter_outline ON chapter_outline_plot_line_links(chapter_outline_id);
CREATE INDEX idx_copll_plot_line ON chapter_outline_plot_line_links(plot_line_id);

COMMENT ON TABLE chapter_outline_plot_line_links IS '章纲-剧情线多对多关联表';
COMMENT ON COLUMN chapter_outline_plot_line_links.role IS '角色类型: main(主线)/sub(支线)/character(角色线)';

-- ============================================
-- 3. 创建 plot_card_plot_line_links 表
-- ============================================
CREATE TABLE plot_card_plot_line_links (
    id VARCHAR(36) PRIMARY KEY,
    plot_card_id VARCHAR(36) NOT NULL,
    plot_line_id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_pcpll_plot_card FOREIGN KEY (plot_card_id) REFERENCES plot_cards(id) ON DELETE CASCADE,
    CONSTRAINT fk_pcpll_plot_line FOREIGN KEY (plot_line_id) REFERENCES plot_lines(id) ON DELETE CASCADE,
    CONSTRAINT uk_card_plot UNIQUE (plot_card_id, plot_line_id)
);

CREATE INDEX idx_pcpll_plot_card ON plot_card_plot_line_links(plot_card_id);
CREATE INDEX idx_pcpll_plot_line ON plot_card_plot_line_links(plot_line_id);

COMMENT ON TABLE plot_card_plot_line_links IS '素材-剧情线多对多关联表';

-- ============================================
-- 4. 创建 plot_card_chapter_outline_links 表
-- ============================================
CREATE TABLE plot_card_chapter_outline_links (
    id VARCHAR(36) PRIMARY KEY,
    plot_card_id VARCHAR(36) NOT NULL,
    chapter_outline_id VARCHAR(36) NOT NULL,
    usage_type VARCHAR(50) DEFAULT 'reference',
    usage_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_pccol_plot_card FOREIGN KEY (plot_card_id) REFERENCES plot_cards(id) ON DELETE CASCADE,
    CONSTRAINT fk_pccol_chapter_outline FOREIGN KEY (chapter_outline_id) REFERENCES chapter_outlines(id) ON DELETE CASCADE,
    CONSTRAINT uk_card_chapter UNIQUE (plot_card_id, chapter_outline_id)
);

CREATE INDEX idx_pccol_plot_card ON plot_card_chapter_outline_links(plot_card_id);
CREATE INDEX idx_pccol_chapter_outline ON plot_card_chapter_outline_links(chapter_outline_id);

COMMENT ON TABLE plot_card_chapter_outline_links IS '素材-章纲多对多关联表';
COMMENT ON COLUMN plot_card_chapter_outline_links.usage_type IS '使用方式: reference(参考)/used(已使用)/planned(计划使用)';

-- ============================================
-- 5. 修改现有表
-- ============================================

-- 5.1 修改 plot_lines 表
DO $$ 
BEGIN
    -- 删除旧字段 outline_id（如果存在）
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'plot_lines' AND column_name = 'outline_id'
    ) THEN
        ALTER TABLE plot_lines DROP COLUMN outline_id;
    END IF;
    
    -- 删除旧字段 plot_cards（如果存在）
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'plot_lines' AND column_name = 'plot_cards'
    ) THEN
        ALTER TABLE plot_lines DROP COLUMN plot_cards;
    END IF;
    
    -- 添加新字段 story_outline_id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'plot_lines' AND column_name = 'story_outline_id'
    ) THEN
        ALTER TABLE plot_lines ADD COLUMN story_outline_id VARCHAR(36);
        ALTER TABLE plot_lines ADD CONSTRAINT fk_plot_line_story_outline 
            FOREIGN KEY (story_outline_id) REFERENCES story_outlines(id) ON DELETE CASCADE;
        CREATE INDEX idx_plot_lines_story_outline ON plot_lines(story_outline_id);
        COMMENT ON COLUMN plot_lines.story_outline_id IS '关联的故事大纲ID';
    END IF;
END $$;

-- 5.2 修改 chapter_outlines 表
DO $$ 
BEGIN
    -- 删除旧字段 plot_line_id（如果存在）
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'chapter_outlines' AND column_name = 'plot_line_id'
    ) THEN
        ALTER TABLE chapter_outlines DROP COLUMN plot_line_id;
    END IF;
END $$;

-- 5.3 修改 plot_cards 表
DO $$ 
BEGIN
    -- 删除旧字段 outline_id（如果存在）
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'plot_cards' AND column_name = 'outline_id'
    ) THEN
        ALTER TABLE plot_cards DROP COLUMN outline_id;
    END IF;
    
    -- 删除旧字段 chapter_outline_id（如果存在）
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'plot_cards' AND column_name = 'chapter_outline_id'
    ) THEN
        ALTER TABLE plot_cards DROP COLUMN chapter_outline_id;
    END IF;
END $$;

-- 5.4 修改 chapters 表（添加版本管理）
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'chapters' AND column_name = 'version'
    ) THEN
        ALTER TABLE chapters ADD COLUMN version INTEGER DEFAULT 1;
        COMMENT ON COLUMN chapters.version IS '版本号';
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'chapters' AND column_name = 'parent_version_id'
    ) THEN
        ALTER TABLE chapters ADD COLUMN parent_version_id VARCHAR(36);
        ALTER TABLE chapters ADD CONSTRAINT fk_chapter_parent_version 
            FOREIGN KEY (parent_version_id) REFERENCES chapters(id) ON DELETE SET NULL;
        COMMENT ON COLUMN chapters.parent_version_id IS '父版本ID';
    END IF;
END $$;

-- 5.5 修改 plot_analysis 表（添加引用字段）
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'plot_analysis' AND column_name = 'related_plot_lines'
    ) THEN
        ALTER TABLE plot_analysis ADD COLUMN related_plot_lines JSONB;
        COMMENT ON COLUMN plot_analysis.related_plot_lines IS '涉及的剧情线ID列表';
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'plot_analysis' AND column_name = 'referenced_plot_cards'
    ) THEN
        ALTER TABLE plot_analysis ADD COLUMN referenced_plot_cards JSONB;
        COMMENT ON COLUMN plot_analysis.referenced_plot_cards IS '引用的剧情卡片ID列表';
    END IF;
END $$;

-- ============================================
-- 验证表创建
-- ============================================
SELECT 
    tablename AS table_name,
    obj_description((schemaname||'.'||tablename)::regclass, 'pg_class') AS table_comment
FROM 
    pg_tables 
WHERE 
    schemaname = 'public'
    AND tablename IN (
        'story_outlines',
        'chapter_outline_plot_line_links',
        'plot_card_plot_line_links',
        'plot_card_chapter_outline_links',
        'plot_lines',
        'chapter_outlines',
        'plot_cards',
        'chapters'
    )
ORDER BY tablename;

-- 完成提示
SELECT '✅ 数据库结构更新完成！' AS status;
