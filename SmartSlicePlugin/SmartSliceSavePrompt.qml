import QtQuick 2.7
import QtQuick.Controls 1.1
import QtQuick.Controls.Styles 1.1
import QtQuick.Layouts 1.1
import QtQuick.Dialogs 1.1
import QtQuick.Window 2.2

import UM 1.2 as UM
import Cura 1.1 as Cura
import SmartSlice 1.0 as SmartSlice

UM.Dialog {
    id: saveDialog

    title: "Smart Slice Warning"

    width: screenScaleFactor * 300;
    height: screenScaleFactor * 150;

    minimumWidth: width;
    maximumWidth: width;

    minimumHeight: height;
    maximumHeight: height;

    closeOnAccept: false

    Column {

        UM.I18nCatalog{id: catalog; name: "smartslice"}
        anchors.fill: parent
        anchors.margins: UM.Theme.getSize("default_margin").width

        spacing: UM.Theme.getSize("default_margin").height

        Label {
            id: resultsLabel

            width: parent.width

            Layout.alignment: Qt.AlignLeft

            font: UM.Theme.getFont("default")
            color: UM.Theme.getColor("text")

            text: 'You have unsaved Smart Slice results!'
        }

        Label {
            id: saveLabel

            width: parent.width

            Layout.alignment: Qt.AlignLeft

            font: UM.Theme.getFont("default")
            color: UM.Theme.getColor("text")

            text: 'Would you like to save your results?'
        }
    }

    Item {
        id: buttonRow

        width: parent.width

        anchors {
            bottom: parent.bottom
            right: parent.right
            left: parent.left
            rightMargin: UM.Theme.getSize("default_margin").width
            leftMargin: UM.Theme.getSize("default_margin").width
        }

        Row {
            id: buttons

            anchors {
                bottom: parent.bottom
                right: parent.right
            }

            spacing: UM.Theme.getSize("default_margin").width

            Button {
                text: catalog.i18nc("@action:button", "Don't Save")
                onClicked: {
                    SmartSlice.Cloud.closeSavePromptClicked()
                }
            }

            Button {
                text: catalog.i18nc("@action:button", "Save")
                onClicked: {
                    SmartSlice.Cloud.savePromptClicked()
                }
            }
        }
    }
}


