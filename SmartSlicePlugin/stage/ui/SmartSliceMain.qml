/*
    SmartSliceMain.qml
    Teton Simulation
    Last Modified October 16, 2019
*/

/*
    Contains definitions for Smart Slice's main structural UI elements

    This includes: (Vert. Horiz.)
        *  Brand Logo (Bottom Middle)
        *  "Smart Slice" Button (Bottom Right)
*/


//  API Imports
import QtQuick 2.7
import QtQuick.Controls 2.1
import QtQuick.Layouts 1.3
import QtQuick.Controls.Styles 1.1

import UM 1.2 as UM
import Cura 1.0 as Cura
import SmartSlice 1.0 as SmartSlice

//  Main UI Stage Components
Item {
    id: smartSliceMain

    //  Main Stage Accessible Properties
    property int smartLoads : 0
    property int smartAnchors : 0

    //  1.) Brand Logo
    Image {
        id: tetonBranding
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.leftMargin: UM.Theme.getSize("thick_margin").width
        anchors.bottomMargin: UM.Theme.getSize("thick_margin").height

        width: 250
        fillMode: Image.PreserveAspectFit
        source: "../images/branding.png"
        mipmap: true
    }

    //  2.) Smart Slice Window
    Rectangle {
        id: smartSliceWindow //    TODO: Change to Widget when everything works

        width: UM.Theme.getSize("action_panel_widget").width
        height: myColumn.height + 2 * UM.Theme.getSize("thick_margin").width

        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.rightMargin: UM.Theme.getSize("thick_margin").width
        anchors.bottomMargin: UM.Theme.getSize("thick_margin").height

        color: UM.Theme.getColor("main_background")
        border.width: UM.Theme.getSize("default_lining").width
        border.color: UM.Theme.getColor("lining")
        radius: UM.Theme.getSize("default_radius").width


        ColumnLayout {
            id: myColumn

            anchors {
                left: parent.left
                right: parent.right
                bottom: parent.bottom
                margins: UM.Theme.getSize("thick_margin").width
            }

            RowLayout {
                Layout.fillHeight: true
                Layout.fillWidth: true

                ColumnLayout {
                    Layout.fillWidth: true
                    // Main status message
                    Label {

                        Layout.fillHeight: true
                        Layout.fillWidth: true
                        font: UM.Theme.getFont("default");
                        renderType: Text.NativeRendering

                        text: SmartSlice.Cloud.sliceStatus

                    }

                    // Secondary status message with hint
                    Label {
                        Layout.fillHeight: true
                        Layout.fillWidth: true
                        font: UM.Theme.getFont("default")
                        renderType: Text.NativeRendering

                        text: SmartSlice.Cloud.sliceHint

                    }
                }

                // Status indicator
                Row{
                Layout.alignment: Qt.AlignTop

                Image {
                    id: smartSliceInfoIcon

                    width: UM.Theme.getSize("section_icon").width
                    height: UM.Theme.getSize("section_icon").height

                    fillMode: Image.PreserveAspectFit
                    mipmap: true

                    source: SmartSlice.Cloud.sliceIconImage
                    visible: SmartSlice.Cloud.sliceIconVisible

                    Connections {
                        target: SmartSlice.Cloud
                        onSliceIconImageChanged: {
                            smartSliceInfoIcon.source = SmartSlice.Cloud.sliceIconImage
                        }
                        onSliceIconVisibleChanged: {
                            smartSliceInfoIcon.visible = SmartSlice.Cloud.sliceIconVisible
                        }
                    }

                    MouseArea
                    {
                        anchors.fill: parent
                        hoverEnabled: true
                        onEntered: {
                            if (visible) {
                                smartSlicePopup.open();
                            }
                        }
                        onExited: smartSlicePopup.close()
                    }

                    // Popup message with slice results
                    Popup {
                        id: smartSlicePopup

                        y: -(height + UM.Theme.getSize("default_arrow").height + UM.Theme.getSize("thin_margin").height)
                        x: parent.width - width + UM.Theme.getSize("thin_margin").width

                        contentWidth: UM.Theme.getSize("action_panel_widget").width
                        contentHeight: smartSlicePopupContents.height

                        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent

                        opacity: opened ? 1 : 0
                        Behavior on opacity { NumberAnimation { duration: 100 } }

                        ColumnLayout {
                            id: smartSlicePopupContents

                            spacing: UM.Theme.getSize("default_margin").height

                            width: UM.Theme.getSize("action_panel_widget").width

                            property var header_font: UM.Theme.getFont("medium")
                            property var header_color: UM.Theme.getColor("text_subtext")
                            property var subheader_font: UM.Theme.getFont("default")
                            property var subheader_color: "#A9A9A9"
                            property var description_font: UM.Theme.getFont("default")
                            property var description_color: UM.Theme.getColor("text")
                            property var value_font: UM.Theme.getFont("default")
                            property var value_color: UM.Theme.getColor("text")

                            property color warningColor: "#F3BA1A"
                            property color errorColor: "#F15F63"
                            property color successColor: "#5DBA47"

                            /* REQUIREMENTS HEADER */
                            Label {
                                font: smartSlicePopupContents.header_font
                                color: smartSlicePopupContents.header_color

                                text: "REQUIREMENTS"
                            }

                            RowLayout {
                                id: layoutRequirements
                                Layout.fillWidth: true
                                spacing: UM.Theme.getSize("default_margin").width

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: UM.Theme.getSize("default_margin").height

                                    Label {
                                        Layout.fillWidth: true

                                        text: "Objective"

                                        font: smartSlicePopupContents.subheader_font
                                        color: smartSlicePopupContents.subheader_color
                                    }
                                    Label {
                                        id: labelDescriptionSafetyFactor
                                        text: "Factor of Safety:"

                                        font: smartSlicePopupContents.description_font
                                        color: SmartSlice.Cloud.safetyFactorColor
                                    }
                                    Label {
                                        id: labelDescriptionMaximumDisplacement
                                        text: "Max Displacement:"

                                        font: smartSlicePopupContents.description_font
                                        color: SmartSlice.Cloud.maxDisplaceColor
                                    }
                                }
                                ColumnLayout {
                                    id: secondColumnPopup

                                    spacing: UM.Theme.getSize("default_margin").height

                                    Label {
                                        Layout.alignment: Qt.AlignRight
                                        font: smartSlicePopupContents.subheader_font
                                        color: smartSlicePopupContents.subheader_color

                                        text: "Computed"
                                    }
                                    Label {
                                        id: labelResultSafetyFactor

                                        Layout.alignment: Qt.AlignRight
                                        font: smartSlicePopupContents.value_font
                                        color: SmartSlice.Cloud.safetyFactorColor

                                        Connections {
                                            target: SmartSlice.Cloud
                                            onResultSafetyFactorChanged: {
                                                labelResultSafetyFactor.text = parseFloat(Math.round(SmartSlice.Cloud.resultSafetyFactor * 1000) / 1000).toFixed(3)
                                            }
                                        }

                                        text: parseFloat(Math.round(SmartSlice.Cloud.resultSafetyFactor * 1000) / 1000).toFixed(3)
                                    }
                                    Label {
                                        id: labelResultMaximalDisplacement

                                        Layout.alignment: Qt.AlignRight
                                        font: smartSlicePopupContents.value_font
                                        color: SmartSlice.Cloud.maxDisplaceColor

                                        Connections {
                                            target: SmartSlice.Cloud
                                            onResultMaximalDisplacementChanged: {
                                                labelResultMaximalDisplacement.text = parseFloat(Math.round(SmartSlice.Cloud.resultMaximalDisplacement * 1000) / 1000).toFixed(3)
                                            }
                                        }

                                        text: parseFloat(Math.round(SmartSlice.Cloud.resultMaximalDisplacement * 1000) / 1000).toFixed(3)
                                    }
                                }
                                ColumnLayout {
                                    id: thirdColumnPopup

                                    spacing: UM.Theme.getSize("default_margin").height

                                    Label {
                                        Layout.alignment: Qt.AlignRight
                                        font: smartSlicePopupContents.subheader_font
                                        color: smartSlicePopupContents.subheader_color

                                        text: "Target"
                                    }
                                    Label {
                                        id: labelTargetSafetyFactor

                                        Layout.alignment: Qt.AlignRight
                                        font: smartSlicePopupContents.value_font
                                        color: SmartSlice.Cloud.safetyFactorColor

                                        Connections {
                                            target: SmartSlice.Cloud
                                            onTargetSafetyFactorChanged: {
                                                labelTargetSafetyFactor.text = parseFloat(Math.round(SmartSlice.Cloud.targetSafetyFactor * 1000) / 1000).toFixed(3)
                                            }
                                        }

                                        text: parseFloat(Math.round(SmartSlice.Cloud.targetSafetyFactor * 1000) / 1000).toFixed(3)
                                    }
                                    Label {
                                        id: labelTargetMaximalDisplacement

                                        Layout.alignment: Qt.AlignRight
                                        font: smartSlicePopupContents.value_font
                                        color: SmartSlice.Cloud.maxDisplaceColor

                                        Connections {
                                            target: SmartSlice.Cloud
                                            onTargetMaximalDisplacementChanged: {
                                                labelTargetMaximalDisplacement.text = parseFloat(Math.round(SmartSlice.Cloud.targetMaximalDisplacement * 1000) / 1000).toFixed(3)
                                            }
                                        }

                                        text: parseFloat(Math.round(SmartSlice.Cloud.targetMaximalDisplacement * 1000) / 1000).toFixed(3)
                                    }
                                }
                            }


                            /* TIME ESTIMATION HEADER */
                            Label {
                                font: smartSlicePopupContents.header_font
                                color: smartSlicePopupContents.header_color

                                text: "TIME ESTIMATION"
                            }

                            RowLayout {
                                spacing: UM.Theme.getSize("default_margin").width

                                ColumnLayout {
                                    spacing: UM.Theme.getSize("default_margin").height

                                    Label {
                                        Layout.fillWidth: true

                                        text: "Print time:"

                                        font: smartSlicePopupContents.description_font
                                        color: smartSlicePopupContents.description_color
                                    }
                                    /*
                                    Label {
                                        Layout.fillWidth: true

                                        text: "Infill:"

                                        font: smartSlicePopupContents.description_font
                                        color: smartSlicePopupContents.description_color
                                    }
                                    Label {
                                        text: "Inner Walls:"

                                        font: smartSlicePopupContents.description_font
                                        color: smartSlicePopupContents.description_color
                                    }
                                    Label {
                                        text: "Outer Walls:"

                                        font: smartSlicePopupContents.description_font
                                        color: smartSlicePopupContents.description_color
                                    }
                                    Label {
                                        text: "Retractions:"

                                        font: smartSlicePopupContents.description_font
                                        color: smartSlicePopupContents.description_color
                                    }
                                    Label {
                                        font: smartSlicePopupContents.description_font
                                        color: smartSlicePopupContents.description_color

                                        text: "Skin:"
                                    }
                                    Label {
                                        font: smartSlicePopupContents.description_font
                                        color: smartSlicePopupContents.description_color

                                        text: "Skirt:"
                                    }
                                    Label {
                                        font: smartSlicePopupContents.description_font
                                        color: smartSlicePopupContents.description_color

                                        text: "Travel:"
                                    }
                                    */
                                }

                                ColumnLayout {
                                    width: secondColumnPopup.width

                                    spacing: UM.Theme.getSize("default_margin").height

                                    Label {
                                        id: labelResultTimeTotal

                                        Layout.alignment: Qt.AlignRight
                                        font: smartSlicePopupContents.value_font
                                        color: smartSlicePopupContents.value_color

                                        text: Qt.formatTime(SmartSlice.Cloud.resultTimeTotal, "hh:mm")
                                    }
                                    /*
                                    Label {
                                        Layout.alignment: Qt.AlignRight
                                        font: smartSlicePopupContents.value_font
                                        color: smartSlicePopupContents.value_color

                                        text: Qt.formatTime(SmartSlice.Cloud.resultTimeInfill, "hh:mm")
                                    }
                                    Label {
                                        Layout.alignment: Qt.AlignRight
                                        font: smartSlicePopupContents.value_font
                                        color: smartSlicePopupContents.value_color

                                        text: Qt.formatTime(SmartSlice.Cloud.resultTimeInnerWalls, "hh:mm")
                                    }
                                    Label {
                                        Layout.alignment: Qt.AlignRight
                                        font: smartSlicePopupContents.value_font
                                        color: smartSlicePopupContents.value_color

                                        text: Qt.formatTime(SmartSlice.Cloud.resultTimeOuterWalls, "hh:mm")
                                    }
                                    Label {
                                        Layout.alignment: Qt.AlignRight
                                        font: smartSlicePopupContents.value_font
                                        color: smartSlicePopupContents.value_color

                                        text: Qt.formatTime(SmartSlice.Cloud.resultTimeRetractions, "hh:mm")
                                    }
                                    Label {
                                        Layout.alignment: Qt.AlignRight
                                        font: smartSlicePopupContents.value_font
                                        color: smartSlicePopupContents.value_color

                                        text: Qt.formatTime(SmartSlice.Cloud.resultTimeSkin, "hh:mm")
                                    }
                                    Label {
                                        Layout.alignment: Qt.AlignRight
                                        font: smartSlicePopupContents.value_font
                                        color: smartSlicePopupContents.value_color

                                        text: Qt.formatTime(SmartSlice.Cloud.resultTimeSkirt, "hh:mm")
                                    }
                                    Label {
                                        Layout.alignment: Qt.AlignRight
                                        font: smartSlicePopupContents.value_font
                                        color: smartSlicePopupContents.value_color

                                        text: Qt.formatTime(SmartSlice.Cloud.resultTimeTravel, "hh:mm")
                                    }
                                    */
                                }

                                ColumnLayout {
                                    width: thirdColumnPopup.width

                                    spacing: UM.Theme.getSize("default_margin").height

                                    Label {
                                        Layout.alignment: Qt.AlignRight
                                        font: smartSlicePopupContents.value_font
                                        color: smartSlicePopupContents.value_color

                                        text: "100 %"
                                    }
                                    /*
                                    Label {
                                        Layout.alignment: Qt.AlignRight
                                        font: smartSlicePopupContents.value_font
                                        color: smartSlicePopupContents.value_color

                                        text: SmartSlice.Cloud.percentageTimeInfill.toFixed(2) + " %"
                                    }
                                    Label {
                                        Layout.alignment: Qt.AlignRight
                                        font: smartSlicePopupContents.value_font
                                        color: smartSlicePopupContents.value_color

                                        text: SmartSlice.Cloud.percentageTimeInnerWalls.toFixed(2) + " %"
                                    }
                                    Label {
                                        Layout.alignment: Qt.AlignRight
                                        font: smartSlicePopupContents.value_font
                                        color: smartSlicePopupContents.value_color

                                        text: SmartSlice.Cloud.percentageTimeOuterWalls.toFixed(2) + " %"
                                    }
                                    Label {
                                        Layout.alignment: Qt.AlignRight
                                        font: smartSlicePopupContents.value_font
                                        color: smartSlicePopupContents.value_color

                                        text: SmartSlice.Cloud.percentageTimeRetractions.toFixed(2) + " %"
                                    }
                                    Label {
                                        Layout.alignment: Qt.AlignRight
                                        font: smartSlicePopupContents.value_font
                                        color: smartSlicePopupContents.value_color

                                        text: SmartSlice.Cloud.percentageTimeSkin.toFixed(2) + " %"
                                    }
                                    Label {
                                        Layout.alignment: Qt.AlignRight
                                        font: smartSlicePopupContents.value_font
                                        color: smartSlicePopupContents.value_color

                                        text: SmartSlice.Cloud.percentageTimeSkirt.toFixed(2) + " %"
                                    }
                                    Label {
                                        Layout.alignment: Qt.AlignRight
                                        font: smartSlicePopupContents.value_font
                                        color: smartSlicePopupContents.value_color

                                        text: SmartSlice.Cloud.percentageTimeTravel.toFixed(2) + " %"
                                    }
                                    */
                                }
                            }

                            /* Material ESTIMATION HEADER */
                            Label {
                                font: smartSlicePopupContents.header_font
                                color: smartSlicePopupContents.header_color

                                text: "MATERIAL ESTIMATION"
                            }

                            RowLayout {
                                spacing: UM.Theme.getSize("default_margin").width

                                Label {
                                    id: labelMaterialName
                                    Layout.fillWidth: true
                                    font: UM.Theme.getFont("default")

                                    text: SmartSlice.Cloud.materialName
                                }

                                // TODO: Hiding material lenght. The radius is zero all the time for some reason,
                                // therefore the value is zero all the time, too.
                                Label {
                                    id: labelMaterialLength
                                    Layout.alignment: Qt.AlignRight
                                    font: smartSlicePopupContents.value_font
                                    color: smartSlicePopupContents.value_color

                                    text: SmartSlice.Cloud.materialLength + " m"
                                }

                                Label {
                                    id: labelMaterialWeight

                                    Layout.alignment: Qt.AlignRight
                                    font: smartSlicePopupContents.value_font
                                    color: smartSlicePopupContents.value_color

                                    text: SmartSlice.Cloud.materialWeight.toFixed(2) + " g"
                                }

                                Label {
                                    id: labelMaterialCost
                                    Layout.alignment: Qt.AlignRight
                                    font: smartSlicePopupContents.value_font
                                    color: smartSlicePopupContents.value_color

                                    text: SmartSlice.Cloud.materialCost.toFixed(2) + " €"
                                }
                            }
                        }


                        background: UM.PointingRectangle
                        {
                            color: UM.Theme.getColor("tool_panel_background")
                            borderColor: UM.Theme.getColor("lining")
                            borderWidth: UM.Theme.getSize("default_lining").width

                            target: Qt.point(width - (smartSliceInfoIcon.width / 2) - UM.Theme.getSize("thin_margin").width,
                                            height + UM.Theme.getSize("default_arrow").height - UM.Theme.getSize("thin_margin").height)

                            arrowSize: UM.Theme.getSize("default_arrow").width
                        }
                    }
                }
                }
            }
            Cura.PrimaryButton {
                id: smartSliceButton

                Layout.fillWidth: SmartSlice.Cloud.sliceButtonFillWidth
                Layout.preferredWidth: UM.Theme.getSize("action_panel_widget").width * 2/3 - UM.Theme.getSize("thick_margin").width

                anchors.right: parent.right
                anchors.bottom: parent.bottom

                text: SmartSlice.Cloud.sliceButtonText

                enabled: SmartSlice.Cloud.sliceButtonEnabled
                visible: SmartSlice.Cloud.sliceButtonVisible

                Connections {
                    target: SmartSlice.Cloud
                    onSliceButtonEnabledChanged: { smartSliceButton.enabled = SmartSlice.Cloud.sliceButtonEnabled }
                    onSliceButtonFillWidthChanged: { smartSliceButton.Layout.fillWidth = SmartSlice.Cloud.sliceButtonFillWidth }
                }

                /*
                    Smart Slice Button Click Event
                */
                onClicked: {
                    //  Show Validation Dialog
                    SmartSlice.Cloud.sliceButtonClicked()
                }
            }
            Cura.SecondaryButton {
                id: smartSliceSecondaryButton

                //width: UM.Theme.getSize("thick_margin").width
                Layout.fillWidth: SmartSlice.Cloud.secondaryButtonFillWidth

                anchors.left: parent.left
                anchors.bottom: parent.bottom

                text: SmartSlice.Cloud.secondaryButtonText
                
                visible: SmartSlice.Cloud.secondaryButtonVisible

                Connections {
                    target: SmartSlice.Cloud
                    onSecondaryButtonVisibleChanged: { smartSliceSecondaryButton.visible = SmartSlice.Cloud.secondaryButtonVisible }
                    onSecondaryButtonFillWidthChanged: { smartSliceSecondaryButton.Layout.fillWidth = SmartSlice.Cloud.secondaryButtonFillWidth }
                }

                /*
                    Smart Slice Button Click Event
                */
                onClicked: {
                    //  Show Validation Dialog
                    SmartSlice.Cloud.secondaryButtonClicked()
                }
            }
        }
    }

}
