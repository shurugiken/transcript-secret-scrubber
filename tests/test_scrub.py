import json
import os
import pytest
import scrub


@pytest.mark.parametrize('encoding', ['utf-8', 'utf-16-le'])
@pytest.mark.parametrize('escaped', [False, True])
def test_encodings(tmp_path, encoding, escaped):
    value = 'fake-' + 'value' + '\\"é'
    form = json.dumps(value, ensure_ascii=True)[1:-1] if escaped else value
    data = b'prefix ' + form.encode(encoding) + b' tail'
    path = tmp_path / 'transcript'
    path.write_bytes(data)
    needles = scrub.patterns([value])
    stamp = path.stat().st_mtime_ns
    assert scrub.scrub(path, needles)['ranges'] == 1
    assert path.read_bytes() == data and path.stat().st_mtime_ns == stamp
    assert scrub.scrub(path, needles, True)['changed']
    assert len(path.read_bytes()) == len(data)
    assert path.read_bytes().startswith(b'prefix ') and path.read_bytes().endswith(b' tail')
    assert not scrub.ranges(path.read_bytes(), needles)


def test_overlaps():
    assert scrub.ranges(b'ababab', [b'abab', b'baba']) == [(0, 6)]


@pytest.mark.parametrize('values', [[], [''], ['abc'], [123]])
def test_invalid_values(values):
    with pytest.raises(ValueError):
        scrub.patterns(values)


def test_cli_default_and_apply(tmp_path, capsys):
    value = 'synthetic-' + 'fixture'
    store = tmp_path / 'values.json'
    store.write_text(json.dumps([value]))
    target = tmp_path / 'transcript'
    target.write_text(value)
    argv = ['--values', str(store), str(target)]
    assert scrub.main(argv) == 0 and target.read_text() == value
    assert scrub.main(['--apply', *argv]) == 0
    assert value not in capsys.readouterr().out


def test_values_file_protected(tmp_path):
    store = tmp_path / 'values.json'
    store.write_text('["synthetic-value"]')
    assert scrub.main(['--values', str(store), '--apply', str(store)]) == 1


def test_hardlink_refused(tmp_path):
    path = tmp_path / 'a'
    path.write_bytes(b'hello')
    os.link(path, tmp_path / 'b')
    with pytest.raises(ValueError):
        scrub.scrub(path, [b'hello'], True)


def test_replacement_collision_has_no_write(tmp_path):
    path = tmp_path / 'a'
    path.write_bytes(b'XXXX')
    with pytest.raises(ValueError):
        scrub.scrub(path, [b'XXXX'], True)
    assert path.read_bytes() == b'XXXX'
