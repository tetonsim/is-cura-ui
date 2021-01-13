import os
import sys

from PyQt5.QtCore import QUrl
from PyQt5.QtQml import qmlRegisterType

from UM.i18n import i18nCatalog
i18n_catalog = i18nCatalog("smartslice")
from UM.Logger import Logger
from UM.PluginRegistry import PluginRegistry

from .utils import SystemUtils

# Loading third party modules
third_party_dir = os.path.realpath(__file__)
third_party_dir = os.path.dirname(third_party_dir)
third_party_dir = os.path.join(third_party_dir, "3rd-party")
if os.path.isdir(third_party_dir):
    SystemUtils.registerThirdPartyModules(third_party_dir)

# Importing pywim for testing
import pywim

from . import SmartSliceExtension, SmartSliceView
from .requirements_tool import SmartSliceRequirements
from .select_tool import SmartSliceSelectTool, BoundaryConditionList
from .stage import SmartSliceStage
from .stage.ui import ResultTable
from .components.SmartSliceMessageExtension import SmartSliceMessageModel

extension = SmartSliceExtension.SmartSliceExtension()
#extension._name = "Extension"
_stage = SmartSliceStage.SmartSliceStage(extension.cloud)
requirements_tool = SmartSliceRequirements.SmartSliceRequirements(extension)
requirements_tool._name = "RequirementsTool"
select_tool = SmartSliceSelectTool.SmartSliceSelectTool(extension)
select_tool._name = "SelectTool"

def getMetaData():
    return {
        "stage": {
            "name": i18n_catalog.i18nc("@item:inmenu", "Smart Slice"),
            "weight": 15
        },
        "tool": [
            {
                "name": i18n_catalog.i18nc("@label", "<b>Requirements</b> <p>Define the requirements for a successful part.</p>"),
                "description": i18n_catalog.i18nc("@info:tooltip", "Define the requirements for a successful part."),
                "icon": "requirements_tool/tool_icon.svg",
                "tool_panel": "requirements_tool/SmartSliceRequirements.qml",
                "weight": 20
            },
            {
                "name": i18n_catalog.i18nc("@label", "<b>Use Cases</b> <p>Define the use cases the part experiences in service.</p>"),
                "description": i18n_catalog.i18nc("@info:tooltip", "Define the use cases the part experiences in service."),
                "icon": "select_tool/media/tool_icon.svg",
                "tool_panel": "select_tool/SmartSliceSelectTool.qml",
                "weight": 10
            }
        ],
        "view": {
            "name": i18n_catalog.i18nc("@item:inmenu", "Smart Slice View"),
            "weight": 0,
            "visible": False
        }
    }


def register(app):
    qmlRegisterType(
        BoundaryConditionList.BoundaryConditionListModel,
        "SmartSlice",
        1, 0,
        "BoundaryConditionListModel"
    )

    directory = os.path.dirname(os.path.abspath(__file__))

    qmlRegisterType(
        ResultTable.ResultTableData,
        "SmartSlice",
        1, 0,
        "ResultsTableModel"
    )

    qmlRegisterType(
        SmartSliceMessageModel,
        "SmartSlice",
        1, 0,
        "SmartSliceMessageModel"
    )

    qmlRegisterType(
        QUrl.fromLocalFile(os.path.join(directory, "components", "SmartSliceMessage.qml")),
        "SmartSlice",
        1, 0,
        "SmartSliceMessage"
    )

    qmlRegisterType(
        QUrl.fromLocalFile(os.path.join(directory, "components", "SmartSliceTooltip.qml")),
        "SmartSlice",
        1, 0,
        "SmartSliceTooltip"
    )

    qmlRegisterType(
        QUrl.fromLocalFile(os.path.join(directory, "components", "HoverableTextField.qml")),
        "SmartSlice",
        1, 0,
        "HoverableTextField"
    )

    qmlRegisterType(
        QUrl.fromLocalFile(os.path.join(directory, "components", "HoverableButton.qml")),
        "SmartSlice",
        1, 0,
        "HoverableButton"
    )

    qmlRegisterType(
        QUrl.fromLocalFile(os.path.join(directory, "stage", "ui", "ResultsTable.qml")),
        "SmartSlice",
        1, 0,
        "ResultsTable"
    )

    qmlRegisterType(
        QUrl.fromLocalFile(os.path.join(directory, "select_tool", "BoundaryConditionList.qml")),
        "SmartSlice",
        1, 0,
        "BoundaryConditionList"
    )

    qmlRegisterType(
        QUrl.fromLocalFile(os.path.join(directory, "stage", "ui", "SmartSliceLogin.qml")),
        "SmartSlice",
        1, 0,
        "SmartSliceLogin"
    )

    qmlRegisterType(
        QUrl.fromLocalFile(os.path.join(directory, "stage", "ui", "SmartSliceResultsButtons.qml")),
        "SmartSlice",
        1, 0,
        "SmartSliceResultsButtons"
    )

    return {
        "extension": extension,
        "stage": _stage,
        "tool": [
            requirements_tool,
            select_tool,
        ],
        "view": SmartSliceView.SmartSliceView()
    }
