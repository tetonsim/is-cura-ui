import UM 1.2 as UM
import QtQuick 2.10
import QtQuick.Layouts 1.3

import SmartSlice 1.0 as SmartSlice

Rectangle {
    id: resultsButtonsWindow

    visible: false

    width: UM.Theme.getSize("action_panel_widget").width / 3
    height: UM.Theme.getSize("action_button").height + (UM.Theme.getSize("thick_margin").height * 2)

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
            stressButton.opacity = 0.5
            stressButton.color = smartSliceMain.proxy.safetyFactorColor
        }

        onMaxDisplaceColorChanged: {
            deflectionButton.opacity = 0.5
            deflectionButton.color = smartSliceMain.proxy.maxDisplaceColor
        }

        onResultsButtonsVisibleChanged: {
            resultsButtonsWindow.visible = smartSliceMain.proxy.resultsButtonsVisible
        }
    }

    RowLayout {
        anchors.fill: parent
        height: childrenRect.height
        width: childrenRect.width

        Row {
            spacing: UM.Theme.getSize("default_margin").width

            anchors.horizontalCenter: parent.horizontalCenter

            UM.SimpleButton {
                id: deflectionButton

                height: UM.Theme.getSize("action_button").height
                width: height

                color: UM.Theme.getColor("action_button_text")

                iconSource: "../images/displacement.png"

                onClicked: {
                    deflectionButton.opacity = 1
                    stressButton.opacity = 0.5
                    //TODO: Activate popup
                }

                onEntered: {
                    deflectionButton.opacity === 1 ? deflectionButton.opacity = 1 : deflectionButton.opacity = 0.75
                }

                onExited: {
                    deflectionButton.opacity === 1 ? deflectionButton.opacity = 1 : deflectionButton.opacity = 0.5
                }

            }

            UM.SimpleButton {
                id: stressButton

                height: UM.Theme.getSize("action_button").height
                width: height

                color: UM.Theme.getColor("action_button_text")

                iconSource: "../images/failure.png"

                onClicked: {
                    stressButton.opacity = 1
                    deflectionButton.opacity = 0.5
                    //TODO: Activate popup
                }

                onEntered: {
                    stressButton.opacity === 1 ? stressButton.opacity = 1 : stressButton.opacity = 0.75
                }

                onExited: {
                    stressButton.opacity === 1 ? stressButton.opacity = 1 : stressButton.opacity = 0.5
                }
            }
        }
    }
}