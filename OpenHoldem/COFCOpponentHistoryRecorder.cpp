//******************************************************************************
// OpenOFC opponent hand-history recorder.
//******************************************************************************

#include "StdAfx.h"
#include "COFCOpponentHistoryRecorder.h"

#include <algorithm>
#include <fstream>
#include <sstream>

#include "CScraper.h"
#include "OpenHoldem.h"

namespace {

std::string JsonEscape(const std::string &value) {
  std::ostringstream out;
  for (size_t i = 0; i < value.size(); ++i) {
    const unsigned char c = static_cast<unsigned char>(value[i]);
    switch (c) {
      case '\\': out << "\\\\"; break;
      case '"': out << "\\\""; break;
      case '\b': out << "\\b"; break;
      case '\f': out << "\\f"; break;
      case '\n': out << "\\n"; break;
      case '\r': out << "\\r"; break;
      case '\t': out << "\\t"; break;
      default:
        if (c < 0x20) {
          char buf[8] = {0};
          sprintf_s(buf, "\\u%04x", static_cast<unsigned int>(c));
          out << buf;
        } else {
          out << static_cast<char>(c);
        }
    }
  }
  return out.str();
}

void AppendCardArray(std::ostringstream &out, const COFCCard *cards, int count) {
  out << "[";
  for (int i = 0; i < count; ++i) {
    if (i != 0) out << ",";
    out << cards[i].value;
  }
  out << "]";
}

void AppendBoard(std::ostringstream &out, const COFCPlayerBoard &board) {
  out << "{\"top\":";
  AppendCardArray(out, board.top, kOFCTopCards);
  out << ",\"middle\":";
  AppendCardArray(out, board.middle, kOFCMiddleCards);
  out << ",\"bottom\":";
  AppendCardArray(out, board.bottom, kOFCBottomCards);
  out << "}";
}

int RoundFromOpponentKnownCount(int known) {
  switch (known) {
    case 5: return 0;
    case 7: return 1;
    case 9: return 2;
    case 11: return 3;
    case 13: return 4;
    default: return -1;
  }
}

std::string LocalTimestamp() {
  SYSTEMTIME now;
  GetLocalTime(&now);
  char buffer[64] = {0};
  sprintf_s(buffer, "%04u-%02u-%02uT%02u:%02u:%02u.%03u",
    now.wYear, now.wMonth, now.wDay,
    now.wHour, now.wMinute, now.wSecond, now.wMilliseconds);
  return buffer;
}

bool SaveBitmap(HBITMAP h_bitmap, const char *filename) {
  if (h_bitmap == NULL || filename == NULL || *filename == 0) return false;

  HDC hdc_screen = CreateDC("DISPLAY", NULL, NULL, NULL);
  if (hdc_screen == NULL) return false;
  HDC hdc_compatible = CreateCompatibleDC(hdc_screen);
  if (hdc_compatible == NULL) {
    DeleteDC(hdc_screen);
    return false;
  }

  BITMAP bmp;
  memset(&bmp, 0, sizeof(bmp));
  if (!GetObject(h_bitmap, sizeof(BITMAP), &bmp)) {
    DeleteDC(hdc_compatible);
    DeleteDC(hdc_screen);
    return false;
  }

  const int color_bits = static_cast<int>(bmp.bmPlanes * bmp.bmBitsPixel);
  const size_t info_size = color_bits > 8
    ? sizeof(BITMAPINFOHEADER)
    : sizeof(BITMAPINFOHEADER) + sizeof(RGBQUAD) * (1 << min(8, color_bits));
  PBITMAPINFO info = reinterpret_cast<PBITMAPINFO>(calloc(1, info_size));
  if (info == NULL) {
    DeleteDC(hdc_compatible);
    DeleteDC(hdc_screen);
    return false;
  }
  info->bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
  if (color_bits <= 8) info->bmiHeader.biClrUsed = (1 << color_bits);

  bool ok = false;
  LPBYTE bits = NULL;
  HANDLE file = INVALID_HANDLE_VALUE;
  BITMAPFILEHEADER header;
  DWORD written = 0;
  memset(&header, 0, sizeof(header));

  if (!GetDIBits(hdc_compatible, h_bitmap, 0, bmp.bmHeight,
      NULL, info, DIB_RGB_COLORS)) goto cleanup;
  info->bmiHeader.biCompression = BI_RGB;
  bits = reinterpret_cast<LPBYTE>(calloc(1, info->bmiHeader.biSizeImage));
  if (bits == NULL) goto cleanup;
  if (!GetDIBits(hdc_compatible, h_bitmap, 0,
      static_cast<WORD>(info->bmiHeader.biHeight), bits, info,
      DIB_RGB_COLORS)) goto cleanup;

  file = CreateFile(filename, GENERIC_READ | GENERIC_WRITE, 0, NULL,
    CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
  if (file == INVALID_HANDLE_VALUE) goto cleanup;

  header.bfType = 0x4d42;
  header.bfOffBits = static_cast<DWORD>(sizeof(BITMAPFILEHEADER)
    + info->bmiHeader.biSize
    + info->bmiHeader.biClrUsed * sizeof(RGBQUAD));
  header.bfSize = header.bfOffBits + info->bmiHeader.biSizeImage;

  if (!WriteFile(file, &header, sizeof(header), &written, NULL)) goto cleanup;
  if (!WriteFile(file, &info->bmiHeader,
      sizeof(BITMAPINFOHEADER)
        + info->bmiHeader.biClrUsed * sizeof(RGBQUAD),
      &written, NULL)) goto cleanup;
  if (!WriteFile(file, bits, info->bmiHeader.biSizeImage, &written, NULL))
    goto cleanup;
  ok = true;

cleanup:
  if (file != INVALID_HANDLE_VALUE) CloseHandle(file);
  if (bits != NULL) free(bits);
  free(info);
  DeleteDC(hdc_compatible);
  DeleteDC(hdc_screen);
  return ok;
}

}  // namespace

COFCOpponentHistoryRecorder::COFCOpponentHistoryRecorder() {
  hand_sequence_ = 0;
  result_frame_sequence_ = 0;
  Reset();
}

void COFCOpponentHistoryRecorder::Reset() {
  hand_active_ = false;
  reveal_edge_seen_ = false;
  partial_written_ = false;
  flushed_ = false;
  hero_chair_ = -1;
  opponent_chair_ = -1;
  dealer_chair_ = -1;
  highest_round_seen_ = -1;
  reveal_mask_ = 0;
  reveal_count_ = 0;
  hero_fantasy_result_ = false;
  opponent_fantasy_result_ = false;
  hand_id_.clear();
  opponent_raw_name_.clear();
  result_frame_relative_path_.clear();
  for (int i = 0; i < kOFCMaxDiscards; ++i) revealed_discards_[i].Clear();
  for (int r = 0; r < 5; ++r) rounds_[r].Reset();
}

std::string COFCOpponentHistoryRecorder::MakeHandId() const {
  SYSTEMTIME now;
  GetLocalTime(&now);
  char buffer[96] = {0};
  sprintf_s(buffer,
    "ofc_%04u%02u%02u_%02u%02u%02u_%03u_%06lu",
    now.wYear, now.wMonth, now.wDay,
    now.wHour, now.wMinute, now.wSecond, now.wMilliseconds,
    hand_sequence_);
  return buffer;
}

void COFCOpponentHistoryRecorder::StartHand(
    const COFCState &state,
    const COFCVisualObservation &observation) {
  ++hand_sequence_;
  hand_active_ = true;
  reveal_edge_seen_ = false;
  partial_written_ = false;
  flushed_ = false;
  hero_chair_ = state.hero_chair;
  opponent_chair_ = -1;
  dealer_chair_ = state.dealer_chair;
  highest_round_seen_ = -1;
  reveal_mask_ = 0;
  reveal_count_ = 0;
  hero_fantasy_result_ = false;
  opponent_fantasy_result_ = false;
  hand_id_ = MakeHandId();
  opponent_raw_name_.clear();
  result_frame_relative_path_.clear();
  for (int i = 0; i < kOFCMaxDiscards; ++i) revealed_discards_[i].Clear();
  for (int r = 0; r < 5; ++r) rounds_[r].Reset();

  for (int p = 0; p < state.player_count; ++p) {
    if (p != hero_chair_ && state.players[p].occupied) {
      opponent_chair_ = p;
      break;
    }
  }
  if (opponent_chair_ < 0 && state.player_count == 2
      && hero_chair_ >= 0 && hero_chair_ < 2) {
    opponent_chair_ = 1 - hero_chair_;
  }
  UpdateIdentity(observation);
  write_log(true,
    "[OpenOFC HISTORY] hand_start id=%s hero=%d opponent=%d dealer=%d name=\"%s\"\n",
    hand_id_.c_str(), hero_chair_, opponent_chair_, dealer_chair_,
    opponent_raw_name_.c_str());
}

void COFCOpponentHistoryRecorder::UpdateIdentity(
    const COFCVisualObservation &observation) {
  if (opponent_chair_ < 0 || opponent_chair_ >= observation.player_count) return;
  const char *raw = observation.players[opponent_chair_].raw_name;
  if (raw != NULL && *raw != 0) opponent_raw_name_ = raw;
}

void COFCOpponentHistoryRecorder::UpdateRoundSnapshot(const COFCState &state) {
  if (!hand_active_ || opponent_chair_ < 0
      || opponent_chair_ >= state.player_count
      || hero_chair_ < 0 || hero_chair_ >= state.player_count) return;

  const COFCPlayerBoard &opp = state.players[opponent_chair_].board;
  const int opponent_known = opp.CountKnownCards();
  const int round = RoundFromOpponentKnownCount(opponent_known);
  if (round < 0 || round > 4) return;

  RoundSnapshot &snapshot = rounds_[round];
  snapshot.seen = true;
  snapshot.opponent_known = opponent_known;
  snapshot.hero_known = state.players[hero_chair_].board.CountKnownCards();
  snapshot.opponent_board = opp;
  snapshot.hero_board = state.players[hero_chair_].board;
  highest_round_seen_ = max(highest_round_seen_, round);
  write_log(true,
    "[OpenOFC HISTORY] hand=%s round_snapshot=%d opponent_known=%d hero_known=%d\n",
    hand_id_.c_str(), round, snapshot.opponent_known, snapshot.hero_known);
}

void COFCOpponentHistoryRecorder::MergeReveal(
    const COFCVisualObservation &observation) {
  if (opponent_chair_ < 0 || opponent_chair_ >= observation.player_count) return;
  const COFCVisualPlayerObservation &opp = observation.players[opponent_chair_];
  for (int i = 0; i < kOFCMaxDiscards; ++i) {
    const int bit = 1 << i;
    if ((opp.revealed_discard_mask & bit) == 0) continue;
    revealed_discards_[i] = opp.revealed_discards[i];
    reveal_mask_ |= bit;
  }
  reveal_count_ = 0;
  for (int i = 0; i < kOFCMaxDiscards; ++i)
    if ((reveal_mask_ & (1 << i)) != 0) ++reveal_count_;
  hero_fantasy_result_ = observation.hero_result_fantasy;
  opponent_fantasy_result_ = observation.opponent_result_fantasy;
}

bool COFCOpponentHistoryRecorder::SaveEvidenceBitmap(std::string *relative_path) {
  if (relative_path == NULL || p_scraper == NULL || hand_id_.empty()) return false;
  CString root;
  root.Format("%s\\OpenOFC_Data", OpenHoldemDirectory());
  CreateDirectory(root.GetString(), NULL);
  CString frames;
  frames.Format("%s\\opponent_frames", root.GetString());
  CreateDirectory(frames.GetString(), NULL);

  ++result_frame_sequence_;
  CString filename;
  filename.Format("%s\\%s_reveal_%06lu.bmp",
    frames.GetString(), hand_id_.c_str(), result_frame_sequence_);
  if (!SaveBitmap(p_scraper->entire_window_cur(), filename.GetString())) {
    write_log(k_always_log_errors,
      "[OpenOFC HISTORY] result_frame_saved=0 hand=%s path=\"%s\"\n",
      hand_id_.c_str(), filename.GetString());
    return false;
  }
  std::ostringstream rel;
  rel << "OpenOFC_Data\\opponent_frames\\" << hand_id_ << "_reveal_";
  char suffix[32] = {0};
  sprintf_s(suffix, "%06lu.bmp", result_frame_sequence_);
  rel << suffix;
  *relative_path = rel.str();
  write_log(true,
    "[OpenOFC HISTORY] result_frame_saved=1 hand=%s path=\"%s\"\n",
    hand_id_.c_str(), relative_path->c_str());
  return true;
}

void COFCOpponentHistoryRecorder::Flush(
    const char *status,
    const char *reason,
    bool terminal_record) {
  if (!hand_active_ || hand_id_.empty()) return;
  CString root;
  root.Format("%s\\OpenOFC_Data", OpenHoldemDirectory());
  CreateDirectory(root.GetString(), NULL);
  CString path;
  path.Format("%s\\opponent_hands.jsonl", root.GetString());

  std::ostringstream json;
  json << "{\"schema\":\"openofc_opponent_hand_v1\""
       << ",\"hand_id\":\"" << JsonEscape(hand_id_) << "\""
       << ",\"emitted_local\":\"" << LocalTimestamp() << "\""
       << ",\"status\":\"" << JsonEscape(status == NULL ? "" : status) << "\""
       << ",\"reason\":\"" << JsonEscape(reason == NULL ? "" : reason) << "\""
       << ",\"terminal_record\":" << (terminal_record ? 1 : 0)
       << ",\"hero_chair\":" << hero_chair_
       << ",\"opponent_chair\":" << opponent_chair_
       << ",\"dealer_chair\":" << dealer_chair_
       << ",\"opponent_raw_name\":\"" << JsonEscape(opponent_raw_name_) << "\""
       << ",\"name_quality\":\""
       << (opponent_raw_name_.empty() ? "MISSING" : "SCRAPED") << "\""
       << ",\"highest_round_seen\":" << highest_round_seen_
       << ",\"reveal_mask\":" << reveal_mask_
       << ",\"reveal_count\":" << reveal_count_
       << ",\"hero_result_fantasy\":" << (hero_fantasy_result_ ? 1 : 0)
       << ",\"opponent_result_fantasy\":" << (opponent_fantasy_result_ ? 1 : 0)
       << ",\"result_frame\":\"" << JsonEscape(result_frame_relative_path_) << "\""
       << ",\"revealed_discards\":";
  AppendCardArray(json, revealed_discards_, kOFCMaxDiscards);
  json << ",\"rounds\":[";
  for (int r = 0; r < 5; ++r) {
    if (r != 0) json << ",";
    json << "{\"round\":" << r
         << ",\"seen\":" << (rounds_[r].seen ? 1 : 0)
         << ",\"opponent_known\":" << rounds_[r].opponent_known
         << ",\"hero_known\":" << rounds_[r].hero_known
         << ",\"opponent_board\":";
    AppendBoard(json, rounds_[r].opponent_board);
    json << ",\"hero_board\":";
    AppendBoard(json, rounds_[r].hero_board);
    json << "}";
  }
  json << "]}";

  std::ofstream out(path.GetString(), std::ios::out | std::ios::app | std::ios::binary);
  if (!out.is_open()) {
    write_log(k_always_log_errors,
      "[OpenOFC HISTORY] jsonl_write=FAILED hand=%s path=\"%s\"\n",
      hand_id_.c_str(), path.GetString());
    return;
  }
  out << json.str() << "\r\n";
  out.close();
  write_log(true,
    "[OpenOFC HISTORY] jsonl_write=OK hand=%s status=%s reveal=%d mask=0x%X terminal=%d\n",
    hand_id_.c_str(), status == NULL ? "" : status,
    reveal_count_, reveal_mask_, terminal_record ? 1 : 0);
  if (terminal_record) flushed_ = true;
}

void COFCOpponentHistoryRecorder::ObserveCanonical(
    const COFCState &state,
    const COFCVisualObservation &observation) {
  if (!state.valid || state.hero_chair < 0
      || state.hero_chair >= state.player_count) return;

  const bool normal_r0 = state.round_index == 0
    && !state.players[state.hero_chair].fantasy
    && state.hero_incoming_count == 5;
  const bool clearly_new_hand = normal_r0 && hand_active_
    && (highest_round_seen_ > 0 || reveal_edge_seen_ || flushed_);
  if (clearly_new_hand) {
    if (!flushed_) {
      Flush("INCOMPLETE_NEW_HAND_EDGE",
        reveal_edge_seen_
          ? "new R0 arrived before four opponent discard identities were recognized"
          : "new R0 arrived without opponent discard face-up terminal evidence",
        true);
    }
    Reset();
  }
  if (!hand_active_) StartHand(state, observation);

  dealer_chair_ = state.dealer_chair;
  UpdateIdentity(observation);
  UpdateRoundSnapshot(state);
  if (observation.opponent_result_faceup_discards > 0) {
    ObserveTerminalReveal(observation, &state);
  }
}

void COFCOpponentHistoryRecorder::ObserveTerminalReveal(
    const COFCVisualObservation &observation,
    const COFCState *last_canonical_state) {
  if (observation.opponent_result_faceup_discards <= 0) return;
  if (!hand_active_) {
    if (last_canonical_state == NULL || !last_canonical_state->valid) return;
    StartHand(*last_canonical_state, observation);
    UpdateRoundSnapshot(*last_canonical_state);
  }
  UpdateIdentity(observation);
  MergeReveal(observation);

  if (!reveal_edge_seen_) {
    reveal_edge_seen_ = true;
    if (result_frame_relative_path_.empty()) SaveEvidenceBitmap(&result_frame_relative_path_);
    Flush("REVEAL_EDGE_PARTIAL",
      "opponent discard face-up edge captured; waiting for complete identities",
      false);
    partial_written_ = true;
  }

  if (reveal_mask_ == ((1 << kOFCMaxDiscards) - 1) && !flushed_) {
    bool all_rounds = true;
    for (int r = 0; r < 5; ++r) all_rounds = all_rounds && rounds_[r].seen;
    Flush(all_rounds ? "COMPLETE_REVEAL" : "INCOMPLETE_ROUND_HISTORY",
      all_rounds
        ? "five round snapshots plus four face-up opponent discards captured"
        : "all opponent discards captured but one or more complete round snapshots are missing",
      true);
  }
}
