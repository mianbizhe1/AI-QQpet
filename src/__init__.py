"""
QQPet Automation - 加载环境变量
"""
from runtime_paths import existing_paths, env_candidates

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - 允许无 dotenv 的轻量运行
    def load_dotenv(*args, **kwargs):
        return False

for env_path in existing_paths(env_candidates()):
    load_dotenv(env_path, override=False)
