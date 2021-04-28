import unittest
from unittest.mock import MagicMock

from datetime import datetime, timedelta

import Bot.lib.input_parser as p



class BasicParseTest(unittest.TestCase):

    def setUp(self):
        self.utcnow = datetime(year=2021, month=1, day=1)


    def test_eoy(self):
        at_cmp = datetime(year=2021, month=12, day=31)
        at, _ = p.parse('eoy', self.utcnow)

        self.assertEqual(at, at_cmp)

    def test_eom(self):
        at_cmp = datetime(year=2021, month=1, day=31, hour=12)
        at, _ = p.parse('eom', self.utcnow)

        self.assertEqual(at, at_cmp)

    def test_eow(self):
        at_cmp = datetime(year=2021, month=1, day=1, hour=23)
        at, _ = p.parse('eow', self.utcnow)

        self.assertEqual(at, at_cmp)

    def test_eod(self):
        at_cmp = datetime(year=2021, month=1, day=1, hour=23, minute=45)
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