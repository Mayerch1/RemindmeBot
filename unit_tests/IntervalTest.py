import unittest
from unittest.mock import MagicMock

from datetime import datetime, timedelta
from dateutil.tz import gettz

import Bot.lib.input_parser as p



class IntervalTest(unittest.TestCase):
    # NOTE: repeating rules are way too complex to test
    # we need to rely on the used libraries to be correct
    # only a few exemplary test cases are implemented,
    # to check if the return type of the function is correct

    def setUp(self):
        self.utcnow = datetime(year=2021, month=1, day=1)


    def test_interval(self):
        at, _ = p.parse('every week from now', self.utcnow, 'Europe/Berlin')
        self.assertTrue('FREQ=WEEKLY' in at)
        
        
    def test_end_date(self):
        at, _ = p.parse('every day until next week', self.utcnow, 'Europe/Berlin')
        self.assertTrue('UNTIL=20210108' in at)
        
        
    def test_skip_days(self):
        at, _ = p.parse('every other day', self.utcnow, 'Europe/Berlin')
        self.assertTrue('INTERVAL=2' in at)
        
        
    def test_invalid_format_str(self):
        at, info = p.parse('this makes no sense', self.utcnow, 'Europe/Berlin')
        self.assertEqual(at, None)
        self.assertNotEqual(info, '')


    def test_ambig_interval(self):
        # the interval holds parts which would be a legal relitve days
        at, _ = p.parse('every 5 hours', self.utcnow, 'Europe/Berlin')
        self.assertTrue('INTERVAL=5' in at and 'FREQ=HOURLY' in at)

        
        