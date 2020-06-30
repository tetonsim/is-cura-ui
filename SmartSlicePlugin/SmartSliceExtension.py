import os
import json
from typing import Dict

from UM.i18n import i18nCatalog
from UM.Application import Application
from UM.Extension import Extension
from UM.Logger import Logger
from UM.PluginRegistry import PluginRegistry
from UM.Workspace.WorkspaceMetadataStorage import WorkspaceMetadataStorage

from cura.CuraApplication import CuraApplication

from .SmartSliceCloudConnector import SmartSliceCloudConnector
from .SmartSliceCloudProxy import SmartSliceCloudProxy, SmartSliceCloudStatus

import pywim

i18n_catalog = i18nCatalog("smartslice")

class SmartSliceExtension(Extension):
    def __init__(self):
        super().__init__()

        # Proxy to the UI, and the cloud connector for the cloud
        self.proxy = SmartSliceCloudProxy()
        self.cloud = SmartSliceCloudConnector(self.proxy)

        #self.setMenuName(i18n_catalog.i18nc("@item:inmenu", "Smart Slice"))

        # About Dialog
        self._about_dialog = None
        self.addMenuItem(i18n_catalog.i18nc("@item:inmenu", "About"), self._openAboutDialog)

        # Login Window
        self._login_dialog = None
        #self.addMenuItem(i18n_catalog.i18n("Login"),
        #                 self._openLoginDialog)

        # Connection to the file writer on File->Save
        self._outputManager = PluginRegistry.getInstance().getPluginObject("LocalFileOutputDevice").getOutputDeviceManager()
        self._outputManager.writeStarted.connect(self._saveState)

        # Connection to File->Open after the mesh is loaded - this depends on if the user is loading a Cura project
        CuraApplication.getInstance().fileCompleted.connect(self._getState)
        Application.getInstance().workspaceLoaded.connect(self._getState)

        # Data storage location for workspaces - this is where we store our data for saving to the Cura project
        self._storage = Application.getInstance().getWorkspaceMetadataStorage()

        # We use the signal from the cloud connector to always update the plugin metadeta after results are generated
        # _saveState is also called when the user actually saves a project
        self.cloud.saveSmartSliceJob.connect(self._saveState)

    def _openLoginDialog(self):
        if not self._login_dialog:
            self._login_dialog = self._createQmlDialog("SmartSliceCloudLogin.qml")
        self._login_dialog.show()

    def _openAboutDialog(self):
        if not self._about_dialog:
            self._about_dialog = self._createQmlDialog("SmartSliceAbout.qml", vars={"aboutText": self._aboutText()})
        self._about_dialog.show()

    def _closeAboutDialog(self):
        if not self._about_dialog:
            self._about_dialog.close()

    def _createQmlDialog(self, dialog_qml, directory = None, vars = None):
        if directory is None:
            directory = PluginRegistry.getInstance().getPluginPath(self.getPluginId())

        mainApp = Application.getInstance()

        return mainApp.createQmlComponent(os.path.join(directory, dialog_qml), vars)

    def _aboutText(self):
        about = 'Smart Slice for Cura\n'

        plugin_info = self._getMetadata()

        if plugin_info:
            about += 'Version: {}'.format(plugin_info['version'])

        return about

    def _saveState(self, output_object=None):
        plugin_info = self._getMetadata()

        # Build the Smart Slice job. We want to always build in case something has changed
        job = self.cloud.smartSliceJobHandle.buildJobFor3mf()

        cloudJob = self.cloud.cloudJob
        if cloudJob:
            job.type = cloudJob.job_type

        # Place the job in the metadata under our plugin ID
        self._storage.setEntryToStore(plugin_id=plugin_info['id'], key='job', data=job.to_dict())
        self._storage.setEntryToStore(plugin_id=plugin_info['id'], key='version', data=plugin_info['version'])
        self._storage.setEntryToStore(plugin_id=plugin_info['id'], key='status', data=self.cloud.status.value)

        # Need to do some checks to see if we've stored the results for the active job
        if cloudJob and cloudJob.getResult() and not cloudJob.saved:
            self._storage.setEntryToStore(plugin_id=plugin_info['id'], key='results', data=cloudJob.getResult().to_dict())
            cloudJob.saved = True
        elif job.type == pywim.smartslice.job.JobType.validation and (not cloudJob or not cloudJob.getResult()):
            self._storage.setEntryToStore(plugin_id=plugin_info['id'], key='results', data=None)

    # Acquires all of the smart slice data from Cura storage and updates the UI
    def _getState(self, filename=None):
        plugin_info = self._getMetadata()

        all_data = self._storage.getPluginMetadata(plugin_info['id'])

        # No need to go further if we don't have any data stored
        if len(all_data) == 0:
            return

        job_dict = all_data['job']
        status = all_data['status']
        results_dict = all_data['results']

        job = pywim.smartslice.job.Job.from_dict(job_dict) if job_dict else None
        results = pywim.smartslice.result.Result.from_dict(results_dict) if results_dict else None

        if job:
            self.proxy.updatePropertiesFromJob(job)

        self.cloud.reset()

        if results:
            self.proxy.updatePropertiesFromResults(results)
            self.cloud.reset()

        if status:
            self.cloud.status = SmartSliceCloudStatus(status)
        else:
            self.proxy.updateStatusFromResults(job, results)
            self.cloud.updateStatus()

        self.cloud.updateSliceWidget()
        self.proxy.updateColorUI()

    def _getMetadata(self) -> Dict[str, str]:
        try:
            plugin_json_path = os.path.dirname(os.path.abspath(__file__))
            plugin_json_path = os.path.join(plugin_json_path, 'plugin.json')
            with open(plugin_json_path, 'r') as f:
                plugin_info = json.load(f)
            return plugin_info
        except:
            return None


