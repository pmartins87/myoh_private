from __future__ import print_function

import base64
import hashlib
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests' / 'fixtures' / 'openofc_v543_joker_pixel'
B64DIR = FIXTURE / 'b64'
OUTDIR = ROOT / 'fixture-materialized'

PARTS = [
    ('frame000005_arrangement_00.txt', 8000, 'c1e1331860040279badd49156d1e5165cec4bd93'),
    ('frame000005_arrangement_01.txt', 8000, 'bc65f5346f3ce940bd7ed2c88117c82b8d3263a1'),
    ('frame000005_arrangement_02.txt', 8000, '97bcf43c3850f84615b5472be5933a9397017648'),
    ('frame000005_arrangement_03.txt', 8000, 'fb109f9bb6b08a9e33b4608f2afb7ed012581735'),
    ('frame000005_arrangement_04.txt', 8000, '88604f565aa25dae455703ec4a66eaa99947b644'),
    ('frame000005_arrangement_05.txt', 8000, '45c7fb7c538f71080772dd76d5a70586f15eb649'),
    ('frame000005_arrangement_06.txt', 5404, '05de489cb57e770d0738f6ba337ca140a84a3a68'),
]

EXPECTED_B64_CHARS = 53404
EXPECTED_PNG_BYTES = 40052
EXPECTED_PNG_SHA256 = '30274d1bc42b26d4254f6646079c69f7f7e4f780f35452ac8d4e5ebb5cfa2921'
EXPECTED_WIDTH = 210
EXPECTED_HEIGHT = 208
SOURCE_BMP_SHA256 = '6ad9be294cabef91ee9d45a9fcfc9f324ed676df91a2e15d04e1db1b54e756b5'
SOURCE_ROI = '[80,98)-[290,306)'


def git_blob_sha(data):
    header = ('blob %d\0' % len(data)).encode('ascii')
    return hashlib.sha1(header + data).hexdigest()


def fail(message):
    raise SystemExit(message)


def main():
    pieces = []
    for name, expected_len, expected_blob in PARTS:
        path = B64DIR / name
        raw = path.read_bytes()
        actual_blob = git_blob_sha(raw)
        print('REAL_JOKER_B64_PART file=%s chars=%d expected_blob=%s actual_blob=%s' % (
            name, len(raw), expected_blob, actual_blob))
        if len(raw) != expected_len:
            fail('unexpected chunk length for %s: expected=%d actual=%d' % (
                name, expected_len, len(raw)))
        if actual_blob != expected_blob:
            fail('Git blob SHA mismatch for %s' % name)
        try:
            text = raw.decode('ascii')
        except UnicodeDecodeError:
            fail('non-ASCII byte in %s' % name)
        if re.search(r'[^A-Za-z0-9+/=]', text):
            fail('invalid Base64 character in %s' % name)
        pieces.append(text)

    encoded = ''.join(pieces)
    if len(encoded) != EXPECTED_B64_CHARS:
        fail('combined Base64 length mismatch: expected=%d actual=%d' % (
            EXPECTED_B64_CHARS, len(encoded)))
    try:
        png = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        fail('strict Base64 decode failed: %s' % exc)

    digest = hashlib.sha256(png).hexdigest()
    print('REAL_JOKER_PNG chars=%d bytes=%d sha256=%s' % (
        len(encoded), len(png), digest))
    if len(png) != EXPECTED_PNG_BYTES:
        fail('decoded PNG length mismatch')
    if digest != EXPECTED_PNG_SHA256:
        fail('decoded PNG SHA-256 mismatch')
    if png[:8] != b'\x89PNG\r\n\x1a\n':
        fail('decoded payload is not PNG')
    if png[12:16] != b'IHDR':
        fail('PNG IHDR chunk missing')
    width, height = struct.unpack('>II', png[16:24])
    if width != EXPECTED_WIDTH or height != EXPECTED_HEIGHT:
        fail('PNG dimensions mismatch: expected=%dx%d actual=%dx%d' % (
            EXPECTED_WIDTH, EXPECTED_HEIGHT, width, height))

    OUTDIR.mkdir(parents=True, exist_ok=True)
    out = OUTDIR / 'frame000005_joker_arrangement.png'
    out.write_bytes(png)

    print('REAL_JOKER_SOURCE=session_1/frame000005.bmp')
    print('REAL_JOKER_SOURCE_BMP_SHA256=%s' % SOURCE_BMP_SHA256)
    print('REAL_JOKER_SOURCE_ROI=%s' % SOURCE_ROI)
    print('REAL_JOKER_PIXEL_TRANSPORT=PASS')
    print('REAL_JOKER_PIXEL=NOT_YET_CERTIFIED')
    print('FIELD_PACKAGE_AUTHORIZED=0')


if __name__ == '__main__':
    main()
