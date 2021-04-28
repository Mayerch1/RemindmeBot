import unittest
from unittest.mock import MagicMock

from datetime import datetime, timedelta

import Bot.lib.input_parser as p



class TimezoneParseTest(unittest.TestCase):
    # intervals can be ignored, as the solely depend on utc time
    # only testing absolute measures (eoy, eom, ...)

    def setUp(self):
        self.utcnow = datetime(year=2021, month=1, day=1)


    def test_eoy(self):
        at_cmp = datetime(year=2021, month=12, day=30, hour=23)
        at, _ = p.parse('2 eoy', self.utcnow, 'Europe/Berlin')

        self.assertEqual(at, at_cmp)


    def test_daylight_saving(self):

        now = datetime(year=2021, month=6, day=1)
        at_cmp = datetime(year=2021, month=6, day=30, hour=10) # summertime is 2h ahead of utc (not 1)
        at, _ = p.parse('eom', now, 'Europe/Berlin')

        self.assertEqual(at, at_cmp)

    
    def test_eom(self):
        at_cmp = datetime(year=2021, month=1, day=31, hour=11)
        at, _ = p.parse('eom', self.utcnow, 'Europe/Berlin')

        self.assertEqual(at, at_cmp)


    def test_eow(self):
        at_cmp = datetime(year=2021, month=1, day=1, hour=22)
        at, _ = p.parse('eow', self.utcnow, 'Europe/Berlin')

        self.assertEqual(at, at_cmp)

    def test_eod(self):
        at_cmp = datetime(year=2021, month=1, day=1, hour=22, minute=45)
        at, _ = p.parse('eod', self.utcnow, 'Europe/Berlin')

        self.assertEqual(at, at_cmp)


    def test_timezone_west(self):
        now = datetime(year=2021, month=1, day=2)
        at_cmp = datetime(year=2021, month=1, day=31, hour=18) # chicago is 6h diff to utc in winter
        at, _ = p.parse('eom', now, 'America/Chicago')

        self.assertEqual(at, at_cmp)


    def test_timezone_west_summer(self):
        now = datetime(year=2021, month=6, day=2)
        at_cmp = datetime(year=2021, month=6, day=30, hour=17) # chicago is 5h diff to utc in summer
        at, _ = p.parse('eom', now, 'America/Chicago')

        self.assertEqual(at, at_cmp)

    def test_timezone_in_last_year(self):
        # timezones towards the west can be stuck in the last year
        # therefore the result of absolute units (eom) might be different than expected

        # example of new year, chicago is still in the old year, therefore eom will result in new years eve
        at_cmp = datetime(year=2020, month=12, day=31, hour=18) # chicago is 6h diff to utc in summer
        at, _ = p.parse('eom', self.utcnow, 'America/Chicago')

        self.assertEqual(at, at_cmp)