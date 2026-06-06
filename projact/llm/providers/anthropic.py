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

    def complete(self, messages: list[dict], tools: list[dict] | None=None, model: str='claude-sonnet-4-6-20250514', on_token=None) -> LLMResponse:
        if on_token is not None:
            return self._complete_stream(messages, tools=tools, model=model, on_token=on_token)
        system, chat_messages = self._split_system(messages)
        anthropic_tools = self._convert_tools(tools) if tools else None
        kwargs = dict(model=model, max_tokens=self.max_tokens, messages=chat_messages)
        if system:
            kwargs['system'] = system
        if anthropic_tools:
            kwargs['tools'] = anthropic_tools
        response = self._client.messages.create(**kwargs)
        return self._parse_response(response, model)

    def _complete_stream(self, messages: list[dict], tools: list[dict] | None, model: str, on_token) -> LLMResponse:
        system, chat_messages = self._split_system(messages)
        anthropic_tools = self._convert_tools(tools) if tools else None
        kwargs = dict(model=model, max_tokens=self.max_tokens, messages=chat_messages, stream=True)
        if system:
            kwargs['system'] = system
        if anthropic_tools:
            kwargs['tools'] = anthropic_tools
        stream = self._client.messages.create(**kwargs)
        content = ''
        tool_calls = []
        reasoning_parts = []
        input_tokens = 0
        output_tokens = 0
        stop_reason = 'end_turn'
        cur_type = None
        cur_text = ''
        cur_tool_id = None
        cur_tool_name = None
        cur_tool_json = ''
        for event in stream:
            et = event.type
            if et == 'message_start':
                if hasattr(event.message, 'usage') and event.message.usage:
                    input_tokens = event.message.usage.input_tokens
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
                elif block.type in ('thinking', 'redacted_thinking'):
                    cur_type = block.type
            elif et == 'content_block_delta':
                delta = event.delta
                if delta.type == 'text_delta':
                    cur_text += delta.text
                    if on_token:
                        on_token(delta.text)
                elif delta.type == 'input_json_delta':
                    cur_tool_json += delta.partial_json
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
                    reasoning_parts.append(cur_text if hasattr(self, '_cur_thinking') else '')
                cur_type = None
            elif et == 'message_delta':
                stop_reason = event.delta.stop_reason or 'end_turn'
                if hasattr(event, 'usage') and event.usage:
                    output_tokens = event.usage.output_tokens
        reasoning = '\n'.join(reasoning_parts) if reasoning_parts else ''
        return LLMResponse(content=content, tool_calls=tool_calls if tool_calls else None, usage=TokenUsage(input=input_tokens, output=output_tokens), model=model, finish_reason=stop_reason, reasoning_content=reasoning)

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

    def _split_system(self, messages: list[dict]) -> tuple[str | None, list[dict]]:
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
        return (system, chat)

    def _convert_message(self, msg: dict) -> dict:
        role = msg['role']
        content = msg.get('content', '')
        if role == 'tool':
            tool_result = {'type': 'tool_result', 'tool_use_id': msg.get('tool_call_id', ''), 'content': str(content)}
            return {'role': 'user', 'content': [tool_result]}
        if role == 'assistant' and msg.get('tool_calls'):
            content_blocks = []
            if content:
                content_blocks.append({'type': 'text', 'text': str(content)})
            for tc in msg['tool_calls']:
                content_blocks.append({'type': 'tool_use', 'id': tc.get('id', ''), 'name': tc['function']['name'], 'input': json.loads(tc['function']['arguments']) if isinstance(tc['function']['arguments'], str) else tc['function']['arguments']})
            return {'role': 'assistant', 'content': content_blocks}
        return {'role': role, 'content': str(content)}

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        anthropic_tools = []
        for tool in tools:
            if tool.get('type') == 'function':
                func = tool['function']
                anthropic_tools.append({'name': func['name'], 'description': func.get('description', ''), 'input_schema': func.get('parameters', {'type': 'object', 'properties': {}})})
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
        return LLMResponse(content=content, tool_calls=tool_calls if tool_calls else None, usage=TokenUsage(input=response.usage.input_tokens, output=response.usage.output_tokens), model=model, finish_reason=response.stop_reason or 'end_turn', reasoning_content=reasoning)

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
