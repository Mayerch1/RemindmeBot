import unittest
from unittest.mock import MagicMock

from datetime import datetime, timedelta

import Bot.lib.input_parser as p



class AmbigParseTest(unittest.TestCase):

    def setUp(self):
        self.utcnow = datetime(year=2021, month=1, day=1)


    def test_week_month(self):
        at, error = p.parse('1m', self.utcnow)

        self.assertEqual(at, self.utcnow)
        self.assertNotEqual(error, '')
