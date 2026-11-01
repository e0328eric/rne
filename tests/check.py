#!/usr/bin/env python3
"""CLI, replacement and capture UI regressions; needs Glosso and Python's stdlib."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def check_command_line(exe, temporary):
    root = temporary / 'cli'
    root.mkdir()
    originals = {'draft1.txt': 'one', 'DRAFT2.TXT': 'two', 'folder/draft3.txt': 'three'}
    for name, content in originals.items():
        path = root / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(content)

    def run(*args, status=0, cwd=root):
        result = subprocess.run(
            [str(exe), *args], cwd=cwd, text=True, capture_output=True, timeout=10,
        )
        assert result.returncode == status, (args, result.returncode, result.stdout, result.stderr)
        return result.stdout

    def plan(*args):
        data = json.loads(run('--json', *args))
        assert data['blocked'] == 0, data
        return {entry['from']: entry['to'] for entry in data['entries']}

    help_text = run('--help')
    assert run('-h') == help_text
    assert 'Usage: rne [flags] [DIRECTORY]' in help_text
    assert '-r, --recursive' in help_text and '--increment <number>' in help_text
    assert 'Replacement: $1, ${name}' in help_text
    defaults = json.loads(run('--json'))
    assert defaults['root'] == '.' and defaults['selected'] == 3, defaults
    assert all(entry['to'] is None for entry in defaults['entries']), defaults

    # Flags may follow the directory; the last short flag in a group may take a value.
    args = ['--search', 'draft', '--replace', 'final']
    assert plan(*args) == plan(str(root), *args)
    assert plan('-rEs', r'draft(\d)', '-w', 'final-$1', '--files-only') == {
        'draft1.txt': 'final-1.txt', 'DRAFT2.TXT': 'final-2.TXT',
        'folder/draft3.txt': 'final-3.txt',
    }
    assert plan('--dirs-only', '-s', 'folder', '-w', 'renamed') == {'folder': 'renamed'}
    assert plan('--search', 'unused', '-s', 'DRAFT', '--replace', '', '--case-sensitive') == {
        'folder': None, 'draft1.txt': None, 'DRAFT2.TXT': '2.TXT',
    }

    # Repeated switches keep their meaning, including repeated short aliases.
    assert plan('-rrEE', '-s', r'draft(\d)', '-w', 'final-$1', '--files-only',
                '--files-only', '--case-sensitive', '--case-sensitive') == {
        'draft1.txt': 'final-1.txt', 'DRAFT2.TXT': None,
        'folder/draft3.txt': 'final-3.txt',
    }
    assert plan('--json', *args) == plan(*args)
    assert 'final1.txt' in run('--preview', '--preview', *args)
    assert plan('--files-only', '--enumerate', '--enumerate') == {
        'draft1.txt': 'draft101.txt', 'DRAFT2.TXT': 'DRAFT202.TXT',
    }
    for start, increment, padding in [(-2, -1, 3), (0, 0, 1), (1, 1, 64),
                                      (-(2**63), 0, 1), (2**63 - 1, 0, 1)]:
        actual = plan('--files-only', '--enumerate', '--start', str(start),
                      '--increment', str(increment), '--padding', str(padding))
        for index, name in enumerate(['draft1.txt', 'DRAFT2.TXT']):
            path = Path(name)
            assert actual[name] == f'{path.stem}{start + index * increment:0{padding}}{path.suffix}'

    snapshot = run('--snapshot')
    assert len(snapshot.splitlines()) == 32
    assert all(len(row) == 120 for row in snapshot.splitlines())
    assert len(run('--snapshot', '--width', '52', '--height', '20').splitlines()) == 20
    assert run('--snapshot', '--width', '1', '--height', '1') == ' \n'
    assert '\x1b[' in run('--snapshot-ansi', '--width', '52', '--height', '20')

    # A bare dash is a directory; -- allows a directory that looks like an option.
    for name, directory_args in [('-', ['-']), ('--help', ['--', '--help'])]:
        directory = temporary / name
        directory.mkdir()
        (directory / 'item.txt').touch()
        data = json.loads(run('--json', *directory_args, cwd=temporary))
        assert data['root'] == name and data['entries'][0]['from'] == 'item.txt', data

    invalid = [
        (['--unknown'], 'unknown flag'),
        (['-z'], 'unknown short flag'),
        (['-sr', 'draft'], 'only the last short flag may take values'),
        (['--search', '--preview'], 'flag needs a value'),
        (['--search', '-draft'], 'flag needs a value'),
        (['--width=52'], 'unknown flag'),
        (['one', 'two'], 'too many positional arguments'),
        (['--scope', 'bad'], 'scope must be whole, name or ext'),
        (['--case', 'bad'], 'unknown case transform'),
        (['--apply'], '--apply requires --yes'),
        (['--files-only', '--dirs-only'], '--files-only cannot be combined with --dirs-only'),
        (['--dirs-only', '--files-only'], '--files-only cannot be combined with --dirs-only'),
    ]
    value_flags = ['-s', '-w', '--search', '--replace', '--scope', '--case',
                   '--start', '--increment', '--padding', '--width', '--height']
    invalid += [([flag], 'flag needs a value') for flag in value_flags]
    for flag in ['--start', '--increment', '--padding', '--width', '--height']:
        for value in ['not-a-number', '1.5', str(2**63), str(-(2**63) - 1)]:
            invalid.append(([flag, value], 'invalid value for parameter type'))
    for flag, limit, message in [('--padding', 64, 'padding must be 1..64'),
                                 ('--width', 500, 'dimensions must be 1..500'),
                                 ('--height', 500, 'dimensions must be 1..500')]:
        for value in ['-1', '0', str(limit + 1)]:
            invalid.append(([flag, value], message))
    for mode in ['--preview', '--json', '--snapshot', '--snapshot-ansi']:
        invalid.append((['--apply', '--yes', mode, mode],
                        '--apply cannot be combined with a preview mode'))
    for args, message in invalid:
        assert message in run(*args, status=2), args

    assert {str(p.relative_to(root)): p.read_text() for p in root.rglob('*') if p.is_file()} == originals
    run('--apply', '--apply', '--yes', '--yes', '-s', 'draft', '-w', 'final')
    assert (root / 'final1.txt').read_text() == 'one'
    assert (root / 'final2.TXT').read_text() == 'two'
    assert (root / 'folder/draft3.txt').read_text() == 'three'


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


def check_review_terminal(exe, temporary):
    if os.name != 'posix':
        return
    import fcntl
    import pty
    import re
    import select
    import struct
    import termios
    import time

    root = temporary / 'terminal-review'
    root.mkdir()
    original = root / '2번 배우 고세구 (1).png'
    original.write_text('unchanged contents')
    master, slave = pty.openpty()
    previous_mode = termios.tcgetattr(slave)
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 32, 120, 0, 0))
    process = subprocess.Popen(
        [str(exe), '-w', 'final', str(root)], stdin=slave, stdout=slave, stderr=slave,
        env={**os.environ, 'TERM': 'xterm-256color'},
    )
    pending = b''
    frame = re.compile(rb'\x1b\[1;1H(.*?)\x1b\[\?25[hl]', re.DOTALL)
    controls = re.compile(rb'\x1b\[[0-?]*[ -/]*[@-~]')

    def wait_for(predicate):
        nonlocal pending
        deadline = time.monotonic() + 5
        last = ''
        while time.monotonic() < deadline:
            match = frame.search(pending)
            if match:
                last = controls.sub(b'', match[1]).decode('utf-8')
                pending = pending[match.end():]
                if predicate(last):
                    return last
                continue
            assert process.poll() is None, (process.returncode, last, pending)
            if select.select([master], [], [], 0.05)[0]:
                pending += os.read(master, 65536)
        raise AssertionError(('terminal did not reach expected state', last, pending))

    def send(data):
        os.write(master, data)

    try:
        wait_for(lambda text: 'RENAMING STUDIO' in text)
        # Find is initially focused. Exercise Korean UTF-8 input and the F9 sequence.
        search = '2번 배우 고세구'.encode('utf-8')
        send(search)
        wait_for(lambda text: 'final (1).png' in text)
        for shortcut in [b'\x1b[20~', b'\r']:
            send(shortcut)
            wait_for(lambda text: 'REVIEW YOUR CHANGESET' in text)
            assert original.read_text() == 'unchanged contents'
            send(b'\x1b[200~\r\x1b[201~')
            wait_for(lambda text: 'REVIEW YOUR CHANGESET' in text)
            assert original.exists(), 'pasted Enter applied a rename'
            send(b'\r')
            wait_for(lambda text: 'REVIEW YOUR CHANGESET' not in text)
            assert original.exists(), 'Enter must cancel the default review selection'

        # A pasted Find edit is included in the next review.
        send(b'\x1b[H\x0b\x1b[200~' + search + b'\x1b[201~\x1b[20~')
        wait_for(lambda text: 'REVIEW YOUR CHANGESET' in text)
        send(b'\x1b[C\r')
        wait_for(lambda text: 'Renamed 1 items' in text)
        assert not original.exists()
        assert (root / 'final (1).png').read_text() == 'unchanged contents'
        send(b'\x11')
        assert process.wait(timeout=5) == 0
        assert termios.tcgetattr(slave) == previous_mode, 'terminal mode was not restored'
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)
        os.close(slave)


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
        check_command_line(binaries[0], temporary)
        check_replacements(binaries[0], temporary)
        ui_root = temporary / 'ui'
        ui_root.mkdir()
        for name in ['1-unrelated.txt', '2번 배우 고세구 (1).png',
                     '2번 배우 고세구 (2).png', 'abcdefghijklmnopqrstuvwxyz.png']:
            (ui_root / name).touch()
        subprocess.run([str(binaries[1]), str(ui_root)], check=True)
        check_review_terminal(binaries[0], temporary)
    print('CLI, replacement, counter, capture preview, review shortcuts and terminal checks passed')


if __name__ == '__main__':
    main()
