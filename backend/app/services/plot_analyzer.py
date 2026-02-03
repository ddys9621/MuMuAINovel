"""剧情分析服务 - 自动分析章节的钩子、伏笔、冲突等元素"""
from typing import Dict, Any, List, Optional
from app.services.ai_service import AIService
from app.logger import get_logger
import json
import re

logger = get_logger(__name__)


class PlotAnalyzer:
    """剧情分析器 - 使用AI分析章节内容"""
    
    # AI分析提示词模板
    ANALYSIS_PROMPT = """你是一位专业的小说编辑和剧情分析师。请深度分析以下章节内容:

**章节信息:**
- 章节: 第{chapter_number}章
- 标题: {title}
- 字数: {word_count}字

**章节内容:**
{content}

---

**分析任务:**
请从专业编辑的角度,全面分析这一章节:

### 1. 剧情钩子 (Hooks) - 吸引读者的元素
识别能够吸引读者继续阅读的关键元素:
- **悬念钩子**: 未解之谜、疑问、谜团
- **情感钩子**: 引发共鸣的情感点、触动心弦的时刻
- **冲突钩子**: 矛盾对抗、紧张局势
- **认知钩子**: 颠覆认知的信息、惊人真相

每个钩子需要:
- 类型分类
- 具体内容描述
- 强度评分(1-10)
- 出现位置(开头/中段/结尾)
- **关键词**: 【必填】从章节原文中逐字复制一段关键文本(8-25字)，必须是原文中真实存在的连续文字，用于在文本中精确定位。不要概括或改写，必须原样复制！

### 2. 伏笔分析 (Foreshadowing)
- **埋下的新伏笔**: 描述内容、预期作用、隐藏程度(1-10)
- **回收的旧伏笔**: 呼应哪一章、回收效果评分
- **伏笔质量**: 巧妙性和合理性评估
- **关键词**: 【必填】从章节原文中逐字复制一段关键文本(8-25字)，必须是原文中真实存在的连续文字，用于在文本中精确定位。不要概括或改写，必须原样复制！

### 3. 冲突分析 (Conflict)
- 冲突类型: 人与人/人与己/人与环境/人与社会
- 冲突各方及其立场
- 冲突强度评分(1-10)
- 冲突解决进度(0-100%)

### 4. 情感曲线 (Emotional Arc)
- 主导情绪: 紧张/温馨/悲伤/激昂/平静等
- 情感强度(1-10)
- 情绪变化轨迹描述

### 5. 角色状态追踪 (Character Development)
对每个出场角色分析:
- 心理状态变化(前→后)
- 关系变化
- 关键行动和决策
- 成长或退步

### 6. 关键情节点 (Plot Points)
列出3-5个核心情节点:
- 情节内容
- 类型(revelation/conflict/resolution/transition)
- 重要性(0.0-1.0)
- 对故事的影响
- **关键词**: 【必填】从章节原文中逐字复制一段关键文本(8-25字)，必须是原文中真实存在的连续文字，用于在文本中精确定位。不要概括或改写，必须原样复制！

### 7. 场景与节奏
- 主要场景
- 叙事节奏(快/中/慢)
- 对话与描写的比例

### 8. 质量评分
- 节奏把控: 1-10分
- 吸引力: 1-10分  
- 连贯性: 1-10分
- 整体质量: 1-10分

### 9. 改进建议
提供3-5条具体的改进建议

### 10. 章节概要 (Summary)
用100-200字概括本章核心内容，要求：
- 概括主要事件和情节发展
- 点明关键转折点或冲突
- 体现与前文的关联（如有）
- 语言简洁流畅，便于快速了解章节大意

---

**输出格式(纯JSON,不要markdown标记):**

{{
  "summary": "100-200字的章节内容概要，概括主要事件、人物行动和情节发展，语言简洁流畅",
  "hooks": [
    {{
      "type": "悬念",
      "content": "具体描述",
      "strength": 8,
      "position": "中段",
      "keyword": "必须从原文逐字复制的文本片段"
    }}
  ],
  "foreshadows": [
    {{
      "content": "伏笔内容",
      "type": "planted",
      "strength": 7,
      "subtlety": 8,
      "reference_chapter": null,
      "keyword": "必须从原文逐字复制的文本片段"
    }}
  ],
  "conflict": {{
    "types": ["人与人", "人与己"],
    "parties": ["主角-复仇", "反派-维护现状"],
    "level": 8,
    "description": "冲突描述",
    "resolution_progress": 0.3
  }},
  "emotional_arc": {{
    "primary_emotion": "紧张",
    "intensity": 8,
    "curve": "平静→紧张→高潮→释放",
    "secondary_emotions": ["期待", "焦虑"]
  }},
  "character_states": [
    {{
      "character_name": "张三",
      "state_before": "犹豫",
      "state_after": "坚定",
      "psychological_change": "心理变化描述",
      "key_event": "触发事件",
      "relationship_changes": {{"李四": "关系改善"}}
    }}
  ],
  "plot_points": [
    {{
      "content": "情节点描述",
      "type": "revelation",
      "importance": 0.9,
      "impact": "推动故事发展",
      "keyword": "必须从原文逐字复制的文本片段"
    }}
  ],
  "scenes": [
    {{
      "location": "地点",
      "atmosphere": "氛围",
      "duration": "时长估计"
    }}
  ],
  "pacing": "varied",
  "dialogue_ratio": 0.4,
  "description_ratio": 0.3,
  "scores": {{
    "pacing": 8,
    "engagement": 9,
    "coherence": 8,
    "overall": 8.5
  }},
  "plot_stage": "发展",
  "suggestions": [
    "具体建议1",
    "具体建议2"
  ]
}}

**重要提示:**
1. 每个钩子、伏笔、情节点的keyword字段是必填的，不能为空
2. keyword必须是从章节原文中逐字复制的文本，长度8-25字
3. keyword用于在前端标注文本位置，所以必须能在原文中精确找到
4. 不要使用概括性语句或改写后的文字作为keyword

只返回JSON,不要其他说明。"""
    
    def __init__(self, ai_service: AIService):
        """
        初始化剧情分析器
        
        Args:
            ai_service: AI服务实例
        """
        self.ai_service = ai_service
        logger.info("✅ PlotAnalyzer初始化成功")
    
    async def analyze_chapter(
        self,
        chapter_number: int,
        title: str,
        content: str,
        word_count: int
    ) -> Optional[Dict[str, Any]]:
        """
        分析单章内容
        
        Args:
            chapter_number: 章节号
            title: 章节标题
            content: 章节内容
            word_count: 字数
        
        Returns:
            分析结果字典,失败返回None
        """
        try:
            logger.info(f"🔍 开始分析第{chapter_number}章: {title}")
            
            # 如果内容过长,截取前8000字(避免超token)
            analysis_content = content[:8000] if len(content) > 8000 else content
            
            # 构建提示词
            prompt = self.ANALYSIS_PROMPT.format(
                chapter_number=chapter_number,
                title=title,
                word_count=word_count,
                content=analysis_content
            )
            
            # 调用AI进行分析
            # 注意：不指定max_tokens，使用用户在设置中配置的值
            logger.info(f"  调用AI分析(内容长度: {len(analysis_content)}字)...")
            response = await self.ai_service.generate_text(
                prompt=prompt,
                temperature=0.3  # 降低温度以获得更稳定的JSON输出
            )
            
            # 🔍 添加调试日志：查看AI返回的原始内容
            # logger.info(f"🔍 AI返回类型: {type(response)}")
            # logger.info(f"🔍 AI返回内容(前500字符): {str(response)}")
            
            # 从返回的字典中提取content字段
            if isinstance(response, dict):
                response_text = response.get('content', '')
                if not response_text:
                    logger.error("❌ AI返回的字典中没有content字段或content为空")
                    return None
            else:
                # 兼容旧的字符串返回格式
                response_text = response
            
            # 解析JSON结果
            analysis_result = self._parse_analysis_response(response_text)
            
            if analysis_result:
                logger.info(f"✅ 第{chapter_number}章分析完成")
                logger.info(f"  - 钩子: {len(analysis_result.get('hooks', []))}个")
                logger.info(f"  - 伏笔: {len(analysis_result.get('foreshadows', []))}个")
                logger.info(f"  - 情节点: {len(analysis_result.get('plot_points', []))}个")
                logger.info(f"  - 整体评分: {analysis_result.get('scores', {}).get('overall', 'N/A')}")
                return analysis_result
            else:
                logger.error(f"❌ 第{chapter_number}章分析失败: JSON解析错误")
                return None
                
        except Exception as e:
            logger.error(f"❌ 章节分析异常: {str(e)}")
            return None
    
    def _parse_analysis_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        解析AI返回的分析结果

        Args:
            response: AI返回的文本

        Returns:
            解析后的字典,失败返回None
        """
        from app.utils.json_cleaner import safe_parse_json

        # 使用安全解析，失败时返回 None
        result = safe_parse_json(
            response,
            default=None,
            expected_type='object',
            log_prefix="[章节分析]"
        )

        if result is None:
            return None

        # 验证必要字段
        required_fields = ['hooks', 'plot_points', 'scores']
        for field in required_fields:
            if field not in result:
                logger.warning(f"⚠️ 分析结果缺少字段: {field}")
                result[field] = [] if field != 'scores' else {}

        return result
    
    def extract_memories_from_analysis(
        self,
        analysis: Dict[str, Any],
        chapter_id: str,
        chapter_number: int,
        chapter_content: str = "",
        chapter_title: str = ""
    ) -> List[Dict[str, Any]]:
        """
        从分析结果中提取记忆片段
        
        Args:
            analysis: 分析结果
            chapter_id: 章节ID
            chapter_number: 章节号
            chapter_content: 章节完整内容(用于计算位置)
            chapter_title: 章节标题
        
        Returns:
            记忆片段列表
        """
        memories = []
        
        try:
            # 【新增】0. 提取章节摘要作为记忆（用于语义检索相关章节）
            chapter_summary = ""
            
            # 尝试从分析结果获取摘要
            if analysis.get('summary'):
                chapter_summary = analysis.get('summary')
            # 或者从情节点组合生成摘要
            elif analysis.get('plot_points'):
                plot_summaries = [p.get('content', '') for p in analysis.get('plot_points', [])[:3]]
                chapter_summary = "；".join(plot_summaries)
            # 或者使用内容前300字
            elif chapter_content:
                chapter_summary = chapter_content[:300] + ("..." if len(chapter_content) > 300 else "")
            
            # 如果有摘要，添加到记忆中
            if chapter_summary:
                memories.append({
                    'type': 'chapter_summary',
                    'content': chapter_summary,
                    'title': f"第{chapter_number}章《{chapter_title}》摘要",
                    'metadata': {
                        'chapter_id': chapter_id,
                        'chapter_number': chapter_number,
                        'importance_score': 0.6,  # 中等重要性
                        'tags': ['摘要', '章节概览', chapter_title],
                        'is_foreshadow': 0,
                        'text_position': 0,
                        'text_length': len(chapter_summary)
                    }
                })
                logger.info(f"  ✅ 添加章节摘要记忆: {len(chapter_summary)}字")
            
            # 1. 提取钩子作为记忆
            for i, hook in enumerate(analysis.get('hooks', [])):
                if hook.get('strength', 0) >= 6:  # 只保存强度>=6的钩子
                    keyword = hook.get('keyword', '')
                    position, length = self._find_text_position(chapter_content, keyword)
                    
                    logger.info(f"  钩子位置: keyword='{keyword[:30]}...', pos={position}, len={length}")
                    
                    memories.append({
                        'type': 'hook',
                        'content': f"[{hook.get('type', '未知')}钩子] {hook.get('content', '')}",
                        'title': f"{hook.get('type', '钩子')} - {hook.get('position', '')}",
                        'metadata': {
                            'chapter_id': chapter_id,
                            'chapter_number': chapter_number,
                            'importance_score': min(hook.get('strength', 5) / 10, 1.0),
                            'tags': [hook.get('type', '钩子'), hook.get('position', '')],
                            'is_foreshadow': 0,
                            'keyword': keyword,
                            'text_position': position,
                            'text_length': length,
                            'strength': hook.get('strength', 5),
                            'position_desc': hook.get('position', '')
                        }
                    })
            
            # 2. 提取伏笔作为记忆
            for i, foreshadow in enumerate(analysis.get('foreshadows', [])):
                is_planted = foreshadow.get('type') == 'planted'
                keyword = foreshadow.get('keyword', '')
                position, length = self._find_text_position(chapter_content, keyword)
                
                logger.info(f"  伏笔位置: keyword='{keyword[:30]}...', pos={position}, len={length}")
                
                memories.append({
                    'type': 'foreshadow',
                    'content': foreshadow.get('content', ''),
                    'title': f"{'埋下伏笔' if is_planted else '回收伏笔'}",
                    'metadata': {
                        'chapter_id': chapter_id,
                        'chapter_number': chapter_number,
                        'importance_score': min(foreshadow.get('strength', 5) / 10, 1.0),
                        'tags': ['伏笔', foreshadow.get('type', 'planted')],
                        'is_foreshadow': 1 if is_planted else 2,
                        'reference_chapter': foreshadow.get('reference_chapter'),
                        'keyword': keyword,
                        'text_position': position,
                        'text_length': length,
                        'foreshadow_type': foreshadow.get('type', 'planted'),
                        'strength': foreshadow.get('strength', 5)
                    }
                })
            
            # 3. 提取关键情节点
            for i, plot_point in enumerate(analysis.get('plot_points', [])):
                if plot_point.get('importance', 0) >= 0.6:  # 只保存重要性>=0.6的情节点
                    keyword = plot_point.get('keyword', '')
                    position, length = self._find_text_position(chapter_content, keyword)
                    
                    logger.info(f"  情节点位置: keyword='{keyword[:30]}...', pos={position}, len={length}")
                    
                    memories.append({
                        'type': 'plot_point',
                        'content': f"{plot_point.get('content', '')}。影响: {plot_point.get('impact', '')}",
                        'title': f"情节点 - {plot_point.get('type', '未知')}",
                        'metadata': {
                            'chapter_id': chapter_id,
                            'chapter_number': chapter_number,
                            'importance_score': plot_point.get('importance', 0.5),
                            'tags': ['情节点', plot_point.get('type', '未知')],
                            'is_foreshadow': 0,
                            'keyword': keyword,
                            'text_position': position,
                            'text_length': length
                        }
                    })
            
            # 4. 提取角色状态变化
            for i, char_state in enumerate(analysis.get('character_states', [])):
                char_name = char_state.get('character_name', '未知角色')
                memories.append({
                    'type': 'character_event',
                    'content': f"{char_name}的状态变化: {char_state.get('state_before', '')} → {char_state.get('state_after', '')}。{char_state.get('psychological_change', '')}",
                    'title': f"{char_name}的变化",
                    'metadata': {
                        'chapter_id': chapter_id,
                        'chapter_number': chapter_number,
                        'importance_score': 0.7,
                        'tags': ['角色', char_name, '状态变化'],
                        'related_characters': [char_name],
                        'is_foreshadow': 0
                    }
                })
            
            # 5. 如果有重要冲突,也记录下来
            conflict = analysis.get('conflict', {})
            
            if conflict and conflict.get('level', 0) >= 7:
                # 确保 parties 和 types 都是字符串列表
                parties = conflict.get('parties', [])
                if parties and isinstance(parties, list):
                    parties = [str(p) for p in parties]
                
                types = conflict.get('types', [])
                if types and isinstance(types, list):
                    types = [str(t) for t in types]
                
                memories.append({
                    'type': 'plot_point',
                    'content': f"重要冲突: {conflict.get('description', '')}。冲突各方: {', '.join(parties)}",
                    'title': f"冲突 - 强度{conflict.get('level', 0)}",
                    'metadata': {
                        'chapter_id': chapter_id,
                        'chapter_number': chapter_number,
                        'importance_score': min(conflict.get('level', 5) / 10, 1.0),
                        'tags': ['冲突'] + types,
                        'is_foreshadow': 0
                    }
                })
            
            logger.info(f"📝 从分析中提取了{len(memories)}条记忆")
            return memories
            
        except Exception as e:
            logger.error(f"❌ 提取记忆失败: {str(e)}")
            return []
    
    def _find_text_position(self, full_text: str, keyword: str) -> tuple[int, int]:
        """
        在全文中查找关键词位置
        
        Args:
            full_text: 完整文本
            keyword: 关键词
        
        Returns:
            (起始位置, 长度) 如果未找到返回(-1, 0)
        """
        if not keyword or not full_text:
            return (-1, 0)
        
        try:
            # 1. 精确匹配
            pos = full_text.find(keyword)
            if pos != -1:
                return (pos, len(keyword))
            
            # 2. 去除标点符号后匹配
            import re
            clean_keyword = re.sub(r'[，。！？、；：""''（）《》【】]', '', keyword)
            clean_text = re.sub(r'[，。！？、；：""''（）《》【】]', '', full_text)
            pos = clean_text.find(clean_keyword)
            
            if pos != -1:
                # 反向映射到原文位置（简化处理）
                return (pos, len(clean_keyword))
            
            # 3. 模糊匹配：查找关键词的前半部分
            if len(keyword) > 10:
                partial = keyword[:min(15, len(keyword))]
                pos = full_text.find(partial)
                if pos != -1:
                    return (pos, len(partial))
            
            # 4. 未找到
            logger.debug(f"未找到关键词位置: {keyword[:30]}...")
            return (-1, 0)
            
        except Exception as e:
            logger.error(f"查找位置失败: {str(e)}")
            return (-1, 0)
    
    def generate_analysis_summary(self, analysis: Dict[str, Any]) -> str:
        """
        生成分析摘要文本
        
        Args:
            analysis: 分析结果
        
        Returns:
            格式化的摘要文本
        """
        try:
            lines = ["=== 章节分析报告 ===\n"]
            
            # 整体评分
            scores = analysis.get('scores', {})
            lines.append(f"【整体评分】")
            lines.append(f"  整体质量: {scores.get('overall', 'N/A')}/10")
            lines.append(f"  节奏把控: {scores.get('pacing', 'N/A')}/10")
            lines.append(f"  吸引力: {scores.get('engagement', 'N/A')}/10")
            lines.append(f"  连贯性: {scores.get('coherence', 'N/A')}/10\n")
            
            # 剧情阶段
            lines.append(f"【剧情阶段】{analysis.get('plot_stage', '未知')}\n")
            
            # 钩子统计
            hooks = analysis.get('hooks', [])
            if hooks:
                lines.append(f"【钩子分析】共{len(hooks)}个")
                for hook in hooks[:3]:  # 只显示前3个
                    lines.append(f"  • [{hook.get('type')}] {hook.get('content', '')[:50]}... (强度:{hook.get('strength', 0)})")
                lines.append("")
            
            # 伏笔统计
            foreshadows = analysis.get('foreshadows', [])
            if foreshadows:
                planted = sum(1 for f in foreshadows if f.get('type') == 'planted')
                resolved = sum(1 for f in foreshadows if f.get('type') == 'resolved')
                lines.append(f"【伏笔分析】埋下{planted}个, 回收{resolved}个\n")
            
            # 冲突分析
            conflict = analysis.get('conflict', {})
            if conflict:
                lines.append(f"【冲突分析】")
                lines.append(f"  类型: {', '.join(conflict.get('types', []))}")
                lines.append(f"  强度: {conflict.get('level', 0)}/10")
                lines.append(f"  进度: {int(conflict.get('resolution_progress', 0) * 100)}%\n")
            
            # 改进建议
            suggestions = analysis.get('suggestions', [])
            if suggestions:
                lines.append(f"【改进建议】")
                for i, sug in enumerate(suggestions, 1):
                    lines.append(f"  {i}. {sug}")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"❌ 生成摘要失败: {str(e)}")
            return "分析摘要生成失败"


# 创建全局实例(需要时手动初始化)
_plot_analyzer_instance = None

def get_plot_analyzer(ai_service: AIService) -> PlotAnalyzer:
    """获取剧情分析器实例"""
    global _plot_analyzer_instance
    if _plot_analyzer_instance is None:
        _plot_analyzer_instance = PlotAnalyzer(ai_service)
    return _plot_analyzer_instance