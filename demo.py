"""Demonstrate dry run and apply with a temporary synthetic transcript."""
import json
from pathlib import Path
import tempfile
import scrub


def main():
    with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
        root = Path(directory)
        value = 'synthetic-' + 'transcript-value'
        store, transcript = root / 'values.json', root / 'transcript.txt'
        store.write_text(json.dumps([value]))
        transcript.write_bytes(value.encode() + b'\n' + value.encode('utf-16-le'))
        scrub.main(['--values', str(store), str(transcript)])
        scrub.main(['--values', str(store), '--apply', str(transcript)])


if __name__ == '__main__':
    main()
