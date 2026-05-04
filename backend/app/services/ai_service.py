"""AI服务封装 - 统一的OpenAI和Claude接口"""
from typing import Optional, AsyncGenerator, List, Dict, Any
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from app.config import settings as app_settings
from app.logger import get_logger
import httpx
import json

logger = get_logger(__name__)


class AIService:
    """AI服务统一接口 - 支持从用户设置或全局配置初始化"""
    
    def __init__(
        self,
        api_provider: Optional[str] = None,
        api_key: Optional[str] = None,
        api_base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        default_temperature: Optional[float] = None,
        default_max_tokens: Optional[int] = None
    ):
        """
        初始化AI客户端（优化并发性能）
        
        Args:
            api_provider: API提供商 (openai/anthropic)，为None时使用全局配置
            api_key: API密钥，为None时使用全局配置
            api_base_url: API基础URL，为None时使用全局配置
            default_model: 默认模型，为None时使用全局配置
            default_temperature: 默认温度，为None时使用全局配置
            default_max_tokens: 默认最大tokens，为None时使用全局配置
        """
        # 保存用户设置或使用全局配置
        self.api_provider = api_provider or app_settings.default_ai_provider
        self.default_model = default_model or app_settings.default_model
        # 使用 is not None 判断，允许 temperature=0 的有效值
        self.default_temperature = default_temperature if default_temperature is not None else app_settings.default_temperature
        self.default_max_tokens = default_max_tokens if default_max_tokens is not None else app_settings.default_max_tokens

        # 标记资源是否已关闭
        self._closed = False

        # 初始化OpenAI客户端
        openai_key = api_key if api_provider == "openai" else app_settings.openai_api_key
        if openai_key:
            try:
                limits = httpx.Limits(
                    max_keepalive_connections=50,
                    max_connections=100,
                    keepalive_expiry=30.0
                )
                
                http_client = httpx.AsyncClient(
                    timeout=httpx.Timeout(connect=60.0, read=180.0, write=60.0, pool=60.0),
                    limits=limits,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    }
                )
                
                client_kwargs = {
                    "api_key": openai_key,
                    "http_client": http_client
                }
                
                base_url = api_base_url if api_provider == "openai" else app_settings.openai_base_url
                if base_url:
                    client_kwargs["base_url"] = base_url
                
                self.openai_client = AsyncOpenAI(**client_kwargs)
                self.openai_http_client = http_client
                self.openai_api_key = openai_key
                self.openai_base_url = base_url
                logger.info("✅ OpenAI客户端初始化成功")
            except Exception as e:
                logger.error(f"OpenAI客户端初始化失败: {e}")
                self.openai_client = None
                self.openai_http_client = None
                self.openai_api_key = None
                self.openai_base_url = None
        else:
            self.openai_client = None
            self.openai_http_client = None
            self.openai_api_key = None
            self.openai_base_url = None
            # 只有当用户明确选择OpenAI作为提供商时才警告
            if self.api_provider == "openai":
                logger.warning("⚠️ OpenAI API key未配置，但被设置为当前AI提供商")
        
        # 初始化Anthropic客户端
        self.anthropic_http_client = None
        anthropic_key = api_key if api_provider == "anthropic" else app_settings.anthropic_api_key
        if anthropic_key:
            try:
                limits = httpx.Limits(
                    max_keepalive_connections=50,
                    max_connections=100,
                    keepalive_expiry=30.0
                )
                
                http_client = httpx.AsyncClient(
                    timeout=httpx.Timeout(connect=60.0, read=180.0, write=60.0, pool=60.0),
                    limits=limits,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    }
                )
                
                client_kwargs = {
                    "api_key": anthropic_key,
                    "http_client": http_client
                }
                
                base_url = api_base_url if api_provider == "anthropic" else app_settings.anthropic_base_url
                if base_url:
                    client_kwargs["base_url"] = base_url
                
                self.anthropic_client = AsyncAnthropic(**client_kwargs)
                self.anthropic_http_client = http_client
                logger.info("✅ Anthropic客户端初始化成功")
            except Exception as e:
                logger.error(f"Anthropic客户端初始化失败: {e}")
                self.anthropic_client = None
                self.anthropic_http_client = None
        else:
            self.anthropic_client = None
            # 只有当用户明确选择Anthropic作为提供商时才警告
            if self.api_provider == "anthropic":
                logger.warning("⚠️ Anthropic API key未配置，但被设置为当前AI提供商")
    
    async def generate_text(
        self,
        prompt: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成文本（支持工具调用）
        
        Args:
            prompt: 用户提示词
            provider: AI提供商 (openai/anthropic)
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大token数
            system_prompt: 系统提示词
            tools: 可用工具列表（MCP工具格式）
            tool_choice: 工具选择策略 (auto/required/none)
            
        Returns:
            Dict包含:
            - content: 文本内容（如果没有工具调用）
            - tool_calls: 工具调用列表（如果AI决定调用工具）
            - finish_reason: 完成原因
        """
        provider = provider or self.api_provider
        model = model or self.default_model
        # 使用 is not None 判断，允许 temperature=0 和 max_tokens=0 的有效值
        temperature = temperature if temperature is not None else self.default_temperature
        max_tokens = max_tokens if max_tokens is not None else self.default_max_tokens

        if provider == "openai":
            return await self._generate_openai_with_tools(
                prompt, model, temperature, max_tokens, system_prompt, tools, tool_choice
            )
        elif provider == "anthropic":
            return await self._generate_anthropic_with_tools(
                prompt, model, temperature, max_tokens, system_prompt, tools, tool_choice
            )
        else:
            raise ValueError(f"不支持的AI提供商: {provider}")
    
    async def generate_text_stream(
        self,
        prompt: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        流式生成文本
        
        Args:
            prompt: 用户提示词
            provider: AI提供商
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大token数
            system_prompt: 系统提示词
            
        Yields:
            生成的文本片段
        """
        provider = provider or self.api_provider
        model = model or self.default_model
        # 使用 is not None 判断，允许 temperature=0 和 max_tokens=0 的有效值
        temperature = temperature if temperature is not None else self.default_temperature
        max_tokens = max_tokens if max_tokens is not None else self.default_max_tokens

        if provider == "openai":
            async for chunk in self._generate_openai_stream(
                prompt, model, temperature, max_tokens, system_prompt
            ):
                yield chunk
        elif provider == "anthropic":
            async for chunk in self._generate_anthropic_stream(
                prompt, model, temperature, max_tokens, system_prompt
            ):
                yield chunk
        else:
            raise ValueError(f"不支持的AI提供商: {provider}")
    
    async def _generate_openai(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        system_prompt: Optional[str]
    ) -> str:
        """使用OpenAI生成文本"""
        if not self.openai_http_client:
            raise ValueError("OpenAI客户端未初始化，请检查API key配置")
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            logger.info(f"🔵 开始调用OpenAI API（直接HTTP请求）")
            logger.info(f"  - 模型: {model}")
            logger.info(f"  - 温度: {temperature}")
            logger.info(f"  - 最大tokens: {max_tokens}")
            logger.info(f"  - Prompt长度: {len(prompt)} 字符")
            logger.info(f"  - 消息数量: {len(messages)}")
            
            url = f"{self.openai_base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.openai_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            logger.debug(f"  - 请求URL: {url}")
            logger.debug(f"  - 请求头: Authorization=Bearer ***")
            
            response = await self.openai_http_client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            logger.info(f"✅ OpenAI API调用成功")
            logger.info(f"  - 响应ID: {data.get('id', 'N/A')}")
            logger.info(f"  - 选项数量: {len(data.get('choices', []))}")
            logger.debug(f"  - 完整API响应: {data}")
            
            if not data.get('choices'):
                logger.error("❌ OpenAI返回的choices为空")
                raise ValueError("API返回的响应格式错误：choices字段为空")
            
            choice = data['choices'][0]
            message = choice.get('message', {})
            finish_reason = choice.get('finish_reason')
            
            # DeepSeek R1特殊处理：只使用content（最终答案），忽略reasoning_content（思考过程）
            # reasoning_content是AI的思考过程，不是我们需要的JSON结果
            content = message.get('content', '')
            
            # 检查是否因达到长度限制而截断
            if finish_reason == 'length':
                logger.warning(f"⚠️  响应因达到max_tokens限制而被截断")
                logger.warning(f"  - 当前max_tokens: {max_tokens}")
                logger.warning(f"  - 建议: 增加max_tokens参数（推荐2000+）")
            
            if content:
                logger.info(f"  - 返回内容长度: {len(content)} 字符")
                logger.info(f"  - 完成原因: {finish_reason}")
                logger.info(f"  - 返回内容预览（前200字符）: {content[:200]}")
                return content
            else:
                logger.error("❌ AI返回了空内容")
                logger.error(f"  - 完整响应: {data}")
                logger.error(f"  - 完成原因: {finish_reason}")
                
                # 提供更详细的错误信息
                if finish_reason == 'length':
                    raise ValueError(f"AI响应被截断且无有效内容。请增加max_tokens参数（当前: {max_tokens}，建议: 2000+）")
                else:
                    raise ValueError(f"AI返回了空内容（finish_reason: {finish_reason}），请检查API配置或稍后重试")
            
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ OpenAI API调用失败 (HTTP {e.response.status_code})")
            logger.error(f"  - 错误信息: {e.response.text}")
            logger.error(f"  - 模型: {model}")
            raise Exception(f"API返回错误 ({e.response.status_code}): {e.response.text}")
        except Exception as e:
            logger.error(f"❌ OpenAI API调用失败")
            logger.error(f"  - 错误类型: {type(e).__name__}")
            logger.error(f"  - 错误信息: {str(e)}")
            logger.error(f"  - 模型: {model}")
            raise
    

    async def _generate_openai_with_tools(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        system_prompt: Optional[str],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None
    ) -> Dict[str, Any]:
        """使用OpenAI生成文本（支持工具调用）"""
        if not self.openai_http_client:
            raise ValueError("OpenAI客户端未初始化，请检查API key配置")
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            logger.info(f"🔵 开始调用OpenAI API（支持工具调用）")
            logger.info(f"  - 模型: {model}")
            logger.info(f"  - 工具数量: {len(tools) if tools else 0}")
            
            url = f"{self.openai_base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.openai_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            # 添加工具参数
            if tools:
                payload["tools"] = tools
                logger.info(f"  - 工具数量: {len(tools)}")
                logger.info(f"  - 工具列表: {[t.get('function', {}).get('name') for t in tools]}")
                # 调试：打印第一个工具的完整定义
                if tools:
                    logger.debug(f"  - 第一个工具定义: {tools[0]}")
                if tool_choice:
                    if tool_choice == "required":
                        payload["tool_choice"] = "required"
                        logger.info(f"  - tool_choice: required（强制调用工具）")
                    elif tool_choice == "auto":
                        payload["tool_choice"] = "auto"
                        logger.info(f"  - tool_choice: auto（AI自行决定）")
                    elif tool_choice == "none":
                        payload["tool_choice"] = "none"
                        logger.info(f"  - tool_choice: none（禁用工具）")
            
            response = await self.openai_http_client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            logger.info(f"✅ OpenAI API调用成功")
            logger.debug(f"  - 完整API响应: {data}")
            
            if not data.get('choices'):
                logger.error(f"❌ API返回的choices为空")
                logger.error(f"  - 完整响应: {data}")
                logger.error(f"  - 响应键: {list(data.keys())}")
                raise ValueError(f"API返回的响应格式错误：choices字段为空。完整响应: {data}")
            
            choice = data['choices'][0]
            message = choice.get('message', {})
            finish_reason = choice.get('finish_reason')
            
            # 检查是否有工具调用
            tool_calls = message.get('tool_calls')
            if tool_calls:
                logger.info(f"🔧 AI请求调用 {len(tool_calls)} 个工具")
                for tc in tool_calls:
                    logger.info(f"   - {tc.get('function', {}).get('name')}: {tc.get('function', {}).get('arguments', '')[:100]}")
                return {
                    "tool_calls": tool_calls,
                    "content": message.get('content', ''),
                    "finish_reason": finish_reason
                }

            # 没有工具调用，返回普通内容
            content = message.get('content', '')
            if content:
                logger.info(f"AI返回文本内容（finish_reason={finish_reason}，长度={len(content)}字符）")
                return {
                    "content": content,
                    "finish_reason": finish_reason
                }
            else:
                raise ValueError(f"AI返回了空内容（finish_reason: {finish_reason}）")
            
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ OpenAI API调用失败 (HTTP {e.response.status_code})")
            logger.error(f"  - 错误信息: {e.response.text}")
            raise Exception(f"API返回错误 ({e.response.status_code}): {e.response.text}")
        except Exception as e:
            logger.error(f"❌ OpenAI API调用失败: {str(e)}")
            raise

    async def _generate_anthropic_with_tools(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        system_prompt: Optional[str],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None
    ) -> Dict[str, Any]:
        """使用Anthropic生成文本（支持工具调用）"""
        if not self.anthropic_client:
            raise ValueError("Anthropic客户端未初始化，请检查API key配置")
        
        try:
            logger.info(f"🔵 开始调用Anthropic API（支持工具调用）")
            logger.info(f"  - 模型: {model}")
            logger.info(f"  - 工具数量: {len(tools) if tools else 0}")
            
            kwargs = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}]
            }
            
            if system_prompt:
                kwargs["system"] = system_prompt
            
            # 添加工具参数
            if tools:
                kwargs["tools"] = tools
                if tool_choice == "required":
                    kwargs["tool_choice"] = {"type": "any"}
                elif tool_choice == "auto":
                    kwargs["tool_choice"] = {"type": "auto"}
            
            response = await self.anthropic_client.messages.create(**kwargs)
            
            # 检查是否有工具调用
            tool_calls = []
            content_text = ""
            
            for block in response.content:
                if block.type == "tool_use":
                    tool_calls.append({
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": block.input
                        }
                    })
                elif block.type == "text":
                    content_text += block.text
            
            if tool_calls:
                logger.info(f"🔧 AI请求调用 {len(tool_calls)} 个工具")
                return {
                    "tool_calls": tool_calls,
                    "content": content_text,
                    "finish_reason": response.stop_reason
                }
            
            return {
                "content": content_text,
                "finish_reason": response.stop_reason
            }
            
        except Exception as e:
            logger.error(f"❌ Anthropic API调用失败: {str(e)}")
            raise

    async def _generate_openai_stream(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        system_prompt: Optional[str]
    ) -> AsyncGenerator[str, None]:
        """使用OpenAI流式生成文本"""
        if not self.openai_http_client:
            raise ValueError("OpenAI客户端未初始化，请检查API key配置")
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            logger.info(f"🔵 开始调用OpenAI流式API（直接HTTP请求）")
            logger.info(f"  - 模型: {model}")
            logger.info(f"  - Prompt长度: {len(prompt)} 字符")
            logger.info(f"  - 最大tokens: {max_tokens}")
            
            url = f"{self.openai_base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.openai_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True
            }
            
            async with self.openai_http_client.stream('POST', url, headers=headers, json=payload) as response:
                response.raise_for_status()
                logger.info(f"✅ OpenAI流式API连接成功，开始接收数据...")
                
                chunk_count = 0
                has_content = False
                finish_reason = None
                
                async for line in response.aiter_lines():
                    if line.startswith('data: '):
                        data_str = line[6:]
                        if data_str.strip() == '[DONE]':
                            break
                        
                        try:
                            import json
                            data = json.loads(data_str)
                            if 'choices' in data and len(data['choices']) > 0:
                                choice = data['choices'][0]
                                delta = choice.get('delta', {})
                                finish_reason = choice.get('finish_reason') or finish_reason
                                
                                # DeepSeek R1特殊处理：只收集content（最终答案），忽略reasoning_content（思考过程）
                                # reasoning_content是AI的思考过程，不是我们需要的JSON结果
                                content = delta.get('content', '')
                                
                                if content:
                                    chunk_count += 1
                                    has_content = True
                                    yield content
                        except json.JSONDecodeError:
                            continue
                
                # 检查是否因长度限制截断
                if finish_reason == 'length':
                    logger.warning(f"⚠️  流式响应因达到max_tokens限制而被截断")
                    logger.warning(f"  - 当前max_tokens: {max_tokens}")
                    logger.warning(f"  - 建议: 增加max_tokens参数（推荐2000+）")
                
                if not has_content:
                    logger.warning(f"⚠️  流式响应未返回任何内容")
                    logger.warning(f"  - 完成原因: {finish_reason}")
                
                logger.info(f"✅ OpenAI流式生成完成，共接收 {chunk_count} 个chunk，完成原因: {finish_reason}")
            
        except httpx.TimeoutException as e:
            logger.error(f"❌ OpenAI流式API超时")
            logger.error(f"  - 错误: {str(e)}")
            logger.error(f"  - 提示: 请检查网络连接或考虑缩短prompt长度")
            raise TimeoutError(f"AI服务超时（180秒），请稍后重试或减少上下文长度") from e
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ OpenAI流式API调用失败 (HTTP {e.response.status_code})")
            logger.error(f"  - 错误信息: {await e.response.aread()}")
            raise
        except Exception as e:
            logger.error(f"❌ OpenAI流式API调用失败: {str(e)}")
            logger.error(f"  - 错误类型: {type(e).__name__}")
            raise
    
    async def _generate_anthropic(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        system_prompt: Optional[str]
    ) -> str:
        """使用Anthropic生成文本"""
        if not self.anthropic_client:
            raise ValueError("Anthropic客户端未初始化，请检查API key配置")
        
        try:
            response = await self.anthropic_client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt or "",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Anthropic API调用失败: {str(e)}")
            raise
    
    async def _generate_anthropic_stream(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        system_prompt: Optional[str]
    ) -> AsyncGenerator[str, None]:
        """使用Anthropic流式生成文本"""
        if not self.anthropic_client:
            raise ValueError("Anthropic客户端未初始化，请检查API key配置")
        
        try:
            logger.info(f"🔵 开始调用Anthropic流式API")
            logger.info(f"  - 模型: {model}")
            logger.info(f"  - Prompt长度: {len(prompt)} 字符")
            logger.info(f"  - 最大tokens: {max_tokens}")
            
            async with self.anthropic_client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt or "",
                messages=[{"role": "user", "content": prompt}]
            ) as stream:
                logger.info(f"✅ Anthropic流式API连接成功，开始接收数据...")
                
                chunk_count = 0
                async for text in stream.text_stream:
                    chunk_count += 1
                    yield text
                
                logger.info(f"✅ Anthropic流式生成完成，共接收 {chunk_count} 个chunk")
                
        except httpx.TimeoutException as e:
            logger.error(f"❌ Anthropic流式API超时")
            logger.error(f"  - 错误: {str(e)}")
            raise TimeoutError(f"AI服务超时（180秒），请稍后重试或减少上下文长度") from e
        except Exception as e:
            logger.error(f"❌ Anthropic流式API调用失败: {str(e)}")
            logger.error(f"  - 错误类型: {type(e).__name__}")
            raise
    
    async def generate_text_with_mcp(
        self,
        prompt: str,
        user_id: str,
        db_session,
        enable_mcp: bool = True,
        selected_plugins: Optional[List[str]] = None,
        max_tool_rounds: int = 3,
        tool_choice: str = "auto",
        context: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        context_prefix = f"[{context}] " if context else ""
        logger.info(f"{context_prefix}generate_text_with_mcp 开始调用: tool_choice={tool_choice}, enable_mcp={enable_mcp}")
        """
        支持MCP工具的AI文本生成（非流式）
        
        Args:
            prompt: 用户提示词
            user_id: 用户ID，用于获取MCP工具
            db_session: 数据库会话
            enable_mcp: 是否启用MCP增强
            selected_plugins: 指定使用的插件名称列表
            max_tool_rounds: 最大工具调用轮次
            tool_choice: 工具选择策略（auto/required/none）
            context: 调用上下文标识（用于日志标记）
            **kwargs: 其他AI参数（provider, model, temperature等）
        
        Returns:
            {
                "content": "AI生成的最终文本",
                "tool_calls_made": 2,  # 实际调用的工具次数
                "tools_used": ["exa_search", "filesystem_read"],
                "finish_reason": "stop",
                "mcp_enhanced": True
            }
        """
        from app.services.mcp_tool_service import mcp_tool_service, MCPToolServiceError
        
        # 初始化返回结果
        result = {
            "content": "",
            "tool_calls_made": 0,
            "tools_used": [],
            "finish_reason": "",
            "mcp_enhanced": False
        }
        
        # 1. 获取MCP工具（如果启用）
        tools = None
        if enable_mcp:
            try:
                tools = await mcp_tool_service.get_user_enabled_tools(
                    user_id=user_id,
                    db_session=db_session,
                    plugin_names=selected_plugins
                )
                if tools:
                    context_prefix = f"[{context}] " if context else ""
                    logger.info(f"{context_prefix}MCP增强: 加载了 {len(tools)} 个工具")
                    result["mcp_enhanced"] = True
            except MCPToolServiceError as e:
                logger.error(f"获取MCP工具失败，降级为普通生成: {e}")
                tools = None
        
        # 2. 工具调用循环
        conversation_history = [
            {"role": "user", "content": prompt}
        ]
        
        for round_num in range(max_tool_rounds):
            context_prefix = f"[{context}] " if context else ""
            logger.info(f"{context_prefix}MCP工具调用轮次: {round_num + 1}/{max_tool_rounds}")
            
            # 调试日志
            if round_num == 0:
                logger.info(f"{context_prefix}工具数量: {len(tools) if tools else 0}")
                logger.info(f"{context_prefix}tool_choice: {tool_choice}")
            
            # 调用AI
            ai_response = await self.generate_text(
                prompt=conversation_history[-1]["content"],
                tools=tools if round_num == 0 else None,  # 只在第一轮传递工具
                tool_choice=tool_choice if round_num == 0 else None,
                **kwargs
            )
            
            # 检查是否有工具调用
            tool_calls = ai_response.get("tool_calls", [])
            context_prefix = f"[{context}] " if context else ""
            logger.info(f"{context_prefix}AI响应检查: tool_calls数量={len(tool_calls)}, finish_reason={ai_response.get('finish_reason', 'unknown')}")
            
            if not tool_calls:
                # AI返回最终内容
                if round_num == 0 and tool_choice == "required":
                    # 第一轮强制工具调用失败
                    logger.warning(f"{context_prefix}⚠️ 第一轮强制工具调用失败！AI未调用工具，直接返回内容")
                    logger.warning(f"{context_prefix}   finish_reason={ai_response.get('finish_reason')}")
                    logger.warning(f"{context_prefix}   内容预览: {ai_response.get('content', '')[:200]}")
                else:
                    # 后续轮次正常返回最终内容
                    logger.info(f"{context_prefix}AI完成任务，返回最终内容（长度：{len(ai_response.get('content', ''))} 字符）")

                result["content"] = ai_response.get("content", "")
                result["finish_reason"] = ai_response.get("finish_reason", "stop")
                break
            
            # 3. 执行工具调用
            logger.info(f"AI请求调用 {len(tool_calls)} 个工具")
            
            try:
                tool_results = await mcp_tool_service.execute_tool_calls(
                    user_id=user_id,
                    tool_calls=tool_calls,
                    db_session=db_session
                )
                
                # 记录使用的工具
                for tool_call in tool_calls:
                    tool_name = tool_call["function"]["name"]
                    if tool_name not in result["tools_used"]:
                        result["tools_used"].append(tool_name)
                
                result["tool_calls_made"] += len(tool_calls)
                
                # 4. 构建工具上下文
                tool_context = await mcp_tool_service.build_tool_context(
                    tool_results,
                    format="markdown"
                )
                
                # 5. 更新对话历史
                conversation_history.append({
                    "role": "assistant",
                    "content": ai_response.get("content", ""),
                    "tool_calls": tool_calls
                })
                
                for tool_result in tool_results:
                    conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tool_result["tool_call_id"],
                        "content": tool_result["content"]
                    })
                
                # 6. 构建下一轮提示
                next_prompt = (
                    f"{prompt}\n\n"
                    f"{tool_context}\n\n"
                    f"请基于以上工具查询结果，继续完成任务。"
                )
                conversation_history.append({
                    "role": "user",
                    "content": next_prompt
                })
                
            except Exception as e:
                logger.error(f"执行MCP工具失败: {e}", exc_info=True)
                # 降级：返回当前AI响应
                result["content"] = ai_response.get("content", "")
                result["finish_reason"] = "tool_error"
                break
        
        else:
            # 达到最大轮次
            logger.warning(f"达到MCP最大调用轮次 {max_tool_rounds}")
            result["content"] = conversation_history[-1].get("content", "")
            result["finish_reason"] = "max_rounds"
        
        return result
    
    async def generate_text_stream_with_mcp(
        self,
        prompt: str,
        user_id: str,
        db_session,
        enable_mcp: bool = True,
        mcp_planning_prompt: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        支持MCP工具的AI流式文本生成（两阶段模式）
        
        Args:
            prompt: 用户提示词
            user_id: 用户ID
            db_session: 数据库会话
            enable_mcp: 是否启用MCP增强
            mcp_planning_prompt: MCP规划阶段的提示词（可选）
            **kwargs: 其他AI参数
        
        Yields:
            流式文本chunk
        """
        from app.services.mcp_tool_service import mcp_tool_service
        
        # 阶段1: 工具调用阶段（非流式）
        enhanced_prompt = prompt
        
        if enable_mcp:
            try:
                # 获取MCP工具
                tools = await mcp_tool_service.get_user_enabled_tools(
                    user_id=user_id,
                    db_session=db_session
                )
                
                if tools:
                    logger.info(f"MCP增强（流式）: 加载了 {len(tools)} 个工具")
                    
                    # 使用规划提示让AI决定需要查询什么
                    if not mcp_planning_prompt:
                        mcp_planning_prompt = (
                            f"任务: {prompt}\n\n"
                            f"请分析这个任务，决定是否需要查询外部信息。"
                            f"如果需要，请调用相应的工具获取信息。\n\n"
                            f"工具调用注意事项：\n"
                            f"1. 所有参数必须是有效的非空值\n"
                            f"2. query 参数必须是具体的搜索关键词字符串\n"
                            f"3. 如果不需要搜索，可以不调用工具"
                        )
                    
                    # 非流式调用获取工具结果
                    planning_result = await self.generate_text_with_mcp(
                        prompt=mcp_planning_prompt,
                        user_id=user_id,
                        db_session=db_session,
                        enable_mcp=True,
                        max_tool_rounds=2,
                        tool_choice="auto",
                        **kwargs
                    )
                    
                    # 如果有工具调用，将结果融入提示
                    if planning_result["tool_calls_made"] > 0:
                        enhanced_prompt = (
                            f"{prompt}\n\n"
                            f"【参考资料】\n"
                            f"{planning_result.get('content', '')}"
                        )
                        logger.info(
                            f"MCP工具规划完成，调用了 "
                            f"{planning_result['tool_calls_made']} 次工具"
                        )
            
            except Exception as e:
                logger.error(f"MCP工具规划失败，使用原始提示: {e}")
        
        # 阶段2: 内容生成阶段（流式）
        async for chunk in self.generate_text_stream(
            prompt=enhanced_prompt,
            **kwargs
        ):
            yield chunk

    async def close(self):
        """关闭所有HTTP客户端连接，释放资源

        应在应用关闭时调用此方法，防止HTTP连接泄漏
        """
        if self._closed:
            return

        self._closed = True

        if self.openai_http_client:
            try:
                await self.openai_http_client.aclose()
                logger.info("✅ OpenAI HTTP客户端已关闭")
            except Exception as e:
                logger.error(f"关闭OpenAI HTTP客户端失败: {e}")

        if self.anthropic_http_client:
            try:
                await self.anthropic_http_client.aclose()
                logger.info("✅ Anthropic HTTP客户端已关闭")
            except Exception as e:
                logger.error(f"关闭Anthropic HTTP客户端失败: {e}")


# 创建全局AI服务实例
ai_service = AIService()


def create_user_ai_service(
    api_provider: str,
    api_key: str,
    api_base_url: str,
    model_name: str,
    temperature: float,
    max_tokens: int
) -> AIService:
    """
    根据用户设置创建AI服务实例
    
    Args:
        api_provider: API提供商
        api_key: API密钥
        api_base_url: API基础URL
        model_name: 模型名称
        temperature: 温度参数
        max_tokens: 最大tokens
        
    Returns:
        AIService实例
    """
    return AIService(
        api_provider=api_provider,
        api_key=api_key,
        api_base_url=api_base_url,
        default_model=model_name,
        default_temperature=temperature,
        default_max_tokens=max_tokens
    )
