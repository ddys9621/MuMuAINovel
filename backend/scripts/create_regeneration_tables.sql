-- 创建章节重新生成任务表
-- 用于支持根据AI分析建议重新生成章节内容的功能

-- 创建重新生成任务表
CREATE TABLE IF NOT EXISTS regeneration_tasks (
    id VARCHAR(36) PRIMARY KEY,
    chapter_id VARCHAR(36) NOT NULL,
    analysis_id VARCHAR(36),
    user_id VARCHAR(100) NOT NULL,
    project_id VARCHAR(36) NOT NULL,
    
    -- 修改指令
    modification_instructions TEXT NOT NULL,
    original_suggestions JSON,
    selected_suggestion_indices JSON,
    custom_instructions TEXT,
    
    -- 生成配置
    style_id INTEGER,
    target_word_count INTEGER DEFAULT 3000,
    focus_areas JSON,
    preserve_elements JSON,
    
    -- 任务状态
    status VARCHAR(20) DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    error_message TEXT,
    
    -- 内容数据
    original_content TEXT,
    original_word_count INTEGER,
    regenerated_content TEXT,
    regenerated_word_count INTEGER,
    
    -- 版本信息
    version_number INTEGER DEFAULT 1,
    version_note TEXT,
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- 外键约束
    CONSTRAINT fk_regeneration_chapter FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE,
    CONSTRAINT fk_regeneration_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    CONSTRAINT fk_regeneration_analysis FOREIGN KEY (analysis_id) REFERENCES analysis_tasks(id) ON DELETE SET NULL,
    CONSTRAINT fk_regeneration_style FOREIGN KEY (style_id) REFERENCES writing_styles(id) ON DELETE SET NULL
);

-- 创建索引以提升查询性能
CREATE INDEX IF NOT EXISTS idx_regeneration_tasks_chapter ON regeneration_tasks(chapter_id);
CREATE INDEX IF NOT EXISTS idx_regeneration_tasks_project ON regeneration_tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_regeneration_tasks_user ON regeneration_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_regeneration_tasks_status ON regeneration_tasks(status);
CREATE INDEX IF NOT EXISTS idx_regeneration_tasks_created ON regeneration_tasks(created_at DESC);

-- 添加注释
COMMENT ON TABLE regeneration_tasks IS '章节重新生成任务表，记录每次根据AI建议重新生成章节的任务';

COMMENT ON COLUMN regeneration_tasks.modification_instructions IS '合并后的完整修改指令';
COMMENT ON COLUMN regeneration_tasks.original_suggestions IS '原始AI分析建议列表';
COMMENT ON COLUMN regeneration_tasks.selected_suggestion_indices IS '用户选择的建议索引';
COMMENT ON COLUMN regeneration_tasks.preserve_elements IS '需要保留的元素配置(JSON)';
COMMENT ON COLUMN regeneration_tasks.focus_areas IS '重点优化方向列表(JSON)';

-- 修复外键约束（合并自 fix_all_missing_columns.sql）
-- 删除可能存在问题的外键约束
ALTER TABLE regeneration_tasks
DROP CONSTRAINT IF EXISTS fk_regeneration_analysis;

-- 完成提示
SELECT '✅ 重新生成任务表创建完成，外键约束已修复' AS status;
