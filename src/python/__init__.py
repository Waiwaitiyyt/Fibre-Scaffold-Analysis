"""
scaffoldAnalysis - Fiber Diameter Measurement Tool
"""
import sys
from pathlib import Path

# 添加lib目录到搜索路径
_project_root = Path(__file__).parent.parent.parent
_lib_path = _project_root / "lib"

if _lib_path.exists():
    sys.path.insert(0, str(_lib_path))
    
# 尝试导入C++模块
try:
    import measure_tool # type: ignore
    _cpp_available = True
    print(f"✓ C++ acceleration enabled: {measure_tool.__file__}")
except ImportError as e:
    _cpp_available = False
    print(f"⚠ C++ module not available: {e}")
    print("  Running in pure Python mode. Performance may be slower.")

# 导出常用功能（可选）
__version__ = "0.3.2"
__all__ = ['measure_tool', '_cpp_available']