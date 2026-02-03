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

