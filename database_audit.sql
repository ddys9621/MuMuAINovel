-- ============================================
-- 数据库审计SQL脚本
-- 用于检查剧情卡片、剧情线、章纲的关联数据完整性
-- ============================================

-- 1. 基础统计信息
-- ============================================

-- 1.1 各表的记录数
SELECT 'plot_lines' as table_name, COUNT(*) as count FROM plot_lines
UNION ALL
SELECT 'plot_cards', COUNT(*) FROM plot_cards
UNION ALL
SELECT 'chapter_outlines', COUNT(*) FROM chapter_outlines
UNION ALL
SELECT 'chapter_outline_plot_line_links', COUNT(*) FROM chapter_outline_plot_line_links
UNION ALL
SELECT 'plot_card_plot_line_links', COUNT(*) FROM plot_card_plot_line_links
UNION ALL
SELECT 'plot_card_chapter_outline_links', COUNT(*) FROM plot_card_chapter_outline_links;

-- 1.2 按项目统计
SELECT 
    p.id as project_id,
    p.title as project_title,
    COUNT(DISTINCT pl.id) as plot_lines_count,
    COUNT(DISTINCT pc.id) as plot_cards_count,
    COUNT(DISTINCT co.id) as chapter_outlines_count
FROM projects p
LEFT JOIN plot_lines pl ON p.id = pl.project_id
LEFT JOIN plot_cards pc ON p.id = pc.project_id
LEFT JOIN chapter_outlines co ON p.id = co.project_id
GROUP BY p.id, p.title;

-- 2. 孤立数据检查
-- ============================================

-- 2.1 检查孤立的剧情线（没有任何关联）
SELECT 
    pl.id,
    pl.title,
    pl.line_type,
    pl.created_at,
    'No links' as issue
FROM plot_lines pl
LEFT JOIN chapter_outline_plot_line_links copl ON pl.id = copl.plot_line_id
LEFT JOIN plot_card_plot_line_links pcpl ON pl.id = pcpl.plot_line_id
WHERE copl.id IS NULL AND pcpl.id IS NULL;

-- 2.2 检查孤立的剧情卡片（没有任何关联）
SELECT 
    pc.id,
    pc.title,
    pc.card_type,
    pc.created_at,
    'No links' as issue
FROM plot_cards pc
LEFT JOIN plot_card_plot_line_links pcpl ON pc.id = pcpl.plot_card_id
LEFT JOIN plot_card_chapter_outline_links pcco ON pc.id = pcco.plot_card_id
WHERE pcpl.id IS NULL AND pcco.id IS NULL;

-- 2.3 检查孤立的章纲（没有任何关联）
SELECT 
    co.id,
    co.chapter_number,
    co.title,
    co.created_at,
    'No links' as issue
FROM chapter_outlines co
LEFT JOIN chapter_outline_plot_line_links copl ON co.id = copl.chapter_outline_id
LEFT JOIN plot_card_chapter_outline_links pcco ON co.id = pcco.chapter_outline_id
WHERE copl.id IS NULL AND pcco.id IS NULL;

-- 3. 无效关联检查（外键不存在）
-- ============================================

-- 3.1 检查章纲-剧情线关联表中的无效关联
SELECT 
    copl.id,
    copl.chapter_outline_id,
    copl.plot_line_id,
    CASE 
        WHEN co.id IS NULL THEN 'Invalid chapter_outline_id'
        WHEN pl.id IS NULL THEN 'Invalid plot_line_id'
        ELSE 'Unknown'
    END as issue
FROM chapter_outline_plot_line_links copl
LEFT JOIN chapter_outlines co ON copl.chapter_outline_id = co.id
LEFT JOIN plot_lines pl ON copl.plot_line_id = pl.id
WHERE co.id IS NULL OR pl.id IS NULL;

-- 3.2 检查剧情卡片-剧情线关联表中的无效关联
SELECT 
    pcpl.id,
    pcpl.plot_card_id,
    pcpl.plot_line_id,
    CASE 
        WHEN pc.id IS NULL THEN 'Invalid plot_card_id'
        WHEN pl.id IS NULL THEN 'Invalid plot_line_id'
        ELSE 'Unknown'
    END as issue
FROM plot_card_plot_line_links pcpl
LEFT JOIN plot_cards pc ON pcpl.plot_card_id = pc.id
LEFT JOIN plot_lines pl ON pcpl.plot_line_id = pl.id
WHERE pc.id IS NULL OR pl.id IS NULL;

-- 3.3 检查剧情卡片-章纲关联表中的无效关联
SELECT 
    pcco.id,
    pcco.plot_card_id,
    pcco.chapter_outline_id,
    CASE 
        WHEN pc.id IS NULL THEN 'Invalid plot_card_id'
        WHEN co.id IS NULL THEN 'Invalid chapter_outline_id'
        ELSE 'Unknown'
    END as issue
FROM plot_card_chapter_outline_links pcco
LEFT JOIN plot_cards pc ON pcco.plot_card_id = pc.id
LEFT JOIN chapter_outlines co ON pcco.chapter_outline_id = co.id
WHERE pc.id IS NULL OR co.id IS NULL;

-- 4. 重复关联检查
-- ============================================

-- 4.1 检查章纲-剧情线的重复关联
SELECT 
    chapter_outline_id,
    plot_line_id,
    COUNT(*) as duplicate_count
FROM chapter_outline_plot_line_links
GROUP BY chapter_outline_id, plot_line_id
HAVING COUNT(*) > 1;

-- 4.2 检查剧情卡片-剧情线的重复关联
SELECT 
    plot_card_id,
    plot_line_id,
    COUNT(*) as duplicate_count
FROM plot_card_plot_line_links
GROUP BY plot_card_id, plot_line_id
HAVING COUNT(*) > 1;

-- 4.3 检查剧情卡片-章纲的重复关联
SELECT 
    plot_card_id,
    chapter_outline_id,
    COUNT(*) as duplicate_count
FROM plot_card_chapter_outline_links
GROUP BY plot_card_id, chapter_outline_id
HAVING COUNT(*) > 1;

-- 5. 跨项目关联检查（不应该存在）
-- ============================================

-- 5.1 检查章纲-剧情线的跨项目关联
SELECT 
    copl.id,
    co.project_id as chapter_project_id,
    pl.project_id as plot_line_project_id,
    co.title as chapter_title,
    pl.title as plot_line_title,
    'Cross-project link' as issue
FROM chapter_outline_plot_line_links copl
JOIN chapter_outlines co ON copl.chapter_outline_id = co.id
JOIN plot_lines pl ON copl.plot_line_id = pl.id
WHERE co.project_id != pl.project_id;

-- 5.2 检查剧情卡片-剧情线的跨项目关联
SELECT 
    pcpl.id,
    pc.project_id as card_project_id,
    pl.project_id as plot_line_project_id,
    pc.title as card_title,
    pl.title as plot_line_title,
    'Cross-project link' as issue
FROM plot_card_plot_line_links pcpl
JOIN plot_cards pc ON pcpl.plot_card_id = pc.id
JOIN plot_lines pl ON pcpl.plot_line_id = pl.id
WHERE pc.project_id != pl.project_id;

-- 5.3 检查剧情卡片-章纲的跨项目关联
SELECT 
    pcco.id,
    pc.project_id as card_project_id,
    co.project_id as chapter_project_id,
    pc.title as card_title,
    co.title as chapter_title,
    'Cross-project link' as issue
FROM plot_card_chapter_outline_links pcco
JOIN plot_cards pc ON pcco.plot_card_id = pc.id
JOIN chapter_outlines co ON pcco.chapter_outline_id = co.id
WHERE pc.project_id != co.project_id;

-- 6. 关联统计分析
-- ============================================

-- 6.1 剧情线的关联统计
SELECT 
    pl.id,
    pl.title,
    pl.line_type,
    COUNT(DISTINCT copl.chapter_outline_id) as linked_chapters,
    COUNT(DISTINCT pcpl.plot_card_id) as linked_cards,
    COUNT(DISTINCT copl.chapter_outline_id) + COUNT(DISTINCT pcpl.plot_card_id) as total_links
FROM plot_lines pl
LEFT JOIN chapter_outline_plot_line_links copl ON pl.id = copl.plot_line_id
LEFT JOIN plot_card_plot_line_links pcpl ON pl.id = pcpl.plot_line_id
GROUP BY pl.id, pl.title, pl.line_type
ORDER BY total_links DESC;

-- 6.2 剧情卡片的关联统计
SELECT 
    pc.id,
    pc.title,
    pc.card_type,
    COUNT(DISTINCT pcpl.plot_line_id) as linked_plot_lines,
    COUNT(DISTINCT pcco.chapter_outline_id) as linked_chapters,
    COUNT(DISTINCT pcpl.plot_line_id) + COUNT(DISTINCT pcco.chapter_outline_id) as total_links
FROM plot_cards pc
LEFT JOIN plot_card_plot_line_links pcpl ON pc.id = pcpl.plot_card_id
LEFT JOIN plot_card_chapter_outline_links pcco ON pc.id = pcco.plot_card_id
GROUP BY pc.id, pc.title, pc.card_type
ORDER BY total_links DESC;

-- 6.3 章纲的关联统计
SELECT 
    co.id,
    co.chapter_number,
    co.title,
    COUNT(DISTINCT copl.plot_line_id) as linked_plot_lines,
    COUNT(DISTINCT pcco.plot_card_id) as linked_cards,
    COUNT(DISTINCT copl.plot_line_id) + COUNT(DISTINCT pcco.plot_card_id) as total_links
FROM chapter_outlines co
LEFT JOIN chapter_outline_plot_line_links copl ON co.id = copl.chapter_outline_id
LEFT JOIN plot_card_chapter_outline_links pcco ON co.id = pcco.chapter_outline_id
GROUP BY co.id, co.chapter_number, co.title
ORDER BY co.chapter_number;

-- 7. 数据完整性检查
-- ============================================

-- 7.1 检查缺少标题的记录
SELECT 'plot_lines' as table_name, id, 'Missing title' as issue
FROM plot_lines
WHERE title IS NULL OR title = ''
UNION ALL
SELECT 'plot_cards', id, 'Missing title'
FROM plot_cards
WHERE title IS NULL OR title = ''
UNION ALL
SELECT 'chapter_outlines', id, 'Missing title'
FROM chapter_outlines
WHERE title IS NULL OR title = '';

-- 7.2 检查缺少project_id的记录
SELECT 'plot_lines' as table_name, id, 'Missing project_id' as issue
FROM plot_lines
WHERE project_id IS NULL
UNION ALL
SELECT 'plot_cards', id, 'Missing project_id'
FROM plot_cards
WHERE project_id IS NULL
UNION ALL
SELECT 'chapter_outlines', id, 'Missing project_id'
FROM chapter_outlines
WHERE project_id IS NULL;

-- 8. 最近的活动
-- ============================================

-- 8.1 最近创建的剧情线
SELECT 
    pl.id,
    pl.title,
    pl.line_type,
    pl.created_at,
    COUNT(DISTINCT copl.chapter_outline_id) as linked_chapters,
    COUNT(DISTINCT pcpl.plot_card_id) as linked_cards
FROM plot_lines pl
LEFT JOIN chapter_outline_plot_line_links copl ON pl.id = copl.plot_line_id
LEFT JOIN plot_card_plot_line_links pcpl ON pl.id = pcpl.plot_line_id
GROUP BY pl.id, pl.title, pl.line_type, pl.created_at
ORDER BY pl.created_at DESC
LIMIT 10;

-- 8.2 最近创建的剧情卡片
SELECT 
    pc.id,
    pc.title,
    pc.card_type,
    pc.created_at,
    COUNT(DISTINCT pcpl.plot_line_id) as linked_plot_lines,
    COUNT(DISTINCT pcco.chapter_outline_id) as linked_chapters
FROM plot_cards pc
LEFT JOIN plot_card_plot_line_links pcpl ON pc.id = pcpl.plot_card_id
LEFT JOIN plot_card_chapter_outline_links pcco ON pc.id = pcco.plot_card_id
GROUP BY pc.id, pc.title, pc.card_type, pc.created_at
ORDER BY pc.created_at DESC
LIMIT 10;

-- 8.3 最近创建的章纲
SELECT 
    co.id,
    co.chapter_number,
    co.title,
    co.created_at,
    COUNT(DISTINCT copl.plot_line_id) as linked_plot_lines,
    COUNT(DISTINCT pcco.plot_card_id) as linked_cards
FROM chapter_outlines co
LEFT JOIN chapter_outline_plot_line_links copl ON co.id = copl.chapter_outline_id
LEFT JOIN plot_card_chapter_outline_links pcco ON co.id = pcco.chapter_outline_id
GROUP BY co.id, co.chapter_number, co.title, co.created_at
ORDER BY co.created_at DESC
LIMIT 10;

-- 9. 清理建议
-- ============================================

-- 9.1 可以删除的孤立剧情线（创建超过7天且无关联）
SELECT 
    pl.id,
    pl.title,
    pl.created_at,
    DATEDIFF(NOW(), pl.created_at) as days_old,
    'Can be deleted' as suggestion
FROM plot_lines pl
LEFT JOIN chapter_outline_plot_line_links copl ON pl.id = copl.plot_line_id
LEFT JOIN plot_card_plot_line_links pcpl ON pl.id = pcpl.plot_line_id
WHERE copl.id IS NULL 
  AND pcpl.id IS NULL
  AND DATEDIFF(NOW(), pl.created_at) > 7;

-- 9.2 可以删除的孤立剧情卡片（创建超过7天且无关联）
SELECT 
    pc.id,
    pc.title,
    pc.created_at,
    DATEDIFF(NOW(), pc.created_at) as days_old,
    'Can be deleted' as suggestion
FROM plot_cards pc
LEFT JOIN plot_card_plot_line_links pcpl ON pc.id = pcpl.plot_card_id
LEFT JOIN plot_card_chapter_outline_links pcco ON pc.id = pcco.plot_card_id
WHERE pcpl.id IS NULL 
  AND pcco.id IS NULL
  AND DATEDIFF(NOW(), pc.created_at) > 7;

-- 9.3 可以删除的孤立章纲（创建超过7天且无关联）
SELECT 
    co.id,
    co.chapter_number,
    co.title,
    co.created_at,
    DATEDIFF(NOW(), co.created_at) as days_old,
    'Can be deleted' as suggestion
FROM chapter_outlines co
LEFT JOIN chapter_outline_plot_line_links copl ON co.id = copl.chapter_outline_id
LEFT JOIN plot_card_chapter_outline_links pcco ON co.id = pcco.chapter_outline_id
WHERE copl.id IS NULL 
  AND pcco.id IS NULL
  AND DATEDIFF(NOW(), co.created_at) > 7;

-- ============================================
-- 审计完成
-- ============================================
