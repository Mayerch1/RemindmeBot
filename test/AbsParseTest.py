import unittest
from unittest.mock import MagicMock

from datetime import datetime, timedelta

import Bot.lib.input_parser as p



class AbsParseTest(unittest.TestCase):

    def setUp(self):
        self.utcnow = datetime(year=2021, month=1, day=1)


    def test_ignore_mixed_input(self):
        p.parse('5h 2 mi eom', self.utcnow)
        p.parse('5h 2mi', self.utcnow)
    
