from pathlib import Path
import os
import time


def _debug_log(message: str) -> None:
    try:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with Path("/tmp/autokyo-mcp-debug.log").open("a", encoding="utf-8") as fh:
            fh.write(f"{timestamp} pid={os.getpid()} main.py {message}\n")
    except OSError:
        pass


_debug_log("module.import.begin")

from autokyo.cli import main

_debug_log("module.import.end")


if __name__ == "__main__":
    _debug_log("__main__.begin")
    try:
        raise SystemExit(main())
    except BaseException as exc:
        _debug_log(f"__main__.exception {exc!r}")
        raise
