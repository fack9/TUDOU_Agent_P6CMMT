from __future__ import annotations
import json
import traceback
from typing import Any, Callable
from flask import Blueprint, request, jsonify, g
from .auth import PairingManager
API = Blueprint('api', __name__, url_prefix='/api')

def create_api_blueprint(pairing: PairingManager, get_agent: Callable[[], Any]) -> Blueprint:

    def require_auth() -> bool:
        auth = request.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            token = auth[7:]
            return pairing.validate_token(token)
        return False

    @API.before_request
    def check_auth():
        if request.endpoint in ('api.pair', 'api.status'):
            return
        if not require_auth():
            return (jsonify({'ok': False, 'error': 'unauthorized'}), 401)

    @API.post('/pair')
    def pair():
        data = request.get_json(silent=True) or {}
        code = data.get('code', '').strip()
        if not code:
            return (jsonify({'ok': False, 'error': 'pairing code required'}), 400)
        token = pairing.verify_code(code)
        if token:
            return jsonify({'ok': True, 'token': token})
        return (jsonify({'ok': False, 'error': 'invalid or expired code'}), 403)

    @API.post('/unpair')
    def unpair():
        pairing.unpair()
        return jsonify({'ok': True})

    @API.get('/status')
    def status():
        agent = get_agent()
        return jsonify({'ok': True, 'online': True, 'bound': pairing.is_bound, 'pairing_active': pairing.pairing_active, 'model': agent.settings.model if agent else ''})

    @API.post('/chat')
    def chat():
        data = request.get_json(silent=True) or {}
        message = data.get('message', '').strip()
        if not message:
            return (jsonify({'ok': False, 'error': 'message required'}), 400)
        agent = get_agent()
        if agent is None:
            return (jsonify({'ok': False, 'error': 'agent not available'}), 503)
        tool_calls_log: list[dict] = []

        def on_tool(name: str, arguments: dict, result: Any):
            output = result.output if hasattr(result, 'output') else str(result)
            success = result.success if hasattr(result, 'success') else True
            tool_calls_log.append({'tool': name, 'arguments': arguments, 'output': str(output)[:3000], 'success': success})
        try:
            response = agent.run_conversation(message, on_tool_call=on_tool)
        except Exception as exc:
            return (jsonify({'ok': False, 'error': str(exc), 'traceback': traceback.format_exc()}), 500)
        return jsonify({'ok': True, 'message': response.final_message, 'tool_calls': tool_calls_log, 'usage': {'input': response.token_usage.input, 'output': response.token_usage.output}, 'duration_ms': response.duration_ms})
    return API
