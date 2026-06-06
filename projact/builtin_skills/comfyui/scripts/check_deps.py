from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DEFAULT_LOCAL_HOST, ENV_API_KEY, emit_json, folder_aliases_for, http_get, is_cloud_host, iter_embedding_refs, iter_model_deps, iter_nodes, parse_model_list, resolve_api_key, resolve_url, unwrap_workflow
NODE_TO_PACKAGE: dict[str, str] = {'Power Lora Loader (rgthree)': 'rgthree-comfy', 'Image Comparer (rgthree)': 'rgthree-comfy', 'Seed (rgthree)': 'rgthree-comfy', 'Display Any (rgthree)': 'rgthree-comfy', 'Display Int (rgthree)': 'rgthree-comfy', 'FaceDetailer': 'comfyui-impact-pack', 'DetailerForEach': 'comfyui-impact-pack', 'BboxDetectorSEGS': 'comfyui-impact-pack', 'SAMLoader': 'comfyui-impact-pack', 'ImpactWildcardProcessor': 'comfyui-impact-pack', 'UltralyticsDetectorProvider': 'comfyui-impact-subpack', 'Image Save': 'was-node-suite-comfyui', 'Number Counter': 'was-node-suite-comfyui', 'Text String': 'was-node-suite-comfyui', 'easy fullLoader': 'comfyui-easy-use', 'easy positive': 'comfyui-easy-use', 'easy negative': 'comfyui-easy-use', 'easy seed': 'comfyui-easy-use', 'easy imageSave': 'comfyui-easy-use', 'VHS_VideoCombine': 'comfyui-videohelpersuite', 'VHS_LoadVideo': 'comfyui-videohelpersuite', 'VHS_LoadAudio': 'comfyui-videohelpersuite', 'ADE_AnimateDiffLoaderWithContext': 'comfyui-animatediff-evolved', 'ADE_AnimateDiffLoaderGen1': 'comfyui-animatediff-evolved', 'ADE_LoadAnimateDiffModel': 'comfyui-animatediff-evolved', 'CannyEdgePreprocessor': 'comfyui_controlnet_aux', 'DWPreprocessor': 'comfyui_controlnet_aux', 'OpenposePreprocessor': 'comfyui_controlnet_aux', 'DepthAnythingPreprocessor': 'comfyui_controlnet_aux', 'Zoe_DepthAnythingPreprocessor': 'comfyui_controlnet_aux', 'AnimalPosePreprocessor': 'comfyui_controlnet_aux', 'IPAdapterAdvanced': 'comfyui_ipadapter_plus', 'IPAdapterUnifiedLoader': 'comfyui_ipadapter_plus', 'IPAdapterModelLoader': 'comfyui_ipadapter_plus', 'IPAdapterInsightFaceLoader': 'comfyui_ipadapter_plus', 'InstantIDModelLoader': 'comfyui_instantid', 'ApplyInstantID': 'comfyui_instantid', 'GetImageSize+': 'comfyui_essentials', 'ImageBatchMultiple+': 'comfyui_essentials', 'ShowText|pysssss': 'comfyui-custom-scripts', 'PreviewImage|pysssss': 'comfyui-custom-scripts', 'SUPIR_Upscale': 'comfyui-supir', 'SUPIR_first_stage': 'comfyui-supir', 'UNETLoaderGGUF': 'ComfyUI-GGUF', 'DualCLIPLoaderGGUF': 'ComfyUI-GGUF', 'Florence2Run': 'comfyui-florence2', 'Image Filter Adjustments': 'was-node-suite-comfyui', 'PhotoMakerLoader': 'ComfyUI-PhotoMaker-Plus', 'WanVideoSampler': 'ComfyUI-WanVideoWrapper', 'WanVideoModelLoader': 'ComfyUI-WanVideoWrapper'}
NODE_TO_GIT_URL: dict[str, str] = {'HunyuanVideoSampler': 'https://github.com/kijai/ComfyUI-HunyuanVideoWrapper', 'HunyuanVideoModelLoader': 'https://github.com/kijai/ComfyUI-HunyuanVideoWrapper'}

def fetch_object_info(url: str, headers: dict) -> tuple[set[str] | None, dict | None]:
    r = http_get(url, headers=headers, retries=2, timeout=30)
    if r.status == 200:
        try:
            data = r.json()
            if isinstance(data, dict):
                return (set(data.keys()), None)
        except Exception:
            pass
        return (None, {'http_status': 200, 'reason': 'non-dict response'})
    if r.status == 403:
        try:
            body = r.json()
        except Exception:
            body = {'raw': r.text()[:200]}
        return (None, {'http_status': 403, 'reason': 'forbidden', 'body': body})
    if r.status == 404:
        return (None, {'http_status': 404, 'reason': 'endpoint not found'})
    return (None, {'http_status': r.status, 'reason': 'unexpected', 'body': r.text()[:200]})

def _fetch_one_folder(base: str, folder: str, headers: dict, *, is_cloud: bool) -> tuple[set[str] | None, dict | None]:
    url = resolve_url(base, f'/models/{folder}', is_cloud=is_cloud)
    r = http_get(url, headers=headers, retries=2, timeout=30)
    if r.status == 200:
        try:
            return (parse_model_list(r.json()), None)
        except Exception:
            return (set(), {'http_status': 200, 'reason': 'non-list response'})
    if r.status == 404:
        body_text = r.text()
        try:
            body = r.json()
        except Exception:
            body = {'raw': body_text[:200]}
        code = body.get('code') if isinstance(body, dict) else None
        if code == 'folder_not_found':
            return (set(), {'http_status': 404, 'reason': 'folder_empty_or_unknown', 'body': body})
        return (None, {'http_status': 404, 'reason': 'endpoint not found', 'body': body})
    if r.status == 403:
        try:
            body = r.json()
        except Exception:
            body = {}
        return (None, {'http_status': 403, 'reason': 'forbidden', 'body': body})
    return (None, {'http_status': r.status, 'reason': 'unexpected'})

def fetch_models_for_folder(base: str, folder: str, headers: dict, *, is_cloud: bool) -> tuple[set[str] | None, dict | None]:
    aliases = folder_aliases_for(folder)
    combined: set[str] = set()
    any_success = False
    last_err: dict | None = None
    for alias in aliases:
        models, err = _fetch_one_folder(base, alias, headers, is_cloud=is_cloud)
        if models is not None:
            combined.update(models)
            any_success = True
            last_err = None
        else:
            last_err = err
    if not any_success:
        return (None, last_err)
    return (combined, None)

def fetch_embeddings(base: str, headers: dict, *, is_cloud: bool) -> tuple[set[str] | None, dict | None]:
    if is_cloud:
        return fetch_models_for_folder(base, 'embeddings', headers, is_cloud=True)
    r = http_get(resolve_url(base, '/embeddings', is_cloud=False), headers=headers, retries=2)
    if r.status == 200:
        try:
            data = r.json()
            if isinstance(data, list):
                names = set()
                for n in data:
                    if isinstance(n, str):
                        names.add(n)
                        names.add(Path(n).stem)
                return (names, None)
        except Exception:
            pass
    return (None, {'http_status': r.status, 'reason': 'unexpected'})

def normalize_for_match(name: str) -> set[str]:
    s = {name}
    s.add(Path(name).stem)
    s.add(Path(name).name)
    if '/' in name or '\\' in name:
        flat = name.replace('\\', '/').split('/')[-1]
        s.add(flat)
        s.add(Path(flat).stem)
    return {x for x in s if x}

def model_present(needed: str, installed: set[str]) -> bool:
    if not installed:
        return False
    needed_variants = normalize_for_match(needed)
    installed_norm: set[str] = set()
    for inst in installed:
        installed_norm.update(normalize_for_match(inst))
    return bool(needed_variants & installed_norm)

def suggest_install_command(node_class: str) -> str | None:
    pkg = NODE_TO_PACKAGE.get(node_class)
    if pkg:
        return f'comfy node install {pkg}'
    return None

def suggest_git_url(node_class: str) -> str | None:
    return NODE_TO_GIT_URL.get(node_class)

def check_deps(workflow: dict, host: str, *, api_key: str | None=None) -> dict:
    headers: dict[str, str] = {}
    if api_key:
        headers['X-API-Key'] = api_key
    is_cloud = is_cloud_host(host)
    base = host.rstrip('/')
    required_nodes: set[str] = set()
    for _, node in iter_nodes(workflow):
        required_nodes.add(node['class_type'])
    object_info_url = resolve_url(base, '/object_info', is_cloud=is_cloud)
    installed_nodes, obj_err = fetch_object_info(object_info_url, headers)
    missing_nodes: list[dict] = []
    node_check_skipped = False
    if installed_nodes is None:
        node_check_skipped = True
    else:
        for cls in sorted(required_nodes):
            if cls not in installed_nodes:
                entry = {'class_type': cls}
                cmd = suggest_install_command(cls)
                git_url = suggest_git_url(cls)
                if cmd:
                    entry['fix_command'] = cmd
                elif git_url:
                    entry['fix_git_url'] = git_url
                    entry['fix_hint'] = f'Not on registry. Install via Manager with this git URL: {git_url}'
                else:
                    entry['fix_hint'] = 'Search https://registry.comfy.org or use ComfyUI-Manager UI to find the package providing this node.'
                missing_nodes.append(entry)
    model_cache: dict[str, tuple[set[str] | None, dict | None]] = {}
    missing_models: list[dict] = []
    folder_errors: dict[str, dict] = {}
    for dep in iter_model_deps(workflow):
        folder = dep['folder']
        if folder not in model_cache:
            model_cache[folder] = fetch_models_for_folder(base, folder, headers, is_cloud=is_cloud)
        installed, err = model_cache[folder]
        if installed is None:
            folder_errors.setdefault(folder, err or {})
            continue
        if not model_present(dep['value'], installed):
            entry = dict(dep)
            entry['fix_hint'] = f'comfy model download --url <URL> --relative-path models/{folder} --filename {dep['value']!r}'
            missing_models.append(entry)
    emb_installed, emb_err = fetch_embeddings(base, headers, is_cloud=is_cloud)
    missing_embeddings: list[dict] = []
    seen_emb: set[tuple[str, str]] = set()
    for nid, emb_name in iter_embedding_refs(workflow):
        if (nid, emb_name) in seen_emb:
            continue
        seen_emb.add((nid, emb_name))
        if emb_installed is None:
            continue
        if not model_present(emb_name, emb_installed):
            missing_embeddings.append({'node_id': nid, 'embedding_name': emb_name, 'folder': 'embeddings', 'fix_hint': f'Download {emb_name}.pt or .safetensors and place in models/embeddings/, or `comfy model download --url <URL> --relative-path models/embeddings`'})
    if emb_err and emb_installed is None:
        folder_errors.setdefault('embeddings', emb_err)
    is_ready = not node_check_skipped and (not missing_nodes) and (not missing_models) and (not missing_embeddings)
    return {'is_ready': is_ready, 'node_check_skipped': node_check_skipped, 'node_check_skip_reason': obj_err if node_check_skipped else None, 'missing_nodes': missing_nodes, 'missing_models': missing_models, 'missing_embeddings': missing_embeddings, 'folder_errors': folder_errors, 'installed_node_count': len(installed_nodes) if installed_nodes is not None else None, 'required_node_count': len(required_nodes), 'required_nodes': sorted(required_nodes), 'host': base, 'is_cloud': is_cloud}

def main(argv: list[str] | None=None) -> int:
    p = argparse.ArgumentParser(description='Check ComfyUI workflow dependencies against a running server')
    p.add_argument('workflow', help='Path to workflow API JSON file')
    p.add_argument('--host', default=DEFAULT_LOCAL_HOST, help='ComfyUI server URL')
    p.add_argument('--port', type=int, help='Server port (overrides --host port)')
    p.add_argument('--api-key', help=f'API key for cloud (or set ${ENV_API_KEY} env var)')
    p.add_argument('--strict', action='store_true', help='Exit non-zero if node check is skipped (e.g. on cloud free tier)')
    args = p.parse_args(argv)
    host = args.host
    if args.port is not None:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(host if '://' in host else f'http://{host}')
        new_netloc = f'{parsed.hostname}:{args.port}'
        host = urlunparse(parsed._replace(netloc=new_netloc))
    api_key = resolve_api_key(args.api_key)
    wf_path = Path(args.workflow).expanduser()
    if not wf_path.exists():
        emit_json({'error': f'Workflow file not found: {args.workflow}'})
        return 1
    try:
        with wf_path.open() as f:
            payload = json.load(f)
        workflow = unwrap_workflow(payload)
    except ValueError as e:
        emit_json({'error': str(e)})
        return 1
    except json.JSONDecodeError as e:
        emit_json({'error': f'Invalid JSON: {e}'})
        return 1
    try:
        result = check_deps(workflow, host=host, api_key=api_key)
    except Exception as e:
        emit_json({'error': f'Dep check failed: {e}', 'host': host})
        return 1
    emit_json(result)
    if not result['is_ready']:
        return 1
    if args.strict and result['node_check_skipped']:
        return 1
    return 0
if __name__ == '__main__':
    sys.exit(main())
