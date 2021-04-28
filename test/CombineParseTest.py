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

        # undefined behaviour for resulting timespan
        # no-throw is neough to pass this test
        pass


    def test_empty_args(self):

        at_cmp = datetime(year=2021, month=1, day=2, hour=1, minute=1)
        at, info = p.parse('mo 1mi 1h y 1d ', self.utcnow)

        self.assertEqual(at, at_cmp)
        self.assertNotEqual(info, None)
