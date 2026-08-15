$ErrorActionPreference = 'Stop'
$utf8 = New-Object System.Text.UTF8Encoding($false)

$path = 'OpenHoldem/CCasinoInterface.cpp'
$text = Get-Content -Raw -Encoding UTF8 $path
$eol = if ($text.Contains("`r`n")) { "`r`n" } else { "`n" }

if ($text -notmatch 'bool CCasinoInterface::DragRectToRect\(') {
  $marker = 'bool CCasinoInterface::ClickButtonSequence('
  $idx = $text.IndexOf($marker)
  if ($idx -lt 0) { throw 'Could not find ClickButtonSequence insertion marker' }

  $methodLines = @(
    'bool CCasinoInterface::DragRectToRect(RECT source_rect, RECT target_rect, int duration_ms) {',
    '  if (theApp._dll_mouse_drag_between == NULL) {',
    '    write_log(k_always_log_errors, "[DeepOFC R10] MouseDragBetweenRects is not loaded\n");',
    '    return false;',
    '  }',
    '  if (p_autoconnector == NULL) return false;',
    '  HWND hwnd = p_autoconnector->attached_hwnd();',
    '  if (hwnd == NULL || !IsWindow(hwnd)) return false;',
    '',
    '  RECT client;',
    '  if (!GetClientRect(hwnd, &client)) return false;',
    '  const bool source_ok = source_rect.right > source_rect.left',
    '    && source_rect.bottom > source_rect.top',
    '    && source_rect.left >= client.left && source_rect.top >= client.top',
    '    && source_rect.right <= client.right && source_rect.bottom <= client.bottom;',
    '  const bool target_ok = target_rect.right > target_rect.left',
    '    && target_rect.bottom > target_rect.top',
    '    && target_rect.left >= client.left && target_rect.top >= client.top',
    '    && target_rect.right <= client.right && target_rect.bottom <= client.bottom;',
    '  if (!source_ok || !target_ok) {',
    '    write_log(k_always_log_errors,',
    '      "[DeepOFC R10] Refusing drag outside attached client bounds src=%d,%d,%d,%d dst=%d,%d,%d,%d client=%d,%d,%d,%d\n",',
    '      source_rect.left, source_rect.top, source_rect.right, source_rect.bottom,',
    '      target_rect.left, target_rect.top, target_rect.right, target_rect.bottom,',
    '      client.left, client.top, client.right, client.bottom);',
    '    return false;',
    '  }',
    '',
    '  // Unlike legacy button clicks, an OFC drag can mutate a multi-card',
    '  // arrangement. Never steal focus and drag if the connected table is not',
    '  // already the foreground window; the higher transaction layer will stop.',
    '  if (TableLostFocus()) {',
    '    write_log(k_always_log_errors,',
    '      "[DeepOFC R10] Refusing drag because attached table lost focus\n");',
    '    return false;',
    '  }',
    '',
    '  write_log(true,',
    '    "[DeepOFC R10] physical drag src=%d,%d,%d,%d dst=%d,%d,%d,%d duration=%d\n",',
    '    source_rect.left, source_rect.top, source_rect.right, source_rect.bottom,',
    '    target_rect.left, target_rect.top, target_rect.right, target_rect.bottom, duration_ms);',
    '  const bool ok = (theApp._dll_mouse_drag_between)(',
    '    hwnd, source_rect, target_rect, duration_ms) != 0;',
    '  if (ok) {',
    '    p_engine_container->symbol_engine_time()->UpdateOnAutoPlayerAction();',
    '  } else {',
    '    write_log(k_always_log_errors,',
    '      "[DeepOFC R10] MouseDragBetweenRects returned failure; transaction must fail closed\n");',
    '  }',
    '  return ok;',
    '}',
    '',
    ''
  )
  $method = $methodLines -join $eol
  $text = $text.Substring(0, $idx) + $method + $text.Substring($idx)
}

[System.IO.File]::WriteAllText((Resolve-Path $path), $text, $utf8)
Select-String -Path $path -Pattern 'DragRectToRect|MouseDragBetweenRects|Refusing drag outside|lost focus'
