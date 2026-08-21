//******************************************************************************
// OpenOFC v5.4.3 supplied real-pixel replay regression.
//
// Rebuilds a native 450x830 HBITMAP from a lossless 410x105 crop taken from
// frame000033, runs the production generic Fantasy recognizer, then feeds the
// resulting current-screen observation into the native OFC reconstructor.
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
    if (error != NULL) *error = "GDI+ failed to decode replay fixture PNG";
    return false;
  }
  if (static_cast<int>(image.GetWidth()) != expected_width
      || static_cast<int>(image.GetHeight()) != expected_height) {
    if (error != NULL) *error = "replay fixture PNG dimensions changed";
    return false;
  }
  if (destination_x < 0 || destination_y < 0
      || destination_x + expected_width > kTableWidth
      || destination_y + expected_height > kTableHeight) {
    if (error != NULL) *error = "replay fixture destination is outside 450x830 table";
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

std::vector<std::string> Labels(
    const std::vector<COFCFantasyPixelObject> &objects) {
  std::vector<std::string> labels;
  for (size_t i = 0; i < objects.size(); ++i)
    labels.push_back(objects[i].card.PhysicalLabel());
  return labels;
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

bool TestFrame000033(const std::wstring &fixture_path) {
  unsigned char *bits = NULL;
  HBITMAP bitmap = CreateBlankTable(&bits);
  if (!Require(bitmap != NULL, "create frame000033 HBITMAP")) return false;

  std::string error;
  if (!BlitLosslessPng(
        fixture_path.c_str(), 410, 105, 20, 630, bits, &error)) {
    DeleteObject(bitmap);
    return Require(false, "frame000033 compose: " + error);
  }

  std::vector<COFCFantasyPixelObject> objects;
  if (!COFCFantasyPixelRecognizer::RecognizeLooseObjectsUnbound(
        bitmap, false, &objects, &error)) {
    DeleteObject(bitmap);
    return Require(false,
      "frame000033 production loose recognition: " + error);
  }
  DeleteObject(bitmap);

  const std::vector<std::string> actual = Labels(objects);
  const std::vector<std::string> expected = {
    "Ah", "Ac", "Kh", "Js", "Jd", "Tc", "9s", "9c",
    "7s", "6s", "6h", "5h", "3s", "3c", "2s"
  };

  if (!Require(actual.size() == 15,
        "frame000033 must expose exactly 15 loose objects; actual="
        + Join(actual))) return false;
  if (!Require(actual == expected,
        "frame000033 left-to-right physical card sequence mismatch; actual="
        + Join(actual))) return false;
  if (!Require(std::set<std::string>(actual.begin(), actual.end()).size() == 15,
        "frame000033 physical card identities must be unique")) return false;

  for (size_t i = 0; i < objects.size(); ++i) {
    if (!Require(objects[i].valid && objects[i].fresh_from_current_bitmap,
          "frame000033 recognizer must return fresh valid pixel objects"))
      return false;
    if (!Require(objects[i].detected_layout_count == 15,
          "frame000033 dynamic geometry must report layout count=15"))
      return false;
    if (!Require(objects[i].geometry_residual <= 3.5,
          "frame000033 dynamic grid residual exceeded fail-closed bound"))
      return false;
  }

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
  for (size_t i = 0; i < objects.size(); ++i) {
    const int value = CardValueFromLabel(actual[i]);
    if (!Require(value != kOFCCardUnknown,
          "frame000033 produced unknown OFC card value")) return false;
    obs.hero_loose_cards[i].value = value;
    obs.hero_loose_sources[i].valid = true;
    obs.hero_loose_sources[i].card_value = value;
    obs.hero_loose_sources[i].rect = objects[i].source_rect;
  }
  obs.hero_loose_count = static_cast<int>(objects.size());

  COFCState state;
  error.clear();
  if (!COFCReconstructor::ReconstructCurrentScreen(obs, &state, &error)) {
    return Require(false,
      "frame000033 native current-screen reconstruction: " + error);
  }
  if (!Require(state.valid && state.players[1].fantasy,
        "frame000033 must reconstruct one valid canonical Fantasy state"))
    return false;
  if (!Require(state.fantasy_card_count == 15
        && state.hero_incoming_count == 15,
        "frame000033 canonical Fantasy count/incoming count must remain 15"))
    return false;
  if (!Require(!state.dealer_known,
        "frame000033 reconstruction must tolerate unknown dealer marker"))
    return false;

  std::cout << "REAL_PIXEL_REPLAY frame000033 cards=" << Join(actual)
            << " count=15 dealer_known=0 PASS\n";
  return true;
}

}  // namespace

int wmain(int argc, wchar_t **argv) {
  if (argc != 2) {
    std::cerr << "usage: COFCRealPixelReplaySelftest <frame000033-loose.png>\n";
    return 2;
  }
  GdiPlusSession gdiplus;
  if (!Require(gdiplus.token != 0, "start GDI+")) return 1;
  if (!TestFrame000033(argv[1])) return 1;
  std::cout
    << "PASS OpenOFC v5.4.3 supplied real-pixel replay: "
    << "HBITMAP -> production recognizer -> native OFC state\n";
  return 0;
}
