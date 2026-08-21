//******************************************************************************
// OpenOFC v5.4.3 real-pixel development gate.
//
// Uses an exact lossless crop from a real OFC/Fantasy capture and drives the
// production generic Fantasy pixel-recognition API without prior process state.
//******************************************************************************

#include <Windows.h>
#include <gdiplus.h>

#include "COFCFantasyPixelRecognizer.h"

#include <cstring>
#include <iostream>
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

bool BlitPngCrop(
    const wchar_t *path,
    int destination_x,
    int destination_y,
    unsigned char *table_bits,
    std::string *error) {
  Gdiplus::Bitmap image(path, FALSE);
  if (image.GetLastStatus() != Gdiplus::Ok) {
    if (error != NULL) *error = "GDI+ failed to decode real-pixel fixture";
    return false;
  }
  const int width = static_cast<int>(image.GetWidth());
  const int height = static_cast<int>(image.GetHeight());
  if (width != 410 || height != 105) {
    if (error != NULL) *error = "real-pixel fixture dimensions changed";
    return false;
  }

  Gdiplus::Rect rect(0, 0, width, height);
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
  for (int y = 0; y < height; ++y) {
    const unsigned char *source = stride >= 0
        ? base + static_cast<size_t>(y) * stride
        : base + static_cast<size_t>(height - 1 - y) * (-stride);
    unsigned char *destination = table_bits
        + (static_cast<size_t>(destination_y + y) * kTableWidth
           + destination_x) * 4;
    std::memcpy(destination, source, static_cast<size_t>(width) * 4);
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
  std::string result;
  for (size_t i = 0; i < labels.size(); ++i) {
    if (i != 0) result += " ";
    result += labels[i];
  }
  return result;
}

void DiagnoseFixedInitialPath(
    HBITMAP bitmap,
    const std::vector<std::string> &expected) {
  std::vector<COFCFantasyPixelObject> fixed;
  std::string error;
  const bool ok = COFCFantasy15PixelRecognizer::RecognizeInitialFanObjects(
      bitmap, &fixed, &error);
  if (!ok) {
    std::cout << "DIAG fixed_initial_path=FAIL error=" << error << "\n";
    return;
  }
  const std::vector<std::string> labels = Labels(fixed);
  std::cout << "DIAG fixed_initial_path="
            << (labels == expected ? "PASS" : "MISMATCH")
            << " cards=" << Join(labels) << "\n";
}

bool TestFrame000033(const std::wstring &fixture_path) {
  unsigned char *bits = NULL;
  HBITMAP bitmap = CreateBlankTable(&bits);
  if (!Require(bitmap != NULL, "create 450x830 HBITMAP")) return false;

  std::string error;
  if (!BlitPngCrop(fixture_path.c_str(), 20, 630, bits, &error)) {
    DeleteObject(bitmap);
    return Require(false, "compose real frame000033 crop: " + error);
  }

  const std::vector<std::string> expected = {
    "Ah", "Ac", "Kh", "Js", "Jd", "Tc", "9s", "9c",
    "7s", "6s", "6h", "5h", "3s", "3c", "2s"
  };

  // Differential diagnostic: the compatibility path uses the measured initial
  // fan rectangles. The generic runtime path below must still pass independently.
  DiagnoseFixedInitialPath(bitmap, expected);

  std::vector<COFCFantasyPixelObject> unbound;
  if (!COFCFantasyPixelRecognizer::RecognizeLooseObjectsUnbound(
        bitmap, false, &unbound, &error)) {
    DeleteObject(bitmap);
    return Require(false, "unbound real-pixel recognition: " + error);
  }

  const std::vector<std::string> actual = Labels(unbound);
  if (!Require(actual == expected,
        "frame000033 exact left-to-right identities mismatch; actual="
        + Join(actual))) {
    DeleteObject(bitmap);
    return false;
  }
  if (!Require(unbound.size() == 15,
        "frame000033 must expose exactly 15 loose objects")) {
    DeleteObject(bitmap);
    return false;
  }
  for (size_t i = 0; i < unbound.size(); ++i) {
    if (!Require(unbound[i].valid && unbound[i].fresh_from_current_bitmap,
          "every real-pixel object must be valid and fresh")) {
      DeleteObject(bitmap);
      return false;
    }
    if (!Require(unbound[i].detected_layout_count == 15,
          "dynamic geometry must report layout_count=15")) {
      DeleteObject(bitmap);
      return false;
    }
  }

  std::vector<COFCFantasyPixelObject> bound;
  if (!COFCFantasyPixelRecognizer::RecognizeLooseObjectsBound(
        bitmap, false, expected, &bound, &error)) {
    DeleteObject(bitmap);
    return Require(false, "bound real-pixel recognition: " + error);
  }
  DeleteObject(bitmap);

  if (!Require(Labels(bound) == expected,
        "bound physical-card lineage changed frame000033 identities"))
    return false;

  std::cout << "REAL_PIXEL frame000033 cards=" << Join(actual)
            << " layout_count=15 bootstrap=UNBOUND bound_lineage=PASS\n";
  return true;
}

}  // namespace

int wmain(int argc, wchar_t **argv) {
  GdiPlusSession gdiplus;
  if (!Require(gdiplus.token != 0, "initialize GDI+")) return 1;
  if (!Require(argc == 2, "usage: COFCRealPixelCorpusSelftest.exe <fixture.png>"))
    return 1;
  if (!TestFrame000033(argv[1])) return 1;
  std::cout << "PASS: OpenOFC real-pixel development corpus gate\n";
  std::cout << "FIELD_PACKAGE_AUTHORIZED=0\n";
  return 0;
}
