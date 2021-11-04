import unittest
from unittest.mock import MagicMock

from datetime import datetime, timedelta
from dateutil.tz import gettz

import Bot.lib.input_parser as p



class AbsParseTest(unittest.TestCase):

    def setUp(self):
        self.utcnow = datetime(year=2021, month=1, day=1)


    def test_timezone_convert(self):
        # timezone in winter is 1h difference
        cmp_at = datetime(year=2021, month=1, day=1, hour=0)
        at, _ = p.parse('2021-1-1 01:00', self.utcnow, 'Europe/Berlin')

        self.assertEqual(at, cmp_at)


    def test_summer_time(self):
        cmp_at = datetime(year=2021, month=3, day=28, hour=0, minute=59)
        at, _ = p.parse('2021-03-28 01:59', self.utcnow, 'Europe/Berlin')
        self.assertEqual(at, cmp_at)

        cmp_at = datetime(year=2021, month=3, day=28, hour=1)
        at, _ = p.parse('2021-03-28 03:00', self.utcnow, 'Europe/Berlin')
        self.assertEqual(at, cmp_at)


    def test_no_american_format(self):
        cmp_at = datetime(year=2021, month=2, day=3)
        at, _ = p.parse('3.2.2021', self.utcnow)

        self.assertEqual(at, cmp_at)

    
    
