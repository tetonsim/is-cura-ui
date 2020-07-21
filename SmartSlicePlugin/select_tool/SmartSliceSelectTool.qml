import QtQuick 2.4
import QtQuick.Controls 1.2
import QtQuick.Layouts 1.1
import QtQuick.Controls.Styles 1.1

import UM 1.2 as UM
import Cura 1.0 as Cura

import SmartSlice 1.0  as SmartSlice

Item {
    id: constraintsTooltip
    //width: childrenRect.width
    width: selectAnchorButton.width * 3 - 2*UM.Theme.getSize("default_margin").width
    //height: childrenRect.height
    //height: selectAnchorButton.height + UM.Theme.getSize("default_margin").width
    height: selectAnchorButton.height + UM.Theme.getSize("default_margin").width + bcListAnchors.height

    UM.I18nCatalog {
        id: catalog;
        name: "smartslice"
    }

    Component.onCompleted: {
        selectAnchorButton.checked = UM.ActiveTool.properties.getValue("AnchorSelectionActive")
        selectLoadButton.checked = UM.ActiveTool.properties.getValue("LoadSelectionActive")
    }

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
        addButtonText: "Add Anchor"
        boundaryConditionType: 0

        anchors.left: selectAnchorButton.left
        anchors.top: selectAnchorButton.bottom
    }

    SmartSlice.BoundaryConditionList {
        id: bcListForces
        visible: selectLoadButton.checked
        addButtonText: "Add Force"
        boundaryConditionType: 1

        anchors.left: selectAnchorButton.left
        anchors.top: selectAnchorButton.bottom

        onSelectionChanged: {
            checkboxLoadDialogFlipDirection.checked = model.loadDirection;
            textLoadDialogMagnitude.text = model.loadMagnitude;
        }
    }

    Rectangle {
        id: applyLoadDialog

        visible: (selectLoadButton.checked) ? true : false

        width: UM.Theme.getSize("action_panel_widget").width/2 + UM.Theme.getSize("default_margin").width
        height: 100 + 2 * UM.Theme.getSize("thick_margin").width

        anchors.bottom: selectAnchorButton.top
        anchors.bottomMargin: UM.Theme.getSize("default_margin").width * 2
        anchors.left: selectAnchorButton.left


        color: UM.Theme.getColor("main_background")
        border.width: UM.Theme.getSize("default_lining").width
        border.color: UM.Theme.getColor("lining")
        radius: UM.Theme.getSize("default_radius").width

        Label {
            id: labelLoadDialogType

            anchors.top: parent.top
            anchors.topMargin: UM.Theme.getSize("default_margin").width
            anchors.left: parent.left
            anchors.leftMargin: UM.Theme.getSize("default_margin").width

            font.bold: true

            text: "Type:"

            ComboBox {
                id: comboLoadDialogType

                width: UM.Theme.getSize("action_panel_widget").width/3

                anchors.top: parent.top
                anchors.left: parent.right
                anchors.leftMargin: UM.Theme.getSize("default_margin").width

                model: ["Push / Pull"]
            }
        }

        CheckBox {
            id: checkboxLoadDialogFlipDirection

            anchors.top: labelLoadDialogType.bottom
            anchors.topMargin: UM.Theme.getSize("default_margin").width
            anchors.left: parent.left
            anchors.leftMargin: UM.Theme.getSize("default_margin").width

            text: "Flip Direction"

            checked: bcListForces.model.loadDirection
            onCheckedChanged: {
                bcListForces.model.loadDirection = checked
			}
        }

        Label {
            id: labelLoadDialogMagnitude

            anchors.top: checkboxLoadDialogFlipDirection.bottom
            anchors.topMargin: UM.Theme.getSize("default_margin").width
            anchors.left: parent.left
            anchors.leftMargin: UM.Theme.getSize("default_margin").width

            font.bold: true

            text: "Magnitude:"
        }

        TextField {
            id: textLoadDialogMagnitude
            style: UM.Theme.styles.text_field;

            anchors.top: labelLoadDialogMagnitude.bottom
            anchors.topMargin: UM.Theme.getSize("default_margin").width
            anchors.left: parent.left
            anchors.leftMargin: UM.Theme.getSize("default_margin").width

            onEditingFinished: {
                bcListForces.model.loadMagnitude = text;
            }

            text: bcListForces.model.loadMagnitude
            property string unit: "[N]";
        }
/*
        Binding {
            target: checkboxLoadDialogFlipDirection
            property: "checked"
            value: UM.ActiveTool.properties.getValue("LoadDirection")
        }

        Binding {
            target: textLoadDialogMagnitude
            property: "text"
            value: UM.ActiveTool.properties.getValue("LoadMagnitude")
        }
*/
    }
}
