"""
QQPet Automation - 加载环境变量
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 查找项目根目录的 .env 文件
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
