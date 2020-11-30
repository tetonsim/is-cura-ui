import unittest
from unittest.mock import MagicMock, patch

from UM.Application import Application

from typing import Callable

from SmartSliceTestCase import _SmartSliceTestCase

class TestMessages(_SmartSliceTestCase):
    @classmethod
    def setUpClass(cls):
        from SmartSlicePlugin.stage.ui.SmartSliceMessageExtension import SmartSliceMessage
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_no_duplicate_message(self):
        message = SmartSliceMessage()
        message.show()

        app = Application.getInstance()
        app.getVisibleMessages()
