#!/usr/bin/env python3

import coverage
coverage = coverage.Coverage(source_pkgs=["aspselftest"])
coverage.erase()
coverage.start()

import aspselftest.plugins.clingo_main_plugin

import aspselftest.session2
import aspselftest.integration
import aspselftest.arguments
import aspselftest.moretests


coverage.stop()
coverage.save()
coverage.html_report()
