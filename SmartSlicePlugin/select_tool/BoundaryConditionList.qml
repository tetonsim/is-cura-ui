import QtQuick 2.4
import QtQuick.Controls 1.2
import QtQuick.Layouts 1.1
import QtQuick.Controls.Styles 1.1

import UM 1.4 as UM
import Cura 1.1 as Cura

import SmartSlice 1.0 as SmartSlice

Column {
    id: mainColumn

    property int maximumHeight: 140
    property string addButtonText: "Add"
    property int boundaryConditionType: 0
    property SmartSlice.BoundaryConditionListModel model: bcListModel

    signal selectionChanged(int index)

    width: constraintsTooltip.width
    height: maximumHeight

    anchors.topMargin: UM.Theme.getSize("default_margin").width

    onVisibleChanged: {
        if (visible) {
            bcListModel.activate();

        } else {
            bcListModel.deactivate();
        }
    }

    ScrollView {
        height: parent.height - addButton.height - UM.Theme.getSize("default_margin").width
        width: parent.width
        style: UM.Theme.styles.scrollview

        ListView {
            id: bcListView
            spacing: UM.Theme.getSize("default_lining").height
            height: parent.height

            model: SmartSlice.BoundaryConditionListModel {
                id: bcListModel
                boundaryConditionType: mainColumn.boundaryConditionType
            }

            onCurrentItemChanged: {
                if (mainColumn.visible) {
                    bcListModel.select(currentIndex);
                    mainColumn.selectionChanged(currentIndex);
                }
            }

            delegate: Rectangle {
                width: mainColumn.width - 15
                height: 20

                Rectangle {
                    width: parent.width - 1.5 * Math.round(UM.Theme.getSize("setting").height / 2)
                    height: parent.height
                    anchors.left: parent.left
                    border.width: bcListView.currentIndex == index ? 1 : 0
                    border.color: UM.Theme.getColor("secondary_button_text")

                    Text {
                        width: parent.width - 10
                        height: parent.height
                        anchors.left: parent.left;
                        anchors.leftMargin: UM.Theme.getSize("default_margin").width;

                        text: model.name
                        color: bcListView.currentIndex == index ?
                            UM.Theme.getColor("secondary_button_text") : UM.Theme.getColor("text")

                        MouseArea {
                            anchors.fill: parent
                            onClicked: {
                                bcListModel.select(index)
                                bcListView.currentIndex = index
                                mainColumn.selectionChanged(index)
                            }
                        }
                    }
                }
                Button {
                    width: Math.round(UM.Theme.getSize("setting").height / 2)
                    height: UM.Theme.getSize("setting").height
                    anchors.right: parent.right
                    visible : index ? true: false

                    onClicked: {
                        bcListModel.remove(index)
                        mainColumn.selectionChanged(bcListView.currentIndex)
                    }
                    style: ButtonStyle {
                        background: Item {
                            UM.RecolorImage {
                                anchors.verticalCenter: parent.verticalCenter
                                width: parent.width
                                height: width
                                sourceSize.height: width
                                color: control.hovered ? UM.Theme.getColor("setting_control_button_hover") : UM.Theme.getColor("setting_control_button")
                                source: UM.Theme.getIcon("minus")
                            }
                        }
                    }
                }
            }
        }
    }

    Cura.SecondaryButton {
        id: addButton;

        text: catalog.i18nc("@action:button", mainColumn.addButtonText);

        onClicked:
        {
            bcListModel.add()
            bcListView.currentIndex = bcListView.count - 1
            bcListModel.select(bcListView.currentIndex)
            mainColumn.selectionChanged(bcListView.currentIndex)
        }
    }
}
