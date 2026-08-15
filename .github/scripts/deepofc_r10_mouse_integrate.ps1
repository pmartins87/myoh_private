$ErrorActionPreference = 'Stop'
$utf8 = New-Object System.Text.UTF8Encoding($false)

$path = 'OpenHoldem/OpenHoldem.cpp'
$text = Get-Content -Raw -Encoding UTF8 $path
$eol = if ($text.Contains("`r`n")) { "`r`n" } else { "`n" }

if ($text -notmatch 'GetProcAddress\(_mouse_dll, "MouseDragBetweenRects"\)') {
  $needle = '        _dll_mouse_click_drag = (mouse_clickdrag_t) GetProcAddress(_mouse_dll, "MouseClickDrag");'
  if (-not $text.Contains($needle)) {
    # The source uses tabs in some historical revisions; fall back to the exact
    # semantic line regardless of indentation.
    $needle = '_dll_mouse_click_drag = (mouse_clickdrag_t) GetProcAddress(_mouse_dll, "MouseClickDrag");'
    $index = $text.IndexOf($needle)
    if ($index -lt 0) { throw 'Could not find MouseClickDrag loader line' }
    $lineStart = $text.LastIndexOf($eol, $index)
    if ($lineStart -lt 0) { $lineStart = 0 } else { $lineStart += $eol.Length }
    $lineEnd = $text.IndexOf($eol, $index)
    if ($lineEnd -lt 0) { $lineEnd = $text.Length }
    $fullLine = $text.Substring($lineStart, $lineEnd - $lineStart)
    $indent = $fullLine.Substring(0, $fullLine.IndexOf('_dll_mouse_click_drag'))
    $replacement = $fullLine + $eol + $indent + '_dll_mouse_drag_between = (mouse_dragbetween_t) GetProcAddress(_mouse_dll, "MouseDragBetweenRects");'
    $text = $text.Substring(0, $lineStart) + $replacement + $text.Substring($lineEnd)
  } else {
    $replacement = $needle + $eol + '        _dll_mouse_drag_between = (mouse_dragbetween_t) GetProcAddress(_mouse_dll, "MouseDragBetweenRects");'
    $text = $text.Replace($needle, $replacement)
  }
}

if ($text -notmatch '_dll_mouse_drag_between==NULL') {
  $old = 'if (_dll_mouse_process_message==NULL || _dll_mouse_click==NULL || _dll_mouse_click_drag==NULL)'
  if (-not $text.Contains($old)) { throw 'Could not find mouse DLL symbol guard' }
  $new = 'if (_dll_mouse_process_message==NULL || _dll_mouse_click==NULL || _dll_mouse_click_drag==NULL || _dll_mouse_drag_between==NULL)'
  $text = $text.Replace($old, $new)
}

[System.IO.File]::WriteAllText((Resolve-Path $path), $text, $utf8)
Select-String -Path $path -Pattern 'MouseClickDrag|MouseDragBetweenRects|_dll_mouse_drag_between==NULL'
