import os
import sys
import threading
import time
import unittest

from contextlib import redirect_stdout, redirect_stderr

from SmartSliceTestCase import _SmartSliceTestCase

from UM.Platform import Platform
from UM.PluginRegistry import PluginRegistry

from cura.CuraApplication import CuraApplication

def cura_app_mock():
    # Taken from cura_app.py
    import Arcus
    import Savitar

    if Platform.isLinux():
        try:
            import ctypes
            from ctypes.util import find_library
            libGL = find_library("GL")
            ctypes.CDLL(libGL, ctypes.RTLD_GLOBAL)
        except:
            pass

    if Platform.isLinux() and getattr(sys, "frozen", False):
        old_env = os.environ.get("LD_LIBRARY_PATH", "")
        # This is where libopenctm.so is in the AppImage.
        search_path = os.path.join(CuraApplication.getInstallPrefix(), "bin")
        path_list = old_env.split(":")
        if search_path not in path_list:
            path_list.append(search_path)
        os.environ["LD_LIBRARY_PATH"] = ":".join(path_list)
        import trimesh.exchange.load
        os.environ["LD_LIBRARY_PATH"] = old_env

    sys.argv.clear()
    sys.argv.append("smartslicetests")
    sys.argv.append("--headless")

    return CuraApplication()

class SmartSliceLoads(_SmartSliceTestCase):
    def test_plugin_path(self):
        plugins = PluginRegistry.getInstance()
        path = plugins.getPluginPath("SmartSlicePlugin")

        self.assertIsNotNone(path)

from test_API import *

if __name__ == "__main__":
    app = cura_app_mock()

    wait_for_app = True

    def unittest_fire():
        global wait_for_app
        wait_for_app = False

    def unittest_wait_and_run():
        while wait_for_app:
            time.sleep(0.1)

        plugins = PluginRegistry.getInstance()

        print("\n", file = sys.__stderr__)
        runner = unittest.TextTestRunner(stream=sys.__stdout__, verbosity=2)
        prog = unittest.main(exit=False, testRunner=runner, verbosity=2, argv=[sys.argv[0]])
        print("\n", file = sys.__stderr__)

        app.closeApplication()

        if prog.result.errors != [] or prog.result.failures != []:
            raise Exception("Tests Failed!")

    # Before running the app, start the unit tests in a thread
    unittest_thread = threading.Thread(target=unittest_wait_and_run)
    unittest_thread.start()

    app.applicationRunning.connect(unittest_fire)
    null_out = open(os.devnull, 'w')
    with redirect_stderr(null_out):
        with redirect_stdout(null_out):
            app.run()
