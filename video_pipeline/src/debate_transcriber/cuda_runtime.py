from __future__ import annotations

import ctypes
import os
import sys
import sysconfig
from pathlib import Path
from typing import Any


_DLL_HANDLES: list[Any] = []
_CONFIGURED_DLL_DIRECTORIES: set[str] = set()
_CUDA_COMPONENTS = ("cublas", "cudnn", "cuda_nvrtc")
_REQUIRED_DLLS = ("cublas64_12.dll", "cudnn64_8.dll")


def configure_cuda_dll_directories() -> list[Path]:
    """Gör NVIDIA:s pip-installerade CUDA-DLL:er synliga i processen."""
    if sys.platform != "win32":
        return []

    purelib = Path(sysconfig.get_paths()["purelib"])
    directories = [
        purelib / "nvidia" / component / "bin" for component in _CUDA_COMPONENTS
    ]
    existing = [directory for directory in directories if directory.is_dir()]
    current_path = os.environ.get("PATH", "")
    path_parts = current_path.split(os.pathsep) if current_path else []

    for directory in existing:
        resolved = str(directory.resolve())
        if resolved.casefold() not in {part.casefold() for part in path_parts}:
            path_parts.insert(0, resolved)
        if (
            hasattr(os, "add_dll_directory")
            and resolved.casefold() not in _CONFIGURED_DLL_DIRECTORIES
        ):
            _DLL_HANDLES.append(os.add_dll_directory(resolved))
            _CONFIGURED_DLL_DIRECTORIES.add(resolved.casefold())

    os.environ["PATH"] = os.pathsep.join(path_parts)
    return existing


def missing_cuda_libraries() -> list[str]:
    if sys.platform != "win32":
        return []
    configure_cuda_dll_directories()
    missing: list[str] = []
    for library in _REQUIRED_DLLS:
        try:
            ctypes.WinDLL(library)
        except OSError:
            missing.append(library)
    return missing
