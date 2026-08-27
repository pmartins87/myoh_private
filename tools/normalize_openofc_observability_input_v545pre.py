from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(path: Path):
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    return text, eol, bom


def write_text(path: Path, text: str, eol: str, bom: bool):
    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)


def normalize_main_tick_guard():
    path = ROOT / "OpenHoldem" / "COFCRuntimeController.cpp"
    text, eol, bom = read_text(path)

    marker = "  if (!state.valid || !observation.valid) {\n"
    start = text.rfind(marker)
    if start < 0:
        raise RuntimeError("v5.4.5 pre-normalizer: main Tick invalid-perception guard missing")
    ret = text.find("    return;\n  }\n", start)
    if ret < 0:
        raise RuntimeError("v5.4.5 pre-normalizer: Tick invalid-perception guard terminator missing")
    end = ret + len("    return;\n  }\n")

    old = text[start:end]
    if "INVALID_PERCEPTION" not in old:
        raise RuntimeError(
            "v5.4.5 pre-normalizer: last invalid-state guard is not INVALID_PERCEPTION"
        )

    canonical = '''  if (!state.valid || !observation.valid) {
    write_log(true, "[DeepOFC TICK] action=NONE reason=INVALID_PERCEPTION\\n");
    return;
  }
'''
    text = text[:start] + canonical + text[end:]
    write_text(path, text, eol, bom)

    verify = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    if verify.count(canonical) != 1:
        raise RuntimeError("v5.4.5 pre-normalizer: canonical Tick guard not unique after rewrite")
    print("OpenOFC v5.4.5 PRE Tick invalid-perception input normalization: PASS")


def harden_v545_status_injector():
    path = ROOT / "tools" / "apply_openofc_observability_deghost_v545.py"
    text, eol, bom = read_text(path)

    helper_marker = "def patch_visible_runtime_status():\n"
    if text.count(helper_marker) != 1:
        raise RuntimeError("v5.4.5 PRE: status helper insertion marker missing")

    first_label = '"surface policy calculation",'
    last_label = '"surface no-preparable-cards wait",'
    function_pos = text.find(helper_marker)
    first_pos = text.find(first_label, function_pos)
    last_pos = text.find(last_label, first_pos + 1)
    if first_pos < 0 or last_pos < 0:
        raise RuntimeError("v5.4.5 PRE: brittle status replacement range missing")

    start = text.rfind("    replace_once(\n", function_pos, first_pos)
    if start < 0:
        raise RuntimeError("v5.4.5 PRE: first brittle replace_once start missing")
    end = text.find("    )\n", last_pos)
    if end < 0:
        raise RuntimeError("v5.4.5 PRE: last brittle replace_once terminator missing")
    end += len("    )\n")
    text = text[:start] + "    patch_remaining_statuses_structurally()\n" + text[end:]

    helper = r'''def patch_remaining_statuses_structurally():
    rel = "OpenHoldem/COFCRuntimeController.cpp"
    path, text, eol, bom = read_source(rel)

    def before_unique(marker: str, insertion: str, label: str):
        nonlocal text
        if insertion.strip() in text:
            return
        count = text.count(marker)
        if count != 1:
            raise RuntimeError(
                f"{label}: semantic marker expected once, got {count}: {marker!r}"
            )
        text = text.replace(marker, insertion + marker, 1)
        print(f"patched {rel}: {label}")

    def after_unique(marker: str, insertion: str, label: str, optional: bool = False):
        nonlocal text
        if insertion.strip() in text:
            return
        count = text.count(marker)
        if count != 1:
            if optional and count == 0:
                print(f"skipped {rel}: {label} (obsolete materialized branch absent)")
                return
            raise RuntimeError(
                f"{label}: semantic marker expected once, got {count}: {marker!r}"
            )
        text = text.replace(marker, marker + insertion, 1)
        print(f"patched {rel}: {label}")

    def before_log_token(token: str, insertion: str, label: str):
        nonlocal text
        if insertion.strip() in text:
            return
        count = text.count(token)
        if count != 1:
            raise RuntimeError(
                f"{label}: log token expected once, got {count}: {token!r}"
            )
        pos = text.find(token)
        starts = [
            text.rfind("      write_log(true,\n", 0, pos),
            text.rfind("    write_log(true,\n", 0, pos),
            text.rfind("  write_log(true,\n", 0, pos),
        ]
        start = max(starts)
        if start < 0:
            raise RuntimeError(f"{label}: owning write_log call not found")
        text = text[:start] + insertion + text[start:]
        print(f"patched {rel}: {label}")

    before_unique(
        "  if (!COFCBaselinePolicy::Choose(state, &action, &error)) {\n",
        '  OpenOFCSetUserStatus("CALCULANDO JOGADA");\n',
        "surface policy calculation",
    )
    before_unique(
        "  if (!orchestrator_.StartTurn(\n",
        '  OpenOFCSetUserStatus("EXECUTANDO JOGADA");\n',
        "surface arrangement execution",
    )
    after_unique(
        "    ++drag_wait_cycles_;\n",
        '    OpenOFCSetUserStatus("VERIFICANDO MOVIMENTO");\n',
        "surface drag verification wait",
    )
    before_log_token(
        "[DeepOFC CONFIRM] sending region=%s rect=(%ld,%ld,%ld,%ld) round=%d fantasy=%d",
        '  OpenOFCSetUserStatus("CONFIRMANDO JOGADA");\n',
        "surface Confirm send",
    )
    after_unique(
        "  phase_ = kConfirmSent;\n",
        '  OpenOFCSetUserStatus("CONFIRM ENVIADO - aguardando proxima rodada");\n',
        "surface post-Confirm wait",
    )
    after_unique(
        "    if (!state.decision_finalizable) {\n",
        '      OpenOFCSetUserStatus("AGUARDANDO OPONENTE - Confirm retido");\n',
        "surface dealer provisional wait",
    )
    before_log_token(
        "[OpenOFC PROVISIONAL] opponent_final_info=1 reanalyze=1 timer=%d",
        '    OpenOFCSetUserStatus("OPONENTE FINALIZOU - recalculando");\n',
        "surface dealer final replan",
    )
    before_log_token(
        "[OpenOFC UNKNOWN] action=WAIT reason=OPENING_IDENTITY_UNREAD",
        '      OpenOFCSetUserStatus("RECUPERANDO CARTA INICIAL - identidade ilegivel");\n',
        "surface opening UNKNOWN wait",
    )
    after_unique(
        "  if (!state.hero_can_prepare) {\n",
        '    OpenOFCSetUserStatus("AGUARDANDO CARTAS / TRANSICAO");\n',
        "surface no-preparable-cards wait",
        optional=True,
    )

    write_source(path, text, eol, bom)


'''
    text = text.replace(helper_marker, helper + helper_marker, 1)
    write_text(path, text, eol, bom)

    verify = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    if verify.count("def patch_remaining_statuses_structurally():") != 1:
        raise RuntimeError("v5.4.5 PRE: structural status helper did not stick")
    if verify.count("    patch_remaining_statuses_structurally()\n") != 1:
        raise RuntimeError("v5.4.5 PRE: structural status helper call did not stick")
    print("OpenOFC v5.4.5 PRE structural status-injection hardening: PASS")


def main():
    normalize_main_tick_guard()
    harden_v545_status_injector()


if __name__ == "__main__":
    main()
