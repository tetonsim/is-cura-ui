import unittest

from cura.CuraApplication import CuraApplication

class _SmartSliceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = CuraApplication.getInstance()

    @classmethod
    def tearDownClass(cls):
        pass