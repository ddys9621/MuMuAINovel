"""JSON 清理工具 - 用于处理 AI 返回的不规范 JSON"""
import json
import re
from typing import Any, Optional
from app.logger import get_logger

logger = get_logger(__name__)


def clean_and_parse_json(
    response: str,
    expected_type: Optional[str] = None,
    log_prefix: str = ""
) -> Any:
    """
    清理并解析 AI 返回的 JSON 字符串
    
    Args:
        response: AI 返回的原始字符串
        expected_type: 期望的类型 ('object', 'array', None=自动检测)
        log_prefix: 日志前缀，用于标识调用来源
        
    Returns:
        解析后的 Python 对象（dict 或 list）
        
    Raises:
        json.JSONDecodeError: 如果清理后仍无法解析
    """
    try:
        # 第一步：基础清理
        cleaned = response.strip()
        
        # 移除 markdown 代码块标记
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:].lstrip('\n\r')
        elif cleaned.startswith('```'):
            cleaned = cleaned[3:].lstrip('\n\r')
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3].rstrip('\n\r')
        cleaned = cleaned.strip()
        
        # 第二步：提取 JSON 部分
        # 根据期望类型选择提取模式
        if expected_type == 'array':
            json_match = re.search(r'(\[[\s\S]*\])', cleaned)
        elif expected_type == 'object':
            json_match = re.search(r'(\{[\s\S]*\})', cleaned)
        else:
            # 自动检测：优先数组，其次对象
            json_match = re.search(r'(\[[\s\S]*\]|\{[\s\S]*\})', cleaned)
        
        if json_match:
            json_text = json_match.group(1)
        else:
            json_text = cleaned
        
        # 第三步：修复常见的 JSON 格式错误
        # 1. 移除对象/数组最后一个元素后的多余逗号
        json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)
        
        # 2. 移除注释（单行和多行）
        json_text = re.sub(r'//.*?$', '', json_text, flags=re.MULTILINE)
        json_text = re.sub(r'/\*.*?\*/', '', json_text, flags=re.DOTALL)
        
        # 3. 移除可能的 BOM 标记
        json_text = json_text.lstrip('\ufeff')
        
        # 记录清理信息
        if log_prefix:
            logger.debug(f"{log_prefix} - 原始长度: {len(response)}, 清理后长度: {len(json_text)}")
        
        # 第四步：解析 JSON
        result = json.loads(json_text)
        
        if log_prefix:
            result_type = type(result).__name__
            logger.debug(f"{log_prefix} - 解析成功，类型: {result_type}")
        
        return result
        
    except json.JSONDecodeError as e:
        # 记录详细的错误信息
        error_msg = f"JSON 解析失败: {str(e)}"
        if log_prefix:
            error_msg = f"{log_prefix} - {error_msg}"
        
        logger.error(error_msg)
        logger.error(f"  错误位置: line {e.lineno}, column {e.colno}")
        logger.error(f"  原始内容（前 500 字符）: {response[:500]}")
        logger.error(f"  清理后内容（前 500 字符）: {json_text[:500] if 'json_text' in locals() else 'N/A'}")
        
        raise
    
    except Exception as e:
        error_msg = f"JSON 清理/解析异常: {str(e)}"
        if log_prefix:
            error_msg = f"{log_prefix} - {error_msg}"
        
        logger.error(error_msg)
        logger.error(f"  原始内容（前 500 字符）: {response[:500]}")
        
        raise


def safe_parse_json(
    response: str,
    default: Any = None,
    expected_type: Optional[str] = None,
    log_prefix: str = ""
) -> Any:
    """
    安全地解析 JSON，失败时返回默认值而不抛出异常
    
    Args:
        response: AI 返回的原始字符串
        default: 解析失败时的默认返回值
        expected_type: 期望的类型 ('object', 'array', None=自动检测)
        log_prefix: 日志前缀
        
    Returns:
        解析后的对象，或默认值
    """
    try:
        return clean_and_parse_json(response, expected_type, log_prefix)
    except Exception as e:
        if log_prefix:
            logger.warning(f"{log_prefix} - 解析失败，使用默认值: {e}")
        else:
            logger.warning(f"JSON 解析失败，使用默认值: {e}")
        return default


async def repair_json_with_llm(
    raw_response: str,
    *,
    user_ai_service: Any,
    expected_type: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    schema_hint: Optional[str] = None,
    log_prefix: str = "",
    max_input_chars: int = 8000,
) -> Any:
    """
    LLM 二次格式修复：当本地 `clean_and_parse_json` 失败时，
    让大模型对已经生成的内容做一次"只改格式、不动内容"的修正后再次解析。

    Args:
        raw_response: 第一次生成的原始返回（可能含杂质 / 格式错误）
        user_ai_service: AIService 实例，依赖注入避免循环引用
        expected_type: 'object' / 'array' / None
        provider: AI 提供商，None 时使用 service 默认值
        model: 模型名称，None 时使用 service 默认值
        schema_hint: 可选字段提示（例如 "time_period, location, atmosphere, rules"），
                     用于约束 LLM 不要更改字段名
        log_prefix: 日志前缀
        max_input_chars: 输入字符上限，超过则截断尾部（保留头部完整结构）

    Returns:
        修复并解析后的 Python 对象（dict 或 list）

    Raises:
        ValueError / json.JSONDecodeError: 当二次修复仍无法解析
    """
    if expected_type == 'object':
        type_label = 'JSON 对象（{...}）'
    elif expected_type == 'array':
        type_label = 'JSON 数组（[...]）'
    else:
        type_label = '合法 JSON'

    schema_line = (
        f"5. 字段名必须与原文完全一致（不能新增/删除/改名）：{schema_hint}\n"
        if schema_hint else ""
    )

    # 防止 prompt 过长拖慢二次修复
    truncated = raw_response or ""
    if len(truncated) > max_input_chars:
        if log_prefix:
            logger.warning(
                f"{log_prefix} 二次修复输入过长（{len(truncated)} 字符），截断至 {max_input_chars}"
            )
        truncated = truncated[:max_input_chars] + "\n...(原始内容过长已截断)"

    repair_prompt = f"""下面这段内容是你刚刚生成的输出，但 JSON 格式存在问题，导致程序无法解析。
请严格按照以下要求修复：

1. **只修正格式问题，禁止修改、增删、概括、翻译任何字段值**；每个字段的字面文本必须与原文保持一致。
2. 仅可以做的修复：补齐缺失的引号 / 逗号 / 括号、转义内部双引号、删除多余逗号、删除注释、移除 Markdown 代码块标记（```json）、闭合未关闭的字符串等。
3. 输出必须是合法的 {type_label}，可被 `json.loads` 直接解析。
4. **只输出 JSON 本身**，不要 ```代码块```、不要任何解释或前后说明文字。
{schema_line}
【需要修复格式的原始内容】
{truncated}

请直接输出修正格式后的 JSON："""

    if log_prefix:
        logger.info(
            f"{log_prefix} 触发 LLM 二次格式修复 (raw_len={len(raw_response or '')}, "
            f"prompt_len={len(repair_prompt)})"
        )

    response = await user_ai_service.generate_text(
        prompt=repair_prompt,
        provider=provider,
        model=model,
        temperature=0.0,  # 格式修复需确定性输出
    )

    repaired_text = ""
    if isinstance(response, dict):
        repaired_text = response.get("content", "") or ""
    elif isinstance(response, str):
        repaired_text = response

    if not repaired_text.strip():
        raise ValueError("LLM 二次格式修复返回为空")

    return clean_and_parse_json(
        repaired_text,
        expected_type=expected_type,
        log_prefix=f"{log_prefix}[二次修复]" if log_prefix else "[二次修复]",
    )

