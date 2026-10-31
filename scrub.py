"""Exact-value byte scrubber. Explicit files only; dry run is the default."""
import argparse
import json
import os
from pathlib import Path
import stat

MAX_BYTES = 64 * 1024 * 1024


def patterns(values):
    result = set()
    for value in values:
        if not isinstance(value, str) or len(value) < 4:
            raise ValueError('values must have at least four characters')
        forms = {value, json.dumps(value, ensure_ascii=True)[1:-1],
                 json.dumps(value, ensure_ascii=False)[1:-1]}
        for form in forms:
            for encoding in ('utf-8', 'utf-16-le'):
                result.add(form.encode(encoding))
    if not result:
        raise ValueError('no patterns')
    return sorted(result, key=lambda item: (-len(item), item))


def ranges(data, needles):
    hits = []
    for needle in needles:
        start = data.find(needle)
        while start >= 0:
            hits.append((start, start + len(needle)))
            start = data.find(needle, start + 1)
    merged = []
    for start, end in sorted(hits):
        if merged and start < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def regular(path):
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('links refused')
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_BYTES:
        raise ValueError('unsupported input')
    return path


def scrub(path, needles, apply=False):
    path = regular(path)
    with path.open('r+b' if apply else 'rb') as stream:
        data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError('input too large')
        found = ranges(data, needles)
        output = bytearray(data)
        for start, end in found:
            output[start:end] = b'X' * (end - start)
        if apply and found:
            # A value composed of the replacement bytes cannot be removed this way.
            if ranges(output, needles):
                raise ValueError('replacement conflicts with a value')
            # In-place writes preserve the inode for existing append handles.
            for start, end in found:
                stream.seek(start)
                stream.write(output[start:end])
            stream.flush()
            os.fsync(stream.fileno())
            stream.seek(0)
            verified = stream.read()
            if len(verified) != len(data) or ranges(verified, needles):
                raise ValueError('verification failed')
    return {'mode': 'apply' if apply else 'dry-run', 'ranges': len(found),
            'changed': bool(apply and found), 'bytes': len(data)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--values', type=Path, required=True,
                        help='JSON array of known values; never printed')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('files', nargs='+', type=Path)
    args = parser.parse_args(argv)
    try:
        source = regular(args.values)
        values = json.loads(source.read_text(encoding='utf-8-sig'))
        if not isinstance(values, list):
            raise ValueError('expected array')
        needles = patterns(values)
        targets = [regular(path) for path in args.files]
        if len(set(targets)) != len(targets) or source in targets:
            raise ValueError('duplicate or protected input')
        for index, path in enumerate(targets, 1):
            print(json.dumps({'file': index, **scrub(path, needles, args.apply)}, sort_keys=True))
        return 0
    except (OSError, ValueError, UnicodeError):
        print('ERROR: input or verification failed; values withheld')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
