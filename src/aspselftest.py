
"""
    Top Level Code + Integration Tests
"""

import selftest
test =  selftest.get_tester(__name__)

from sessionng import clingo_session, default_plugins, Noop, run_clingo_plus_main


@test
def simple_syntax_error_with_clingo_main(stdout, stderr):
    run_clingo_plus_main(b'plugin(".:errorplugin"). a')
    test.startswith(stdout.getvalue(), 'clingo+ version 5.7.1\nReading from stdin\nUNKNOWN')
    traceback = stderr.getvalue()
    test.startswith(traceback, 'Traceback (most recent call last):')
    test.eq('', traceback, diff=test.diff)

