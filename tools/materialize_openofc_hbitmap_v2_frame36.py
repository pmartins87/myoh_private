from __future__ import print_function
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests' / 'fixtures' / 'openofc_v543_hbitmap_v2'
PARTS = FIXTURE / 'loose_chunks'
MANIFEST = FIXTURE / 'frame000036_loose_manifest.json'
OUTDIR = ROOT / 'fixture-materialized'
OUTFILE = OUTDIR / 'frame000036_loose.png'


def git_blob_sha(data):
    header = ('blob %d\0' % len(data)).encode('ascii')
    return hashlib.sha1(header + data).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    pieces = []
    for part in manifest['parts']:
        path = PARTS / part['file']
        data = path.read_bytes()
        if len(data) != int(part['bytes']):
            raise SystemExit('size mismatch %s expected=%s actual=%s' % (
                part['file'], part['bytes'], len(data)))
        actual_blob = git_blob_sha(data)
        expected_blob = part['git_blob_sha'].lower()
        print('HBITMAP_V2_LOOSE_PART file=%s bytes=%d expected_blob=%s actual_blob=%s' % (
            part['file'], len(data), expected_blob, actual_blob))
        if actual_blob != expected_blob:
            raise SystemExit('Git blob mismatch for %s' % part['file'])
        pieces.append(data)

    combined = b''.join(pieces)
    actual_sha = hashlib.sha256(combined).hexdigest()
    expected_bytes = int(manifest['png_bytes'])
    expected_sha = manifest['png_sha256'].lower()
    print('HBITMAP_V2_LOOSE_COMBINED bytes=%d expected_bytes=%d sha256=%s expected_sha256=%s' % (
        len(combined), expected_bytes, actual_sha, expected_sha))
    if len(combined) != expected_bytes:
        raise SystemExit('combined byte length mismatch')
    if actual_sha != expected_sha:
        raise SystemExit('combined SHA-256 mismatch')
    if combined[:8] != b'\x89PNG\r\n\x1a\n':
        raise SystemExit('combined file is not PNG')

    OUTDIR.mkdir(parents=True, exist_ok=True)
    OUTFILE.write_bytes(combined)
    print('HBITMAP_V2_FRAME000036_LOOSE_TRANSPORT=PASS')
    print('HBITMAP_V2_FRAME000036=NOT_YET_CERTIFIED')
    print('REAL_JOKER_PIXEL=NOT_YET_CERTIFIED')
    print('FIELD_PACKAGE_AUTHORIZED=0')


if __name__ == '__main__':
    main()
