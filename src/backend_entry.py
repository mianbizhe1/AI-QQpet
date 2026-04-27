"""
PyInstaller 打包入口。
"""

from runtime_paths import ensure_runtime_layout


def main() -> None:
    ensure_runtime_layout()

    from ai_server import run_server

    run_server()


if __name__ == "__main__":
    main()
