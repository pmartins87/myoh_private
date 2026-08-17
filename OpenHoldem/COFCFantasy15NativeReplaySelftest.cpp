#include <Windows.h>

#include <cstdio>
#include <iostream>
#include <string>
#include <vector>

#include "COFCFantasy15PixelRecognizer.h"

namespace {

HBITMAP Load(const std::string &root, int frame) {
  char name[64];
  sprintf_s(name, "frame%06d.bmp", frame);
  const std::string path = root + "\\" + name;
  return static_cast<HBITMAP>(LoadImageA(
    NULL, path.c_str(), IMAGE_BITMAP, 0, 0,
    LR_LOADFROMFILE | LR_CREATEDIBSECTION));
}

std::vector<std::string> Labels(
    const std::vector<COFCFantasyPixelObject> &objects) {
  std::vector<std::string> result;
  for (size_t i = 0; i < objects.size(); ++i)
    result.push_back(objects[i].card.PhysicalLabel());
  return result;
}

bool Same(
    const std::vector<std::string> &actual,
    const char *const expected[],
    int count) {
  if (actual.size() != static_cast<size_t>(count)) return false;
  for (int i = 0; i < count; ++i)
    if (actual[i] != expected[i]) return false;
  return true;
}

bool Initial(
    const std::string &root,
    int frame,
    const char *const expected[],
    std::vector<std::string> *labels) {
  HBITMAP bitmap = Load(root, frame);
  if (bitmap == NULL) return false;
  std::vector<COFCFantasyPixelObject> objects;
  std::string error;
  const bool ok = COFCFantasy15PixelRecognizer::RecognizeInitialFanObjects(
    bitmap, &objects, &error);
  DeleteObject(bitmap);
  if (!ok) {
    std::cerr << "initial frame " << frame << " rejected: " << error << "\n";
    return false;
  }
  *labels = Labels(objects);
  if (!Same(*labels, expected, 15)) {
    std::cerr << "initial frame " << frame << " mismatch\n";
    return false;
  }
  return true;
}

bool Loose(
    const std::string &root,
    int frame,
    bool upright,
    const std::vector<std::string> &original,
    const char *const expected[],
    int count,
    bool expected_accept) {
  HBITMAP bitmap = Load(root, frame);
  if (bitmap == NULL) return false;
  std::vector<COFCFantasyPixelObject> objects;
  std::string error;
  const bool ok = COFCFantasy15PixelRecognizer::RecognizeCurrentLooseObjects(
    bitmap, upright, original, &objects, &error);
  DeleteObject(bitmap);
  if (ok != expected_accept) {
    std::cerr << "loose frame " << frame << " acceptance mismatch: "
      << error << "\n";
    return false;
  }
  if (!ok) return true;
  if (!Same(Labels(objects), expected, count)) {
    std::cerr << "loose frame " << frame << " identity mismatch\n";
    return false;
  }
  return true;
}

bool PersistentJokers(const std::string &root) {
  HBITMAP bitmap = Load(root, 54);
  if (bitmap == NULL) return false;
  RECT jk2 = {169, 583, 224, 659};
  RECT jk1 = {289, 583, 344, 659};
  RECT standard = {229, 583, 284, 659};
  int a = 0, b = 0, c = 0;
  std::string error;
  const bool ok =
    COFCFantasy15PixelRecognizer::DetectPersistentJoker(bitmap, jk2, &a, &error)
    && COFCFantasy15PixelRecognizer::DetectPersistentJoker(bitmap, jk1, &b, &error)
    && COFCFantasy15PixelRecognizer::DetectPersistentJoker(bitmap, standard, &c, &error);
  DeleteObject(bitmap);
  return ok && a == 2 && b == 1 && c == 0;
}

std::vector<RECT> ArrangementRects() {
  const RECT measured[] = {
    {112,414,160,480}, {167,415,216,481}, {223,415,271,481},
    {112,488,160,554}, {167,488,216,554}, {223,488,271,554},
    {278,488,326,554}, {333,488,381,554},
    {112,561,160,627}, {167,561,216,627}, {223,561,271,627},
    {278,561,326,627}, {333,561,381,627}
  };
  return std::vector<RECT>(measured, measured + 13);
}

bool Arrangement(
    const std::string &root,
    int frame,
    const std::vector<std::string> *expected_set,
    const char *const expected_slots[]) {
  HBITMAP bitmap = Load(root, frame);
  if (bitmap == NULL) return false;
  std::vector<bool> occupied;
  std::vector<COFCFantasy15PixelCard> cards;
  std::string error;
  const std::vector<RECT> rects = ArrangementRects();
  const bool ok = expected_set == NULL
    ? COFCFantasy15PixelRecognizer::RecognizeArrangementSlots(
        bitmap, rects, &occupied, &cards, &error)
    : COFCFantasy15PixelRecognizer::RecognizeArrangementSlotsAgainstExpected(
        bitmap, rects, *expected_set, &occupied, &cards, &error);
  DeleteObject(bitmap);
  if (!ok) {
    std::cerr << "arrangement frame " << frame << " rejected: "
      << error << "\n";
    return false;
  }
  std::vector<std::string> labels;
  for (size_t i = 0; i < occupied.size(); ++i) {
    if (!occupied[i] || !cards[i].valid) {
      std::cerr << "arrangement frame " << frame
        << " has an empty/invalid slot " << i << "\n";
      return false;
    }
    labels.push_back(cards[i].PhysicalLabel());
  }
  if (!Same(labels, expected_slots, 13)) {
    std::cerr << "arrangement frame " << frame << " identity mismatch\n";
    return false;
  }
  return true;
}

}  // namespace

int main(int argc, char **argv) {
  if (argc != 2) {
    std::cerr << "usage: COFCFantasy15NativeReplaySelftest FRAMES_DIR\n";
    return 2;
  }
  const char *initial32[] = {
    "Ah","Ac","Kh","Js","Jd","Tc","9s","9c","7s","6s","6h","5h","3s","3c","2s"};
  const char *initial52[] = {
    "JK1","JK2","Ac","Kd","Qc","Qd","Js","9s","9h","7s","6h","4s","4c","3s","2c"};
  const char *initial60[] = {
    "Ac","Ad","Qd","Tc","8c","7h","7c","6d","5c","4h","4d","3s","3c","3d","2s"};
  std::vector<std::string> original32, original52, original60;
  if (!Initial(argv[1], 32, initial32, &original32)
      || !Initial(argv[1], 52, initial52, &original52)
      || !Initial(argv[1], 60, initial60, &original60)) return 1;

  const char *reflow36[] = {"Ah","Ac","Kh","Jd","Tc","9c","6h","5h","3c","2s"};
  const char *reflow39[] = {"Ah","Ac","Kh","Jd","Tc","9c","6h","5h","3s","3c"};
  const char *reflow40[] = {"Kh","Jd","Tc","9c","6h","5h"};
  const char *upright53[] = {"3s","2c"};
  const char *upright61[] = {"4h","2s"};
  const char *arrangement53[] = {
    "Ac","Kd","6h","Qc","Qd","9h","4s","4c",
    "JK1","JK2","Js","9s","7s"};
  const char *arrangement62[] = {
    "7h","3s","3c","Ac","Tc","8c","7c","5c",
    "Ad","Qd","6d","4d","3d"};
  const char *unused[] = {""};
  if (!Loose(argv[1], 35, false, original32, unused, 0, false)
      || !Loose(argv[1], 36, false, original32, reflow36, 10, true)
      || !Loose(argv[1], 37, false, original32, unused, 0, false)
      || !Loose(argv[1], 39, false, original32, reflow39, 10, true)
      || !Loose(argv[1], 40, false, original32, reflow40, 6, true)
      || !Loose(argv[1], 41, false, original32, unused, 0, false)
      || !Loose(argv[1], 53, true, original52, upright53, 2, true)
      || !Loose(argv[1], 61, true, original60, upright61, 2, true)
      || !Loose(argv[1], 62, true, original60, upright61, 2, true)
      || !PersistentJokers(argv[1])) return 1;

  std::vector<std::string> expected62;
  for (size_t i = 0; i < original60.size(); ++i)
    if (original60[i] != "4h" && original60[i] != "2s")
      expected62.push_back(original60[i]);
  if (!Arrangement(argv[1], 53, NULL, arrangement53)
      || !Arrangement(argv[1], 62, &expected62, arrangement62)) return 1;

  std::cout << "DEEPOFC FANTASY15 NATIVE REPLAY: PASS\n";
  return 0;
}
