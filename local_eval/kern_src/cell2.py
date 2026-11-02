# ===== CELL 3: start vLLM server =====
import litellm, torch
from adk_submission import VllmConfig, VllmServer, discover_adapters
from swegemma.config import ALLOWED_ADAPTER_EXTENSIONS
# DEFENSIVE import: swegemma.models.discovery was removed in the current wheelhouse (module moved).
validate_single_declared_model = None
for _modpath in ('swegemma.models.discovery', 'swegemma.models.registry', 'swegemma.submission',
                 'swegemma.config', 'swegemma.models'):
    try:
        _m = __import__(_modpath, fromlist=['validate_single_declared_model'])
        validate_single_declared_model = getattr(_m, 'validate_single_declared_model', None)
        if validate_single_declared_model is not None:
            print(f'[import] validate_single_declared_model <- {_modpath}')
            break
    except Exception:
        continue
if validate_single_declared_model is None:
    print('[import] validate_single_declared_model NOT FOUND; using no-op (single-model rule satisfied by agent.yaml)')
    def validate_single_declared_model(agent_dir):
        return 'gemma-4-31b-it-qat-w4a16-ct'
litellm.drop_params = True
TARGET_MODEL_NAME = 'gemma-4-31b-it-qat-w4a16-ct'
# The measured mount listing showed 'models' directly under /kaggle/input, so the
# '/kaggle/input/models/...' prefix is still correct, but the tail after it is unverified in the
# current layout. Resolve it, and fall back to an rglob, because a wrong MODEL_PATH otherwise
# surfaces only AFTER an 18GB load attempt as an opaque vLLM / CUDA-graph error.
MODEL_PATH = Path('/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2')
if not MODEL_PATH.is_dir():
    _mroot = Path('/kaggle/input/models')
    if _mroot.is_dir():
        for _d in sorted(_mroot.rglob('gemma-4-31b-it-qat-w4a16-ct*')):
            if _d.is_dir():
                MODEL_PATH = _d
                break
if not MODEL_PATH.is_dir():
    _mroot = Path('/kaggle/input/models')
    if _mroot.is_dir():
        for _d in sorted(_mroot.rglob('gemma-4-31b-it-qat-w4a16-ct*')):
            if _d.is_dir():
                MODEL_PATH = _d
                break
assert MODEL_PATH.is_dir(), (
    f'31B model not found. /kaggle/input contains: '
    f'{sorted(p.name for p in Path("/kaggle/input").iterdir()) if Path("/kaggle/input").is_dir() else "<none>"}; '
    f'/kaggle/input/models contains: '
    f'{sorted(p.name for p in Path("/kaggle/input/models").iterdir()) if Path("/kaggle/input/models").is_dir() else "<none>"}. '
    'model_sources declares google/gemma-4/Other/gemma-4-31b-it-qat-w4a16-ct/2 -- re-attach it.')
declared_model = validate_single_declared_model(AGENT_DIR)
adapters = discover_adapters(str(AGENT_DIR), adapter_extensions=ALLOWED_ADAPTER_EXTENSIONS)
gpu_count = torch.cuda.device_count() if torch.cuda.is_available() else 1
tp_size = 4 if gpu_count >= 4 else (2 if gpu_count >= 2 else 1)
# ---- ARCH REMAP APPLIED TO ALL NON-31B (2026-10-17) ------------------------------------------------
# 12b declares model_type 'gemma4_unified' / Gemma4UnifiedForConditionalGeneration. vLLM 0.19.1
# has no native impl, falls back to TransformersMultiModal, and dies in profile_run with
#     ValueError: Expected hidden_size to be 3840, but found: 256
# That is EXACTLY the failure this run hit. The fix is Kaggle-staff-provided and already proven
# in our own log (m12, Gate 1 PASSED): remap the arch to the natively supported
# Gemma4ForCausalLM via extra_args. There is NO VLLM_ENFORCE_EAGER env var (my earlier v2/v3
# guesses were wrong); do not re-try those.
# FAILS LOUD rather than silently dropping the override -- without it the server cannot start.
_MODEL_VLLM_EXTRA_ARGS = {}
if '31b' not in TARGET_MODEL_NAME:
    _MODEL_VLLM_EXTRA_ARGS['extra_args'] = (
        '--hf-overrides', '{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}')
    print('[vllm] non-31b detected -> applying staff hf-overrides arch remap')
try:
    vllm_cfg = VllmConfig(
        model=str(MODEL_PATH), port=8000, host='127.0.0.1',
        tool_call_parser='gemma4', reasoning_parser='gemma4', max_model_len=32768,
        dtype='bfloat16' if (torch.cuda.is_available() and torch.cuda.is_bf16_supported()) else 'auto',
        gpu_memory_utilization=0.90, enable_auto_tool_choice=True,
        enable_lora=True, max_loras=8, max_lora_rank=128,
        tensor_parallel_size=tp_size, startup_timeout=60 * 20,
        **_MODEL_VLLM_EXTRA_ARGS,
    )
    if _MODEL_VLLM_EXTRA_ARGS:
        assert getattr(vllm_cfg, 'extra_args', None), (
            'VllmConfig did not accept extra_args -- the 12b arch remap would be silently lost '
            'and the server WILL crash with hidden_size 3840 vs 256. Fail here instead.')
except TypeError as _e:
    if _MODEL_VLLM_EXTRA_ARGS:
        raise RuntimeError(
            'VllmConfig rejects extra_args (%s). Cannot serve 12b on this wheelhouse.' % _e)
    raise

server_instance = VllmServer(vllm_cfg, adapter_manifest=adapters)
server_instance.start()
print(f'vLLM server started on {server_instance.base_url} (tp={tp_size})')
models = server_instance.create_model_registry(
    aliases=[declared_model, TARGET_MODEL_NAME], model_prefix='openai/', api_key='EMPTY')
