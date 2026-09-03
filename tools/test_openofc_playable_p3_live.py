#!/usr/bin/env python3
"""Focused build contract for the OpenOFC P3 hybrid runtime."""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
POLICY_DIR = ROOT / "OpenOFC" / "Policies"
CPP = ROOT / "OpenHoldem" / "COFCP3Policy.cpp"
CONTROLLER = ROOT / "OpenHoldem" / "COFCRuntimeController.cpp"
BUILD_INFO = ROOT / "OpenHoldem" / "COFCBuildInfo.h"
PROJECT = ROOT / "OpenHoldem" / "OpenHoldem.vcxproj"
SELFTEST = ROOT / "tools" / "openofc_p3_policy_selftest.cpp"
FIXTURE = POLICY_DIR / "playable_p3_synthetic_replay_v1.txt"
TABLEMAP = (
    ROOT
    / "OpenOFC"
    / "TableMaps"
    / "KKPoker_Chines_v5_5_2_FANTASY_LIVE_RECOVERY.tm"
)

EXPECTED = {
    "playable_p3_native_manifest.json": (
        "afe3161c6a944f761485742e37271a6079188fd7b258c79ad2740c36e6ca9381"
    ),
    "playable_p3_b0_weights.f64le": (
        "52be780cda5b0e36da645e6ea36fc07dd445fcc6785281a769a91d8fce0d699c"
    ),
    "playable_p3_b1_weights.f64le": (
        "08e3b9d2523f092aee45fddc1170e9ffb7486595ea2f36f8c6db7296df27a0d3"
    ),
    "playable_p3_synthetic_replay_v1.txt": (
        "7cd5878f4628c3d5d8ec0fd43663104c83e7d5baa2ce4a8a4005ee248394254b"
    ),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def verify_runtime_contract() -> None:
    for filename, expected in EXPECTED.items():
        path = POLICY_DIR / filename
        require(path.is_file(), f"missing P3 policy asset: {filename}")
        require(sha(path) == expected, f"P3 policy asset changed: {filename}")

    controller = CONTROLLER.read_text(encoding="utf-8")
    for token in (
        "p3_policy_.Choose",
        "COFCBaselinePolicy::Choose",
        "p3_history_.Observe",
        "orchestrator_.StartTurn",
        "orchestrator_.AdvanceAfterFreshScrape",
        "ClickRectSafely",
        "SendConfirm(",
        "source=%s",
    ):
        require(token in controller, f"hybrid runtime wiring missing: {token}")

    build_info = BUILD_INFO.read_text(encoding="utf-8")
    for token in (
        'OPENOFC_PRODUCT_VERSION "5.9.0"',
        'OPENOFC_TABLEMAP_ASSET_VERSION "5.5.2"',
        "OPENOFC_PHYSICAL_EXECUTION_AUTHORIZED 1",
        "P3_NORMAL_WITH_OPERATIONAL_FALLBACK",
    ):
        require(token in build_info, f"live build identity missing: {token}")

    project = PROJECT.read_text(encoding="utf-8")
    for filename in (
        "COFCP3Policy.cpp",
        "playable_p3_native_manifest.json",
        "playable_p3_b0_weights.f64le",
        "playable_p3_b1_weights.f64le",
    ):
        require(filename in project, f"OpenHoldem project omits P3 input: {filename}")

    require(
        sha(TABLEMAP)
        == "28587f10d3f8436880e6ef98280b5f86d85e26b674f15cfe61f5a03bc5751ee6",
        "live TableMap identity changed",
    )
    tablemap = TABLEMAP.read_text(encoding="ascii")
    require("s$ofc_executor_enabled      1" in tablemap, "executor is disabled")
    require("s$ofc_drag_targets_calibrated 1" in tablemap, "drag targets disabled")


def compile_and_run_policy_parity() -> None:
    compiler = shutil.which("g++") or shutil.which("clang++")
    if compiler is None:
        print("OPENOFC_P3_PORTABLE_COMPILE=SKIP_NO_COMPILER")
        return
    with tempfile.TemporaryDirectory(prefix="openofc-p3-live-") as raw_tmp:
        executable = Path(raw_tmp) / "openofc_p3_policy_selftest"
        subprocess.run(
            [
                compiler,
                "-std=c++11",
                "-DDEEPOFC_P3_STANDALONE",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-I",
                str(ROOT / "OpenHoldem"),
                str(CPP),
                str(SELFTEST),
                "-o",
                str(executable),
            ],
            check=True,
            cwd=ROOT,
        )
        completed = subprocess.run(
            [str(executable), str(POLICY_DIR), str(FIXTURE)],
            check=True,
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        require(
            "OPENOFC_P3_NATIVE_POLICY_PARITY=PASS states=20 decisions=10"
            in completed.stdout,
            "native P3 parity failed",
        )
    print("OPENOFC_P3_PORTABLE_COMPILE=PASS")


def main() -> None:
    verify_runtime_contract()
    compile_and_run_policy_parity()
    print("OPENOFC_PLAYABLE_P3_HYBRID_REGRESSION=PASS")


if __name__ == "__main__":
    main()
