"""Fail the native Windows gate if the mandatory exec tests were skipped or absent."""
import sys
import xml.etree.ElementTree as ET

cases = [case for case in ET.parse(sys.argv[1]).iter('testcase')
         if case.attrib.get('classname', '').endswith('test_hook_exec')]
if len(cases) < 50 or any(case.find('skipped') is not None for case in cases):
    raise SystemExit('Native exec hook coverage is missing or skipped')
