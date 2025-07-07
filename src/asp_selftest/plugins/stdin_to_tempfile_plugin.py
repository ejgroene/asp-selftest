import os
import subprocess
import tempfile
import pathlib

from .misc import write_tempfile

import selftest
test = selftest.get_tester(__name__)


def stdin_to_tempfile_plugin(next, files=(), **etc):
    """ Writes stdin to a temporary file so it can be read by multiple plugins """

    stdinput_file = None

    if not files:
        stdinput = open(os.dup(0)).read()
        stdinput_file = write_tempfile('-stdin.lp', stdinput)
        files = [stdinput_file.name]

    logger, _main = next(files=files, **etc)

    def main():
        stdinput_file   # keep save from GC
        return _main()

    return logger, main


def run_test():
    # NB: runs in another process!
    def next_plugin(files=(), **etc):
        def main():
            data = open(files[0]).read()
            return files, data
        return 42, main
    logger, main = stdin_to_tempfile_plugin(next_plugin, files=())
    test.eq(42, logger)
    files, data = main()
    for f in files:
        print(f)
    print(data)


@test
def turn_stdin_into_tempfile():
    # test in another process since we cannot mock stdin when read from Clingo's C++ runtime
    path = pathlib.Path(__file__).parent
    p = subprocess.run(
        ["python", "-c", f"from asp_selftest.plugins.stdin_to_tempfile_plugin import run_test; run_test()"],
        env=os.environ | {'PYTHONPATH': path},
        input=b"asp. is. nice.",
        capture_output=True)
    test.eq(b'', p.stderr)
    output_lines = p.stdout.splitlines()
    test.startswith(output_lines[0], tempfile.gettempdir().encode())
    test.endswith(output_lines[0], b"-stdin.lp")
    test.eq(b"asp. is. nice.", output_lines[1])
    test.eq(2, len(output_lines))

