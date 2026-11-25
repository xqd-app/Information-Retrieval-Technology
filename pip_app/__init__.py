"""PIP 应用层（W1：真实采集链路）。

依赖 ../pip_skeleton 里的可判定内核模块（去重/时间可信度/状态机）。
"""

import sys
from pathlib import Path

_SKELETON = Path(__file__).resolve().parent.parent / "pip_skeleton"
if str(_SKELETON) not in sys.path:
    sys.path.insert(0, str(_SKELETON))

__version__ = "0.1.0"
