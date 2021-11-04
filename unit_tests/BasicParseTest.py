import unittest
from unittest.mock import MagicMock

from datetime import datetime, timedelta

import Bot.lib.input_parser as p



class BasicParseTest(unittest.TestCase):

    def setUp(self):
        self.utcnow = datetime(year=2021, month=1, day=1)


    def test_eoy(self):
        at_cmp = datetime(year=2021, month=12, day=31, hour=9)
        at, _ = p.parse('eoy', self.utcnow)

        self.assertEqual(at, at_cmp)

    def test_eom(self):
        at_cmp = datetime(year=2021, month=1, day=31, hour=12)
        at, _ = p.parse('eom', self.utcnow)

        self.assertEqual(at, at_cmp)

    def test_eow(self):
        at_cmp = datetime(year=2021, month=1, day=1, hour=17)
        at, _ = p.parse('eow', self.utcnow)

        self.assertEqual(at, at_cmp)

    def test_eod(self):
        at_cmp = datetime(year=2021, month=1, day=1, hour=17)
        at, _ = p.parse('eod', self.utcnow)

        self.assertEqual(at, at_cmp)
        
    def test_years(self):
        at_cmp = self.utcnow.replace(year=2022)
        at2_cmp = self.utcnow.replace(year=2023)
        at3_cmp = self.utcnow.replace(year=2024)

        at, _ = p.parse('1y', self.utcnow)
        at2, _ = p.parse('2y', self.utcnow)
        at3, _ = p.parse('3 y', self.utcnow)

        self.assertEqual(at, at_cmp)
        self.assertEqual(at2, at2_cmp)
        self.assertEqual(at3, at3_cmp)
        
    def test_year_word(self):
        at_cmp = self.utcnow.replace(year=2022)
        at2_cmp = self.utcnow.replace(year=2023)
        at3_cmp = self.utcnow.replace(year=2024) 

        at, _ = p.parse('1ye', self.utcnow)
        at2, _ = p.parse('2  year', self.utcnow)
        at3, _ = p.parse('3 years', self.utcnow)

        self.assertEqual(at, at_cmp)
        self.assertEqual(at2, at2_cmp)
        self.assertEqual(at3, at3_cmp)

    def test_month(self):
        at_cmp = self.utcnow.replace(month=2)
        at2_cmp = self.utcnow.replace(month=3)
        at3_cmp = self.utcnow.replace(month=4)

        at, _ = p.parse('1mo', self.utcnow)
        at2, _ = p.parse('2mo', self.utcnow)
        at3, _ = p.parse('3 mo', self.utcnow)

        self.assertEqual(at, at_cmp)
        self.assertEqual(at2, at2_cmp)
        self.assertEqual(at3, at3_cmp)
        
    def test_month_word(self):
        at_cmp = self.utcnow.replace(month=2)
        at2_cmp = self.utcnow.replace(month=3)
        at3_cmp = self.utcnow.replace(month=4)

        at, _ = p.parse('1 mon', self.utcnow)
        at2, _ = p.parse('2month', self.utcnow)
        at3, _ = p.parse('3 months', self.utcnow)

        self.assertEqual(at, at_cmp)
        self.assertEqual(at2, at2_cmp)
        self.assertEqual(at3, at3_cmp)

    def test_week(self):
        at_cmp = self.utcnow.replace(day=8)
        at2_cmp = self.utcnow.replace(day=15)
        at3_cmp = self.utcnow.replace(day=22)

        at, _ = p.parse('1w', self.utcnow)
        at2, _ = p.parse('2w', self.utcnow)
        at3, _ = p.parse('3 w', self.utcnow)

        self.assertEqual(at, at_cmp)
        self.assertEqual(at2, at2_cmp)
        self.assertEqual(at3, at3_cmp)

    def test_week_word(self):
        at_cmp = self.utcnow.replace(day=8)
        at2_cmp = self.utcnow.replace(day=15)
        at3_cmp = self.utcnow.replace(day=22)

        at, _ = p.parse('1wee', self.utcnow)
        at2, _ = p.parse('2 week', self.utcnow)
        at3, _ = p.parse('3  weeks', self.utcnow)

        self.assertEqual(at, at_cmp)
        self.assertEqual(at2, at2_cmp)
        self.assertEqual(at3, at3_cmp)

  
    def test_day(self):
        at_cmp = self.utcnow.replace(day=2)
        at2_cmp = self.utcnow.replace(day=3)
        at3_cmp = self.utcnow.replace(day=4)

        at, _ = p.parse('1d', self.utcnow)
        at2, _ = p.parse('2 d', self.utcnow)
        at3, _ = p.parse('3  d', self.utcnow)

        self.assertEqual(at, at_cmp)
        self.assertEqual(at2, at2_cmp)
        self.assertEqual(at3, at3_cmp)

    def test_day_word(self):
        at_cmp = self.utcnow.replace(day=2)
        at2_cmp = self.utcnow.replace(day=3)
        at3_cmp = self.utcnow.replace(day=4)

        at, _ = p.parse('1da', self.utcnow)
        at2, _ = p.parse('2 day', self.utcnow)
        at3, _ = p.parse('3  days', self.utcnow)

        self.assertEqual(at, at_cmp)
        self.assertEqual(at2, at2_cmp)
        self.assertEqual(at3, at3_cmp)


    def test_hour(self):
        at_cmp = self.utcnow.replace(hour=1)
        at2_cmp = self.utcnow.replace(hour=2)
        at3_cmp = self.utcnow.replace(hour=3)

        at, _ = p.parse('1h', self.utcnow)
        at2, _ = p.parse('2 h', self.utcnow)
        at3, _ = p.parse('3  h', self.utcnow)

        self.assertEqual(at, at_cmp)
        self.assertEqual(at2, at2_cmp)
        self.assertEqual(at3, at3_cmp)

    def test_hour_word(self):
        at_cmp = self.utcnow.replace(hour=1)
        at2_cmp = self.utcnow.replace(hour=2)
        at3_cmp = self.utcnow.replace(hour=3)

        at, _ = p.parse('1ho', self.utcnow)
        at2, _ = p.parse('2hour', self.utcnow)
        at3, _ = p.parse('3 hours', self.utcnow)

        self.assertEqual(at, at_cmp)
        self.assertEqual(at2, at2_cmp)
        self.assertEqual(at3, at3_cmp)


    def test_minute(self):
        at_cmp = self.utcnow.replace(minute=1)
        at2_cmp = self.utcnow.replace(minute=2)
        at3_cmp = self.utcnow.replace(minute=3)

        at, _ = p.parse('1mi', self.utcnow)
        at2, _ = p.parse('2mi', self.utcnow)
        at3, _ = p.parse('3 mi', self.utcnow)

        self.assertEqual(at, at_cmp)
        self.assertEqual(at2, at2_cmp)
        self.assertEqual(at3, at3_cmp)

    def test_minute_word(self):
        at_cmp = self.utcnow.replace(minute=1)
        at2_cmp = self.utcnow.replace(minute=2)
        at3_cmp = self.utcnow.replace(minute=3)

        at, _ = p.parse('1min', self.utcnow)
        at2, _ = p.parse('2minut', self.utcnow)
        at3, _ = p.parse('3 minutes', self.utcnow)

        self.assertEqual(at, at_cmp)
        self.assertEqual(at2, at2_cmp)
        self.assertEqual(at3, at3_cmp)


    def test_overflow_relative(self):
        # gracefully fail overflows
        at, _ = p.parse('100000y', self.utcnow)
        self.assertEqual(at, self.utcnow)


    def test_overflow_iso(self):
        # iso overflow must not throw an exception either
        at, _ = p.parse('10000-08-05T15:21:21Z', self.utcnow)
        self.assertEqual(at, self.utcnow+timedelta(hours=1)) # parser will return +1 on error


    def test_overflow_fuzzy(self):
        # fuzzy parser must not throw exception on overflow
        at, _ = p.parse('00:00 1st jan 10000', self.utcnow)
        self.assertEqual(at, self.utcnow)


    def test_epoch_overflow(self):
        # reminders are stored in unix timestmaps
        # but datetime can represent greater intervals
        # those cannot be stored and must be failed

        # choose target date which is out of unix epoch
        # but doesn't overflow the datetime object
        at, _ = p.parse('00:00 1st jan 5000', self.utcnow)
        self.assertEqual(at, self.utcnow)


class BasicPushbackTest(unittest.TestCase):
    
    def setUp(self):
        # this date is eoy, eom AND eow
        self.default = datetime(year=2021, month=12, day=31, hour=18)
        self.limit = datetime(year=2021, month=12, day=31, hour=23)
    
    def test_eod_2h(self):
        at_cmp = self.default + timedelta(hours=2)
        at, _ = p.parse('eod', self.default)
        self.assertEqual(at, at_cmp)
    
    def test_eow_2h(self):
        at_cmp = self.default + timedelta(hours=2)
        at, _ = p.parse('eow', self.default)
        self.assertEqual(at, at_cmp)
    
    def test_eom_2h(self):
        at_cmp = self.default + timedelta(hours=2)
        at, _ = p.parse('eom', self.default)
        self.assertEqual(at, at_cmp)
    
    def test_eoy_2h(self):
        at_cmp = self.default + timedelta(hours=2)
        at, _ = p.parse('eoy', self.default)
        self.assertEqual(at, at_cmp)
        
        
        
    def test_eod_limit(self):
        at_cmp = self.limit.replace(hour=23, minute=59, second=59)
        at, _ = p.parse('eod', self.limit)
        self.assertEqual(at, at_cmp)
    
    def test_eow_limit(self):
        at_cmp = self.limit.replace(hour=23, minute=59, second=59)
        at, _ = p.parse('eow', self.limit)
        self.assertEqual(at, at_cmp)
    
    def test_eom_limit(self):
        at_cmp = self.limit.replace(hour=23, minute=59, second=59)
        at, _ = p.parse('eom', self.limit)
        self.assertEqual(at, at_cmp)
    
    def test_eoy_limit(self):
        at_cmp = self.limit.replace(hour=23, minute=59, second=59)
        at, _ = p.parse('eoy', self.limit)
        self.assertEqual(at, at_cmp)
        
        
    
class AbsolutoOffsetTest(unittest.TestCase):
    def setUp(self):
        # this date is eoy, eom AND eow
        self.utcnow = datetime(year=2021, month=12, day=31, hour=9)
        
        
    def test_eod_offset(self):
        at_cmp = self.utcnow.replace(hour=20)
        at, _ = p.parse('eod at 8pm', self.utcnow)
        self.assertEqual(at, at_cmp)
        
    def test_eow_offset(self):
        at_cmp = self.utcnow.replace(hour=20)
        at, _ = p.parse('eow at 8pm', self.utcnow)
        self.assertEqual(at, at_cmp)
        
    def test_eom_offset(self):
        at_cmp = self.utcnow.replace(hour=20)
        at, _ = p.parse('eom at 8pm', self.utcnow)
        self.assertEqual(at, at_cmp)
        
    def test_eoy_offset(self):
        at_cmp = self.utcnow.replace(hour=20)
        at, _ = p.parse('eoy at 8pm', self.utcnow)
        self.assertEqual(at, at_cmp)