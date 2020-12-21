import UM 1.2 as UM
import QtQuick 2.10
import QtQuick.Layouts 1.3

import SmartSlice 1.0 as SmartSlice

Rectangle {
    id: resultsButtonsWindow

    visible: false

    width: UM.Theme.getSize("action_panel_widget").width / 3
    height: UM.Theme.getSize("action_button").height + (UM.Theme.getSize("thick_margin").height * 2)

    property var tooltipLocations: UM.Controller.activeStage.proxy.tooltipLocations

    anchors {
        rightMargin: UM.Theme.getSize("thick_margin").width
        bottomMargin: UM.Theme.getSize("thick_margin").height
        bottom: parent.bottom
    }
    color: UM.Theme.getColor("main_background")
    border {
        width: UM.Theme.getSize("default_lining").width
        color: UM.Theme.getColor("lining")
    }
    radius: UM.Theme.getSize("default_radius").width

    Connections {
        target: smartSliceMain.proxy
        onSafetyFactorColorChanged: {
            stressButton.buttonOpacity = 0.5
            stressButton.color = smartSliceMain.proxy.safetyFactorColor
            smartSliceMain.proxy.closeResultsButtonPopup()
        }

        onMaxDisplaceColorChanged: {
            deflectionButton.buttonOpacity = 0.5
            deflectionButton.color = smartSliceMain.proxy.maxDisplaceColor
            smartSliceMain.proxy.closeResultsButtonPopup()
        }

        onResultsButtonsVisibleChanged: {
            resultsButtonsWindow.visible = smartSliceMain.proxy.resultsButtonsVisible
            smartSliceMain.proxy.closeResultsButtonPopup()
        }

        onResetResultsButtonsOpacity: {
            deflectionButton.buttonOpacity = 0.5
            stressButton.buttonOpacity = 0.5
        }

        onUnableToOptimizeStress: {
            stressButton.buttonOpacity = 1
        }

        onUnableToOptimizeDisplacement: {
            deflectionButton.buttonOpacity = 1
        }
    }

    RowLayout {
        anchors.fill: parent
        height: childrenRect.height
        width: childrenRect.width

        Row {
            id: resultsButtonsRow
            spacing: UM.Theme.getSize("default_margin").width

            anchors.horizontalCenter: parent.horizontalCenter

            SmartSlice.HoverableButton {
                id: deflectionButton

                height: UM.Theme.getSize("action_button").height
                width: height

                color: UM.Theme.getColor("action_button_text")

                iconSource: "../images/displacement.png"

                onClicked: {
                    deflectionButton.buttonOpacity = 1
                    stressButton.buttonOpacity = 0.5
                    smartSliceMain.proxy.displayResultsMessage("deflection")
                }

                onEntered: {
                    deflectionButton.buttonOpacity === 1 ? deflectionButton.buttonOpacity = 1 : deflectionButton.buttonOpacity = 0.75
                }

                onExited: {
                    deflectionButton.buttonOpacity === 1 ? deflectionButton.buttonOpacity = 1 : deflectionButton.buttonOpacity = 0.5
                }

                tooltipHeader: catalog.i18nc("@textfp", "Show Displaced Part")
                tooltipDescription: catalog.i18nc("@textfp", "Show the deformation of the part under the defined use cases, "
                    + "and identify the regions of the geometry which could be modified to meet the target max displacement, if any.")

                tooltipTarget.x: 0.5 * width
                tooltipTarget.y: -UM.Theme.getSize("thick_margin").height
                tooltipLocation: resultsButtonsWindow.tooltipLocations["top"]
            }

            SmartSlice.HoverableButton {
                id: stressButton

                height: UM.Theme.getSize("action_button").height
                width: height

                color: UM.Theme.getColor("action_button_text")

                iconSource: "../images/failure.png"

                onClicked: {
                    stressButton.buttonOpacity = 1
                    deflectionButton.buttonOpacity = 0.5
                    smartSliceMain.proxy.displayResultsMessage("stress")
                }

                onEntered: {
                    stressButton.buttonOpacity === 1 ? stressButton.buttonOpacity = 1 : stressButton.buttonOpacity = 0.75;
                }

                onExited: {
                    stressButton.buttonOpacity === 1 ? stressButton.buttonOpacity = 1 : stressButton.buttonOpacity = 0.5;
                }

                tooltipHeader: catalog.i18nc("@textfp", "Show “Failure” Locations")
                tooltipDescription: catalog.i18nc("@textfp", "Identify all regions of the geometry which do not meet the target factor of safety, if any.")

                tooltipTarget.x: 0.5 * width
                tooltipTarget.y: -UM.Theme.getSize("thick_margin").height
                tooltipLocation: resultsButtonsWindow.tooltipLocations["top"]
            }
        }
    }
}