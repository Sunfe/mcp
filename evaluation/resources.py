from __future__ import annotations

import ctypes
import os
import platform
import shutil
from ctypes import wintypes
from typing import Final

from evaluation.models import FrozenModel


class MemoryStatus(ctypes.Structure):
    _fields_: Final = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
        (name, ctypes.c_ulonglong) for name in (
            "total_physical", "available_physical", "total_page", "available_page",
            "total_virtual", "available_virtual", "available_extended",
        )
    ]


class ProcessCounters(ctypes.Structure):
    _fields_: Final = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in (
            "peak_working_set", "working_set", "quota_peak_paged", "quota_paged",
            "quota_peak_nonpaged", "quota_nonpaged", "pagefile", "peak_pagefile",
        )
    ]


class Hardware(FrozenModel):
    logical_processors: int | None
    cpu_model: str
    os: str
    total_physical_bytes: int | None
    available_physical_bytes: int | None
    memory_reason: str | None
    disk_total_bytes: int
    disk_free_bytes: int
    disk_scope: str = "current_working_directory_volume"
    gpu: str = "unknown_not_probed"


class ProcessPeak(FrozenModel):
    bytes: int | None
    method: str
    scope: str = "current_process_lifetime_including_setup_and_warmup"
    reason: str | None = None


def hardware() -> Hardware:
    total: int | None = None
    available: int | None = None
    reason: str | None = "memory_api_unavailable"
    cpu = platform.processor() or "unknown"
    if platform.system().startswith("Windows"):
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                cpu = str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
        except OSError:
            cpu = "unknown_registry_unavailable"
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        probe = kernel.GlobalMemoryStatusEx
        probe.argtypes = [ctypes.POINTER(MemoryStatus)]
        probe.restype = wintypes.BOOL
        state = MemoryStatus()
        state.length = ctypes.sizeof(state)
        if probe(ctypes.byref(state)):
            total, available, reason = state.total_physical, state.available_physical, None
    disk = shutil.disk_usage(os.getcwd())
    return Hardware(logical_processors=os.cpu_count(), cpu_model=cpu, os=platform.platform(),
                    total_physical_bytes=total, available_physical_bytes=available,
                    memory_reason=reason, disk_total_bytes=disk.total, disk_free_bytes=disk.free)


def process_peak() -> ProcessPeak:
    if not platform.system().startswith("Windows"):
        return ProcessPeak(bytes=None, method="unavailable", reason="platform_not_implemented")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    current = kernel.GetCurrentProcess
    current.argtypes = []
    current.restype = wintypes.HANDLE
    probe = ctypes.WinDLL("psapi", use_last_error=True).GetProcessMemoryInfo
    probe.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessCounters), wintypes.DWORD]
    probe.restype = wintypes.BOOL
    counters = ProcessCounters()
    counters.cb = ctypes.sizeof(counters)
    if not probe(current(), ctypes.byref(counters), counters.cb):
        return ProcessPeak(bytes=None, method="GetProcessMemoryInfo.PeakWorkingSetSize", reason="os_call_failed")
    return ProcessPeak(bytes=counters.peak_working_set, method="GetProcessMemoryInfo.PeakWorkingSetSize")
