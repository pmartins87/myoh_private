from __future__ import annotations

from pathlib import Path

from openofc_tablemap_identity import validate_v552_semantic_contract


ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def test_central_build_identity() -> None:
    build = text("OpenHoldem/COFCBuildInfo.h")
    assert '#define OPENOFC_PRODUCT_VERSION "5.8.3"' in build
    assert '#define OPENOFC_PRODUCT_VERSION_LABEL "OpenOFC v5.8.3"' in build
    assert '#define OPENOFC_TABLEMAP_ASSET_VERSION "5.5.2"' in build
    assert '#define OPENOFC_TABLEMAP_CONTRACT_VERSION 5' in build


def test_ui_separates_runtime_and_asset_versions() -> None:
    view = text("OpenHoldem/OpenHoldemView.cpp")
    statusbar = text("OpenHoldem/COpenHoldemStatusbar.cpp")
    assert '#include "COFCBuildInfo.h"' in view
    assert '#include "COFCBuildInfo.h"' in statusbar
    assert "OPENOFC_PRODUCT_VERSION_LABEL" in view
    assert "TABLEMAP ASSET" in view
    assert "OPENOFC_TABLEMAP_ASSET_VERSION" in view
    assert "PAIRED V551=OK" not in view
    assert "COUNTED-TEXT V551 SYMBOL MISSING" not in view
    assert "TM V551 REQUIRED" not in statusbar
    assert "OPENOFC_TABLEMAP_ASSET_VERSION" in statusbar
    assert 'OpenOFC  |  KKPoker Joker Ultimate  |  TMv%d' not in view


def test_runtime_status_is_phase_accurate() -> None:
    runtime = text("OpenHoldem/COFCRuntimeController.cpp")
    assert "OPENOFC_V583_BLOCK_STATUS" in runtime
    assert "g_openofc_block_reason = message.empty()" in runtime
    assert '"TRAVADO - " + g_openofc_block_reason' in runtime
    assert 'OpenOFCSetUserStatus(visible.c_str())' in runtime
    assert 'reason=RUNTIME_BLOCKED detail=' in runtime
    assert 'LEITURA INVALIDA - aguardando nova leitura; sem agir' in runtime
    assert 'OpenOFCSetUserStatus("CALCULANDO JOGADA")' in runtime
    assert 'OpenOFCSetUserStatus("EXECUTANDO JOGADA")' in runtime
    assert 'OpenOFCSetUserStatus("AGUARDANDO RESULTADO")' in runtime
    assert 'OpenOFCSetUserStatus("AGUARDANDO VEZ / TRANSICAO")' in runtime
    block = runtime.split("void COFCRuntimeController::Block", 1)[1].split(
        "bool COFCRuntimeController::", 1
    )[0]
    assert block.index("g_openofc_block_reason =") < block.index("phase_ = kBlocked")
    assert block.index("OpenOFCSetUserStatus") < block.index("phase_ = kBlocked")


def test_tablemap_asset_semantic_identity() -> None:
    identity = validate_v552_semantic_contract()
    assert identity["stage"] == "openofc_v5_5_2_fantasy_live_recovery"
    assert identity["contract"] == 5
    assert identity["field_revision"] == 552
    assert int(identity["regions"]) >= 250


def main() -> None:
    test_central_build_identity()
    test_ui_separates_runtime_and_asset_versions()
    test_runtime_status_is_phase_accurate()
    test_tablemap_asset_semantic_identity()
    print(
        "OPENOFC_V583_FIELD_OBSERVABILITY=PASS "
        "runtime_version=5.8.3 tablemap_asset=5.5.2 "
        "blocked_reason=VISIBLE calculating=ACTIVE_DECISION_ONLY "
        "tablemap=V552_SEMANTIC_CONTRACT_VALID"
    )


if __name__ == "__main__":
    main()
