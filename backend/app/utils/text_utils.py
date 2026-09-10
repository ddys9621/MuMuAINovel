"""
文本处理工具模块
提供中英文混合文本的字数统计等功能
"""
import re


def count_words(text: str) -> int:
    """
    统计文本字数（支持中英文混合）
    
    统计规则：
    - 中文字符：每个字符计为1个字
    - 英文单词：每个单词计为1个字（连续的字母序列）
    - 数字：每个连续数字序列计为1个字
    - 标点符号和空白字符不计入字数
    
    Args:
        text: 要统计的文本
        
    Returns:
        字数统计结果
        
    Examples:
        >>> count_words("你好世界")
        4
        >>> count_words("Hello World")
        2
        >>> count_words("你好Hello世界World")
        4
        >>> count_words("2024年1月1日")
        5
    """
    if not text:
        return 0
    
    count = 0
    
    # 统计中文字符数量
    # 中文字符范围：\u4e00-\u9fff（基本汉字）
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    count += len(chinese_chars)
    
    # 移除中文字符后，统计英文单词
    text_without_chinese = re.sub(r'[\u4e00-\u9fff]', ' ', text)
    
    # 统计英文单词（连续的字母序列）
    english_words = re.findall(r'[a-zA-Z]+', text_without_chinese)
    count += len(english_words)
    
    # 统计数字序列（每个连续数字序列计为1个字）
    numbers = re.findall(r'\d+', text_without_chinese)
    count += len(numbers)
    
    return count
