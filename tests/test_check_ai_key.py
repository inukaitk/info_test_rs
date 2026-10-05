"""Actions用：APIキーの無料確認（scripts/check_ai_key.py）のテスト。実際のAPIには接続しない。"""
from conftest import REPO_ROOT


def _load_check_ai_key():
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_ai_key", REPO_ROOT / "scripts" / "check_ai_key.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_check_ai_key_reports_missing_key_without_secrets():
    ok, message = _load_check_ai_key().check({"provider": "anthropic", "model": "m", "effort": "medium", "fallbacks": True}, environ={})
    assert ok is False and "INFO_AI_API_KEY" in message


def test_check_ai_key_ok_and_invalid_key_never_prints_the_key():
    mod = _load_check_ai_key()
    cfg = {"provider": "anthropic", "model": "m", "effort": "medium", "fallbacks": True}

    class Good:
        def __init__(self, **kw): pass
        def count_tokens(self, system, user): return 12

    class Rejected:
        def __init__(self, **kw): pass
        def count_tokens(self, system, user):
            err = RuntimeError("invalid x-api-key: sk-ant-SECRETVALUE")
            err.status_code = 401
            raise err

    assert mod.check(cfg, factory=Good) == (True, "AIのAPIキーは使えます（課金されない確認）")
    ok, message = mod.check(cfg, factory=Rejected)
    assert ok is False and "HTTP 401" in message and "無効" in message
    assert "SECRETVALUE" not in message and "sk-ant" not in message
