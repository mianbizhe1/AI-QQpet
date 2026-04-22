#!/usr/bin/env python3
"""
AI企鹅Agent测试脚本
验证API和LLM是否正常工作
"""

import requests
import json
import time

BASE_URL = "http://127.0.0.1:18080"

def test(name, fn):
    """测试装饰器"""
    print(f"\n{'='*50}")
    print(f"测试: {name}")
    print('='*50)
    try:
        result = fn()
        print(f"✅ 通过")
        return result
    except Exception as e:
        print(f"❌ 失败: {e}")
        return None

def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║           AI企鹅Agent测试脚本                            ║
╚══════════════════════════════════════════════════════════╝
    """)

    # 检查服务器
    def check_server():
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        assert r.status_code == 200
        print(f"服务器状态: {r.json()}")

    test("服务器连接", check_server)

    # 测试宠物状态
    def test_pet_status():
        r = requests.get(f"{BASE_URL}/pet/status", timeout=5)
        assert r.status_code == 200
        data = r.json()
        print(f"宠物名称: {data.get('name')}")
        print(f"心情: {data.get('mood')}/{data.get('mood_max')}")
        print(f"饥饿: {data.get('hunger')}/{data.get('hunger_max')}")
        print(f"清洁: {data.get('clean')}/{data.get('clean_max')}")
        print(f"健康: {data.get('health')}")
        return data

    pet_status = test("获取宠物状态", test_pet_status)

    # 测试AI感知
    def test_ai_perception():
        r = requests.post(f"{BASE_URL}/ai/perception", timeout=30)
        assert r.status_code == 200
        data = r.json()
        print(f"宠物状态: {data.get('pet', {}).get('mood_level')}")
        print(f"提醒: {[a.get('message') for a in data.get('alerts', [])]}")
        print(f"建议: {[s.get('action') for s in data.get('suggestions', [])]}")
        print(f"对话场景: {data.get('dialogue_scene')}")
        return data

    perception = test("AI感知分析", test_ai_perception)

    # 测试LLM对话生成
    def test_llm_dialogue():
        scenes = ['click_response', 'hungry', 'dirty', 'greeting', 'sad']
        for scene in scenes:
            r = requests.post(
                f"{BASE_URL}/ai/dialogue",
                json={"scene": scene, "pet_name": "小Q"},
                timeout=30
            )
            assert r.status_code == 200
            data = r.json()
            print(f"\n场景 [{scene}]:")
            print(f"  → {data.get('response')}")
            time.sleep(0.5)

    test("LLM对话生成", test_llm_dialogue)

    # 测试游戏动作
    def test_game_actions():
        # 喂食
        r = requests.post(f"{BASE_URL}/pet/feed", json={"amount": 500}, timeout=5)
        print(f"喂食: {r.json().get('success')}")

        # 洗澡
        r = requests.post(f"{BASE_URL}/pet/bath", json={"amount": 500}, timeout=5)
        print(f"洗澡: {r.json().get('success')}")

        # 逗玩
        r = requests.post(f"{BASE_URL}/pet/play", json={"mood_boost": 50}, timeout=5)
        print(f"逗玩: {r.json().get('success')}")

        # 一键养护
        r = requests.post(f"{BASE_URL}/pet/auto_care", timeout=10)
        print(f"一键养护: {r.json().get('success')}")
        print(f"执行动作: {r.json().get('actions_taken')}")

    test("游戏动作", test_game_actions)

    # 最终状态
    print("\n" + "="*50)
    print("最终宠物状态")
    print("="*50)
    r = requests.get(f"{BASE_URL}/pet/status", timeout=5)
    data = r.json()
    print(f"心情: {data.get('mood')}/{data.get('mood_max')}")
    print(f"饥饿: {data.get('hunger')}/{data.get('hunger_max')}")
    print(f"清洁: {data.get('clean')}/{data.get('clean_max')}")

    print("\n" + "="*50)
    print("✅ 测试完成!")
    print("="*50)
    print("""
下一步:
1. 启动Electron宠物应用
2. 打开DevTools (Cmd+Option+I)
3. 在控制台执行:
   fetch('file:///Users/shenjiachen.1/qqpet_automation/qq-pet-macos/src/windows/util/pet/aiIntegration.js')
     .then(r => r.text())
     .then(code => eval(code))
4. 输入 ai.help() 查看可用命令
    """)

if __name__ == "__main__":
    main()
