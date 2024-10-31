
""" Functions to runs all tests in an ASP program. """

import inspect
import clingo
import threading


# Allow ASP programs started in Python to include Python themselves.
from clingo.script import enable_python
enable_python()


import selftest
test = selftest.get_tester(__name__)


