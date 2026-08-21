//******************************************************************************
// OpenOFC v5.4.3 real-Joker native-HBITMAP certification gate.
//
// Uses a lossless crop derived from original replay source
// session_1/frame000005.bmp. The crop contains the real orange/red and gray
// Joker glyphs. This test deliberately calls the ordinary production
// RecognizeArrangementSlots() API; expected labels are assertions only and do
// not participate in classification.
//******************************************************************************

#include <Windows.h>
#include <gdiplus.h>

#include "COFCFantasyPixelRecognizer.h"

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
    if (error != NULL) *error = "GDI+ failed to decode real-Joker fixture PNG";
    return false;
  }
  if (static_cast<int>(image.GetWidth()) != expected_width
      || static_cast<int>(image.GetHeight()) != expected_height) {
    if (error != NULL) *error = "real-Joker fixture PNG dimensions changed";
    return false;
  }
  if (destination_x < 0 || destination_y < 0
      || destination_x + expected_width > kTableWidth
      || destination_y + expected_height > kTableHeight) {
    if (error != NULL) *error = "real-Joker fixture destination outside 450x830 table";
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

RECT MakeRect(LONG left, LONG top, LONG right, LONG bottom) {
  RECT rect;
  rect.left = left;
  rect.top = top;
  rect.right = right;
  rect.bottom = bottom;
  return rect;
}

bool TestRealJokers(const std::wstring &fixture_path) {
  unsigned char *bits = NULL;
  HBITMAP bitmap = CreateBlankTable(&bits);
  if (!Require(bitmap != NULL, "create real-Joker 450x830 HBITMAP"))
    return false;

  std::string error;
  if (!BlitLosslessPng(
        fixture_path.c_str(), 210, 208, 80, 98, bits, &error)) {
    DeleteObject(bitmap);
    return Require(false, "compose real-Joker HBITMAP: " + error);
  }

  std::vector<RECT> slots;
  slots.push_back(MakeRect(87, 104, 133, 166));  // real orange/red Joker
  slots.push_back(MakeRect(87, 172, 133, 234));  // real gray Joker

  std::vector<bool> occupied;
  std::vector<COFCFantasyPixelCard> cards;
  if (!COFCFantasyPixelRecognizer::RecognizeArrangementSlots(
        bitmap, slots, &occupied, &cards, &error)) {
    DeleteObject(bitmap);
    return Require(false,
      "unconditioned production Joker recognition: " + error);
  }
  DeleteObject(bitmap);

  if (!Require(occupied.size() == 2 && cards.size() == 2,
        "real-Joker gate must return exactly two slot results"))
    return false;
  if (!Require(occupied[0] && occupied[1],
        "both real Joker slots must be occupied"))
    return false;
  if (!Require(cards[0].valid && cards[1].valid,
        "both real Joker cards must be valid"))
    return false;

  const std::string first = cards[0].PhysicalLabel();
  const std::string second = cards[1].PhysicalLabel();
  if (!Require(first == "JK1",
        "orange/red real Joker must classify as JK1; got=" + first))
    return false;
  if (!Require(second == "JK2",
        "gray real Joker must classify as JK2; got=" + second))
    return false;

  std::set<std::string> unique;
  unique.insert(first);
  unique.insert(second);
  if (!Require(unique.size() == 2,
        "real Joker identities must remain physically distinct"))
    return false;

  std::cout
    << "REAL_JOKER_PIXEL labels=" << first << " " << second
    << " source=session_1/frame000005.bmp"
    << " roi=80,98,290,306 PASS\n";
  std::cout
    << "PASS OpenOFC real Joker pixel: real source -> native HBITMAP -> "
    << "unconditioned production recognizer -> JK1 JK2\n";
  return true;
}

}  // namespace

int wmain(int argc, wchar_t **argv) {
  if (argc != 2) {
    std::cerr
      << "usage: COFCRealJokerPixelSelftest <frame000005-joker-arrangement.png>\n";
    return 2;
  }
  GdiPlusSession gdiplus;
  if (!Require(gdiplus.token != 0, "start GDI+")) return 1;
  if (!TestRealJokers(argv[1])) return 1;
  return 0;
}
