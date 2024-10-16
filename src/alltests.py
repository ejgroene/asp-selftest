#!/usr/bin/env python3

import coverage
c = coverage.Coverage(source_pkgs=["asp_selftest"])
c.erase()
c.start()

import asp_selftest.__main__

c.stop()
c.save()
c.html_report()
