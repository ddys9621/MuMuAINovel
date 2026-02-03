"""灵感模式API - 通过对话引导创建项目"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
import json

from app.database import get_db
from app.services.ai_service import AIService
from app.api.settings import get_user_ai_service
from app.logger import get_logger

router = APIRouter(prefix="/inspiration", tags=["灵感模式"])
logger = get_logger(__name__)


# 灵感模式提示词模板
INSPIRATION_PROMPTS = {
    "title": {
        "system": """你是一位专业的小说创作顾问。
用户想写的小说：{description}

请根据用户的想法，生成6个吸引人的书名建议，要求：
1. 符合用户的故事构思
2. 富有创意和吸引力
3. 涵盖不同的风格倾向

返回JSON格式：
{{
    "prompt": "根据你的想法，我为你准备了几个书名建议：",
    "options": ["书名1", "书名2", "书名3", "书名4", "书名5", "书名6"]
}}

只返回纯JSON，不要有其他文字。""",
        "user": "用户的想法：{description}\n请生成6个书名建议"
    },
    
    "description": {
        "system": """你是一位专业的小说创作顾问。
用户已经确定了书名：{title}

请生成6个精彩的小说简介，要求：
1. 符合书名风格
2. 简洁有力，每个50-100字
3. 包含核心冲突
4. 涵盖不同的故事走向

返回JSON格式：
{{"prompt":"选择一个简介：","options":["简介1","简介2","简介3","简介4","简介5","简介6"]}}

只返回纯JSON，不要有其他文字，不要换行。""",
        "user": "书名是：{title}，请生成6个简介选项"
    },
    
    "theme": {
        "system": """你是一位专业的小说创作顾问。
用户的小说信息：
- 书名：{title}
- 简介：{description}

请生成6个深刻的主题选项，要求：
1. 符合书名和简介的风格
2. 有深度和思想性
3. 每个50-150字
4. 涵盖不同角度（如：成长、复仇、救赎、探索等）

返回JSON格式：
{{"prompt":"这本书的核心主题是什么？","options":["主题1","主题2","主题3","主题4","主题5","主题6"]}}

只返回纯JSON，不要有其他文字，不要换行。""",
        "user": "书名：{title}\n简介：{description}\n请生成6个主题选项"
    },
    
    "genre": {
        "system": """你是一位专业的小说创作顾问。
用户的小说信息：
- 书名：{title}
- 简介：{description}
- 主题：{theme}

请生成6个合适的类型标签（每个2-4字），要求：
1. 符合小说整体风格
2. 可以多选组合

常见类型：玄幻、都市、科幻、武侠、仙侠、历史、言情、悬疑、奇幻、修仙等

返回JSON格式：
{{"prompt":"选择类型标签（可多选）：","options":["类型1","类型2","类型3","类型4","类型5","类型6"]}}

只返回紧凑的纯JSON，不要换行，不要有其他文字。""",
        "user": "书名：{title}\n简介：{description}\n主题：{theme}\n请生成6个类型标签"
    }
}


def validate_options_response(result: Dict[str, Any], step: str, max_retries: int = 3) -> tuple[bool, str]:
    """
    校验AI返回的选项格式是否正确
    
    Returns:
        (is_valid, error_message)
    """
    # 检查必需字段
    if "options" not in result:
        return False, "缺少options字段"
    
    options = result.get("options", [])
    
    # 检查options是否为数组
    if not isinstance(options, list):
        return False, "options必须是数组"
    
    # 检查数组长度
    if len(options) < 3:
        return False, f"选项数量不足，至少需要3个，当前只有{len(options)}个"
    
    if len(options) > 10:
        return False, f"选项数量过多，最多10个，当前有{len(options)}个"
    
    # 检查每个选项是否为字符串且不为空
    for i, option in enumerate(options):
        if not isinstance(option, str):
            return False, f"第{i+1}个选项不是字符串类型"
        if not option.strip():
            return False, f"第{i+1}个选项为空"
        if len(option) > 500:
            return False, f"第{i+1}个选项过长（超过500字符）"
    
    # 根据不同步骤进行特定校验
    if step == "genre":
        # 类型标签应该比较短
        for i, option in enumerate(options):
            if len(option) > 10:
                return False, f"类型标签【{option}】过长，应该在2-10字之间"
    
    return True, ""


@router.post("/generate-options")
async def generate_options(
    data: Dict[str, Any],
    ai_service: AIService = Depends(get_user_ai_service)
) -> Dict[str, Any]:
    """
    根据当前收集的信息生成下一步的选项建议（带自动重试）
    
    Request:
        {
            "step": "title",  // title/description/theme/genre
            "context": {
                "title": "...",
                "description": "...",
                "theme": "..."
            }
        }
    
    Response:
        {
            "prompt": "引导语",
            "options": ["选项1", "选项2", ...]
        }
    """
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            step = data.get("step", "title")
            context = data.get("context", {})
            
            logger.info(f"灵感模式：生成{step}阶段的选项（第{attempt + 1}次尝试）")
            
            # 获取对应的提示词模板
            if step not in INSPIRATION_PROMPTS:
                return {
                    "error": f"不支持的步骤: {step}",
                    "prompt": "",
                    "options": []
                }
            
            prompt_template = INSPIRATION_PROMPTS[step]
            
            # 准备格式化参数（提供默认值避免KeyError）
            format_params = {
                "title": context.get("title", ""),
                "description": context.get("description", ""),
                "theme": context.get("theme", "")
            }
            
            # 格式化系统提示词
            system_prompt = prompt_template["system"].format(**format_params)
            user_prompt = prompt_template["user"].format(**format_params)
            
            # 如果是重试，在提示词中强调格式要求
            if attempt > 0:
                system_prompt += f"\n\n⚠️ 这是第{attempt + 1}次生成，请务必严格按照JSON格式返回，确保options数组包含6个有效选项！"
            
            # 调用AI生成选项
            logger.info(f"调用AI生成{step}选项...")
            response = await ai_service.generate_text(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.8  # 提高创造性
            )
            
            content = response.get("content", "")
            logger.info(f"AI返回内容长度: {len(content)}")
            
            # 解析JSON
            try:
                # 清理可能的markdown标记
                cleaned_content = content.strip()
                if cleaned_content.startswith('```json'):
                    cleaned_content = cleaned_content[7:].lstrip('\n\r')
                elif cleaned_content.startswith('```'):
                    cleaned_content = cleaned_content[3:].lstrip('\n\r')
                if cleaned_content.endswith('```'):
                    cleaned_content = cleaned_content[:-3].rstrip('\n\r')
                cleaned_content = cleaned_content.strip()
                
                # 检查JSON是否完整
                if not cleaned_content.endswith('}'):
                    logger.warning(f"⚠️ JSON可能被截断，尝试补全...")
                    if '"options"' in cleaned_content:
                        if cleaned_content.count('[') > cleaned_content.count(']'):
                            cleaned_content += '"]}'
                        elif cleaned_content.count('{') > cleaned_content.count('}'):
                            cleaned_content += '}'
                
                result = json.loads(cleaned_content)
                
                # 校验返回格式
                is_valid, error_msg = validate_options_response(result, step)
                
                if not is_valid:
                    logger.warning(f"⚠️ 第{attempt + 1}次生成格式校验失败: {error_msg}")
                    if attempt < max_retries - 1:
                        logger.info("准备重试...")
                        continue  # 重试
                    else:
                        # 最后一次尝试也失败了
                        return {
                            "prompt": f"请为【{step}】提供内容：",
                            "options": ["让AI重新生成", "我自己输入"],
                            "error": f"AI生成格式错误（{error_msg}），已自动重试{max_retries}次，请手动重试或自己输入"
                        }
                
                logger.info(f"✅ 第{attempt + 1}次成功生成{len(result.get('options', []))}个有效选项")
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"第{attempt + 1}次JSON解析失败: {e}")
                
                if attempt < max_retries - 1:
                    logger.info("JSON解析失败，准备重试...")
                    continue  # 重试
                else:
                    # 最后一次尝试也失败了
                    return {
                        "prompt": f"请为【{step}】提供内容：",
                        "options": ["让AI重新生成", "我自己输入"],
                        "error": f"AI返回格式错误，已自动重试{max_retries}次，请手动重试或自己输入"
                    }
        
        except Exception as e:
            logger.error(f"第{attempt + 1}次生成失败: {e}", exc_info=True)
            if attempt < max_retries - 1:
                logger.info("发生异常，准备重试...")
                continue
            else:
                return {
                    "error": str(e),
                    "prompt": "生成失败，请重试",
                    "options": ["重新生成", "我自己输入"]
                }
    
    # 理论上不会到这里
    return {
        "error": "生成失败",
        "prompt": "请重试",
        "options": []
    }


@router.post("/quick-generate")
async def quick_generate(
    data: Dict[str, Any],
    ai_service: AIService = Depends(get_user_ai_service)
) -> Dict[str, Any]:
    """
    智能补全：根据用户已提供的部分信息，AI自动补全缺失字段
    
    Request:
        {
            "title": "书名（可选）",
            "description": "简介（可选）",
            "theme": "主题（可选）",
            "genre": ["类型1", "类型2"]（可选）
        }
    
    Response:
        {
            "title": "补全的书名",
            "description": "补全的简介",
            "theme": "补全的主题",
            "genre": ["补全的类型"]
        }
    """
    try:
        logger.info("灵感模式：智能补全")
        
        # 构建补全提示词
        existing_info = []
        if data.get("title"):
            existing_info.append(f"- 书名：{data['title']}")
        if data.get("description"):
            existing_info.append(f"- 简介：{data['description']}")
        if data.get("theme"):
            existing_info.append(f"- 主题：{data['theme']}")
        if data.get("genre"):
            existing_info.append(f"- 类型：{', '.join(data['genre'])}")
        
        existing_text = "\n".join(existing_info) if existing_info else "暂无信息"
        
        system_prompt = """你是一位专业的小说创作顾问。用户提供了部分小说信息，请补全缺失的字段。

用户已提供的信息：
{existing}

请生成完整的小说方案，包含：
1. title: 书名（3-6字，如果用户已提供则保持原样）
2. description: 简介（50-100字）
3. theme: 核心主题（30-50字）
4. genre: 类型标签数组（2-3个）

返回JSON格式：
{{
    "title": "书名",
    "description": "简介内容...",
    "theme": "主题内容...",
    "genre": ["类型1", "类型2"]
}}

只返回纯JSON，不要有其他文字。"""
        
        user_prompt = "请补全小说信息"
        
        # 调用AI
        response = await ai_service.generate_text(
            prompt=user_prompt,
            system_prompt=system_prompt.format(existing=existing_text),
            temperature=0.7
        )
        
        content = response.get("content", "")
        
        # 使用统一的 JSON 清理工具解析 AI 响应
        from app.utils.json_cleaner import clean_and_parse_json

        try:
            result = clean_and_parse_json(
                content,
                expected_type='object',
                log_prefix="[灵感补全]"
            )
            
            # 合并用户已提供的信息（用户输入优先）
            final_result = {
                "title": data.get("title") or result.get("title", ""),
                "description": data.get("description") or result.get("description", ""),
                "theme": data.get("theme") or result.get("theme", ""),
                "genre": data.get("genre") or result.get("genre", [])
            }
            
            logger.info(f"✅ 智能补全成功")
            return final_result
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            raise Exception("AI返回格式错误，请重试")
    
    except Exception as e:
        logger.error(f"智能补全失败: {e}", exc_info=True)
        return {
            "error": str(e)
        }