#!/usr/bin/env python3

import coverage
coverage = coverage.Coverage(source_pkgs=["asp_selftest"])
coverage.erase()
coverage.start()

import asp_selftest.plugins.clingo_main_plugin

import asp_selftest.session2
import asp_selftest.integration
import asp_selftest.arguments
import asp_selftest.moretests


coverage.stop()
coverage.save()
coverage.html_report()
