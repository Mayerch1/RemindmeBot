import unittest
from unittest.mock import MagicMock

from datetime import datetime, timedelta

import Bot.lib.input_parser as p



class CombineParseTest(unittest.TestCase):

    def setUp(self):
        self.utcnow = datetime(year=2021, month=1, day=1)


    def test_combine_all_relatives(self):
        at_cmp = datetime(year=2022, month=2, day=2, hour=1, minute=1)
        at, _ = p.parse('1 y 1 mo 1 d 1h 1mi', self.utcnow)

        self.assertEqual(at, at_cmp)


    def test_mixed_arg_order(self):
        at_cmp = datetime(year=2022, month=2, day=2, hour=1, minute=1)
        at, _ = p.parse('1mo 1  mi 1 h 1y 1d ', self.utcnow)

        self.assertEqual(at, at_cmp)


    def test_no_space(self):
        at_cmp = datetime(year=2021, month=1, day=2, hour=1, minute=1)
        at, info = p.parse('1y1mo1we 1d', self.utcnow)

        # undefined behavior for resulting timespan
        # no-throw is neough to pass this test
        pass


    def test_negative_intvl(self):
        at_cmp = self.utcnow
        at, info = p.parse('1mo -1y', self.utcnow)

        self.assertTrue(at < at_cmp)


    def test_substract(self):
        at_cmp = datetime(year=2021, month=1, day=31)
        at, info = p.parse('1mo -1d', self.utcnow)

        self.assertEqual(at, at_cmp)


    def test_ignore_mixed_input(self):
        at_cmp = datetime(year=2022, month=1, day=31, hour=14, minute=0)
        at, info = p.parse('5h 1y eom 5mi', self.utcnow)
        
        self.assertEqual(at, at_cmp) # relative must fail, eom is interpreted
        self.assertEqual(info, '') # no warning?