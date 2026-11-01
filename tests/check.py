#!/usr/bin/env python3
"""Replacement and capture UI regressions; needs Glosso and Python's stdlib."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def check_replacements(exe, temporary):
    def fixture(label, names):
        root = temporary / label
        root.mkdir()
        for name in names:
            (root / name).write_text(name)
        return root

    def plan(root, *args):
        result = subprocess.run(
            [str(exe), '--json', *args, str(root)],
            text=True, capture_output=True, timeout=10, check=True,
        )
        data = json.loads(result.stdout)
        assert data['blocked'] == 0, data
        return {entry['from']: entry['to'] for entry in data['entries']}

    names = [f'1번_배우_채은채_{n:02}.png' for n in range(1, 15)]
    matches = [f'2번 배우 고세구 ({n}).png' for n in range(1, 16)]
    names += matches + [f'3번 배우 마레플로스 ({n}).png' for n in range(1, 15)]
    root = fixture('mixed', names)
    pattern = r'2번 배우 고세구 \(\d+\)\.png'
    for start, step, padding in [(0, 1, 2), (11, 1, 2), (0, 3, 1), (0, -1, 3)]:
        replacement = f'고세구_${{start={start},increment={step},padding={padding}}}.png'
        actual = plan(root, '-E', '-s', pattern, '-w', replacement)
        for index, name in enumerate(matches):
            expected = f'고세구_{start + step * index:0{padding}}.png'
            assert actual[name] == expected, (name, actual[name], expected)
        assert all(actual[name] is None for name in names if name not in matches)
    # Previews never touch the filesystem.
    assert {p.name: p.read_text() for p in root.iterdir()} == {n: n for n in names}

    root = fixture('unchanged-match', ['00.png', '1.png'])
    assert plan(root, '-E', '--scope', 'name', '-s', r'^\d+$', '-w', '${start=0}') == {
        '00.png': None, '1.png': '01.png',
    }
    root = fixture('scope', ['item1.png', 'item2.txt', 'item3.png'])
    assert plan(root, '--scope', 'ext', '-s', 'png', '-w', '${start=0,padding=1}') == {
        'item1.png': 'item1.0', 'item2.txt': None, 'item3.png': 'item3.1',
    }
    root = fixture('literal', ['aaa.txt', 'draft2.txt', 'draft10.txt', 'zzz.txt'])
    assert plan(root, '-s', 'draft', '-w', 'final_$#', '--start', '0') == {
        'aaa.txt': None, 'draft2.txt': 'final_02.txt',
        'draft10.txt': 'final_110.txt', 'zzz.txt': None,
    }
    root = fixture('automatic', ['a.txt', 'b.txt'])
    assert plan(root, '--enumerate', '--start', '0') == {
        'a.txt': 'a00.txt', 'b.txt': 'b01.txt',
    }
    # A counter in Replace also suppresses the automatic appended counter.
    assert plan(root, '-E', '-s', r'([ab])', '-w', '$1_$#', '--start', '0', '--enumerate') == {
        'a.txt': 'a_0.txt', 'b.txt': 'b_1.txt',
    }

    root = fixture('captures', ['사진-12.jpeg'])
    for replacement, expected in [
        ('$1_$2.png', '사진_12.png'),
        ('$2_photo.png', '12_photo.png'),
        ('$2photo.png', '12photo.png'),
        ('${2}_photo.png', '12_photo.png'),
        ('${stem}_$2.png', '사진_12.png'),
        ('$2${start=0,padding=1}.png', '120.png'),
        ('$2$#.png', '120.png'),
        ('$2$YYYY.png', None),
        ('$$1_$2_$$.png', '$1_12_$.png'),
        ('$0.bak', '사진-12.jpeg.bak'),
    ]:
        actual = plan(root, '-E', '-s', r'(?<stem>\w+)-(\d+)\.jpeg',
                      '-w', replacement, '--start', '0')['사진-12.jpeg']
        if expected is None:
            assert actual.startswith('12') and len(actual) == len('122026.png'), actual
        else:
            assert actual == expected, (replacement, actual, expected)
    assert plan(root, '-s', '사진-12', '-w', '$1_photo_$$') == {
        '사진-12.jpeg': '$1_photo_$$.jpeg',
    }
    root = fixture('multidigit', ['abcdefghijkl.png'])
    assert plan(root, '-E', '-s', r'(a)(b)(c)(d)(e)(f)(g)(h)(i)(j)(k)(l)',
                '-w', '$12_$1') == {'abcdefghijkl.png': 'l_a.png'}
    root = fixture('all-matches', ['a1-a2.txt'])
    args = ['-E', '-s', r'a(\d)', '-w', '$1_$#', '--start', '0']
    assert plan(root, *args) == {'a1-a2.txt': '1_0-2_0.txt'}
    assert plan(root, *args, '--first') == {'a1-a2.txt': '1_0-a2.txt'}
    root = fixture('dollar$1', ['photo.jpg'])
    assert plan(root, '-E', '-s', '(photo)', '-w', '$parent') == {
        'photo.jpg': 'dollar$1.jpg',
    }

    # Apply must produce exactly the previewed names and preserve file contents.
    root = fixture('apply', ['aaa.txt', 'photo1.png', 'photo2.png'])
    args = ['-E', '-s', r'photo(\d+)\.png', '-w', '$1_${start=0}.png']
    before = {p.name: p.read_text() for p in root.iterdir()}
    changes = plan(root, *args)
    subprocess.run([str(exe), '--apply', '--yes', *args, str(root)], check=True)
    assert {p.name: p.read_text() for p in root.iterdir()} == {
        changes[name] or name: value for name, value in before.items()
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('compiler', nargs='?', default='glosso')
    parser.add_argument('--std', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='rne-tests-') as directory:
        temporary = Path(directory)
        binaries = []
        for name, source in [('rne', ROOT / 'main.glo'), ('core', ROOT / 'tests/core.glo')]:
            executable = temporary / name
            command = [args.compiler, '-O3', str(source), '--cache-dir',
                       str(temporary / 'cache'), '-o', str(executable)]
            if args.std:
                command += ['--std', str(args.std.resolve())]
            subprocess.run(command, check=True, cwd=ROOT)
            binaries.append(executable)
        check_replacements(binaries[0], temporary)
        ui_root = temporary / 'ui'
        ui_root.mkdir()
        for name in ['1-unrelated.txt', '2번 배우 고세구 (1).png',
                     '2번 배우 고세구 (2).png', 'abcdefghijklmnopqrstuvwxyz.png']:
            (ui_root / name).touch()
        subprocess.run([str(binaries[1]), str(ui_root)], check=True)
    print('Replacement, counter, capture preview and keyboard checks passed')


if __name__ == '__main__':
    main()
