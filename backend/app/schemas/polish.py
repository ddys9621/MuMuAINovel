"""AI去味相关的Pydantic模型"""
from pydantic import BaseModel, Field
from typing import Optional


class PolishRequest(BaseModel):
    """AI去味请求模型"""
    original_text: str = Field(..., description="原始文本（AI生成的文本）")
    project_id: Optional[int] = Field(None, description="项目ID（可选，用于记录历史）")
    provider: Optional[str] = Field(None, description="AI提供商")
    model: Optional[str] = Field(None, description="AI模型")
    temperature: Optional[float] = Field(0.8, description="温度参数，建议0.7-0.9")


class PolishResponse(BaseModel):
    """AI去味响应模型"""
    original_text: str = Field(..., description="原始文本")
    polished_text: str = Field(..., description="去味后的文本")
    word_count_before: int = Field(..., description="处理前字数")
    word_count_after: int = Field(..., description="处理后字数")