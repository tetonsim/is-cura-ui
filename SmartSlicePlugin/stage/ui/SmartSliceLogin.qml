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
        id: loginItem

        width: 0.2 * smartSliceMain.width
        height: childrenRect.height

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
                        width: contentColumn.width - 2 * UM.Theme.getSize("default_margin").width;
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
                            textColor: UM.Theme.getColor("setting_control_text")
                            placeholderTextColor: UM.Theme.getColor("text_inactive")
                            font: UM.Theme.getFont("default")

                            background: Rectangle {
                                implicitHeight: control.height;
                                implicitWidth: control.width;

                                border.width: UM.Theme.getSize("default_lining").width;
                                border.color: control.hovered ? UM.Theme.getColor("setting_control_border_highlight") : UM.Theme.getColor("setting_control_border");
                                radius: UM.Theme.getSize("setting_control_radius").width

                                color: UM.Theme.getColor("setting_validation_ok");

                                Label {
                                    anchors.right: parent.right;
                                    anchors.rightMargin: UM.Theme.getSize("setting_unit_margin").width;
                                    anchors.verticalCenter: parent.verticalCenter;

                                    text: control.unit ? control.unit : ""
                                    color: UM.Theme.getColor("setting_unit");
                                    font: UM.Theme.getFont("default");
                                    renderType: Text.NativeRendering
                                }
                            }
                        }

                        font: UM.Theme.getFont("default")
                        text: SmartSlice.API.loginUsername

                        onTextChanged: {
                            SmartSlice.API.loginUsername = text
                        }

                        onAccepted: password_input.forceActiveFocus()
                        placeholderText: catalog.i18nc("@label", "email")
                        KeyNavigation.tab: password_input
                    }

                    TextField {
                        id: password_input

                        width: parent.width

                        validator: RegExpValidator { regExp: /.+/ }

                        style: TextFieldStyle {
                            textColor: UM.Theme.getColor("setting_control_text")
                            placeholderTextColor: UM.Theme.getColor("text_inactive")
                            font: UM.Theme.getFont("default")

                            background: Rectangle {
                                implicitHeight: control.height;
                                implicitWidth: control.width;

                                border.width: UM.Theme.getSize("default_lining").width;
                                border.color: control.hovered ? UM.Theme.getColor("setting_control_border_highlight") : UM.Theme.getColor("setting_control_border");
                                radius: UM.Theme.getSize("setting_control_radius").width

                                color: UM.Theme.getColor("setting_validation_ok");

                                Label {
                                    anchors.right: parent.right;
                                    anchors.rightMargin: UM.Theme.getSize("setting_unit_margin").width;
                                    anchors.verticalCenter: parent.verticalCenter;

                                    text: control.unit ? control.unit : ""
                                    color: UM.Theme.getColor("setting_unit");
                                    font: UM.Theme.getFont("default");
                                    renderType: Text.NativeRendering
                                }
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
                            SmartSlice.API.onLoginButtonClicked()
                        }

                        KeyNavigation.tab: username_input
                    }
                }
            }
        }
    }
}