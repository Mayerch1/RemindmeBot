import unittest
from unittest.mock import MagicMock

from datetime import datetime, timedelta

import Bot.lib.input_parser as p



class WrapParseTest(unittest.TestCase):

    def setUp(self):
        self.utcnow = datetime(year=2021, month=1, day=1)


    def test_month_wrap(self):
        at_cmp = datetime(year=2022, month=2, day=1)
        at, _ = p.parse('13mo', self.utcnow)

        self.assertEqual(at, at_cmp)

    def test_week_wrap(self):
        at_cmp = datetime(year=2021, month=2, day=5)
        at, _ = p.parse('5w', self.utcnow)

        self.assertEqual(at, at_cmp)


    def test_day_wrap(self):
        at_cmp = datetime(year=2021, month=2, day=1)
        at, _ = p.parse('31d', self.utcnow)

        self.assertEqual(at, at_cmp)


    def test_hour_wrap(self):
        at_cmp = datetime(year=2021, month=1, day=2, hour=2)
        at, _ = p.parse('26h', self.utcnow)

        self.assertEqual(at, at_cmp)


    def test_minute_wrap(self):
        at_cmp = datetime(year=2021, month=1, day=1, hour=1, minute=1)
        at, _ = p.parse('61mi', self.utcnow)

        self.assertEqual(at, at_cmp)
