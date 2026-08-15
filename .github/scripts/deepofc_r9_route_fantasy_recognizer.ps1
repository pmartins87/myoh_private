$ErrorActionPreference = 'Stop'
$utf8 = New-Object System.Text.UTF8Encoding($false)

$path = 'OpenHoldem/COFCScraper.cpp'
$text = Get-Content -Raw -Encoding UTF8 $path
$eol = if ($text.Contains("`r`n")) { "`r`n" } else { "`n" }

if ($text -notmatch 'DEEPOFC_NATIVE_FANTASY15_RECOGNIZER_CERTIFIED') {
  $anchor = 'using namespace std;' + $eol
  if (-not $text.Contains($anchor)) { throw 'Could not find namespace anchor' }
  $insert = @(
    'using namespace std;',
    '',
    '// Native Fantasy recognition is a separate capability from tablemap mode',
    '// detection. Keep this 0 until a real-pixel C++ replay gate certifies the',
    '// implementation. A tablemap value alone can never make an unfinished build',
    '// treat Fantasy pixels as a valid observation.',
    '#define DEEPOFC_NATIVE_FANTASY15_RECOGNIZER_CERTIFIED 0'
  ) -join $eol
  $text = $text.Replace($anchor, $insert + $eol)
}

if ($text -notmatch 'bool CScraper::ScrapeOFCFantasyVisualObservation\(') {
  $anchor = 'bool CScraper::ScrapeOFCVisualObservation() {'
  $pos = $text.IndexOf($anchor)
  if ($pos -lt 0) { throw 'Could not locate ScrapeOFCVisualObservation' }

  $method = @(
    'bool CScraper::ScrapeOFCFantasyVisualObservation(int player_count, int hero_chair) {',
    '  // This function is intentionally unreachable from a replay/production',
    '  // draft while ofc_fantasy_recognizer_calibrated=0. It also carries an',
    '  // independent build-capability gate so an incorrectly edited tablemap',
    '  // cannot activate an uncertified native recognizer.',
    '  if (!p_tablemap->OFCFantasyRecognizerCalibrated()) {',
    '    write_log(k_always_log_errors,',
    '      "[DeepOFC] Fantasy recognizer route called without tablemap authority\n");',
    '    return false;',
    '  }',
    '  if (!p_tablemap->OFCFantasy15GeometryMeasured()) {',
    '    write_log(k_always_log_errors,',
    '      "[DeepOFC] Fantasy recognizer authority present but measured Fantasy15 geometry is absent\n");',
    '    return false;',
    '  }',
    '  if (player_count != 2 || hero_chair != 1) {',
    '    // Current measured 450x830 Fantasy geometry is HU/hero-chair-1 only.',
    '    // Never extrapolate it to 3-player or another chair mapping.',
    '    write_log(k_always_log_errors,',
    '      "[DeepOFC] Current Fantasy15 geometry only certifies HU hero_chair=1\n");',
    '    return false;',
    '  }',
    '',
    '  // Prove that the geometry package contains the complete measured source',
    '  // and arrangement contract before any pixel classifier is allowed to run.',
    '  CString region;',
    '  for (int i = 0; i < 15; ++i) {',
    '    region.Format("ofc_fantasy15_src%02d", i);',
    '    if (!DeepOFCRegionExists(region)) {',
    '      write_log(k_always_log_errors,',
    '        "[DeepOFC] Missing measured Fantasy15 source region: %s\n",',
    '        region.GetString());',
    '      return false;',
    '    }',
    '  }',
    '  const int row_counts[3] = {3, 5, 5};',
    '  const char *row_names[3] = {"top", "middle", "bottom"};',
    '  for (int row = 0; row < 3; ++row) {',
    '    for (int i = 0; i < row_counts[row]; ++i) {',
    '      region.Format("ofc_fantasy15_arrange_%s%d", row_names[row], i);',
    '      if (!DeepOFCRegionExists(region)) {',
    '        write_log(k_always_log_errors,',
    '          "[DeepOFC] Missing measured Fantasy15 arrangement region: %s\n",',
    '          region.GetString());',
    '        return false;',
    '      }',
    '    }',
    '  }',
    '  if (!DeepOFCRegionExists("ofc_fantasy15_unused_span")) {',
    '    write_log(k_always_log_errors,',
    '      "[DeepOFC] Missing measured Fantasy15 unused-card span\n");',
    '    return false;',
    '  }',
    '',
    '#if DEEPOFC_NATIVE_FANTASY15_RECOGNIZER_CERTIFIED',
    '  // The certified implementation will populate COFCVisualObservation here',
    '  // from _entire_window_cur, using the measured source geometry and a',
    '  // fail-closed distance+margin classifier. The compile-time flag may only',
    '  // become 1 in the same commit whose real-pixel native replay gate passes.',
    '  return false;',
    '#else',
    '  write_log(k_always_log_errors,',
    '    "[DeepOFC] Fantasy tablemap authority requested, but this OH build has no certified native Fantasy15 pixel recognizer\n");',
    '  return false;',
    '#endif',
    '}',
    ''
  ) -join $eol
  $text = $text.Substring(0, $pos) + $method + $text.Substring($pos)
}

$new = @(
  '  if (fantasy_active) {',
  '    if (!p_tablemap->OFCFantasyRecognizerCalibrated()) {',
  '      write_log(k_always_log_errors,',
  '        "[DeepOFC] Fantasy arrangement detected; normal geometry is forbidden and Fantasy recognizer authority is OFF\n");',
  '      return false;',
  '    }',
  '    // Never fall through to normal row/incoming geometry while Fantasy is',
  '    // active. The isolated path has its own tablemap and build authority.',
  '    return ScrapeOFCFantasyVisualObservation(player_count, hero_chair);',
  '  }'
) -join $eol

if ($text -notmatch 'Fantasy recognizer authority is OFF') {
  $pattern = '(?s)  if \(fantasy_active\) \{\s*write_log\(k_always_log_errors,\s*"\[DeepOFC\] Fantasy arrangement detected; normal geometry is forbidden until the 14-17-card Fantasy pixel path is certified\\n"\);\s*return false;\s*\}'
  $updated = [regex]::Replace($text, $pattern, [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $new }, 1)
  if ($updated -eq $text) {
    throw 'Could not structurally replace old Fantasy fail-closed routing block'
  }
  $text = $updated
}

[System.IO.File]::WriteAllText((Resolve-Path $path), $text, $utf8)
Write-Host 'DeepOFC Fantasy recognizer router patch applied.'
Select-String -Path $path -Pattern 'DEEPOFC_NATIVE_FANTASY15_RECOGNIZER_CERTIFIED|ScrapeOFCFantasyVisualObservation|Fantasy recognizer authority is OFF'
