-- 添加剧情相关表结构的SQL脚本
-- 运行前请确保已有projects和outlines表

-- 创建剧情卡片表
CREATE TABLE IF NOT EXISTS plot_cards (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    outline_id VARCHAR(36) REFERENCES outlines(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    content TEXT,
    card_type VARCHAR(50) DEFAULT 'plot',
    order_index INTEGER,
    tags TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建剧情线表
CREATE TABLE IF NOT EXISTS plot_lines (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    outline_id VARCHAR(36) REFERENCES outlines(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    line_type VARCHAR(50) DEFAULT 'main',
    order_index INTEGER,
    plot_cards TEXT,
    timeline_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建章纲表
CREATE TABLE IF NOT EXISTS chapter_outlines (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    plot_line_id VARCHAR(36) REFERENCES plot_lines(id) ON DELETE CASCADE,
    chapter_number INTEGER NOT NULL,
    title VARCHAR(200) NOT NULL,
    summary TEXT,
    key_events TEXT,
    characters_involved TEXT,
    plot_points TEXT,
    target_word_count INTEGER DEFAULT 3000,
    order_index INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_plot_cards_project_id ON plot_cards(project_id);
CREATE INDEX IF NOT EXISTS idx_plot_cards_outline_id ON plot_cards(outline_id);
CREATE INDEX IF NOT EXISTS idx_plot_cards_order ON plot_cards(order_index);

CREATE INDEX IF NOT EXISTS idx_plot_lines_project_id ON plot_lines(project_id);
CREATE INDEX IF NOT EXISTS idx_plot_lines_outline_id ON plot_lines(outline_id);
CREATE INDEX IF NOT EXISTS idx_plot_lines_order ON plot_lines(order_index);

CREATE INDEX IF NOT EXISTS idx_chapter_outlines_project_id ON chapter_outlines(project_id);
CREATE INDEX IF NOT EXISTS idx_chapter_outlines_plot_line_id ON chapter_outlines(plot_line_id);
CREATE INDEX IF NOT EXISTS idx_chapter_outlines_chapter_number ON chapter_outlines(chapter_number);
CREATE INDEX IF NOT EXISTS idx_chapter_outlines_order ON chapter_outlines(order_index);

-- 创建更新时间触发器
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为新表添加更新时间触发器
DROP TRIGGER IF EXISTS update_plot_cards_updated_at ON plot_cards;
CREATE TRIGGER update_plot_cards_updated_at
    BEFORE UPDATE ON plot_cards
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_plot_lines_updated_at ON plot_lines;
CREATE TRIGGER update_plot_lines_updated_at
    BEFORE UPDATE ON plot_lines
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_chapter_outlines_updated_at ON chapter_outlines;
CREATE TRIGGER update_chapter_outlines_updated_at
    BEFORE UPDATE ON chapter_outlines
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 输出完成信息
DO $$
BEGIN
    RAISE NOTICE '==================================================';
    RAISE NOTICE 'MuMuAINovel 剧情表结构创建完成';
    RAISE NOTICE '已创建表:';
    RAISE NOTICE '  - plot_cards: 剧情卡片表';
    RAISE NOTICE '  - plot_lines: 剧情线表';
    RAISE NOTICE '  - chapter_outlines: 章纲表';
    RAISE NOTICE '已创建索引和触发器';
    RAISE NOTICE '==================================================';
END $$;
