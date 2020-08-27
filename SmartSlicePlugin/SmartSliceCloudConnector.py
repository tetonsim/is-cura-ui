from typing import Dict, Tuple, Callable

import os
import uuid
import json
import time
import tempfile
import datetime
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse

import pywim  # @UnresolvedImport

from PyQt5.QtCore import pyqtSignal, pyqtProperty, pyqtSlot
from PyQt5.QtCore import QTime, QUrl, QObject
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtQml import qmlRegisterSingletonType

from UM.i18n import i18nCatalog
from UM.Application import Application
from UM.Job import Job
from UM.Logger import Logger
from UM.Message import Message
from UM.PluginRegistry import PluginRegistry

from UM.Signal import Signal

from .SmartSliceCloudStatus import SmartSliceCloudStatus
from .SmartSliceCloudProxy import SmartSliceCloudProxy
from .SmartSlicePropertyHandler import SmartSlicePropertyHandler
from .SmartSliceJobHandler import SmartSliceJobHandler
from .stage.ui.ResultTable import ResultTableData

from .requirements_tool.SmartSliceRequirements import SmartSliceRequirements
from .select_tool.SmartSliceSelectTool import SmartSliceSelectTool

from .utils import getPrintableNodes
from .utils import getModifierMeshes
from .utils import getNodeActiveExtruder

i18n_catalog = i18nCatalog("smartslice")


class SmartSliceCloudJob(Job):
    # This job is responsible for uploading the backup file to cloud storage.
    # As it can take longer than some other tasks, we schedule this using a Cura Job.

    class JobException(Exception):
        def __init__(self, problem: str):
            super().__init__(problem)
            self.problem = problem

    def __init__(self, connector) -> None:
        super().__init__()
        self.connector = connector
        self.job_type = None
        self._id = 0
        self._saved = False
        self.api_job_id = None

        self.canceled = False

        self._job_status = None
        self._wait_time = 1.0

        self.ui_status_per_job_type = {
            pywim.smartslice.job.JobType.validation : SmartSliceCloudStatus.BusyValidating,
            pywim.smartslice.job.JobType.optimization : SmartSliceCloudStatus.BusyOptimizing,
        }

        #TODO: Get API connection
        self._client = self.connector.api_connection

    @property
    def job_status(self):
        return self._job_status

    @job_status.setter
    def job_status(self, value):
        if value is not self._job_status:
            self._job_status = value
            Logger.log("d", "Status changed: {}".format(self.job_status))

    @property
    def saved(self):
        return self._saved

    @saved.setter
    def saved(self, value):
        if self._saved != value:
            self._saved = value

    def determineTempDirectory(self):
        temporary_directory = tempfile.gettempdir()
        base_subdirectory_name = "smartslice"
        private_subdirectory_name = base_subdirectory_name
        abs_private_subdirectory_name = os.path.join(temporary_directory,
                                                     private_subdirectory_name)
        private_subdirectory_suffix_num = 1
        while os.path.exists(abs_private_subdirectory_name) and not os.path.isdir(abs_private_subdirectory_name):
            private_subdirectory_name = "{}_{}".format(base_subdirectory_name,
                                                       private_subdirectory_suffix_num)
            abs_private_subdirectory_name = os.path.join(temporary_directory,
                                                         private_subdirectory_name)
            private_subdirectory_suffix_num += 1

        if not os.path.exists(abs_private_subdirectory_name):
            os.makedirs(abs_private_subdirectory_name)

        return abs_private_subdirectory_name

    # Sending jobs to AWS
    # - job_type: Job type to be sent. Can be either:
    #             > pywim.smartslice.job.JobType.validation
    #             > pywim.smartslice.job.JobType.optimization
    def prepareJob(self, filename=None, filedir=None):
        # Using tempfile module to probe for a temporary file path
        # TODO: We can do this more elegant of course, too.

        # Setting up file output
        if not filename:
            filename = "{}.3mf".format(uuid.uuid1())
        if not filedir:
            filedir = self.determineTempDirectory()
        filepath = os.path.join(filedir, filename)

        Logger.log("d", "Saving temporary (and custom!) 3MF file at: {}".format(filepath))

        # Checking whether count of models == 1
        mesh_nodes = getPrintableNodes()
        mod_mesh = getModifierMeshes()


        if len(mesh_nodes) != 1:
            Logger.log("d", "Found {} meshes!".format(["no", "too many"][len(mesh_nodes) > 1]))
            return None
        for node in mod_mesh:
            Logger.log("d", "Adding modifier mesh {} to validation".format(node.getName()))
            mesh_nodes.append(node)

        Logger.log("d", "Writing 3MF file")
        job = self.connector.smartSliceJobHandle.buildJobFor3mf()
        if not job:
            Logger.log("d", "Error building the Smart Slice job for 3MF")
            return None

        job.type = self.job_type
        SmartSliceJobHandler.write3mf(filepath, mesh_nodes, job)

        if not os.path.exists(filepath):
            return None

        return filepath

    def processCloudJob(self, filepath):
        # Read the 3MF file into bytes
        threemf_fd = open(filepath, 'rb')
        threemf_data = threemf_fd.read()
        threemf_fd.close()

        # Submit the 3MF data for a new task
        job = self._client.submitSmartSliceJob(self, threemf_data)
        return job

    def run(self) -> None:
        if not self.job_type:
            error_message = Message()
            error_message.setTitle("Smart Slice")
            error_message.setText(i18n_catalog.i18nc("@info:status", "Job type not set for processing:\nDon't know what to do!"))
            error_message.show()
            self.connector.cancelCurrentJob()

        Job.yieldThread()  # Should allow the UI to update earlier

        try:
            job = self.prepareJob()
            Logger.log("i", "Smart Slice job prepared")
        except SmartSliceCloudJob.JobException as exc:
            Logger.log("w", "Smart Slice job cannot be prepared: {}".format(exc.problem))

            self.setError(exc)
            Message(
                title='Smart Slice',
                text=i18n_catalog.i18nc("@info:status", exc.problem)
            ).show()

            return

        task = self.processCloudJob(job)

        try:
            os.remove(job)
        except:
            Logger.log("w", "Unable to remove temporary 3MF {}".format(job))

        if task and task.result:
            self._result = task.result

class SmartSliceCloudVerificationJob(SmartSliceCloudJob):

    def __init__(self, connector) -> None:
        super().__init__(connector)

        self.job_type = pywim.smartslice.job.JobType.validation


class SmartSliceCloudOptimizeJob(SmartSliceCloudJob):

    def __init__(self, connector) -> None:
        super().__init__(connector)

        self.job_type = pywim.smartslice.job.JobType.optimization


class JobStatusTracker:
    def __init__(self, connector, status) -> None:
        self._previous_status = status
        self.connector = connector

    def __call__(self, job: pywim.http.thor.JobInfo) -> bool:
        Logger.log("d", "Current job status: {}".format(job.status))
        self.connector.api_connection.clearErrorMessage()
        self.connector._proxy.jobProgress = job.progress
        if job.status == pywim.http.thor.JobInfo.Status.queued and self.connector.status is not SmartSliceCloudStatus.Queued:
            self.connector.status = SmartSliceCloudStatus.Queued
            self.connector.updateSliceWidget()
        elif job.status == pywim.http.thor.JobInfo.Status.running and self.connector.status not in (SmartSliceCloudStatus.BusyOptimizing, SmartSliceCloudStatus.BusyValidating):
            self.connector.status = self._previous_status
            self.connector.updateSliceWidget()
        return False


# This class defines and contains our API connection. API errors, login and token
#   checking is all handled here.
class SmartSliceAPIClient(QObject):
    class ConnectionErrorCodes(Enum):
        genericInternetConnectionError = 1
        loginCredentialsError = 2

    def __init__(self, connector):
        super().__init__()
        self._client = None
        self.connector = connector
        self.extension = connector.extension
        self._token_file_path = ""
        self._token = None
        self._error_message = None

        self._number_of_timeouts = 20
        self._timeout_sleep = 3

        self._username_preference = "smartslice/username"
        self._app_preferences = Application.getInstance().getPreferences()

        #Login properties
        self._login_username = ""
        self._login_password = ""
        self._badCredentials = False

        self._plugin_metadata = connector.extension.metadata

    # If the user has logged in before, we will hold on to the email. If they log out, or
    #   the login is unsuccessful, the email will not persist.
    def _usernamePreferenceExists(self):
        username = self._app_preferences.getValue(self._username_preference)
        if username is not None and username != "" and self._login_username == "":
            self._login_username = username
        else:
            self._app_preferences.addPreference(self._username_preference, "")

    # Opening a connection is our main goal with the API client object. We get the address to connect to,
    #   then we check to see if the user has a valid token, if they are already logged in. If not, we log
    #   them in.
    def openConnection(self):
        self._token_file_path = os.path.join(PluginRegistry.getInstance().getPluginPath("SmartSlicePlugin"), ".token")

        url = urlparse(self._plugin_metadata.url)

        protocol = url.scheme
        hostname = url.hostname
        if url.port:
            port = url.port
        else:
            port = 443

        self._usernamePreferenceExists()

        if type(port) is not int:
            port = int(port)

        self._client = pywim.http.thor.Client(
            protocol=protocol,
            hostname=hostname,
            port=port,
            cluster=self._plugin_metadata.cluster
        )

        # To ensure that the user is tracked and has a proper subscription, we let them login and then use the token we recieve
        # to track them and their login status.
        self._getToken()

        #If there is a token, ensure it is a valid token
        self._checkToken()

        #If invalid token, attempt to Login.
        if not self.logged_in:
            self.loggedInChanged.emit()
            self._login()

        #If now a valid token, allow access
        if self.logged_in:
            self.loggedInChanged.emit()

        Logger.log("d", "SmartSlice HTTP Client: {}".format(self._client.address))

    def _connectionCheck(self):
        try:
            self._client.info()
        except Exception as error:
            Logger.log("e", "An error has occured checking the internet connection: {}".format(error))
            return (self.ConnectionErrorCodes.genericInternetConnectionError)

        return None

    # API calls need to be executed through this function using a lambda passed in, as well as a failure code.
    #  This prevents a fatal crash of Cura in some circumstances, as well as allows for a timeout/retry system.
    #  The failure codes give us better control over the messages that come from an internet disconnect issue.
    def executeApiCall(self, endpoint: Callable[[], Tuple[int, object]], failure_code):
        api_code = self._connectionCheck()
        timeout_counter = 0
        self.clearErrorMessage()

        if api_code is not None:
            return api_code, None

        while api_code is None and timeout_counter < self._number_of_timeouts:
            try:
                api_code, api_result = endpoint()
            except Exception as error:
                # If this error occurs, there was a connection issue
                Logger.log("e", "An error has occured with an API call: {}".format(error))
                timeout_counter += 1
                time.sleep(self._timeout_sleep)

            if timeout_counter == self._number_of_timeouts:
                return failure_code, None

        self.clearErrorMessage()

        return api_code, api_result

    def clearErrorMessage(self):
        if self._error_message is not None:
            self._error_message.hide()
            self._error_message = None

    # Login is fairly simple, the email and password is pulled from the Login popup that is displayed
    #   on the Cura stage, and then sent to the API.
    def _login(self):
        username = self._login_username
        password = self._login_password

        if self._token is None:
            self.loggedInChanged.emit()

        if password != "":
            api_code, user_auth = self.executeApiCall(
                lambda: self._client.basic_auth_login(username, password),
                self.ConnectionErrorCodes.loginCredentialsError
            )

            if api_code != 200:
                # If we get bad login credentials, this will set the flag that alerts the user on the popup
                if api_code == 400:
                    Logger.log("d", "API Code 400")
                    self.badCredentials = True
                    self._login_password = ""
                    self.badCredentialsChanged.emit()
                    self._token = None

                else:
                    self._handleThorErrors(api_code, user_auth)

            # If all goes well, we will be able to store the login token for the user
            else:
                self.clearErrorMessage()
                self.badCredentials = False
                self._login_password = ""
                self._app_preferences.setValue(self._username_preference, username)
                self._token = self._client.get_token()
                self._createTokenFile()

    # Logout removes the current token, clears the last logged in username and signals the popup to reappear.
    def logout(self):
        self._token_file_path = os.path.join(PluginRegistry.getInstance().getPluginPath("SmartSlicePlugin"), ".token")
        self._token = None
        self._login_password = ""
        self._createTokenFile()
        self._app_preferences.setValue(self._username_preference, "")
        self.loggedInChanged.emit()

    # If our user has logged in before, their login token will be in the file.
    def _getToken(self):
        #TODO: If no token file, try to login and create one. For now, we will just create a token file.
        if not os.path.exists(self._token_file_path):
            self._token = None
        else:
            try:
                with open(self._token_file_path, "r") as token_file:
                    self._token = json.load(token_file)
            except:
                Logger.log("d", "Unable to read Token JSON")
                self._token = None

            if self._token == "" or self._token is None:
                self._token = None

    # Once we have pulled the token, we want to check with the API to make sure the token is valid.
    def _checkToken(self):
        self._client.set_token(self._token)
        api_code, api_result = self.executeApiCall(
            lambda: self._client.whoami(),
            self.ConnectionErrorCodes.loginCredentialsError
        )

        if api_code != 200:
            self._token = None
            self._createTokenFile()

    # If there is no token in the file, or the file does not exist, we create one.
    def _createTokenFile(self):
        with open(self._token_file_path, "w") as token_file:
            json.dump(self._token, token_file)

    def getSubscription(self):
        api_code, api_result = self.executeApiCall(
            lambda: self._client.smartslice_subscription(),
            self.ConnectionErrorCodes.genericInternetConnectionError
        )

        if api_code != 200:
            self._handleThorErrors(api_code, api_result)
            return None

        return api_result

    def cancelJob(self, job_id):
        api_code, api_result = self.executeApiCall(
            lambda: self._client.smartslice_job_abort(job_id),
            self.ConnectionErrorCodes.genericInternetConnectionError
        )

        if api_code != 200:
            self._handleThorErrors(api_code, api_result)

    # If the user is correctly logged in, and has a valid token, we can use the 3mf data from
    #    the plugin to submit a job to the API, and the results will be handled when they are returned.
    def submitSmartSliceJob(self, cloud_job, threemf_data):
        thor_status_code, task = self.executeApiCall(
            lambda: self._client.new_smartslice_job(threemf_data),
            self.ConnectionErrorCodes.genericInternetConnectionError
        )

        job_status_tracker = JobStatusTracker(self.connector, self.connector.status)

        Logger.log("d", "API Status after posting: {}".format(thor_status_code))

        if thor_status_code != 200:
            self._handleThorErrors(thor_status_code, task)
            self.connector.cancelCurrentJob()

        if getattr(task, 'status', None):
            Logger.log("d", "Job status after posting: {}".format(task.status))

        # While the task status is not finished/failed/crashed/aborted continue to
        # wait on the status using the API.
        thor_status_code = None
        while thor_status_code != 1 and not cloud_job.canceled and task.status not in (
            pywim.http.thor.JobInfo.Status.failed,
            pywim.http.thor.JobInfo.Status.crashed,
            pywim.http.thor.JobInfo.Status.aborted,
            pywim.http.thor.JobInfo.Status.finished
        ):

            self.job_status = task.status
            cloud_job.api_job_id = task.id

            thor_status_code, task = self.executeApiCall(
                lambda: self._client.smartslice_job_wait(task.id, callback=job_status_tracker),
                self.ConnectionErrorCodes.genericInternetConnectionError
            )

            if thor_status_code == 200:
                thor_status_code, task = self.executeApiCall(
                    lambda: self._client.smartslice_job_wait(task.id, callback=job_status_tracker),
                    self.ConnectionErrorCodes.genericInternetConnectionError
                )

            if thor_status_code not in (200, None):
                self._handleThorErrors(thor_status_code, task)
                self.connector.cancelCurrentJob()

        if not cloud_job.canceled:
            self.connector.propertyHandler._cancelChanges = False

            if task.status == pywim.http.thor.JobInfo.Status.failed:
                error_message = Message()
                error_message.setTitle("Smart Slice Solver")
                error_message.setText(i18n_catalog.i18nc(
                    "@info:status",
                    "Error while processing the job:\n{}".format(task.errors[0].message)
                ))
                error_message.show()

                self.connector.cancelCurrentJob()
                cloud_job.setError(SmartSliceCloudJob.JobException(error_message.getText()))

                Logger.log(
                    "e",
                    "An error occured while sending and receiving cloud job: {}".format(error_message.getText())
                )
                self.connector.propertyHandler._cancelChanges = False
                return None
            elif task.status == pywim.http.thor.JobInfo.Status.finished:
                return task
            elif len(task.errors) > 0:
                error_message = Message()
                error_message.setTitle("Smart Slice Solver")
                error_message.setText(i18n_catalog.i18nc(
                    "@info:status",
                    "Unexpected status occured:\n{}".format(task.errors[0].message)
                ))
                error_message.show()

                self.connector.cancelCurrentJob()
                cloud_job.setError(SmartSliceCloudJob.JobException(error_message.getText()))

                Logger.log(
                    "e",
                    "An unexpected status occured while sending and receiving cloud job: {}".format(error_message.getText())
                )
                self.connector.propertyHandler._cancelChanges = False
                return None


    # When something goes wrong with the API, the errors are sent here. The http_error_code is an int that indicates
    #   the problem that has occurred. The returned object may hold additional information about the error, or it may be None.
    def _handleThorErrors(self, http_error_code, returned_object):
        if self._error_message is not None:
            self._error_message.hide()

        self._error_message = Message(lifetime= 180)
        self._error_message.setTitle("Smart Slice API")

        if http_error_code == 400:
            if returned_object.error.startswith('User\'s maximum job queue count reached'):
                print(self._error_message.getActions())
                self._error_message.setTitle("")
                self._error_message.setText("You have exceeded the maximum allowable "
                                      "number of queued\n jobs. Please cancel a "
                                      "queued job or wait for your queue to clear.")
                self._error_message.addAction(
                    "continue",
                    i18n_catalog.i18nc("@action", "Ok"),
                    "", ""
                )
                self._error_message.actionTriggered.connect(self.errorMessageAction)
            else:
                self._error_message.setText(i18n_catalog.i18nc("@info:status", "SmartSlice Server Error (400: Bad Request):\n{}".format(returned_object.error)))
        elif http_error_code == 401:
            self._error_message.setText(i18n_catalog.i18nc("@info:status", "SmartSlice Server Error (401: Unauthorized):\nAre you logged in?"))
        elif http_error_code == 429:
            self._error_message.setText(i18n_catalog.i18nc("@info:status", "SmartSlice Server Error (429: Too Many Attempts)"))
        elif http_error_code == self.ConnectionErrorCodes.genericInternetConnectionError:
            self._error_message.setText(i18n_catalog.i18nc("@info:status", "Internet connection issue:\nPlease check your connection and try again."))
        elif http_error_code == self.ConnectionErrorCodes.loginCredentialsError:
            self._error_message.setText(i18n_catalog.i18nc("@info:status", "Internet connection issue:\nCould not verify your login credentials."))
        else:
            self._error_message.setText(i18n_catalog.i18nc("@info:status", "SmartSlice Server Error (HTTP Error: {})".format(http_error_code)))
        self._error_message.show()

    @staticmethod
    def errorMessageAction(msg, action):
        msg.hide()

    @pyqtSlot()
    def onLoginButtonClicked(self):
        self.openConnection()

    @pyqtProperty(str, constant=True)
    def smartSliceUrl(self):
        return self._plugin_metadata.url

    badCredentialsChanged = pyqtSignal()
    loggedInChanged = pyqtSignal()

    @pyqtProperty(bool, notify=loggedInChanged)
    def logged_in(self):
        return self._token is not None

    @pyqtProperty(str, constant=True)
    def loginUsername(self):
        return self._login_username

    @loginUsername.setter
    def loginUsername(self,value):
        self._login_username = value

    @pyqtProperty(str, constant=True)
    def loginPassword(self):
        return self._login_password

    @loginPassword.setter
    def loginPassword(self,value):
        self._login_password = value

    @pyqtProperty(bool, notify=badCredentialsChanged)
    def badCredentials(self):
        return self._badCredentials

    @badCredentials.setter
    def badCredentials(self, value):
        self._badCredentials = value
        self.badCredentialsChanged.emit()


class SmartSliceCloudConnector(QObject):
    debug_save_smartslice_package_preference = "smartslice/debug_save_smartslice_package"
    debug_save_smartslice_package_location = "smartslice/debug_save_smartslice_package_location"

    class SubscriptionTypes(Enum):
        subscriptionExpired = 0
        trialExpired = 1
        outOfUses = 2
        noSubscription = 3

    def __init__(self, proxy: SmartSliceCloudProxy, extension):
        super().__init__()

        # Variables
        self._job = None
        self._jobs = {}
        self._current_job = 0
        self._jobs[self._current_job] = None

        # Proxy
        #General
        self._proxy = proxy
        self._proxy.sliceButtonClicked.connect(self.onSliceButtonClicked)
        self._proxy.secondaryButtonClicked.connect(self.onSecondaryButtonClicked)

        self.extension = extension

        # Debug stuff
        self.app_preferences = Application.getInstance().getPreferences()
        self.app_preferences.addPreference(self.debug_save_smartslice_package_preference, False)
        default_save_smartslice_package_location = str(Path.home())
        self.app_preferences.addPreference(self.debug_save_smartslice_package_location, default_save_smartslice_package_location)
        self.debug_save_smartslice_package_message = None

        # Executing a set of function when some activitiy has changed
        Application.getInstance().activityChanged.connect(self._onApplicationActivityChanged)

        #  Machines / Extruders
        self.activeMachine = None
        self.propertyHandler = None # SmartSlicePropertyHandler
        self.smartSliceJobHandle = None

        Application.getInstance().engineCreatedSignal.connect(self._onEngineCreated)

        self._confirmDialog = []
        self.confirming = False

        self.saveSmartSliceJob = Signal()

        self.api_connection = SmartSliceAPIClient(self)

    onSmartSlicePrepared = pyqtSignal()

    @property
    def cloudJob(self) -> SmartSliceCloudJob:
        if len(self._jobs) > 0:
            return self._jobs[self._current_job]

        return None

    def addJob(self, job_type: pywim.smartslice.job.JobType):

        self.propertyHandler._cancelChanges = False
        self._current_job += 1

        if job_type == pywim.smartslice.job.JobType.optimization:
            self._jobs[self._current_job] = SmartSliceCloudOptimizeJob(self)
        else:
            self._jobs[self._current_job] = SmartSliceCloudVerificationJob(self)

        self._jobs[self._current_job]._id = self._current_job
        self._jobs[self._current_job].finished.connect(self._onJobFinished)

    def cancelCurrentJob(self):
        self.api_connection.cancelJob(self._jobs[self._current_job].api_job_id)
        if self._jobs[self._current_job] is not None:
            if not self._jobs[self._current_job].canceled:
                self.status = SmartSliceCloudStatus.Cancelling
                self.updateStatus()
            self._jobs[self._current_job].cancel()
            self._jobs[self._current_job].canceled = True
            self._jobs[self._current_job] = None

    # Resets all of the tracked properties and jobs
    def clearJobs(self):

        # Cancel the running job (if any)
        if len(self._jobs) > 0 and self._jobs[self._current_job] and self._jobs[self._current_job].isRunning():
            self.cancelCurrentJob()

        # Clear out the jobs
        self._jobs.clear()
        self._current_job = 0
        self._jobs[self._current_job] = None

    def _onSaveDebugPackage(self, messageId: str, actionId: str) -> None:
        dummy_job = SmartSliceCloudVerificationJob(self)
        if self.status == SmartSliceCloudStatus.ReadyToVerify:
            dummy_job.job_type = pywim.smartslice.job.JobType.validation
        elif self.status in SmartSliceCloudStatus.optimizable():
            dummy_job.job_type = pywim.smartslice.job.JobType.optimization
        else:
            Logger.log("e", "DEBUG: This is not a defined state. Provide all input to create the debug package.")
            return

        jobname = Application.getInstance().getPrintInformation().jobName
        debug_filename = "{}_smartslice.3mf".format(jobname)
        debug_filedir = self.app_preferences.getValue(self.debug_save_smartslice_package_location)
        dummy_job = dummy_job.prepareJob(filename=debug_filename, filedir=debug_filedir)

    def getProxy(self, engine=None, script_engine=None):
        return self._proxy

    def getAPI(self, engine=None, script_engine=None):
        return self.api_connection

    def _onEngineCreated(self):
        self.activeMachine = Application.getInstance().getMachineManager().activeMachine
        self.propertyHandler = SmartSlicePropertyHandler(self)
        self.smartSliceJobHandle = SmartSliceJobHandler(self.propertyHandler)

        self.onSmartSlicePrepared.emit()
        self.propertyHandler.cacheChanges() # Setup Cache

        Application.getInstance().getMachineManager().printerConnectedStatusChanged.connect(self._refreshMachine)

        if self.app_preferences.getValue(self.debug_save_smartslice_package_preference):
            self.debug_save_smartslice_package_message = Message(
                title="[DEBUG] SmartSlicePlugin",
                text= "Click on the button below to generate a debug package",
                lifetime= 0,
            )
            self.debug_save_smartslice_package_message.addAction("", i18n_catalog.i18nc("@action", "Save package"), "", "")
            self.debug_save_smartslice_package_message.actionTriggered.connect(self._onSaveDebugPackage)
            self.debug_save_smartslice_package_message.show()

    def _refreshMachine(self):
        self.activeMachine = Application.getInstance().getMachineManager().activeMachine

    def updateSliceWidget(self):
        if self.status is SmartSliceCloudStatus.Errors:
            self._proxy.sliceStatus = ""
            self._proxy.sliceHint = ""
            self._proxy.sliceButtonText = "Validate"
            self._proxy.sliceButtonEnabled = False
            self._proxy.sliceButtonVisible = True
            self._proxy.sliceButtonFillWidth = True
            self._proxy.secondaryButtonVisible = False
            self._proxy.sliceInfoOpen = False
            self._proxy.progressBarVisible = False
            self._proxy.jobProgress = 0
        elif self.status is SmartSliceCloudStatus.Cancelling:
            self._proxy.sliceStatus = ""
            self._proxy.sliceHint = ""
            self._proxy.sliceButtonText = "Cancelling"
            self._proxy.sliceButtonEnabled = False
            self._proxy.sliceButtonVisible = True
            self._proxy.sliceButtonFillWidth = True
            self._proxy.secondaryButtonVisible = False
            self._proxy.sliceInfoOpen = False
            self._proxy.progressBarVisible = False
            self._proxy.jobProgress = 0
        elif self.status is SmartSliceCloudStatus.ReadyToVerify:
            self._proxy.sliceStatus = ""
            self._proxy.sliceHint = ""
            self._proxy.sliceButtonText = "Validate"
            self._proxy.sliceButtonEnabled = True
            self._proxy.sliceButtonVisible = True
            self._proxy.sliceButtonFillWidth = True
            self._proxy.secondaryButtonVisible = False
            self._proxy.sliceInfoOpen = False
            self._proxy.progressBarVisible = False
            self._proxy.jobProgress = 0
        elif self.status is SmartSliceCloudStatus.BusyValidating:
            self._proxy.sliceStatus = "Validating requirements..."
            self._proxy.sliceHint = ""
            self._proxy.secondaryButtonText = "Cancel"
            self._proxy.sliceButtonVisible = False
            self._proxy.secondaryButtonVisible = True
            self._proxy.secondaryButtonFillWidth = True
            self._proxy.sliceInfoOpen = False
            self._proxy.progressBarVisible = False
            self._proxy.jobProgress = 0
        elif self.status is SmartSliceCloudStatus.Underdimensioned:
            self._proxy.sliceStatus = "Requirements not met!"
            self._proxy.sliceHint = "Optimize to meet requirements?"
            self._proxy.sliceButtonText = "Optimize"
            self._proxy.secondaryButtonText = "Preview"
            self._proxy.sliceButtonEnabled = True
            self._proxy.sliceButtonVisible = True
            self._proxy.sliceButtonFillWidth = False
            self._proxy.secondaryButtonVisible = True
            self._proxy.secondaryButtonFillWidth = False
            self._proxy.sliceInfoOpen = True
            self._proxy.progressBarVisible = False
            self._proxy.jobProgress = 0
        elif self.status is SmartSliceCloudStatus.Overdimensioned:
            self._proxy.sliceStatus = "Part appears overdesigned"
            self._proxy.sliceHint = "Optimize to reduce print time and material?"
            self._proxy.sliceButtonText = "Optimize"
            self._proxy.secondaryButtonText = "Preview"
            self._proxy.sliceButtonEnabled = True
            self._proxy.sliceButtonVisible = True
            self._proxy.sliceButtonFillWidth = False
            self._proxy.secondaryButtonVisible = True
            self._proxy.secondaryButtonFillWidth = False
            self._proxy.sliceInfoOpen = True
            self._proxy.progressBarVisible = False
            self._proxy.jobProgress = 0
        elif self.status is SmartSliceCloudStatus.BusyOptimizing:
            self._proxy.sliceStatus = "Optimizing..."
            self._proxy.sliceHint = ""
            self._proxy.secondaryButtonText = "Cancel"
            self._proxy.sliceButtonVisible = False
            self._proxy.secondaryButtonVisible = True
            self._proxy.secondaryButtonFillWidth = True
            self._proxy.sliceInfoOpen = False
            self._proxy.progressBarVisible = True
        elif self.status is SmartSliceCloudStatus.Optimized:
            self._proxy.sliceStatus = ""
            self._proxy.sliceHint = ""
            self._proxy.secondaryButtonText = "Preview"
            self._proxy.sliceButtonVisible = False
            self._proxy.secondaryButtonVisible = True
            self._proxy.secondaryButtonFillWidth = True
            self._proxy.sliceInfoOpen = True
            self._proxy.progressBarVisible = False
            self._proxy.jobProgress = 0
        elif self.status is SmartSliceCloudStatus.Queued:
            self._proxy.sliceStatus = "Queued..."
            self._proxy.sliceHint = ""
            self._proxy.secondaryButtonText = "Cancel"
            self._proxy.sliceButtonVisible = False
            self._proxy.secondaryButtonVisible = True
            self._proxy.secondaryButtonFillWidth = True
            self._proxy.sliceInfoOpen = False
            self._proxy.progressBarVisible = False
            self._proxy.jobProgress = 0
        elif self.status is SmartSliceCloudStatus.RemoveModMesh:
            self._proxy.sliceStatus = ""
            self._proxy.sliceHint = ""
            self._proxy.secondaryButtonText = "Cancel"
            self._proxy.sliceButtonVisible = False
            self._proxy.secondaryButtonVisible = True
            self._proxy.secondaryButtonFillWidth = True
            self._proxy.sliceInfoOpen = False
            self._proxy.progressBarVisible = False
            self._proxy.jobProgress = 0
        else:
            self._proxy.sliceStatus = "Unknown status"
            self._proxy.sliceHint = "Sorry, something went wrong!"
            self._proxy.sliceButtonText = "..."
            self._proxy.sliceButtonEnabled = False
            self._proxy.sliceButtonVisible = True
            self._proxy.secondaryButtonVisible = False
            self._proxy.secondaryButtonFillWidth = False
            self._proxy.sliceInfoOpen = False
            self._proxy.progressBarVisible = False
            self._proxy.jobProgress = 0

        # Setting icon path
        stage_path = PluginRegistry.getInstance().getPluginPath("SmartSlicePlugin")
        stage_images_path = os.path.join(stage_path, "stage", "images")
        icon_done_green = os.path.join(stage_images_path, "done_green.png")
        icon_error_red = os.path.join(stage_images_path, "error_red.png")
        icon_warning_yellow = os.path.join(stage_images_path, "warning_yellow.png")
        current_icon = icon_done_green
        if self.status is SmartSliceCloudStatus.Overdimensioned:
            current_icon = icon_warning_yellow
        elif self.status is SmartSliceCloudStatus.Underdimensioned:
            current_icon = icon_error_red
        current_icon = QUrl.fromLocalFile(current_icon)
        self._proxy.sliceIconImage = current_icon

        # Setting icon visibiltiy
        if self.status in (SmartSliceCloudStatus.Optimized,) + SmartSliceCloudStatus.optimizable():
            self._proxy.sliceIconVisible = True
        else:
            self._proxy.sliceIconVisible = False

        self._proxy.updateColorUI()

    @property
    def status(self):
        return self._proxy.sliceStatusEnum

    @status.setter
    def status(self, value):
        Logger.log("d", "Setting status: {} -> {}".format(self._proxy.sliceStatusEnum, value))
        if self._proxy.sliceStatusEnum is not value:
            self._proxy.sliceStatusEnum = value
        self.updateSliceWidget()

    def _onApplicationActivityChanged(self):
        printable_nodes_count = len(getPrintableNodes())

        sel_tool = SmartSliceSelectTool.getInstance()

        if printable_nodes_count != 1 or len(self._proxy.errors) > 0:
            self.status = SmartSliceCloudStatus.Errors

    def _onJobFinished(self, job):
        if self._jobs[self._current_job] is None or self._jobs[self._current_job].canceled:
            Logger.log("d", "Smart Slice Job was Cancelled")
            return

        if self._jobs[self._current_job].hasError():
            exc = self._jobs[self._current_job].getError()
            error = str(exc) if exc else "Unknown Error"
            self.cancelCurrentJob()
            Logger.logException("e", error)
            Message(
                title='Smart Slice job unexpectedly failed',
                text=error
            ).show()
            return

        self.propertyHandler._propertiesChanged.clear()
        self._proxy.shouldRaiseConfirmation = False

        if self._jobs[self._current_job].getResult():
            if len(self._jobs[self._current_job].getResult().analyses) > 0:
                self.processAnalysisResult()
                if self._jobs[self._current_job].job_type == pywim.smartslice.job.JobType.optimization:
                    self.status = SmartSliceCloudStatus.Optimized
                else:
                    self.prepareOptimization()
                self.saveSmartSliceJob.emit()
            else:
                if self.status != SmartSliceCloudStatus.ReadyToVerify and self.status != SmartSliceCloudStatus.Errors:
                    self.status = SmartSliceCloudStatus.ReadyToVerify
                    results = self._jobs[self._current_job].getResult().feasibility_result['structural']
                    Message(
                        title="Smart Slice Error",
                        text="<p>Smart Slice cannot find a solution for the problem, "
                             "please check the setup for errors. </p>"
                             "<p></p>"
                             "<p>Alternatively, you may need to modify the geometry "
                             "and/or try a different material:</p>"
                             "<p></p>"
                             "<p> <u>Solid Print:</u> </p>"
                             "<p></p>"
                             "<p style = 'margin-left:50px;'> <i> Minimum Safety Factor: "
                             "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; %.2f </i> </p>"
                             "<p></p>"
                             "<p style = 'margin-left:50px;'> <i> Maximum Displacement: "
                             "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; %.2f </i> </p>" %
                             (results["min_safety_factor"], results["max_displacement"]),
                        lifetime=1000,
                        dismissable=True
                    ).show()

    def processAnalysisResult(self, selectedRow=0):
        job = self._jobs[self._current_job]
        active_extruder = getNodeActiveExtruder(getPrintableNodes()[0])

        if job.job_type == pywim.smartslice.job.JobType.validation and active_extruder:
            resultData = ResultTableData.analysisToResultDict(0, job.getResult().analyses[0])
            self._proxy.updatePropertiesFromResults(resultData)

        elif job.job_type == pywim.smartslice.job.JobType.optimization and active_extruder:
            self._proxy.resultsTable.setResults(job.getResult().analyses, selectedRow)

    def updateStatus(self, show_warnings=False):
        job, self._proxy.errors = self.smartSliceJobHandle.checkJob(show_extruder_warnings=show_warnings)

        if len(self._proxy.errors) > 0 or job is None:
            self.status = SmartSliceCloudStatus.Errors
        elif self.status == SmartSliceCloudStatus.Errors or self.status == SmartSliceCloudStatus.Cancelling:
            self.status = SmartSliceCloudStatus.ReadyToVerify

        Application.getInstance().activityChanged.emit()

    def doVerification(self):
        self.status = SmartSliceCloudStatus.BusyValidating
        self.addJob(pywim.smartslice.job.JobType.validation)
        self._jobs[self._current_job].start()

    """
      prepareOptimization()
        Convenience function for updating the cloud status outside of Validation/Optimization Jobs
    """

    def prepareOptimization(self):
        self._proxy.optimizationStatus()
        self.updateSliceWidget()

    def doOptimization(self):
        if len(getModifierMeshes()) > 0:
            self.propertyHandler.askToRemoveModMesh()
        else:
            self.status = SmartSliceCloudStatus.BusyOptimizing
            self.addJob(pywim.smartslice.job.JobType.optimization)
            self._jobs[self._current_job].start()

    def _checkSubscription(self, subscription, product):
        if subscription.status in (pywim.http.thor.Subscription.Status.active, pywim.http.thor.Subscription.Status.trial):
            for prod in subscription.products:
                if prod.name == product:
                    if prod.usage_type == pywim.http.thor.Product.UsageType.unlimited:
                        return -1
                    elif prod.used < prod.total:
                        return prod.total - prod.used
                    else:
                        self._subscriptionMessages(self.SubscriptionTypes.outOfUses, prod)

        elif subscription.status == pywim.http.thor.Subscription.Status.inactive:
            if subscription.trial_end > datetime.datetime(1900, 1, 1):
                self._subscriptionMessages(self.SubscriptionTypes.trialExpired)
            else:
                self._subscriptionMessages(self.SubscriptionTypes.subscriptionExpired)

        else:
            self._subscriptionMessages(self.SubscriptionTypes.noSubscription)

        return 0

    def _subscriptionMessages(self, messageCode, prod=None):
        notification_message = Message(lifetime=0)

        if messageCode == self.SubscriptionTypes.outOfUses:
            notification_message.setText(
                i18n_catalog.i18nc("@info:status", "You are out of {}s! Please purchase more to continue.".format(prod.name))
            )
            notification_message.addAction(
                action_id="more_products_link",
                name="<b>Purchase {}s</b>".format(prod.name),
                icon="",
                description="Click here to get more {}s!".format(prod.name),
                button_style=Message.ActionButtonStyle.LINK
            )

        else:
            if messageCode == self.SubscriptionTypes.trialExpired:
                notification_message.setText(
                    i18n_catalog.i18nc("@info:status", "Your free trial has expired! Please subscribe to submit jobs.")
                )
            elif messageCode == self.SubscriptionTypes.subscriptionExpired:
                notification_message.setText(
                    i18n_catalog.i18nc("@info:status", "Your subscription has expired! Please renew your subscription to submit jobs.")
                )
            elif messageCode == self.SubscriptionTypes.noSubscription:
                notification_message.setText(
                    i18n_catalog.i18nc("@info:status", "You do not have a subscription! Please subscribe to submit jobs.")
                )

            notification_message.addAction(
                action_id="subscribe_link",
                name="<h3><b>Manage Subscription</b></h3>",
                icon="",
                description="Click here to subscribe!",
                button_style=Message.ActionButtonStyle.LINK
            )

        notification_message.actionTriggered.connect(self._openSubscriptionPage)
        notification_message.show()

    def _openSubscriptionPage(self, msg, action):
        if action in ("subscribe_link", "more_products_link"):
            QDesktopServices.openUrl(QUrl('%s/static/account.html' % self.extension.metadata.url))

    '''
      Primary Button Actions:
        * Validate
        * Optimize
        * Slice
    '''

    def onSliceButtonClicked(self):
        if self.status in SmartSliceCloudStatus.busy():
            self._jobs[self._current_job].cancel()
            self._jobs[self._current_job] = None
        else:
            self._subscription = self.api_connection.getSubscription()
            if self._subscription is not None:
                if self.status is SmartSliceCloudStatus.ReadyToVerify:
                    if self._checkSubscription(self._subscription, "validation") != 0:
                        self.doVerification()
                elif self.status in SmartSliceCloudStatus.optimizable():
                    if self._checkSubscription(self._subscription, "optimization") != 0:
                        self.doOptimization()
                elif self.status is SmartSliceCloudStatus.Optimized:
                    Application.getInstance().getController().setActiveStage("PreviewStage")
            else:
                self._subscriptionMessages(self.SubscriptionTypes.noSubscription)

    '''
      Secondary Button Actions:
        * Cancel  (Validating / Optimizing)
        * Preview
    '''

    def onSecondaryButtonClicked(self):
        if self.status in SmartSliceCloudStatus.busy():
            job_status = self._jobs[self._current_job].job_type
            self.cancelCurrentJob()
            if job_status == pywim.smartslice.job.JobType.optimization:
                self.prepareOptimization()
        else:
            Application.getInstance().getController().setActiveStage("PreviewStage")
