"""PyInstaller 打包入口（等价于 python -m mstsc_manager）。"""

from mstsc_manager.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
