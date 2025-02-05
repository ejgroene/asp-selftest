#!/usr/bin/env python3

import coverage
c = coverage.Coverage(source_pkgs=["asp_selftest"])
c.erase()
c.start()
import asp_selftest.delegate
import asp_selftest.session

import asp_selftest.utils
import asp_selftest.reify
import asp_selftest.tester
import asp_selftest.arguments_tests
import asp_selftest.error_handling
import asp_selftest.application
import asp_selftest.processors
import asp_selftest.moretests
import asp_selftest.runasptests


c.stop()
c.save()
c.html_report()
