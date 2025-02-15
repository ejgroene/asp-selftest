#!/usr/bin/env python3

import coverage
coverage = coverage.Coverage(source_pkgs=["asp_selftest"])
coverage.erase()
coverage.start()

import asp_selftest.arguments_tests
import asp_selftest.utils
import asp_selftest.asputil
import asp_selftest.delegate
import asp_selftest.session
import asp_selftest.error_handling
import asp_selftest.syntaxerrorhandler
import asp_selftest.exceptionguard
import asp_selftest.application
import asp_selftest.tester
import asp_selftest.runasptests
import asp_selftest.moretests
import asp_selftest.reifyhandler
import asp_selftest.quote


coverage.stop()
coverage.save()
coverage.html_report()
