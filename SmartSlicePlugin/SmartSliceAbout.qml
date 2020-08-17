import QtQuick 2.7
import QtQuick.Controls 1.1
import QtQuick.Controls.Styles 1.1
import QtQuick.Layouts 1.1
import QtQuick.Dialogs 1.1
import QtQuick.Window 2.2

import UM 1.2 as UM

UM.Dialog {
    id: aboutDialog
    title: "Smart Slice by Teton Simulation"

    width: Math.floor(screenScaleFactor * 450)
    minimumWidth: width
    maximumWidth: width

    height: Math.floor(screenScaleFactor * 500)
    // height: mainColumn.height + closeButton.height + 4 * UM.Theme.getSize("thick_margin").height
    minimumHeight: height
    maximumHeight: height

    Column {
        id: mainColumn
        UM.I18nCatalog{id: catalog; name: "smartslice"}

        height: childrenRect.height
        width: parent.width

        spacing: UM.Theme.getSize("default_margin").height

        Image {
            // height: Math.floor(screenScaleFactor * 250)
            height: aboutDialog.height - textColumn.height - closeButton.height - 6 * UM.Theme.getSize("default_margin").width
            anchors.horizontalCenter: parent.horizontalCenter

            fillMode: Image.PreserveAspectFit
            source: "images/logo_vertical.png"
            mipmap: true
        }

        Column {
            id: textColumn

            width: parent.width
            height: childrenRect.height

            spacing: UM.Theme.getSize("default_margin").height

            Text {
                anchors.horizontalCenter: parent.horizontalCenter

                horizontalAlignment: Text.AlignHCenter

                font.underline: true
                color: '#0000ff'
                text: 'Teton Simulation'
                renderType: Text.NativeRendering
                onLinkActivated: Qt.openUrlExternally(link)

                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: Qt.openUrlExternally('https://tetonsim.com')
                }
            }

            Text {
                id: statusText

                anchors.horizontalCenter: parent.horizontalCenter

                horizontalAlignment: Text.AlignHCenter

                font: UM.Theme.getFont("default")
                color: UM.Theme.getColor("text")

                text: aboutText
                renderType: Text.NativeRendering
            }

            Column {

                height: childrenRect.height
                width: parent.width

                leftPadding: UM.Theme.getSize("thick_margin").height
                topPadding: UM.Theme.getSize("thick_margin").height

                spacing: UM.Theme.getSize("default_margin").height

                Text {

                    horizontalAlignment: Text.AlignLeft

                    anchors.leftMargin: UM.Theme.getSize("thick_margin").width

                    font.underline: true
                    color: '#0000ff'
                    text: 'End User License Agreement (EULA)'
                    renderType: Text.NativeRendering
                    onLinkActivated: Qt.openUrlExternally(link)

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: Qt.openUrlExternally('https://help.tetonsim.com/eula-end-user-license-agreement')
                    }
                }

                Text {

                    horizontalAlignment: Text.AlignLeft

                    font.underline: true
                    color: '#0000ff'
                    text: 'Privacy Policy'
                    renderType: Text.NativeRendering
                    onLinkActivated: Qt.openUrlExternally(link)

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: Qt.openUrlExternally('https://help.tetonsim.com/privacy-policy')
                    }
                }

                Text {

                    horizontalAlignment: Text.AlignLeft

                    font.underline: true
                    color: '#0000ff'
                    text: 'System Requirements'
                    renderType: Text.NativeRendering
                    onLinkActivated: Qt.openUrlExternally(link)

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: Qt.openUrlExternally('https://help.tetonsim.com/system-requirements')
                    }
                }

                Text {

                    horizontalAlignment: Text.AlignLeft

                    font.underline: true
                    color: '#0000ff'
                    text: 'Open Source Licenses'
                    renderType: Text.NativeRendering
                    onLinkActivated: Qt.openUrlExternally(link)

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: Qt.openUrlExternally('https://help.tetonsim.com/open-source-licenses')
                    }
                }
            }
        }
    }

    Button {
        id: closeButton

        anchors.bottom: parent.bottom
        anchors.right: parent.right
        anchors.rightMargin: UM.Theme.getSize("thick_margin").height

        text: catalog.i18nc("@action:button", "Close")
        onClicked: aboutDialog.close()
    }
}
