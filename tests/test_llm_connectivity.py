"""AI LLM 连通性测试脚本

用法:
    python -m tests.test_llm_connectivity
    python -m tests.test_llm_connectivity --verbose
    python -m tests.test_llm_connectivity --config /path/to/config.yaml
"""

import argparse
import sys
import time
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ai_llm.llm_client import LLMClient, Message


def test_config(config_path: str | None = None) -> dict:
    """测试配置加载"""
    print("\n[1/4] 测试配置加载...")
    try:
        client = LLMClient(config_path)
        config = client.config
        print(f"  - base_url: {config.base_url}")
        print(f"  - model: {config.model}")
        print(f"  - timeout: {config.timeout}s")
        print(f"  - max_retries: {config.max_retries}")
        return {"passed": True, "config": config}
    except Exception as e:
        print(f"  [FAIL] 配置加载失败: {e}")
        return {"passed": False, "error": str(e)}


def test_config_validation(client: LLMClient) -> dict:
    """测试配置有效性"""
    print("\n[2/4] 测试配置有效性...")
    is_configured = client.is_configured()
    if is_configured:
        print(f"  [PASS] API Key 和 Base URL 均已配置")
        return {"passed": True}
    else:
        print(f"  [FAIL] API Key 或 Base URL 未配置")
        return {"passed": False, "error": "missing_config"}


def test_basic_connectivity(client: LLMClient) -> dict:
    """测试基础连通性（不带实际请求）"""
    print("\n[3/4] 测试网络连通性...")
    try:
        import httpx
        with httpx.Client(timeout=10, follow_redirects=True) as http_client:
            # HEAD 请求测试服务器可达性
            health_url = client.config.base_url.rstrip("/") + "/health"
            try:
                response = http_client.head(health_url)
                print(f"  [PASS] 服务器可达 (status: {response.status_code})")
                return {"passed": True, "method": "head"}
            except httpx.exceptions.RequestError:
                # HEAD 不支持时尝试 GET /models
                models_url = client.config.base_url.rstrip("/") + "/models"
                headers = {"Authorization": f"Bearer {client.config.api_key}"}
                response = http_client.get(models_url, headers=headers)
                print(f"  [PASS] 服务器可达 (status: {response.status_code})")
                return {"passed": True, "method": "get_models"}
    except Exception as e:
        print(f"  [WARN] 网络连通性测试跳过: {e}")
        return {"passed": None, "error": str(e), "note": "will_test_with_actual_request"}


def test_llm_chat(client: LLMClient) -> dict:
    """测试 LLM 对话功能"""
    print("\n[4/4] 测试 LLM 对话...")
    start_time = time.time()

    test_messages = [
        Message(role="user", content="你好，请回复'连通性测试成功'。只需回复这四个字，不要其他内容。")
    ]

    try:
        response = client.chat(
            messages=test_messages,
            temperature=0.1,
            max_tokens=50,
        )
        elapsed = time.time() - start_time

        print(f"  - 模型: {response.model}")
        print(f"  - 响应: {response.content}")
        print(f"  - 耗时: {elapsed:.2f}s")
        print(f"  - Usage: {response.usage}")

        if response.content:
            print(f"  [PASS] LLM 对话正常")
            return {
                "passed": True,
                "model": response.model,
                "response": response.content,
                "elapsed": elapsed,
                "usage": response.usage,
            }
        else:
            print(f"  [FAIL] LLM 返回空内容")
            return {"passed": False, "error": "empty_response"}

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"  [FAIL] LLM 请求失败: {e}")
        return {"passed": False, "error": str(e), "elapsed": elapsed}


def run_all_tests(config_path: str | None = None, verbose: bool = False) -> dict:
    """运行所有测试"""
    print("=" * 50)
    print("AI LLM 连通性测试")
    print("=" * 50)

    results = {}

    # 1. 配置加载
    config_result = test_config(config_path)
    results["config_loading"] = config_result
    if not config_result["passed"]:
        print("\n[ABORT] 配置加载失败，停止测试")
        return results

    client = LLMClient(config_path)

    # 2. 配置有效性
    results["config_validation"] = test_config_validation(client)
    if not results["config_validation"]["passed"]:
        print("\n[ABORT] 配置不完整，停止测试")
        return results

    # 3. 基础连通性
    results["connectivity"] = test_basic_connectivity(client)
    if results["connectivity"].get("note") == "will_test_with_actual_request":
        print("  (将在实际请求中验证连通性)")

    # 4. LLM 对话测试
    results["llm_chat"] = test_llm_chat(client)

    # 汇总
    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    all_passed = all(r.get("passed", False) for r in results.values())
    print(f"  配置加载: {'PASS' if results['config_loading']['passed'] else 'FAIL'}")
    print(f"  配置有效性: {'PASS' if results['config_validation']['passed'] else 'FAIL'}")
    print(f"  网络连通性: {results['connectivity'].get('method', 'SKIP')}")
    print(f"  LLM 对话: {'PASS' if results['llm_chat']['passed'] else 'FAIL'}")

    if all_passed:
        print("\n[SUCCESS] 所有测试通过！")
    else:
        print("\n[WARNING] 部分测试未通过，请检查配置和网络")

    results["all_passed"] = all_passed
    return results


def main():
    parser = argparse.ArgumentParser(description="AI LLM 连通性测试")
    parser.add_argument("--config", "-c", type=str, default=None,
                        help="配置文件路径")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="详细输出")
    args = parser.parse_args()

    results = run_all_tests(config_path=args.config, verbose=args.verbose)

    # 返回退出码
    sys.exit(0 if results.get("all_passed", False) else 1)


if __name__ == "__main__":
    main()
