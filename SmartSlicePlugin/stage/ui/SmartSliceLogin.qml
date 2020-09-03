import QtQuick 2.10
import QtQuick.Controls 2.2
import QtQuick.Layouts 1.3
import QtQuick.Controls.Styles 1.4

import Cura 1.0 as Cura
import UM 1.2 as UM

MouseArea {
    id: loginDialog

    visible: true

    width: smartSliceMain.width
    height: smartSliceMain.height

    acceptedButtons: Qt.AllButtons
    hoverEnabled: true
    preventStealing: true
    scrollGestureEnabled: false

    onClicked: {}
    onWheel: {}

    Keys.onEnterPressed: {
        if (username_input.acceptableInput && password_input.acceptableInput) {
            smartSliceMain.api.onLoginButtonClicked()
        }
    }

    Keys.onReturnPressed: {
        if (username_input.acceptableInput && password_input.acceptableInput) {
            smartSliceMain.api.onLoginButtonClicked()
        }
    }

    Item {
        id: loginItem

        property int minimumWidth: 350
        property int computedWidth: 0.2 * smartSliceMain.width

        width: computedWidth >= minimumWidth ? computedWidth : minimumWidth
        height: childrenRect.height

        x: (0.5 * smartSliceMain.width) - (loginContainer.width * 0.5)
        y: (0.5 * smartSliceMain.height) - (loginContainer.height * 0.5)

        states: [
            State {
                name: "notLoggedIn"
                when: smartSliceMain.api.logged_in == false

                PropertyChanges { target: loginDialog; visible: true }
            },
            State {
                name: "loggedIn"
                when: smartSliceMain.api.logged_in == true

                PropertyChanges { target: loginDialog; visible: false }
                PropertyChanges { target: password_input; text: "" }
            }
        ]

        Rectangle {
            id: loginContainer

            color: UM.Theme.getColor("main_background")
            height: logoAndFields.height + hyperLinkTexts.height + buttonContainer.height + 2 * UM.Theme.getSize("thick_margin").height
            width: parent.width
            radius: 2
            anchors.bottomMargin: UM.Theme.getSize("default_margin").height

            border.width: UM.Theme.getSize("default_lining").width
            border.color: UM.Theme.getColor("lining")

            ColumnLayout {
                id: contentColumn
                UM.I18nCatalog{id: catalog; name: "smartslice"}
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.verticalCenter: parent.verticalCenter
                height: parent.height * 0.90
                width: parent.width * 0.62

                spacing: UM.Theme.getSize("thick_margin").height

                Column {
                    id: logoAndFields

                    Layout.alignment: Qt.AlignCenter
                    anchors.topMargin: 0
                    anchors.bottomMargin: 0
                    anchors.horizontalCenter: parent.horizontalCenter

                    Layout.fillWidth: true

                    spacing: UM.Theme.getSize("default_margin").height

                    Image {
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: contentColumn.width - 2 * UM.Theme.getSize("default_margin").width
                        fillMode: Image.PreserveAspectFit
                        source: "../images/only_symbol_logo.png"
                        mipmap: true
                    }

                    Text {
                        id: statusText

                        anchors.horizontalCenter: parent.horizontalCenter

                        height: UM.Theme.getSize("thick_margin").height

                        font: UM.Theme.getFont("default")
                        renderType: Text.NativeRendering
                        color: "red"

                        text: " "
                        visible: true

                        states: [
                            State {
                                name: "noStatus"
                                when: smartSliceMain.api.badCredentials == false

                                PropertyChanges { target: statusText; text: " "}
                            },
                            State {
                                name: "badCredentials"
                                when: smartSliceMain.api.badCredentials == true

                                PropertyChanges { target: statusText; text: "Invalid email or password" }
                                PropertyChanges { target: password_input; text: "" }
                            }
                        ]
                    }

                    TextField {
                        id: username_input

                        width: parent.width

                        validator: RegExpValidator { regExp: /^([a-zA-Z0-9_\-\.]+)@([a-zA-Z0-9_\-\.]+)\.([a-zA-Z]{2,5})$/ }

                        background: Rectangle {
                            anchors.fill: parent

                            border.width: UM.Theme.getSize("default_lining").width
                            border.color: username_input.hovered ? UM.Theme.getColor("setting_control_border_highlight") : UM.Theme.getColor("setting_control_border")
                            radius: UM.Theme.getSize("setting_control_radius").width

                            color: UM.Theme.getColor("setting_validation_ok")

                        }

                        color: UM.Theme.getColor("setting_control_text")
                        font: UM.Theme.getFont("default")

                        text: smartSliceMain.api.loginUsername

                        onTextChanged: {
                            smartSliceMain.api.loginUsername = text
                        }

                        onAccepted: password_input.forceActiveFocus()
                        placeholderText: catalog.i18nc("@label", "email")
                        KeyNavigation.tab: password_input
                    }

                    TextField {
                        id: password_input

                        width: parent.width

                        validator: RegExpValidator { regExp: /.+/ }

                        background: Rectangle {
                            anchors.fill: parent

                            border.width: UM.Theme.getSize("default_lining").width
                            border.color: password_input.hovered ? UM.Theme.getColor("setting_control_border_highlight") : UM.Theme.getColor("setting_control_border")
                            radius: UM.Theme.getSize("setting_control_radius").width

                            color: UM.Theme.getColor("setting_validation_ok")

                        }

                        color: UM.Theme.getColor("setting_control_text")
                        font: UM.Theme.getFont("default")

                        text: smartSliceMain.api.loginPassword

                        onTextChanged: {
                            smartSliceMain.api.loginPassword = text
                            if (text != "") {
                                smartSliceMain.api.badCredentials = false;
                            }
                        }

                        placeholderText: catalog.i18nc("@label", "password")
                        echoMode: TextInput.Password
                        KeyNavigation.tab: login_button
                    }

                    Column {
                        id: hyperLinkTexts

                        Layout.alignment: Qt.AlignCenter

                        width: parent.width

                        spacing: UM.Theme.getSize("default_margin").height

                        Text {
                            id: forgotPasswordText

                            anchors.horizontalCenter: parent.horizontalCenter

                            font: UM.Theme.getFont("default")

                            color: "#266faa"
                            text: "Forgot password?"

                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: Qt.openUrlExternally('https://www.tetonsim.com/forgot-password')
                            }
                        }

                        Text {
                            id: noAccountText

                            anchors.horizontalCenter: parent.horizontalCenter

                            font: UM.Theme.getFont("medium_bold")

                            color: "#266faa"
                            text: "Don't have an account?"

                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: Qt.openUrlExternally('https://www.tetonsim.com/trial-registration')
                            }
                        }
                    }
                }

                Column {
                    id: buttonContainer

                    Layout.alignment: Qt.AlignCenter
                    width: parent.width
                    height: childrenRect.height

                    Cura.PrimaryButton {
                        id: login_button

                        height: UM.Theme.getSize("action_button").height
                        width: loginContainer.width * 0.4
                        fixedWidthMode: true

                        enabled: username_input.acceptableInput && password_input.acceptableInput

                        anchors {
                            topMargin: UM.Theme.getSize("thick_margin").height
                            bottomMargin: UM.Theme.getSize("thick_margin").height
                        }

                        text: catalog.i18nc("@action:button", "Login")
                        textDisabledColor: textColor

                        onClicked: {
                            smartSliceMain.api.onLoginButtonClicked()
                        }

                        KeyNavigation.tab: username_input
                    }
                }
            }
        }
    }
}