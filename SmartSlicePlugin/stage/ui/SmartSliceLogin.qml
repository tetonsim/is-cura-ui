import QtQuick 2.7
import QtQuick.Controls 1.4
import QtQuick.Layouts 1.3
import QtQuick.Controls.Styles 1.1

import Cura 1.0 as Cura
import UM 1.2 as UM
import SmartSlice 1.0 as SmartSlice

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
            SmartSlice.API.onLoginButtonClicked()
        }
    }

    Keys.onReturnPressed: {
        if (username_input.acceptableInput && password_input.acceptableInput) {
            SmartSlice.API.onLoginButtonClicked()
        }
    }

    Item {
        width: 0.2 * smartSliceMain.width
        height: 0.4 * smartSliceMain.height

        x: (0.5 * smartSliceMain.width) - (loginContainer.width * 0.5)
        y: (0.5 * smartSliceMain.height) - (loginContainer.height * 0.5)

        states: [
            State {
                name: "notLoggedIn"
                when: SmartSlice.API.logged_in == false

                PropertyChanges { target: loginDialog; visible: true }
            },
            State {
                name: "loggedIn"
                when: SmartSlice.API.logged_in == true

                PropertyChanges { target: loginDialog; visible: false }
                PropertyChanges { target: password_input; text: "" }
            }
        ]

        Rectangle {
            id: loginContainer

            color: UM.Theme.getColor("main_background")
            height: logoAndFields.height + hyperLinkTexts.height + buttonContainer.height + 22
            width: 356
            radius: 2
            anchors.bottomMargin: 4

            border.color: "light gray"

            ColumnLayout {
                id: contentColumn
                UM.I18nCatalog{id: catalog; name: "smartslice"}
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.verticalCenter: parent.verticalCenter
                height: parent.height * 0.90
                width: parent.width * 0.62

                spacing: 15

                Column {
                    id: logoAndFields

                    Layout.alignment: Qt.AlignCenter
                    anchors.topMargin: 0
                    anchors.bottomMargin: 0
                    anchors.horizontalCenter: parent.horizontalCenter

                    Layout.fillWidth: true

                    spacing: 10

                    Image {
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: contentColumn.width - 15;
                        fillMode: Image.PreserveAspectFit
                        source: "../images/only_symbol_logo.png"
                        mipmap: true
                    }

                    Text {
                        id: statusText

                        anchors.horizontalCenter: parent.horizontalCenter

                        height: 15

                        font: UM.Theme.getFont("default")
                        renderType: Text.NativeRendering
                        color: "red"

                        text: " "
                        visible: true

                        states: [
                            State {
                                name: "noStatus"
                                when: SmartSlice.API.badCredentials == false

                                PropertyChanges { target: statusText; text: " "}
                            },
                            State {
                                name: "badCredentials"
                                when: SmartSlice.API.badCredentials == true

                                PropertyChanges { target: statusText; text: "Invalid email or password" }
                                PropertyChanges { target: password_input; text: "" }
                            }
                        ]
                    }

                    TextField {
                        id: username_input

                        width: parent.width

                        validator: RegExpValidator { regExp: /^([a-zA-Z0-9_\-\.]+)@([a-zA-Z0-9_\-\.]+)\.([a-zA-Z]{2,5})$/ }

                        style: TextFieldStyle {
                            renderType: Text.NativeRendering
                            background: Rectangle {
                                implicitHeight: 30
                                border.color: "light gray"
                                border.width: 1
                                radius: 3
                            }
                        }

                        font: UM.Theme.getFont("default")
                        text: SmartSlice.API.loginUsername

                        onTextChanged: {
                            SmartSlice.API.loginUsername = text
                        }

                        onAccepted: password_input.forceActiveFocus()
                        placeholderText: catalog.i18nc("@label", "Email")
                        KeyNavigation.tab: password_input
                    }

                    TextField {
                        id: password_input

                        width: parent.width

                        validator: RegExpValidator { regExp: /.+/ }

                        style: TextFieldStyle {
                            renderType: Text.NativeRendering
                            background: Rectangle {
                                implicitHeight: 30
                                border.color: "light gray"
                                border.width: 1
                                radius: 3
                            }
                        }

                        font: UM.Theme.getFont("default")
                        text: SmartSlice.API.loginPassword

                        onTextChanged: {
                            SmartSlice.API.loginPassword = text
                            if (text != "") {
                                SmartSlice.API.badCredentials = false;
                            }
                        }

                        placeholderText: catalog.i18nc("@label", "Password")
                        echoMode: TextInput.Password
                        KeyNavigation.tab: login_button
                    }

                    Column {
                        id: hyperLinkTexts

                        Layout.alignment: Qt.AlignCenter

                        width: parent.width

                        spacing: 10

                        Text {
                            id: forgotPasswordText

                            anchors.horizontalCenter: parent.horizontalCenter

                            font.underline: false
                            color: "#266faa"
                            text: "Forgot password?"
                            renderType: Text.NativeRendering

                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: Qt.openUrlExternally(SmartSlice.API.smartSliceUrl + '/static/account.html#forgot-password')
                            }
                        }

                        Text {
                            id: noAccountText

                            anchors.horizontalCenter: parent.horizontalCenter

                            font.underline: true
                            color: "#266faa"
                            text: "<b>Don't have an account?</b>"
                            renderType: Text.NativeRendering

                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: Qt.openUrlExternally(SmartSlice.API.smartSliceUrl + '/static/account.html')
                            }
                        }
                    }
                }

                Column {
                    id: buttonContainer

                    Layout.alignment: Qt.AlignCenter

                    Button
                    {
                        id: login_button

                        Layout.alignment: Qt.AlignCenter

                        text: catalog.i18nc("@action:button", "<font color='#ffffff'>Login</font>")
                        enabled: username_input.acceptableInput && password_input.acceptableInput

                        anchors.topMargin: 10

                        style: ButtonStyle {
                            background: Rectangle {
                                implicitWidth: 150
                                implicitHeight: 30
                                color: login_button.enabled ? "#0066ff" : "#f0f0f0"
                                radius: 2
                            }
                        }

                        onClicked:
                        {
                            SmartSlice.API.onLoginButtonClicked()
                        }

                        KeyNavigation.tab: username_input
                    }
                }
            }
        }
    }
}