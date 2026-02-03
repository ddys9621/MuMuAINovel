-- ============================================
-- Phase 1: 创建新表和关联表 (PostgreSQL)
-- ============================================

-- 1. 创建 story_outlines 表（故事大纲）
CREATE TABLE IF NOT EXISTS story_outlines (
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

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_story_outlines_project_id ON story_outlines(project_id);
CREATE INDEX IF NOT EXISTS idx_story_outlines_project_active ON story_outlines(project_id, is_active);

-- 添加注释
COMMENT ON TABLE story_outlines IS '故事大纲表';
COMMENT ON COLUMN story_outlines.title IS '大纲标题';
COMMENT ON COLUMN story_outlines.content IS '大纲内容';
COMMENT ON COLUMN story_outlines.structure IS '结构化大纲数据(JSON)';
COMMENT ON COLUMN story_outlines.version IS '版本号';
COMMENT ON COLUMN story_outlines.is_active IS '是否为当前激活版本';
COMMENT ON COLUMN story_outlines.order_index IS '排序序号';
COMMENT ON COLUMN story_outlines.created_at IS '创建时间';
COMMENT ON COLUMN story_outlines.updated_at IS '更新时间';

-- 2. 创建 chapter_outline_plot_line_links 表（章纲-剧情线关联）
CREATE TABLE IF NOT EXISTS chapter_outline_plot_line_links (
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

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_copll_chapter_outline ON chapter_outline_plot_line_links(chapter_outline_id);
CREATE INDEX IF NOT EXISTS idx_copll_plot_line ON chapter_outline_plot_line_links(plot_line_id);

-- 添加注释
COMMENT ON TABLE chapter_outline_plot_line_links IS '章纲-剧情线关联表';
COMMENT ON COLUMN chapter_outline_plot_line_links.role IS '角色类型: main(主线)/sub(支线)/character(角色线)';
COMMENT ON COLUMN chapter_outline_plot_line_links.order_index IS '在该章纲中的优先级';
COMMENT ON COLUMN chapter_outline_plot_line_links.created_at IS '创建时间';

-- 3. 创建 plot_card_plot_line_links 表（素材-剧情线关联）
CREATE TABLE IF NOT EXISTS plot_card_plot_line_links (
    id VARCHAR(36) PRIMARY KEY,
    plot_card_id VARCHAR(36) NOT NULL,
    plot_line_id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_pcpll_plot_card FOREIGN KEY (plot_card_id) REFERENCES plot_cards(id) ON DELETE CASCADE,
    CONSTRAINT fk_pcpll_plot_line FOREIGN KEY (plot_line_id) REFERENCES plot_lines(id) ON DELETE CASCADE,
    CONSTRAINT uk_card_plot UNIQUE (plot_card_id, plot_line_id)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_pcpll_plot_card ON plot_card_plot_line_links(plot_card_id);
CREATE INDEX IF NOT EXISTS idx_pcpll_plot_line ON plot_card_plot_line_links(plot_line_id);

-- 添加注释
COMMENT ON TABLE plot_card_plot_line_links IS '素材-剧情线关联表';
COMMENT ON COLUMN plot_card_plot_line_links.created_at IS '创建时间';

-- 4. 创建 plot_card_chapter_outline_links 表（素材-章纲关联）
CREATE TABLE IF NOT EXISTS plot_card_chapter_outline_links (
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

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_pccol_plot_card ON plot_card_chapter_outline_links(plot_card_id);
CREATE INDEX IF NOT EXISTS idx_pccol_chapter_outline ON plot_card_chapter_outline_links(chapter_outline_id);

-- 添加注释
COMMENT ON TABLE plot_card_chapter_outline_links IS '素材-章纲关联表';
COMMENT ON COLUMN plot_card_chapter_outline_links.usage_type IS '使用方式: reference(参考)/used(已使用)/planned(计划使用)';
COMMENT ON COLUMN plot_card_chapter_outline_links.usage_notes IS '使用说明';
COMMENT ON COLUMN plot_card_chapter_outline_links.created_at IS '创建时间';
COMMENT ON COLUMN plot_card_chapter_outline_links.updated_at IS '更新时间';

-- 5. 修改 plot_lines 表，添加 story_outline_id
DO $$ 
BEGIN
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

-- 6. 扩展 chapters 表（可选：版本管理）
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

-- 7. 扩展 plot_analysis 表
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
        'plot_card_chapter_outline_links'
    )
ORDER BY tablename;
