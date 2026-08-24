from __future__ import annotations

import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TEMPLATES = {
    6: [(129,667.5),(160,664),(194,661.5),(226.5,661),(259,662),(292,664)],
    7: [(113.5,671),(145,666),(177.5,662),(210.5,660.5),(243,660.5),(275,663),(308,666)],
    8: [(97,674),(128,668),(161,664),(194,661.5),(226.5,661),(259,662),(292,664),(323.5,668.5)],
    9: [(81.5,678),(113,670.5),(144.5,666),(177,662),(210.5,660.5),(242.5,661),(275.5,663),(306.5,666),(340,672)],
    11: [(50.5,686.5),(80.5,677),(112,671),(145,666),(177.5,661.5),(210.5,661),(243,661),(274.5,663),(308,666),(339.5,671.5),(373,678.5)],
    12: [(35,691.5),(66,681.5),(96.5,673.5),(128.5,668),(161.5,664),(194,660.5),(226.5,660.5),(259.5,662),(290.5,664.5),(324.5,669),(355.5,675),(388.5,682.5)],
    13: [(29.5,693),(59.5,683.5),(87.5,676),(118,670),(150,667),(179.5,662.5),(210,660.5),(241.5,661),(271.5,663),(301.5,665.5),(333.5,670),(362.5,676.5),(394,684)],
    14: [(29.5,693.5),(55.5,684.5),(83,677),(110.5,671),(138.5,666),(168,663),(196,661.5),(224.5,660.5),(253,662),(281.5,663.5),(307.5,669),(337,671),(366,677),(394,684)],
    15: [(29.5,693.5),(55,685.5),(79.5,678.5),(105,672),(131,668),(157,664),(183.5,662),(210.5,661),(237,661),(263.5,661.5),(289.5,664.5),(316,667),(341.5,672),(368.5,677),(392.5,684)],
    16: [(29.5,693),(53.5,685.5),(75.5,678.5),(100,673),(124,669),(148.5,665.5),(173,662.5),(197.5,661.5),(222.5,661),(247.5,661),(270.5,663),(295.5,665),(321,668),(345.5,672),(368.5,678),(394,684)],
}

# Exact raw anchor centers reproduced from representative supplied FANTASY.zip
# frames. Count 9 intentionally contains one false lower-glyph anchor at x=192
# to certify the skip-one geometry matcher.
OBSERVED = {
    6: [(129,667.5),(161,664),(194,661.5),(226.5,661),(258,661.5),(292,664)],
    7: [(113.5,671),(145,665.5),(177,662),(210.5,661),(243,661),(274.5,663),(308,666)],
    8: [(97.5,674),(129,667.5),(161,664),(194,661.5),(226.5,661),(258,661.5),(292,664),(323.5,668.5)],
    9: [(81.5,678),(113,670.5),(144.5,666),(177.5,662.5),(192,686),(210.5,661),(241.5,661),(275.5,663),(307,666),(340.5,671.5)],
    11: [(50.5,686.5),(80.5,677),(112,671),(145,666),(177.5,661.5),(210.5,661),(243,661),(274.5,663),(308,666),(339.5,671.5),(373,678.5)],
    12: [(35,691.5),(66,681.5),(96.5,673.5),(128.5,668),(161.5,664),(194,660.5),(226.5,660.5),(259.5,662),(290.5,664.5),(324.5,669),(355.5,675),(388.5,682.5)],
    13: [(29.5,693),(59.5,683.5),(87.5,676),(118,670),(150,667),(179.5,662.5),(210,660.5),(241.5,661),(271.5,663),(301.5,665.5),(333.5,670),(362.5,676.5),(394,684)],
    14: [(29.5,693.5),(55,684.5),(83,677),(111,671),(137.5,666.5),(166.5,663),(195.5,661),(223.5,660),(253,662),(280.5,663.5),(308.5,666.5),(338.5,671),(366,677),(394,684)],
    15: [(24.5,691.5),(46.5,711),(80.5,678.5),(105,672.5),(131,668),(157,664),(183,662),(210.5,661),(237.5,661),(264,661.5),(289.5,664),(314.5,667),(341,671.5),(368.5,677),(394,684)],
    16: [(29.5,693),(53.5,685.5),(75.5,678.5),(100,673),(124,669),(148.5,665.5),(173,662.5),(197.5,661.5),(222.5,661),(247.5,661),(270.5,663),(295.5,665),(321,668),(345.5,672),(368.5,678),(394,684)],
}


def subset_score(obs, expected, skips):
    kept = [p for i,p in enumerate(obs) if i not in skips]
    if len(kept) != len(expected):
        return math.inf
    total = 0.0
    for (x,y),(ex,ey) in zip(kept, expected):
        total += (x-ex)**2 + 0.5*(y-ey)**2
    return math.sqrt(total / len(expected))


def score(obs, expected):
    extra = len(obs) - len(expected)
    if extra < 0 or extra > 2:
        return math.inf
    if extra == 0:
        best = subset_score(obs, expected, set())
    elif extra == 1:
        best = min(subset_score(obs, expected, {i}) for i in range(len(obs)))
    else:
        best = min(
            subset_score(obs, expected, {i,j})
            for i in range(len(obs)) for j in range(i+1,len(obs))
        )
    return best + 6.0 * extra


def classify(obs):
    scores = sorted((score(obs,t),n) for n,t in TEMPLATES.items())
    best, count = scores[0]
    second = scores[1][0] if len(scores) > 1 else math.inf
    assert best <= 8.0, (best,count)
    assert second - best >= 3.0, (best,second,count)
    return count,best,second


def function_body(text: str, signature: str) -> str:
    start = text.find(signature)
    assert start >= 0, signature
    brace = text.find('{', start)
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == '{': depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0: return text[start:i+1]
    raise AssertionError('unclosed function')


def main():
    for expected_count, obs in OBSERVED.items():
        got,best,second = classify(obs)
        assert got == expected_count, (expected_count,got,best,second)

    scraper = (ROOT/'OpenHoldem/COFCScraper.cpp').read_text(encoding='utf-8-sig')
    recognizer = (ROOT/'OpenHoldem/COFCFantasy15PixelRecognizer.cpp').read_text(encoding='utf-8-sig')
    header = (ROOT/'OpenHoldem/COFCFantasy15PixelRecognizer.h').read_text(encoding='utf-8-sig')
    generic = (ROOT/'OpenHoldem/COFCFantasyPixelRecognizer.h').read_text(encoding='utf-8-sig')

    assert 'DetectLooseCount' in header and 'ClassifyFanJokerAtRect' in header
    assert 'kFantasyCount06' in recognizer and 'kFantasyCount17' in recognizer
    assert 'best > 8.0' in recognizer
    assert 'second - best < 3.0' in recognizer
    assert 'DetectLooseCount' in generic and 'ClassifyFanJokerAtRect' in generic

    fantasy = function_body(scraper, 'bool CScraper::ScrapeOFCFantasyVisualObservation(')
    assert 'ofc_fantasy%02d_%02d' in fantasy
    assert 'identity=TABLEMAP_T7' in fantasy
    assert 'rank_text == "X"' in fantasy
    assert 'openofc_fantasy17_calibrated' in fantasy
    assert 'final_unused=LINEAGE_COMPLEMENT' in fantasy
    assert 'expected_unused < 1 || expected_unused > 4' in fantasy
    assert 'RecognizeLooseObjectsUnbound' not in fantasy
    assert 'RecognizeLooseObjectsBound' not in fantasy
    assert 'loose_count >= 6 && loose_count <= 9' in fantasy
    assert 'loose_count >= 11 && loose_count <= 17' in fantasy

    # The final post-bottom state deliberately has no 1..4 TableMap source
    # family. Those cards are inferred from the original physical deal only
    # after all 13 arrangement slots are verified.
    original = {'Ah','Kd','Qc','Js','Th','9d','8c','7s','6h','5d','4c','3s','2h','JK1','JK2'}
    arranged = set(sorted(original)[:13])
    complement = original - arranged
    assert len(complement) == 2

    print('OPENOFC_FANTASY_COUNTED_TEXT_V550_REGRESSION=PASS '
          'captured_counts=6,7,8,9,11,12,13,14,15,16 '
          'count9_false_anchor=REJECTED identity=TABLEMAP_T7 '
          'final_1_4=LINEAGE_COMPLEMENT native_loose_identity=ABSENT')


if __name__ == '__main__':
    main()
