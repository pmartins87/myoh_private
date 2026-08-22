from __future__ import print_function

import base64
import hashlib
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests' / 'fixtures' / 'openofc_v543_joker_pixel'
B64DIR = FIXTURE / 'b64'
HEXDIR = FIXTURE / 'hex'
BINDIR = FIXTURE / 'bin'
OUTDIR = ROOT / 'fixture-materialized'

B64_HEAD = [
    ('frame000005_arrangement_00.txt', 8000, 'c1e1331860040279badd49156d1e5165cec4bd93'),
    ('frame000005_arrangement_01.txt', 8000, 'bc65f5346f3ce940bd7ed2c88117c82b8d3263a1'),
    ('frame000005_arrangement_02.txt', 8000, '97bcf43c3850f84615b5472be5933a9397017648'),
    ('frame000005_arrangement_03.txt', 8000, 'fb109f9bb6b08a9e33b4608f2afb7ed012581735'),
]

HEX_MIDDLE = [
    ('frame000005_mid_00.hex', 2000, '34f7ba91b2b8a9668d201f26f38b2530c37354a1'),
    ('frame000005_mid_01.hex', 2000, 'd1fed9b8e4d34a51d9661f938bef4e3260dca0cc'),
    ('frame000005_mid_02.hex', 2000, '28f7d66dbe0831aa184f55eef2a65f57b5a6ecc7'),
    ('frame000005_mid_03a.hex', 500, 'f9dfe8f97d43c7384455c25bbdee7832adbca9c2'),
    ('frame000005_mid_03b.hex', 500, '4ffe13164601c8bbc9631e040444330263b908ef'),
    ('frame000005_mid_03c.hex', 500, 'b0e58f9bd4dd01f1815cbf62d5944b0f83672f7a'),
    ('frame000005_mid_03d.hex', 500, '9fdb9995fd30f1be6a425339f82eb40428dac316'),
    ('frame000005_mid_04.hex', 2000, 'dfa63847e289584aecf759813aa65b6bf8c26de5'),
    ('frame000005_mid_05.hex', 2000, 'fb68fe6097b72d45e78e1a156aab47710910b0ea'),
]

BIN_TAIL = [
    ('frame000005_tail_00.bin', 1000, '9af03eda9563c0c1776f60c4ac7cfd4c4866d531'),
    ('frame000005_tail_01.bin', 1000, 'bb0e826b4b17835db8ae4660af0be6b95c979881'),
    ('frame000005_tail_02.bin', 1000, '338c1a65a1e42695e02b281ca264b455a70edd84'),
    ('frame000005_tail_03.bin', 1000, '7c4b799f4a54987248446a335c0cdcfccc6052fa'),
    ('frame000005_tail_04.bin', 1000, '9dcd14aad9e654a6c991ef151f44adf6feff09bd'),
    ('frame000005_tail_05.bin', 1000, '74771cde83c5b60d012686f886f4a6266b88a4f8'),
]

B64_LAST = ('frame000005_arrangement_06.txt', 5404, '05de489cb57e770d0738f6ba337ca140a84a3a68')

EXPECTED_PNG_BYTES = 40052
EXPECTED_PNG_SHA256 = '30274d1bc42b26d4254f6646079c69f7f7e4f780f35452ac8d4e5ebb5cfa2921'
EXPECTED_WIDTH = 210
EXPECTED_HEIGHT = 208
SOURCE_BMP_SHA256 = '6ad9be294cabef91ee9d45a9fcfc9f324ed676df91a2e15d04e1db1b54e756b5'
SOURCE_ROI = '[80,98)-[290,306)'


def git_blob_sha(data):
    return hashlib.sha1(('blob %d\0' % len(data)).encode('ascii') + data).hexdigest()


def fail(message):
    raise SystemExit(message)


def read_b64(path, expected_len, expected_blob):
    raw = path.read_bytes()
    actual_blob = git_blob_sha(raw)
    print('REAL_JOKER_B64_PART file=%s chars=%d expected_blob=%s actual_blob=%s' % (
        path.name, len(raw), expected_blob, actual_blob))
    if len(raw) != expected_len:
        fail('unexpected Base64 chunk length for %s' % path.name)
    if actual_blob != expected_blob:
        fail('Git blob SHA mismatch for %s' % path.name)
    try:
        text = raw.decode('ascii')
    except UnicodeDecodeError:
        fail('non-ASCII Base64 chunk %s' % path.name)
    if re.search(r'[^A-Za-z0-9+/=]', text):
        fail('invalid Base64 character in %s' % path.name)
    try:
        return base64.b64decode(text, validate=True)
    except Exception as exc:
        fail('strict Base64 decode failed for %s: %s' % (path.name, exc))


def read_hex(path, expected_len, expected_blob):
    raw = path.read_bytes()
    actual_blob = git_blob_sha(raw)
    print('REAL_JOKER_HEX_PART file=%s chars=%d expected_blob=%s actual_blob=%s' % (
        path.name, len(raw), expected_blob, actual_blob))
    if len(raw) != expected_len:
        fail('unexpected HEX chunk length for %s' % path.name)
    if actual_blob != expected_blob:
        fail('Git blob SHA mismatch for %s' % path.name)
    try:
        text = raw.decode('ascii')
    except UnicodeDecodeError:
        fail('non-ASCII HEX chunk %s' % path.name)
    if re.search(r'[^0-9a-f]', text):
        fail('invalid lowercase HEX character in %s' % path.name)
    try:
        return bytes.fromhex(text)
    except ValueError as exc:
        fail('HEX decode failed for %s: %s' % (path.name, exc))


def read_binary(path, expected_len, expected_blob):
    raw = path.read_bytes()
    actual_blob = git_blob_sha(raw)
    print('REAL_JOKER_BIN_PART file=%s bytes=%d expected_blob=%s actual_blob=%s' % (
        path.name, len(raw), expected_blob, actual_blob))
    if len(raw) != expected_len:
        fail('unexpected binary chunk length for %s' % path.name)
    if actual_blob != expected_blob:
        fail('Git blob SHA mismatch for %s' % path.name)
    return raw


def main():
    pieces = []

    for name, expected_len, expected_blob in B64_HEAD:
        part = read_b64(B64DIR / name, expected_len, expected_blob)
        if len(part) != 6000:
            fail('unexpected decoded head size for %s' % name)
        pieces.append(part)

    hex_total = b''.join(read_hex(HEXDIR / name, expected_len, expected_blob)
                         for name, expected_len, expected_blob in HEX_MIDDLE)
    if len(hex_total) != 6000:
        fail('HEX middle must decode to exactly 6000 bytes')
    pieces.append(hex_total)

    bin_total = b''.join(read_binary(BINDIR / name, expected_len, expected_blob)
                         for name, expected_len, expected_blob in BIN_TAIL)
    if len(bin_total) != 6000:
        fail('binary tail must total exactly 6000 bytes')
    pieces.append(bin_total)

    last_name, last_len, last_blob = B64_LAST
    last = read_b64(B64DIR / last_name, last_len, last_blob)
    if len(last) != 4052:
        fail('final Base64 chunk must decode to exactly 4052 bytes')
    pieces.append(last)

    png = b''.join(pieces)
    digest = hashlib.sha256(png).hexdigest()
    print('REAL_JOKER_PNG bytes=%d sha256=%s' % (len(png), digest))
    if len(png) != EXPECTED_PNG_BYTES:
        fail('materialized PNG length mismatch')
    if digest != EXPECTED_PNG_SHA256:
        fail('materialized PNG SHA-256 mismatch')
    if png[:8] != b'\x89PNG\r\n\x1a\n':
        fail('materialized payload is not PNG')
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
