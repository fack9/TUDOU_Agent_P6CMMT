import json
from dataclasses import dataclass
from typing import Any
from ..types import LLMResponse, ToolCall, TokenUsage

@dataclass
class AnthropicProvider:
    api_key: str | None = None
    base_url: str | None = None
    max_tokens: int = 8192

    def __post_init__(self):
        import anthropic
        import os
        key = self.api_key or os.environ.get('ANTHROPIC_API_KEY')
        if not key:
            raise ValueError('Anthropic API key required. Set ANTHROPIC_API_KEY env var or configure providers.anthropic.api_key in config.')
        kwargs = {'api_key': key}
        if self.base_url:
            kwargs['base_url'] = self.base_url
        self._client = anthropic.Anthropic(**kwargs)

    def complete(self, messages: list[dict], tools: list[dict] | None=None, model: str='claude-sonnet-4-6-20250514', on_token=None, thinking_budget: int | None=None, prompt_caching: bool=True, response_format: str | None=None, tool_choice: str='auto') -> LLMResponse:
        if on_token is not None:
            return self._complete_stream(messages, tools=tools, model=model, on_token=on_token, thinking_budget=thinking_budget, prompt_caching=prompt_caching, tool_choice=tool_choice)

        def _call(use_cache: bool):
            system, chat_messages = self._split_system(messages, prompt_caching=use_cache)
            anthropic_tools = self._convert_tools(tools, prompt_caching=use_cache) if tools else None
            if system:
                system_block = [{'type': 'text', 'text': system}]
                if use_cache:
                    system_block[0]['cache_control'] = {'type': 'ephemeral'}
                system = system_block
            kwargs = dict(model=model, max_tokens=self.max_tokens, messages=chat_messages)
            if system:
                kwargs['system'] = system
            if anthropic_tools:
                kwargs['tools'] = anthropic_tools
            if thinking_budget:
                kwargs['thinking'] = {'type': 'enabled', 'budget_tokens': thinking_budget}
            if tool_choice and tool_choice != 'auto':
                if isinstance(tool_choice, dict):
                    kwargs['tool_choice'] = tool_choice
                else:
                    kwargs['tool_choice'] = {'type': tool_choice}
            if response_format:
                kwargs['response_format'] = response_format if isinstance(response_format, dict) else {'type': response_format}
            return self._client.messages.create(**kwargs), model

        if prompt_caching:
            try:
                response, _ = _call(True)
                return self._parse_response(response, model)
            except Exception as e:
                if self._is_cache_error(e):
                    response, _ = _call(False)
                    return self._parse_response(response, model)
                raise
        response, _ = _call(False)
        return self._parse_response(response, model)

    def _complete_stream(self, messages: list[dict], tools: list[dict] | None, model: str, on_token, thinking_budget: int | None=None, prompt_caching: bool=True, tool_choice: str='auto') -> LLMResponse:
        def _build_kwargs(use_cache: bool):
            system, chat_messages = self._split_system(messages, prompt_caching=use_cache)
            anthropic_tools = self._convert_tools(tools, prompt_caching=use_cache) if tools else None
            if system:
                system_block = [{'type': 'text', 'text': system}]
                if use_cache:
                    system_block[0]['cache_control'] = {'type': 'ephemeral'}
                system = system_block
            kwargs = dict(model=model, max_tokens=self.max_tokens, messages=chat_messages, stream=True)
            if system:
                kwargs['system'] = system
            if anthropic_tools:
                kwargs['tools'] = anthropic_tools
            if thinking_budget:
                kwargs['thinking'] = {'type': 'enabled', 'budget_tokens': thinking_budget}
            if tool_choice and tool_choice != 'auto':
                if isinstance(tool_choice, dict):
                    kwargs['tool_choice'] = tool_choice
                else:
                    kwargs['tool_choice'] = {'type': tool_choice}
            if response_format:
                kwargs['response_format'] = response_format if isinstance(response_format, dict) else {'type': response_format}
            return kwargs

        if prompt_caching:
            try:
                stream = self._client.messages.create(**_build_kwargs(True))
            except Exception as e:
                if self._is_cache_error(e):
                    stream = self._client.messages.create(**_build_kwargs(False))
                else:
                    raise
        else:
            stream = self._client.messages.create(**_build_kwargs(False))
        content = ''
        tool_calls = []
        reasoning_parts = []
        input_tokens = 0
        output_tokens = 0
        cache_read = 0
        cache_write = 0
        stop_reason = 'end_turn'
        cur_type = None
        cur_text = ''
        cur_thinking_text = ''
        cur_tool_id = None
        cur_tool_name = None
        cur_tool_json = ''
        for event in stream:
            et = event.type
            if et == 'message_start':
                if hasattr(event.message, 'usage') and event.message.usage:
                    usage = event.message.usage
                    input_tokens = usage.input_tokens
                    cache_read = getattr(usage, 'cache_read_input_tokens', 0)
                    cache_write = getattr(usage, 'cache_creation_input_tokens', 0)
            elif et == 'content_block_start':
                block = event.content_block
                if block.type == 'text':
                    cur_type = 'text'
                    cur_text = ''
                elif block.type == 'tool_use':
                    cur_type = 'tool_use'
                    cur_tool_id = block.id
                    cur_tool_name = block.name
                    cur_tool_json = ''
                elif block.type == 'thinking':
                    cur_type = 'thinking'
                    cur_thinking_text = ''
                elif block.type == 'redacted_thinking':
                    cur_type = 'redacted_thinking'
                    cur_thinking_text = ''
            elif et == 'content_block_delta':
                delta = event.delta
                if delta.type == 'text_delta':
                    cur_text += delta.text
                    if on_token:
                        on_token(delta.text)
                elif delta.type == 'input_json_delta':
                    cur_tool_json += delta.partial_json
                elif delta.type == 'thinking_delta':
                    cur_thinking_text += delta.thinking
                elif delta.type == 'signature_delta':
                    pass
            elif et == 'content_block_stop':
                if cur_type == 'text':
                    content += cur_text
                elif cur_type == 'tool_use':
                    try:
                        arguments = json.loads(cur_tool_json)
                    except json.JSONDecodeError:
                        arguments = {}
                    tool_calls.append(ToolCall(id=cur_tool_id, name=cur_tool_name, arguments=arguments))
                elif cur_type == 'thinking':
                    if cur_thinking_text:
                        reasoning_parts.append(cur_thinking_text)
                elif cur_type == 'redacted_thinking':
                    reasoning_parts.append('[redacted]')
                cur_type = None
            elif et == 'message_delta':
                stop_reason = event.delta.stop_reason or 'end_turn'
                if hasattr(event, 'usage') and event.usage:
                    output_tokens = event.usage.output_tokens
        reasoning = '\n'.join(reasoning_parts) if reasoning_parts else ''
        return LLMResponse(content=content, tool_calls=tool_calls if tool_calls else None, usage=TokenUsage(input=input_tokens, output=output_tokens, cache_read=cache_read, cache_write=cache_write), model=model, finish_reason=stop_reason, reasoning_content=reasoning)

    def count_tokens(self, messages: list[dict]) -> int:
        try:
            system, chat_messages = self._split_system(messages)
            kwargs = dict(model='claude-sonnet-4-6-20250514', messages=chat_messages)
            if system:
                kwargs['system'] = system
            resp = self._client.messages.count_tokens(**kwargs)
            return resp.input_tokens
        except Exception:
            return self._estimate_tokens(messages)

    def _split_system(self, messages: list[dict], prompt_caching: bool = False) -> tuple[str | None, list[dict]]:
        system_parts = []
        chat = []
        for msg in messages:
            if msg['role'] == 'system':
                content = msg.get('content', '')
                if isinstance(content, str):
                    system_parts.append(content)
            else:
                chat.append(self._convert_message(msg))
        system = '\n\n'.join(system_parts) if system_parts else None
        if system is not None and len(system.strip()) == 0:
            system = None

        # Cache stable conversation history: cache all but the last 3 messages
        # (last turn's assistant + tool_result + current user query)
        if prompt_caching and len(chat) >= 5:
            cache_idx = len(chat) - 3
            content = chat[cache_idx].get('content', '')
            if isinstance(content, str) and content:
                chat[cache_idx]['content'] = [
                    {'type': 'text', 'text': content, 'cache_control': {'type': 'ephemeral'}}
                ]
            elif isinstance(content, list) and content:
                content[-1]['cache_control'] = {'type': 'ephemeral'}

        return (system, chat)

    def _convert_message(self, msg: dict) -> dict:
        role = msg['role']
        content = msg.get('content', '')

        # Convert list content blocks (images etc.) to Anthropic format
        converted = self._convert_content(content)

        if role == 'tool':
            tool_result = {'type': 'tool_result', 'tool_use_id': msg.get('tool_call_id', ''), 'content': converted}
            return {'role': 'user', 'content': [tool_result]}
        if role == 'assistant' and msg.get('tool_calls'):
            content_blocks = []
            if isinstance(converted, list):
                content_blocks = converted
            elif converted:
                content_blocks.append({'type': 'text', 'text': str(converted)})
            for tc in msg['tool_calls']:
                content_blocks.append({'type': 'tool_use', 'id': tc.get('id', ''), 'name': tc['function']['name'], 'input': json.loads(tc['function']['arguments']) if isinstance(tc['function']['arguments'], str) else tc['function']['arguments']})
            return {'role': 'assistant', 'content': content_blocks}
        if isinstance(converted, list):
            return {'role': role, 'content': converted}
        return {'role': role, 'content': str(converted) if converted else ''}

    def _convert_content(self, content):
        """Convert content (str or list of blocks) to Anthropic format."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            result = []
            for block in content:
                if isinstance(block, dict):
                    bt = block.get('type', '')
                    if bt == 'text':
                        result.append({'type': 'text', 'text': block.get('text', '')})
                    elif bt == 'image':
                        result.append({
                            'type': 'image',
                            'source': {
                                'type': 'base64',
                                'media_type': block['source']['media_type'],
                                'data': block['source']['data'],
                            }
                        })
                    else:
                        result.append(block)
            return result if result else str(content)
        return str(content)

    def _convert_tools(self, tools: list[dict], prompt_caching: bool=True) -> list[dict]:
        anthropic_tools = []
        for tool in tools:
            if tool.get('type') == 'function':
                func = tool['function']
                anthropic_tools.append({'name': func['name'], 'description': func.get('description', ''), 'input_schema': func.get('parameters', {'type': 'object', 'properties': {}})})
        if anthropic_tools and prompt_caching:
            anthropic_tools[-1]['cache_control'] = {'type': 'ephemeral'}
        return anthropic_tools

    def _parse_response(self, response, model: str) -> LLMResponse:
        content = ''
        tool_calls = []
        reasoning_parts = []
        for block in response.content:
            if block.type == 'text':
                content += block.text
            elif block.type == 'tool_use':
                tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=block.input if isinstance(block.input, dict) else json.loads(block.input)))
            elif block.type == 'thinking':
                reasoning_parts.append(block.thinking)
            elif block.type == 'redacted_thinking':
                reasoning_parts.append('[redacted]')
        reasoning = '\n'.join(reasoning_parts) if reasoning_parts else ''
        usage = response.usage
        cache_read = getattr(usage, 'cache_read_input_tokens', 0) if usage else 0
        cache_write = getattr(usage, 'cache_creation_input_tokens', 0) if usage else 0
        return LLMResponse(content=content, tool_calls=tool_calls if tool_calls else None, usage=TokenUsage(input=usage.input_tokens if usage else 0, output=usage.output_tokens if usage else 0, cache_read=cache_read, cache_write=cache_write), model=model, finish_reason=response.stop_reason or 'end_turn', reasoning_content=reasoning)

    @staticmethod
    def _is_cache_error(error: Exception) -> bool:
        """Detect errors caused by unsupported cache_control. Retry without caching."""
        msg = str(error).lower()
        return any(kw in msg for kw in ['cache_control', 'ephemeral'])

    def _estimate_tokens(self, messages: list[dict]) -> int:
        total = 0
        for msg in messages:
            content = msg.get('content', '')
            if isinstance(content, str):
                total += len(content) // 4
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and 'text' in block:
                        total += len(block['text']) // 4
        return total
