"""Use the same shell selector as the independently packaged Accuracy doctor."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/llm-accuracy/scripts'))
from hook_shell import shell_argv  # noqa: E402,F401
