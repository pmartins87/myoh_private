//******************************************************************************
// OpenOFC v5.4.3 HBITMAP v2 partial-reconnect regression.
//
// Uses lossless crops derived from the original replay source
// session_1/frame000036.bmp. The test composes a native 450x830 HBITMAP,
// recognizes the five already-arranged cards plus the ten currently-loose
// cards through production pixel entry points, then reconstructs the current
// Fantasy state with no prior process state.
//******************************************************************************

#include <Windows.h>
#include <gdiplus.h>

#include "COFCFantasyPixelRecognizer.h"
#include "COFCReconstructor.h"

#include <cstring>
#include <iostream>
#include <set>
#include <string>
#include <vector>

#pragma comment(lib, "gdiplus.lib")
#pragma comment(lib, "gdi32.lib")

namespace {

const int kTableWidth = 450;
const int kTableHeight = 830;

struct GdiPlusSession {
  ULONG_PTR token;
  GdiPlusSession() : token(0) {
    Gdiplus::GdiplusStartupInput input;
    if (Gdiplus::GdiplusStartup(&token, &input, NULL) != Gdiplus::Ok)
      token = 0;
  }
  ~GdiPlusSession() {
    if (token != 0) Gdiplus::GdiplusShutdown(token);
  }
};

bool Require(bool condition, const std::string &message) {
  if (condition) return true;
  std::cerr << "FAIL: " << message << "\n";
  return false;
}

HBITMAP CreateBlankTable(unsigned char **bits_out) {
  if (bits_out == NULL) return NULL;
  *bits_out = NULL;
  BITMAPINFO info;
  ZeroMemory(&info, sizeof(info));
  info.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
  info.bmiHeader.biWidth = kTableWidth;
  info.bmiHeader.biHeight = -kTableHeight;
  info.bmiHeader.biPlanes = 1;
  info.bmiHeader.biBitCount = 32;
  info.bmiHeader.biCompression = BI_RGB;
  void *bits = NULL;
  HBITMAP bitmap = CreateDIBSection(
    NULL, &info, DIB_RGB_COLORS, &bits, NULL, 0);
  if (bitmap == NULL || bits == NULL) return NULL;
  std::memset(bits, 0,
    static_cast<size_t>(kTableWidth) * kTableHeight * 4);
  *bits_out = static_cast<unsigned char *>(bits);
  return bitmap;
}

bool BlitLosslessPng(
    const wchar_t *path,
    int expected_width,
    int expected_height,
    int destination_x,
    int destination_y,
    unsigned char *table_bits,
    std::string *error) {
  if (table_bits == NULL) {
    if (error != NULL) *error = "table DIB pixels are null";
    return false;
  }
  Gdiplus::Bitmap image(path, FALSE);
  if (image.GetLastStatus() != Gdiplus::Ok) {
    if (error != NULL) *error = "GDI+ failed to decode v2 fixture PNG";
    return false;
  }
  if (static_cast<int>(image.GetWidth()) != expected_width
      || static_cast<int>(image.GetHeight()) != expected_height) {
    if (error != NULL) *error = "v2 fixture PNG dimensions changed";
    return false;
  }
  if (destination_x < 0 || destination_y < 0
      || destination_x + expected_width > kTableWidth
      || destination_y + expected_height > kTableHeight) {
    if (error != NULL) *error = "v2 fixture destination outside 450x830 table";
    return false;
  }

  Gdiplus::Rect rect(0, 0, expected_width, expected_height);
  Gdiplus::BitmapData data;
  ZeroMemory(&data, sizeof(data));
  if (image.LockBits(
        &rect, Gdiplus::ImageLockModeRead,
        PixelFormat32bppARGB, &data) != Gdiplus::Ok) {
    if (error != NULL) *error = "GDI+ LockBits failed";
    return false;
  }

  const int stride = data.Stride;
  const unsigned char *base =
    static_cast<const unsigned char *>(data.Scan0);
  for (int y = 0; y < expected_height; ++y) {
    const unsigned char *source = stride >= 0
      ? base + static_cast<size_t>(y) * stride
      : base + static_cast<size_t>(expected_height - 1 - y) * (-stride);
    unsigned char *destination = table_bits
      + (static_cast<size_t>(destination_y + y) * kTableWidth
        + destination_x) * 4;
    std::memcpy(destination, source,
      static_cast<size_t>(expected_width) * 4);
  }
  image.UnlockBits(&data);
  if (error != NULL) error->clear();
  return true;
}

std::vector<RECT> ArrangementRects() {
  std::vector<RECT> slots;
  const LONG raw[13][4] = {
    {112, 414, 160, 480}, {167, 415, 216, 481}, {223, 415, 271, 481},
    {112, 488, 160, 554}, {167, 488, 216, 554}, {223, 488, 271, 554},
    {278, 488, 326, 554}, {333, 488, 381, 554},
    {112, 561, 160, 627}, {167, 561, 216, 627}, {223, 561, 271, 627},
    {278, 561, 326, 627}, {333, 561, 381, 627}
  };
  for (int i = 0; i < 13; ++i) {
    RECT r;
    r.left = raw[i][0]; r.top = raw[i][1];
    r.right = raw[i][2]; r.bottom = raw[i][3];
    slots.push_back(r);
  }
  return slots;
}

std::vector<std::string> Labels(
    const std::vector<COFCFantasyPixelObject> &objects) {
  std::vector<std::string> labels;
  for (size_t i = 0; i < objects.size(); ++i)
    labels.push_back(objects[i].card.PhysicalLabel());
  return labels;
}

std::set<std::string> LabelSet(const std::vector<std::string> &labels) {
  return std::set<std::string>(labels.begin(), labels.end());
}

std::string Join(const std::vector<std::string> &labels) {
  std::string out;
  for (size_t i = 0; i < labels.size(); ++i) {
    if (i != 0) out += " ";
    out += labels[i];
  }
  return out;
}

int CardValueFromLabel(const std::string &label) {
  if (label == "JK1") return kOFCCardJoker1;
  if (label == "JK2") return kOFCCardJoker2;
  if (label.size() != 2) return kOFCCardUnknown;
  const std::string ranks = "23456789TJQKA";
  const std::string suits = "cdhs";
  const size_t rank = ranks.find(label[0]);
  const size_t suit = suits.find(label[1]);
  if (rank == std::string::npos || suit == std::string::npos)
    return kOFCCardUnknown;
  return static_cast<int>(rank + 13 * suit);
}

bool TestFrame000036(
    const std::wstring &arrangement_path,
    const std::wstring &loose_path) {
  unsigned char *bits = NULL;
  HBITMAP bitmap = CreateBlankTable(&bits);
  if (!Require(bitmap != NULL, "create frame000036 HBITMAP")) return false;

  std::string error;
  if (!BlitLosslessPng(
        arrangement_path.c_str(), 269, 213, 112, 414, bits, &error)
      || !BlitLosslessPng(
        loose_path.c_str(), 410, 105, 20, 630, bits, &error)) {
    DeleteObject(bitmap);
    return Require(false, "frame000036 compose: " + error);
  }

  const std::vector<RECT> slots = ArrangementRects();
  std::vector<bool> occupied;
  std::vector<COFCFantasyPixelCard> arrangement_cards;
  if (!COFCFantasyPixelRecognizer::RecognizeArrangementSlots(
        bitmap, slots, &occupied, &arrangement_cards, &error)) {
    DeleteObject(bitmap);
    return Require(false,
      "frame000036 production arrangement recognition: " + error);
  }
  if (!Require(occupied.size() == 13 && arrangement_cards.size() == 13,
        "frame000036 arrangement recognizer must preserve 13 destinations")) {
    DeleteObject(bitmap);
    return false;
  }

  const std::vector<std::string> expected_bottom = {
    "Js", "9s", "7s", "6s", "3s"
  };
  std::vector<std::string> arranged;
  for (int i = 0; i < 13; ++i) {
    const bool should_be_occupied = i >= 8;
    if (!Require(occupied[i] == should_be_occupied,
          "frame000036 occupancy mismatch at arrangement index "
          + std::to_string(i))) {
      DeleteObject(bitmap);
      return false;
    }
    if (!occupied[i]) continue;
    const std::string label = arrangement_cards[i].PhysicalLabel();
    arranged.push_back(label);
    if (!Require(label == expected_bottom[i - 8],
          "frame000036 bottom card mismatch at index "
          + std::to_string(i - 8) + " got=" + label)) {
      DeleteObject(bitmap);
      return false;
    }
  }

  std::vector<COFCFantasyPixelObject> loose;
  if (!COFCFantasyPixelRecognizer::RecognizeLooseObjectsUnbound(
        bitmap, false, &loose, &error)) {
    DeleteObject(bitmap);
    return Require(false,
      "frame000036 production loose recognition: " + error);
  }
  DeleteObject(bitmap);

  const std::vector<std::string> loose_labels = Labels(loose);
  const std::vector<std::string> expected_loose = {
    "Ah", "Ac", "Kh", "Jd", "Tc", "9c", "6h", "5h", "3c", "2s"
  };
  if (!Require(arranged == expected_bottom,
        "frame000036 exact arranged sequence mismatch; actual="
        + Join(arranged))) return false;
  if (!Require(loose_labels == expected_loose,
        "frame000036 exact loose sequence mismatch; actual="
        + Join(loose_labels))) return false;

  std::vector<std::string> physical_union = arranged;
  physical_union.insert(
    physical_union.end(), loose_labels.begin(), loose_labels.end());
  if (!Require(physical_union.size() == 15
        && LabelSet(physical_union).size() == 15,
        "frame000036 must expose 5 arranged + 10 loose = 15 unique cards"))
    return false;

  COFCVisualObservation obs;
  obs.Reset();
  obs.valid = true;
  obs.player_count = 2;
  obs.hero_chair = 1;
  obs.acting_chair = 1;
  obs.dealer_chair = -1;
  obs.dealer_known = false;
  obs.round_index = -1;
  obs.fantasy_card_count = 15;
  obs.hero_can_prepare = true;
  obs.hero_timer_active = false;
  obs.confirm_visible = false;
  for (int p = 0; p < 2; ++p) {
    obs.players[p].occupied = true;
    obs.players[p].source_chair = p;
    obs.players[p].fantasy = (p == 1);
  }

  for (int i = 0; i < 5; ++i) {
    const int value = CardValueFromLabel(arranged[i]);
    if (!Require(value != kOFCCardUnknown,
          "frame000036 arranged card produced unknown OFC value"))
      return false;
    obs.players[1].visual_board.bottom[i].value = value;
  }
  for (size_t i = 0; i < loose.size(); ++i) {
    const int value = CardValueFromLabel(loose_labels[i]);
    if (!Require(value != kOFCCardUnknown,
          "frame000036 loose card produced unknown OFC value"))
      return false;
    obs.hero_loose_cards[i].value = value;
    obs.hero_loose_sources[i].valid = true;
    obs.hero_loose_sources[i].card_value = value;
    obs.hero_loose_sources[i].rect = loose[i].source_rect;
  }
  obs.hero_loose_count = static_cast<int>(loose.size());

  COFCState state;
  error.clear();
  if (!COFCReconstructor::ReconstructCurrentScreen(obs, &state, &error)) {
    return Require(false,
      "frame000036 fresh-process current-screen reconstruction: " + error);
  }
  if (!Require(state.valid && state.players[1].fantasy,
        "frame000036 must reconstruct one valid canonical Fantasy state"))
    return false;
  if (!Require(state.fantasy_card_count == 15
        && state.hero_incoming_count == 15,
        "frame000036 canonical Fantasy count/incoming count must remain 15"))
    return false;
  if (!Require(!state.dealer_known,
        "frame000036 fresh reconnect must tolerate missing dealer marker"))
    return false;

  int pending = 0;
  for (int i = 0; i < kOFCMaxIncomingCards; ++i) {
    if (state.pending[i].active) ++pending;
  }
  if (!Require(pending == 5,
        "frame000036 fresh reconnect must preserve five tentative placements"))
    return false;

  std::cout
    << "HBITMAP_V2 frame000036 arranged=" << Join(arranged)
    << " loose=" << Join(loose_labels)
    << " union=15 previous=NULL dealer_known=0 pending=5 PASS\n";
  return true;
}

}  // namespace

int wmain(int argc, wchar_t **argv) {
  if (argc != 3) {
    std::cerr
      << "usage: COFCHBitmapV2Selftest <frame000036-arrangement.png> "
      << "<frame000036-loose.png>\n";
    return 2;
  }
  GdiPlusSession gdiplus;
  if (!Require(gdiplus.token != 0, "start GDI+")) return 1;
  if (!TestFrame000036(argv[1], argv[2])) return 1;
  std::cout
    << "PASS OpenOFC v5.4.3 HBITMAP v2 partial reconnect: "
    << "real pixels -> native HBITMAP -> production recognizers -> fresh state\n";
  return 0;
}
