import QtQuick 2.4
import QtQuick.Controls 1.2
import QtQuick.Layouts 1.1
import QtQuick.Controls.Styles 1.4

import UM 1.2 as UM
import Cura 1.0 as Cura

import SmartSlice 1.0  as SmartSlice

Item {
    id: constraintsTooltip
    width: selectAnchorButton.width * 3 - 2*UM.Theme.getSize("default_margin").width
    height: {
        if (selectAnchorButton.checked) {
            return selectAnchorButton.height + UM.Theme.getSize("default_margin").width + bcListAnchors.height
        }
        if (selectLoadButton.checked) {
            return selectLoadButton.height + UM.Theme.getSize("default_margin").width + bcListForces.height
        }
    }

    UM.I18nCatalog {
        id: catalog;
        name: "smartslice"
    }

    Component.onCompleted: {
        selectAnchorButton.checked = UM.ActiveTool.properties.getValue("AnchorSelectionActive")
        selectLoadButton.checked = UM.ActiveTool.properties.getValue("LoadSelectionActive")
    }

    MouseArea {

        propagateComposedEvents: false
        anchors.fill: parent

        Button
        {
            id: selectAnchorButton

            anchors.left: parent.left
            z: 2

            text: catalog.i18nc("@action:button", "Anchor (Mount)")
            iconSource: "./anchor_icon.svg"
            property bool needBorder: true

            style: UM.Theme.styles.tool_button;

            onClicked: {
                UM.ActiveTool.triggerAction("setAnchorSelection");
                selectAnchorButton.checked = true;
                selectLoadButton.checked = false;
                bcListForces.model.loadMagnitude = textLoadDialogMagnitude.text;
            }
        }

        Button {
            id: selectLoadButton
            anchors.left: selectAnchorButton.right;
            anchors.leftMargin: UM.Theme.getSize("default_margin").width;
            z: 1

            text: catalog.i18nc("@action:button", "Load (Directed force)")
            iconSource: "./load_icon.svg"
            property bool needBorder: true

            style: UM.Theme.styles.tool_button;

            onClicked: {
                UM.ActiveTool.triggerAction("setLoadSelection");
                selectAnchorButton.checked = false;
                selectLoadButton.checked = true;
            }
        }

        SmartSlice.BoundaryConditionList {
            id: bcListAnchors
            visible: selectAnchorButton.checked
            boundaryConditionType: 0

            anchors.left: selectAnchorButton.left
            anchors.top: selectAnchorButton.bottom
        }

        SmartSlice.BoundaryConditionList {
            id: bcListForces
            visible: selectLoadButton.checked
            boundaryConditionType: 1

            anchors.left: selectAnchorButton.left
            anchors.top: selectAnchorButton.bottom

            onSelectionChanged: {
                checkboxLoadDialogFlipDirection.checked = model.loadDirection;
                textLoadDialogMagnitude.text = model.loadMagnitude;
            }
        }
    }

    Item {
        id: applyLoadDialog

        visible: (selectLoadButton.checked) ? true : false

        width: UM.Theme.getSize("action_panel_widget").width / 2 + 2 * UM.Theme.getSize("default_margin").width
        height: childrenRect.height

        property var handler: SmartSlice.Cloud.loadDialog

        property int xStart: constraintsTooltip.x + selectAnchorButton.width
        property int yStart: constraintsTooltip.y - 15 * UM.Theme.getSize("default_margin").height

        property bool positionSet: handler.positionSet
        property int xPosition: handler.xPosition
        property int yPosition: handler.yPosition

        x: {
            if (handler.positionSet) {
                return xPosition
            }
            return xStart
        }

        y: {
            if (handler.positionSet) {
                return yPosition
            }
            return yStart
        }

        z: 3 //-> A hack to get this on the top

        function trySetPosition(posNewX, posNewY)
        {
            var margin = UM.Theme.getSize("narrow_margin");
            var minPt = base.mapFromItem(null, margin.width, margin.height);
            var maxPt = base.mapFromItem(null,
                CuraApplication.appWidth() - (2 * applyLoadDialog.width),
                CuraApplication.appHeight() - (2 * applyLoadDialog.height)
            );
            var initialY = minPt.y + 100 * screenScaleFactor
            var finalY = maxPt.y - 200 * screenScaleFactor

            applyLoadDialog.x = Math.max(minPt.x, Math.min(maxPt.x, posNewX));
            applyLoadDialog.y = Math.max(initialY, Math.min(finalY, posNewY));

            applyLoadDialog.handler.setPosition(applyLoadDialog.x, applyLoadDialog.y)
        }

        Column {
            id: loadColumn

            anchors.fill: parent

            MouseArea {
                cursorShape: Qt.SizeAllCursor

                height: topDragArea.height
                width: parent.width

                property var clickPos: Qt.point(0, 0)
                property bool dragging: false
                // property int absoluteMinimumHeight: 200 * screenScaleFactor

                onPressed: {
                    clickPos = Qt.point(mouse.x, mouse.y);
                    dragging = true
                }
                onPositionChanged: {
                    if(dragging) {
                        var delta = Qt.point(mouse.x - clickPos.x, mouse.y - clickPos.y);
                        if (delta.x !== 0 || delta.y !== 0) {
                            applyLoadDialog.trySetPosition(applyLoadDialog.x + delta.x, applyLoadDialog.y + delta.y);
                        }
                    }
                }
                onReleased: {
                    dragging = false
                }
                onDoubleClicked: {
                    dragging = false
                    applyLoadDialog.x = applyLoadDialog.xStart
                    applyLoadDialog.y = applyLoadDialog.yStart
                    applyLoadDialog.handler.setPosition(applyLoadDialog.x, applyLoadDialog.y)
                }

                Rectangle {
                    id: topDragArea
                    width: parent.width
                    height: UM.Theme.getSize("narrow_margin").height
                    color: "transparent"
                }
            }

            Rectangle {

                color: UM.Theme.getColor("main_background")
                border.width: UM.Theme.getSize("default_lining").width
                border.color: UM.Theme.getColor("lining")
                radius: UM.Theme.getSize("default_radius").width

                height: contentColumn.height
                width: parent.width

                Column {
                    id: contentColumn

                    width: parent.width
                    height: childrenRect.height + 2 * UM.Theme.getSize("default_margin").width

                    anchors.top: parent.top

                    anchors.topMargin: UM.Theme.getSize("default_margin").width
                    anchors.bottomMargin: UM.Theme.getSize("default_margin").width

                    spacing: UM.Theme.getSize("default_margin").width

                    Row {
                        anchors.left: parent.left
                        anchors.topMargin: UM.Theme.getSize("default_margin").width
                        anchors.leftMargin: UM.Theme.getSize("default_margin").width

                        width: childrenRect.width
                        height: childrenRect.height

                        spacing: UM.Theme.getSize("default_margin").width

                        Label {
                            id: labelLoadDialogType

                            height: parent.height
                            verticalAlignment: Text.AlignVCenter

                            font.bold: true

                            text: "Type:"
                        }

                        ComboBox {
                            id: comboLoadDialogType

                            style: UM.Theme.styles.combobox

                            width: UM.Theme.getSize("action_panel_widget").width / 3
                            anchors.verticalCenter: parent.verticalCenter

                            model: ["Push / Pull"]
                        }
                    }

                    CheckBox {
                        id: checkboxLoadDialogFlipDirection

                        anchors.left: parent.left
                        anchors.leftMargin: 2 * UM.Theme.getSize("default_margin").width

                        text: "Flip Direction"

                        checked: bcListForces.model.loadDirection
                        onCheckedChanged: {
                            bcListForces.model.loadDirection = checked
                        }
                    }

                    Label {
                        id: labelLoadDialogMagnitude

                        anchors.left: parent.left
                        anchors.leftMargin: UM.Theme.getSize("default_margin").width

                        font.bold: true

                        text: "Magnitude:"
                    }

                    TextField {
                        id: textLoadDialogMagnitude
                        style: UM.Theme.styles.text_field

                        anchors.left: parent.left
                        anchors.leftMargin: 2 * UM.Theme.getSize("default_margin").width

                        onEditingFinished: {
                            bcListForces.model.loadMagnitude = text;
                        }

                        validator: DoubleValidator {bottom: 0.0}
                        inputMethodHints: Qt.ImhFormattedNumbersOnly

                        text: bcListForces.model.loadMagnitude
                        property string unit: "[N]";
                    }
                }
            }
        }
    }
}
