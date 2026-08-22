//******************************************************************************
// OpenOFC v5.4.3 native real-pixel HBITMAP regression.
//
// The fixtures are lossless pixel crops from the user's v5.3 field-failure
// frames. This test reconstructs a 450x830 HBITMAP, drives the production
// Fantasy pixel recognizer, and then feeds the partial current-screen result
// into the native reconstructor with no prior process state.
//******************************************************************************

#include <Windows.h>
#include <gdiplus.h>

#include "COFCFantasyPixelRecognizer.h"
#include "COFCReconstructor.h"

#include <algorithm>
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
    if (Gdiplus::GdiplusStartup(&token, &input, NULL) != Gdiplus::Ok) token = 0;
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
  std::memset(bits, 0, static_cast<size_t>(kTableWidth) * kTableHeight * 4);
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
    if (error != NULL) *error = "GDI+ failed to decode fixture PNG";
    return false;
  }
  if (static_cast<int>(image.GetWidth()) != expected_width
      || static_cast<int>(image.GetHeight()) != expected_height) {
    if (error != NULL) *error = "fixture PNG dimensions changed";
    return false;
  }
  if (destination_x < 0 || destination_y < 0
      || destination_x + expected_width > kTableWidth
      || destination_y + expected_height > kTableHeight) {
    if (error != NULL) *error = "fixture destination is outside 450x830 table";
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
  const unsigned char *base = static_cast<const unsigned char *>(data.Scan0);
  for (int y = 0; y < expected_height; ++y) {
    const unsigned char *source = stride >= 0
      ? base + static_cast<size_t>(y) * stride
      : base + static_cast<size_t>(expected_height - 1 - y) * (-stride);
    unsigned char *destination = table_bits
      + (static_cast<size_t>(destination_y + y) * kTableWidth + destination_x) * 4;
    std::memcpy(destination, source, static_cast<size_t>(expected_width) * 4);
  }
  image.UnlockBits(&data);
  if (error != NULL) error->clear();
  return true;
}

std::vector<std::string> Labels(
    const std::vector<COFCFantasyPixelObject> &objects) {
  std::vector<std::string> out;
  for (size_t i = 0; i < objects.size(); ++i) {
    out.push_back(objects[i].card.PhysicalLabel());
  }
  return out;
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

int PixelCardValue(const COFCFantasyPixelCard &card) {
  return CardValueFromLabel(card.PhysicalLabel());
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

bool TestInitialDualJokerFrame(const std::wstring &fixture_root) {
  unsigned char *bits = NULL;
  HBITMAP bitmap = CreateBlankTable(&bits);
  if (!Require(bitmap != NULL, "create initial-frame HBITMAP")) return false;
  std::string error;
  const std::wstring path = fixture_root + L"\\field_frame000000_loose.png";
  if (!BlitLosslessPng(path.c_str(), 410, 105, 20, 630, bits, &error)) {
    DeleteObject(bitmap);
    return Require(false, "initial fixture compose: " + error);
  }

  std::vector<COFCFantasyPixelObject> objects;
  if (!COFCFantasyPixelRecognizer::RecognizeLooseObjectsUnbound(
        bitmap, false, &objects, &error)) {
    DeleteObject(bitmap);
    return Require(false, "initial field HBITMAP recognition: " + error);
  }
  DeleteObject(bitmap);

  const std::vector<std::string> actual = Labels(objects);
  const std::vector<std::string> expected = {
    "JK1", "JK2", "Jh", "Ts", "9s", "9h", "9c", "9d",
    "8s", "8c", "7h", "7c", "6c", "5h", "3c"
  };
  if (!Require(actual.size() == 15,
        "initial field frame must expose exactly 15 current loose objects")) return false;
  if (!Require(LabelSet(actual).size() == 15,
        "initial field frame physical identities must be unique")) return false;
  if (!Require(LabelSet(actual) == LabelSet(expected),
        "initial field frame exact card set mismatch; actual=" + Join(actual))) return false;
  if (!Require(std::find(actual.begin(), actual.end(), "JK1") != actual.end()
        && std::find(actual.begin(), actual.end(), "JK2") != actual.end(),
        "initial field frame must preserve both Joker physical identities")) return false;

  std::cout << "HBITMAP_FIELD initial15 dual_joker cards=" << Join(actual)
            << " PASS\n";
  return true;
}

bool TestPartialReconnectFrame(const std::wstring &fixture_root) {
  unsigned char *bits = NULL;
  HBITMAP bitmap = CreateBlankTable(&bits);
  if (!Require(bitmap != NULL, "create partial-frame HBITMAP")) return false;
  std::string error;
  const std::wstring arrangement_path = fixture_root + L"\\field_frame000005_arrangement.png";
  const std::wstring loose_path = fixture_root + L"\\field_frame000005_loose.png";
  if (!BlitLosslessPng(
        arrangement_path.c_str(), 269, 213, 112, 414, bits, &error)
      || !BlitLosslessPng(
        loose_path.c_str(), 410, 105, 20, 630, bits, &error)) {
    DeleteObject(bitmap);
    return Require(false, "partial fixture compose: " + error);
  }

  const std::vector<RECT> slots = ArrangementRects();
  std::vector<bool> occupied;
  std::vector<COFCFantasyPixelCard> arrangement_cards;
  if (!COFCFantasyPixelRecognizer::RecognizeArrangementSlots(
        bitmap, slots, &occupied, &arrangement_cards, &error)) {
    DeleteObject(bitmap);
    return Require(false, "partial arrangement recognition: " + error);
  }
  if (!Require(occupied.size() == 13 && arrangement_cards.size() == 13,
        "partial arrangement result must preserve 13 physical destinations")) {
    DeleteObject(bitmap);
    return false;
  }

  const std::vector<std::string> expected_bottom = {"Qs", "Ts", "9s", "8s", "6s"};
  int arrangement_count = 0;
  for (int i = 0; i < 13; ++i) {
    const bool should_be_occupied = i >= 8;
    if (!Require(occupied[i] == should_be_occupied,
          "partial field frame occupancy mismatch at arrangement index "
          + std::to_string(i))) {
      DeleteObject(bitmap);
      return false;
    }
    if (!occupied[i]) continue;
    ++arrangement_count;
    if (!Require(arrangement_cards[i].PhysicalLabel() == expected_bottom[i - 8],
          "partial field frame bottom card mismatch at index "
          + std::to_string(i - 8) + " got="
          + arrangement_cards[i].PhysicalLabel())) {
      DeleteObject(bitmap);
      return false;
    }
  }

  std::vector<COFCFantasyPixelObject> loose;
  if (!COFCFantasyPixelRecognizer::RecognizeLooseObjectsUnbound(
        bitmap, false, &loose, &error)) {
    DeleteObject(bitmap);
    return Require(false, "partial current loose recognition: " + error);
  }
  DeleteObject(bitmap);

  const std::vector<std::string> loose_labels = Labels(loose);
  const std::vector<std::string> expected_loose = {
    "Ad", "Qd", "Jc", "Th", "9c", "7c", "4d", "3s", "3c", "2s"
  };
  if (!Require(arrangement_count == 5 && loose_labels.size() == 10,
        "partial field frame must reconstruct 5 arranged + 10 loose")) return false;
  if (!Require(LabelSet(loose_labels) == LabelSet(expected_loose),
        "partial loose exact card set mismatch; actual=" + Join(loose_labels))) return false;

  std::vector<std::string> physical_union = expected_bottom;
  physical_union.insert(physical_union.end(), loose_labels.begin(), loose_labels.end());
  if (!Require(physical_union.size() == 15 && LabelSet(physical_union).size() == 15,
        "partial field frame union must be 15 unique physical cards")) return false;

  COFCVisualObservation obs;
  obs.Reset();
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
    obs.players[1].visual_board.bottom[i].value =
      PixelCardValue(arrangement_cards[8 + i]);
  }
  for (size_t i = 0; i < loose.size(); ++i) {
    obs.hero_loose_cards[i].value = PixelCardValue(loose[i].card);
    obs.hero_loose_sources[i].valid = true;
    obs.hero_loose_sources[i].card_value = obs.hero_loose_cards[i].value;
    obs.hero_loose_sources[i].rect = loose[i].source_rect;
  }
  obs.hero_loose_count = static_cast<int>(loose.size());
  obs.valid = true;

  COFCState state;
  error.clear();
  if (!COFCReconstructor::ReconstructCurrentScreen(obs, &state, &error)) {
    return Require(false,
      "fresh-process partial Fantasy current-screen reconstruction: " + error);
  }
  if (!Require(state.valid && state.players[1].fantasy,
        "partial field frame must reconstruct one canonical Fantasy state")) return false;
  if (!Require(state.fantasy_card_count == 15 && state.hero_incoming_count == 15,
        "partial field frame canonical count must remain explicit data=15")) return false;
  if (!Require(!state.dealer_known,
        "real partial reconnect must tolerate missing dealer marker as uncertainty")) return false;

  int pending = 0;
  for (int i = 0; i < kOFCMaxIncomingCards; ++i) {
    if (state.pending[i].active) ++pending;
  }
  if (!Require(pending == 5,
        "fresh partial reconnect must preserve the five current tentative placements")) return false;

  std::cout
    << "HBITMAP_FIELD partial_reconnect arranged=5 loose=10 count=15 "
    << "previous=NULL dealer_known=0 pending=5 PASS\n";
  return true;
}

}  // namespace

int wmain(int argc, wchar_t **argv) {
  if (argc != 2) {
    std::cerr << "usage: COFCFantasyHBitmapSelftest <fixture-directory>\n";
    return 2;
  }
  GdiPlusSession gdiplus;
  if (!Require(gdiplus.token != 0, "start GDI+")) return 1;

  const std::wstring root = argv[1];
  if (!TestInitialDualJokerFrame(root)) return 1;
  if (!TestPartialReconnectFrame(root)) return 1;

  std::cout
    << "PASS OpenOFC v5.4.3 native real-pixel HBITMAP gate: "
    << "field initial dual-Joker + field partial reconnect\n";
  return 0;
}
