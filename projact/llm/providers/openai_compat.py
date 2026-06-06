import json
from dataclasses import dataclass
from ..types import LLMResponse, ToolCall, TokenUsage

@dataclass
class OpenAICompatProvider:
    api_key: str | None = None
    base_url: str = 'https://api.openai.com/v1'
    max_tokens: int = 8192

    def __post_init__(self):
        from openai import OpenAI
        import os
        key = self.api_key or os.environ.get('OPENAI_API_KEY', 'not-needed')
        self._client = OpenAI(api_key=key, base_url=self.base_url)

    def complete(self, messages: list[dict], tools: list[dict] | None=None, model: str='gpt-4o', on_token=None) -> LLMResponse:
        if on_token is not None:
            return self._complete_stream(messages, tools=tools, model=model, on_token=on_token)
        kwargs = dict(model=model, messages=messages, max_tokens=self.max_tokens)
        if tools:
            kwargs['tools'] = tools
        response = self._client.chat.completions.create(**kwargs)
        return self._parse_response(response, model)

    def _complete_stream(self, messages: list[dict], tools: list[dict] | None, model: str, on_token) -> LLMResponse:
        kwargs = dict(model=model, messages=messages, max_tokens=self.max_tokens, stream=True)
        if tools:
            kwargs['tools'] = tools
        stream = self._client.chat.completions.create(**kwargs)
        content = ''
        tool_calls_dict: dict[int, dict] = {}
        input_tokens = 0
        output_tokens = 0
        finish_reason = 'stop'
        reasoning = ''
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            r = getattr(delta, 'reasoning_content', '')
            if r:
                reasoning += r
            if delta.content:
                content += delta.content
                if on_token:
                    on_token(delta.content)
            if delta.tool_calls:
                for tc_chunk in delta.tool_calls:
                    idx = tc_chunk.index
                    if idx not in tool_calls_dict:
                        tool_calls_dict[idx] = {'id': tc_chunk.id or '', 'name': tc_chunk.function.name or '', 'arguments': ''}
                    if tc_chunk.id:
                        tool_calls_dict[idx]['id'] = tc_chunk.id
                    if tc_chunk.function.name:
                        tool_calls_dict[idx]['name'] = tc_chunk.function.name
                    if tc_chunk.function.arguments:
                        tool_calls_dict[idx]['arguments'] += tc_chunk.function.arguments
            if chunk.choices[0].finish_reason:
                finish_reason = chunk.choices[0].finish_reason
        tool_calls = []
        for idx in sorted(tool_calls_dict.keys()):
            tc_data = tool_calls_dict[idx]
            try:
                args = json.loads(tc_data['arguments'])
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(id=tc_data['id'], name=tc_data['name'], arguments=args))
        if output_tokens == 0:
            output_tokens = len(content) // 4
        return LLMResponse(content=content, tool_calls=tool_calls if tool_calls else None, usage=TokenUsage(input=input_tokens, output=output_tokens), model=model, finish_reason=finish_reason, reasoning_content=reasoning)

    def count_tokens(self, messages: list[dict]) -> int:
        try:
            import tiktoken
            enc = tiktoken.get_encoding('cl100k_base')
            total = 0
            for msg in messages:
                content = msg.get('content', '')
                if isinstance(content, str):
                    total += len(enc.encode(content))
                if msg.get('tool_calls'):
                    total += len(enc.encode(json.dumps(msg['tool_calls'])))
            return total
        except Exception:
            return sum((len(str(m.get('content', ''))) // 4 for m in messages))

    def _parse_response(self, response, model: str) -> LLMResponse:
        choice = response.choices[0]
        message = choice.message
        tool_calls = None
        if message.tool_calls:
            tool_calls = []
            for tc in message.tool_calls:
                args = tc.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))
        reasoning = getattr(message, 'reasoning_content', '') or ''
        return LLMResponse(content=message.content or '', tool_calls=tool_calls, usage=TokenUsage(input=response.usage.prompt_tokens if response.usage else 0, output=response.usage.completion_tokens if response.usage else 0), model=model, finish_reason=choice.finish_reason or 'stop', reasoning_content=reasoning)
