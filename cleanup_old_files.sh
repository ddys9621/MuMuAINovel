#!/bin/bash
# ============================================
# 自动清理旧文件脚本
# 用途：删除重构后不再需要的旧文件
# ============================================

set -e  # 遇到错误立即退出

echo "🧹 开始清理旧文件..."
echo "================================"

# 切换到项目根目录
cd "$(dirname "$0")"

# 创建备份目录
BACKUP_DIR="backup/old_files_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
echo "📦 备份目录: $BACKUP_DIR"

# ============================================
# 1. 备份并删除旧迁移脚本
# ============================================
echo ""
echo "📝 步骤 1: 清理旧迁移脚本..."

OLD_SCRIPTS=(
    "backend/scripts/add_chapter_outline_id_to_plot_cards.sql"
    "backend/scripts/add_plot_tables.sql"
    "backend/scripts/migration_phase1_create_tables.sql"
    "backend/scripts/migration_phase2_migrate_data.py"
    "backend/scripts/migration_phase3_cleanup.sql"
)

for script in "${OLD_SCRIPTS[@]}"; do
    if [ -f "$script" ]; then
        echo "  ✓ 备份: $script"
        cp "$script" "$BACKUP_DIR/"
        rm "$script"
        echo "  ✓ 删除: $script"
    else
        echo "  ⊘ 不存在: $script"
    fi
done

# ============================================
# 2. 检查 Outline 相关文件的引用
# ============================================
echo ""
echo "🔍 步骤 2: 检查 Outline 相关文件引用..."

OUTLINE_FILES=(
    "backend/app/models/outline.py"
    "backend/app/api/outlines.py"
    "backend/app/schemas/outline.py"
)

echo "  搜索 Outline 引用..."
OUTLINE_REFS=$(grep -r "from app.models.outline import" backend/app/ 2>/dev/null || true)
OUTLINE_API_REFS=$(grep -r "from app.api import.*outlines" backend/app/ 2>/dev/null || true)
OUTLINE_ROUTER_REFS=$(grep -r "outlines.router" backend/app/ 2>/dev/null || true)

if [ -z "$OUTLINE_REFS" ] && [ -z "$OUTLINE_API_REFS" ] && [ -z "$OUTLINE_ROUTER_REFS" ]; then
    echo "  ✓ 未发现 Outline 引用，可以安全删除"
    
    # 备份并删除 Outline 相关文件
    for file in "${OUTLINE_FILES[@]}"; do
        if [ -f "$file" ]; then
            echo "  ✓ 备份: $file"
            mkdir -p "$BACKUP_DIR/$(dirname $file)"
            cp "$file" "$BACKUP_DIR/$file"
            rm "$file"
            echo "  ✓ 删除: $file"
        else
            echo "  ⊘ 不存在: $file"
        fi
    done
else
    echo "  ⚠️  发现 Outline 引用，跳过删除"
    echo "  请手动检查以下引用："
    [ -n "$OUTLINE_REFS" ] && echo "$OUTLINE_REFS"
    [ -n "$OUTLINE_API_REFS" ] && echo "$OUTLINE_API_REFS"
    [ -n "$OUTLINE_ROUTER_REFS" ] && echo "$OUTLINE_ROUTER_REFS"
    
    # 仅备份，不删除
    for file in "${OUTLINE_FILES[@]}"; do
        if [ -f "$file" ]; then
            echo "  ✓ 仅备份: $file"
            mkdir -p "$BACKUP_DIR/$(dirname $file)"
            cp "$file" "$BACKUP_DIR/$file"
        fi
    done
fi

# ============================================
# 3. 清理 Python 缓存
# ============================================
echo ""
echo "🗑️  步骤 3: 清理 Python 缓存..."

find backend -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find backend -type f -name "*.pyc" -delete 2>/dev/null || true
find backend -type f -name "*.pyo" -delete 2>/dev/null || true

echo "  ✓ Python 缓存已清理"

# ============================================
# 4. 生成清理报告
# ============================================
echo ""
echo "📊 步骤 4: 生成清理报告..."

REPORT_FILE="$BACKUP_DIR/cleanup_report.txt"
cat > "$REPORT_FILE" << EOF
清理报告
========================================
清理时间: $(date)
备份目录: $BACKUP_DIR

已删除的文件:
EOF

for script in "${OLD_SCRIPTS[@]}"; do
    if [ ! -f "$script" ]; then
        echo "  ✓ $script" >> "$REPORT_FILE"
    fi
done

if [ -z "$OUTLINE_REFS" ] && [ -z "$OUTLINE_API_REFS" ] && [ -z "$OUTLINE_ROUTER_REFS" ]; then
    for file in "${OUTLINE_FILES[@]}"; do
        if [ ! -f "$file" ]; then
            echo "  ✓ $file" >> "$REPORT_FILE"
        fi
    done
else
    echo "" >> "$REPORT_FILE"
    echo "未删除的文件（发现引用）:" >> "$REPORT_FILE"
    for file in "${OUTLINE_FILES[@]}"; do
        if [ -f "$file" ]; then
            echo "  ⚠️  $file" >> "$REPORT_FILE"
        fi
    done
fi

echo "" >> "$REPORT_FILE"
echo "备份文件列表:" >> "$REPORT_FILE"
ls -lh "$BACKUP_DIR" >> "$REPORT_FILE"

echo "  ✓ 报告已生成: $REPORT_FILE"

# ============================================
# 5. 验证清理结果
# ============================================
echo ""
echo "✅ 步骤 5: 验证清理结果..."

# 检查 Python 语法
echo "  检查 Python 语法..."
if command -v python3 &> /dev/null; then
    python3 -m py_compile backend/app/models/__init__.py 2>/dev/null && echo "  ✓ models/__init__.py 语法正确" || echo "  ⚠️  models/__init__.py 语法错误"
    python3 -m py_compile backend/app/main.py 2>/dev/null && echo "  ✓ main.py 语法正确" || echo "  ⚠️  main.py 语法错误"
else
    echo "  ⊘ Python3 未安装，跳过语法检查"
fi

# ============================================
# 完成
# ============================================
echo ""
echo "================================"
echo "🎉 清理完成！"
echo ""
echo "📦 备份位置: $BACKUP_DIR"
echo "📊 清理报告: $REPORT_FILE"
echo ""
echo "下一步:"
echo "  1. 查看清理报告: cat $REPORT_FILE"
echo "  2. 启动服务测试: cd backend && uvicorn app.main:app --reload"
echo "  3. 如果一切正常，可以删除备份: rm -rf $BACKUP_DIR"
echo ""
