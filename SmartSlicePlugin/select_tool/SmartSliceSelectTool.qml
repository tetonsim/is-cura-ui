import QtQuick 2.4
import QtQuick.Controls 1.2
import QtQuick.Controls 2.0 as QTC
import QtQuick.Layouts 1.1
import QtQuick.Controls.Styles 1.4

import UM 1.2 as UM
import Cura 1.0 as Cura

import SmartSlice 1.0  as SmartSlice

Item {
    id: constraintsTooltip
    width: selectAnchorButton.width * 3 - 2 * UM.Theme.getSize("default_margin").width
    height: {
        if (selectAnchorButton.checked) {
            return selectAnchorButton.height + UM.Theme.getSize("default_margin").width + bcListAnchors.height
        }
        if (selectLoadButton.checked) {
            return selectLoadButton.height + UM.Theme.getSize("default_margin").width + bcListForces.height
        }
    }

    property var loadHelperData: {
        "maxValue": 1500,
        "stepSize": 300,
        "textLoadDialogConverter": [0, 150, 250, 500, 1500],
        "textLoadMultiplier": [2.4, 2.4, 1.2, .6],
        "textLoadOffset": [0, 0, 300, 600],
        "loadStepFunction": [0, 300, 600, 900, 1200, 1500],
        "loadStepDivision": [1, 2.4, 2.4, 1.8, 1.2, 1],
        "imageLocation": ["media/Toddler.png", "media/Child.png", "media/Teenager.png", "media/Adult.png"],
        "imageType": ["<b>Toddler</b>", "<b>Young Child</b>", "<b>Teenager</b>", "<b>Adult</b>"],
        "loadHelperEquivalentValue": ["125 N (~30 lbs)", "250 N (~60 lbs)", "500 N (~110 lbs)", "1000 N (~225 lbs)"]
    }

    UM.I18nCatalog {
        id: catalog;
        name: "smartslice"
    }

    Component.onCompleted: {
        selectAnchorButton.checked = UM.ActiveTool.properties.getValue("AnchorSelectionActive");
        selectLoadButton.checked = UM.ActiveTool.properties.getValue("LoadSelectionActive");
        faceDialog.comboboxElements();
        loadColumn.iconsEnabled();
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
            iconSource: "./media/anchor_icon.svg"
            property bool needBorder: true

            style: UM.Theme.styles.tool_button;

            onClicked: {
                UM.ActiveTool.triggerAction("setAnchorSelection");
                selectAnchorButton.checked = true;
                selectLoadButton.checked = false;
                faceDialog.comboboxElements();
                bcListForces.model.loadMagnitude = textLoadDialogMagnitude.text;
                loadColumn.iconsEnabled();
            }
        }

        Button {
            id: selectLoadButton
            anchors.left: selectAnchorButton.right;
            anchors.leftMargin: UM.Theme.getSize("default_margin").width;
            z: 1

            text: catalog.i18nc("@action:button", "Load (Directed force)")
            iconSource: "./media/load_icon.svg"
            property bool needBorder: true

            style: UM.Theme.styles.tool_button;

            onClicked: {
                UM.ActiveTool.triggerAction("setLoadSelection");
                selectAnchorButton.checked = false;
                selectLoadButton.checked = true;
                faceDialog.comboboxElements();
                loadColumn.iconsEnabled();
            }
        }

        SmartSlice.BoundaryConditionList {
            id: bcListAnchors
            visible: selectAnchorButton.checked
            boundaryConditionType: 0

            anchors.left: selectAnchorButton.left
            anchors.top: selectAnchorButton.bottom

            onSelectionChanged: {
                loadColumn.iconsEnabled();
            }
        }

        SmartSlice.BoundaryConditionList {
            id: bcListForces
            visible: selectLoadButton.checked
            boundaryConditionType: 1

            anchors.left: selectAnchorButton.left
            anchors.top: selectAnchorButton.bottom

            onSelectionChanged: {
                textLoadDialogMagnitude.text = model.loadMagnitude;
                loadColumn.iconsEnabled();
            }
        }
    }

    Item {
        id: faceDialog

        visible: true

        width: UM.Theme.getSize("action_panel_widget").width / 2 + 3 * UM.Theme.getSize("default_margin").width
        height: childrenRect.height

        property var handler: UM.Controller.activeStage.proxy.loadDialog

        property int xStart: constraintsTooltip.x + constraintsTooltip.width + 2 * UM.Theme.getSize("default_margin").width
        property int yStart: constraintsTooltip.y - 1.5 * UM.Theme.getSize("default_margin").height

        property bool positionSet: handler.positionSet
        property int xPosition: handler.xPosition
        property int yPosition: handler.yPosition

        property Component tickmarks: Repeater {
            id: repeater
            model: control.stepSize > 0 ? 1 + (control.maximumValue - control.minimumValue) / control.stepSize : 0
            Rectangle {
                color: "#777"
                width: 1 ; height: 3
                y: repeater.height
                x: styleData.handleWidth / 2 + index * ((repeater.width - styleData.handleWidth) / (repeater.count-1))
            }
        }

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
                CuraApplication.appWidth() - (2 * faceDialog.width),
                CuraApplication.appHeight() - (2 * faceDialog.height)
            );
            var initialY = minPt.y + 100 * screenScaleFactor
            var finalY = maxPt.y - 200 * screenScaleFactor

            faceDialog.x = Math.max(minPt.x, Math.min(maxPt.x, posNewX));
            faceDialog.y = Math.max(initialY, Math.min(finalY, posNewY));

            faceDialog.handler.setPosition(faceDialog.x, faceDialog.y)
        }

        function comboboxElements() {
            if (selectLoadButton.checked) {
                comboDialogType.model = ["Push / Pull"];
            }
            if (selectAnchorButton.checked) {
                comboDialogType.model = ["Fixed"];
            }
        }

        Connections {
            target: bcListForces.model, bcListAnchors.model
            onPropertyChanged: {
                loadColumn.iconsEnabled()
            }
        }

        Column {
            id: loadColumn

            anchors.fill: parent

            function iconsEnabled()
            {
                if (selectLoadButton.checked) {
                    if (bcListForces.model.surfaceType === 1) {
                        flatFace.color = UM.Theme.getColor("action_button_text");
                        concaveFace.color = UM.Theme.getColor("text_inactive");
                        convexFace.color = UM.Theme.getColor("text_inactive");
                    } else if (bcListForces.model.surfaceType === 2) {
                        flatFace.color = UM.Theme.getColor("text_inactive");
                        concaveFace.color = UM.Theme.getColor("action_button_text");
                        convexFace.color = UM.Theme.getColor("text_inactive");
                    } else if (bcListForces.model.surfaceType === 3) {
                        flatFace.color = UM.Theme.getColor("text_inactive");
                        concaveFace.color = UM.Theme.getColor("text_inactive");
                        convexFace.color = UM.Theme.getColor("action_button_text");
                    }
                }

                if (selectAnchorButton.checked) {
                    if (bcListAnchors.model.surfaceType === 1) {
                        flatFace.color = UM.Theme.getColor("action_button_text");
                        concaveFace.color = UM.Theme.getColor("text_inactive");
                        convexFace.color = UM.Theme.getColor("text_inactive");
                    } else if (bcListAnchors.model.surfaceType === 2) {
                        flatFace.color = UM.Theme.getColor("text_inactive");
                        concaveFace.color = UM.Theme.getColor("action_button_text");
                        convexFace.color = UM.Theme.getColor("text_inactive");
                    } else if (bcListAnchors.model.surfaceType === 3) {
                        flatFace.color = UM.Theme.getColor("text_inactive");
                        concaveFace.color = UM.Theme.getColor("text_inactive");
                        convexFace.color = UM.Theme.getColor("action_button_text");
                    }
                }

                if (bcListForces.model.loadType === 1) {
                    normalLoad.color  =UM.Theme.getColor("action_button_text");
                    parallelLoad.color = UM.Theme.getColor("text_inactive");
                } else {
                    normalLoad.color = UM.Theme.getColor("text_inactive");
                    parallelLoad.color = UM.Theme.getColor("action_button_text");
                }

                if (bcListForces.model.loadDirection) {
                    flipIcon.color = UM.Theme.getColor("action_button_text");
                } else {
                    flipIcon.color = UM.Theme.getColor("text_inactive");
                }
            }

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
                            faceDialog.trySetPosition(faceDialog.x + delta.x, faceDialog.y + delta.y);
                        }
                    }
                }
                onReleased: {
                    dragging = false
                }
                onDoubleClicked: {
                    dragging = false
                    faceDialog.x = faceDialog.xStart
                    faceDialog.y = faceDialog.yStart
                    faceDialog.handler.setPosition(faceDialog.x, faceDialog.y)
                }

                Rectangle {
                    id: topDragArea
                    width: parent.width
                    height: UM.Theme.getSize("narrow_margin").height
                    color: "transparent"
                }
            }

            Rectangle {
                id: contentRectangle

                color: UM.Theme.getColor("main_background")
                border.width: UM.Theme.getSize("default_lining").width
                border.color: UM.Theme.getColor("lining")
                radius: UM.Theme.getSize("default_radius").width

                height: contentColumn.height //- UM.Theme.getSize("default_margin").width
                width: parent.width

                MouseArea {
                    id: loadDialogMouseArea
                    propagateComposedEvents: false
                    anchors.fill: parent

                    ColumnLayout {
                        id: contentColumn

                        width: parent.width

                        anchors {
                            top: parent.top
                            topMargin: UM.Theme.getSize("default_margin").width
                        }

                        spacing: UM.Theme.getSize("default_margin").width

                        Row {
                            id: typeRow

                            anchors {
                                left: parent.left
                                topMargin: UM.Theme.getSize("default_margin").width
                                leftMargin: UM.Theme.getSize("default_margin").width
                            }

                            width: childrenRect.width

                            spacing: UM.Theme.getSize("default_margin").width

                            Label {
                                id: labelLoadDialogType

                                height: parent.height
                                verticalAlignment: Text.AlignVCenter

                                font.bold: true
                                renderType: Text.NativeRendering

                                text: "Type:"
                            }

                            ComboBox {
                                id: comboDialogType

                                style: UM.Theme.styles.combobox

                                width: contentColumn.width - labelLoadDialogType.width - 3 * UM.Theme.getSize("default_margin").width
                                anchors.verticalCenter: parent.verticalCenter

                                model: faceDialog.comboboxElements()
                            }
                        }

                        Column {
                            id: labelsColumn

                            anchors {
                                top: typeRow.bottom
                                left: parent.left
                                bottom: iconsColumn.bottom
                                leftMargin: UM.Theme.getSize("default_margin").width
                                topMargin: UM.Theme.getSize("default_margin").height * 1.4
                            }

                            height: iconsColumn.height

                            spacing: UM.Theme.getSize("default_margin").height * 1.8

                            Label {
                                id: labelDialogSelection

                                verticalAlignment: Text.AlignVCenter

                                font.bold: true
                                renderType: Text.NativeRendering

                                text: "Selection:"
                            }

                            Label {
                                id: labelLoadDialogDirection

                                visible: selectLoadButton.checked

                                verticalAlignment: Text.AlignVCenter

                                font.bold: true
                                renderType: Text.NativeRendering

                                text: "Direction:"
                            }
                        }

                        Column {
                            id: iconsColumn

                            anchors {
                                top: labelsColumn.top
                                left: labelsColumn.right
                                right: parent.right
                                topMargin: -(UM.Theme.getSize("default_margin").height * 0.395)
                            }

                            spacing: UM.Theme.getSize("default_margin").width

                            Row {
                                anchors {
                                    left: parent.left
                                    topMargin: UM.Theme.getSize("default_margin").width
                                    leftMargin: UM.Theme.getSize("default_margin").width
                                }

                                width: childrenRect.width
                                spacing: UM.Theme.getSize("default_margin").width

                                UM.SimpleButton {
                                    id: flatFace
                                    width: height
                                    height: comboDialogType.height

                                    iconSource: "media/flat.png"
                                    visible: true
                                    enabled: true

                                    hoverColor: UM.Theme.getColor("setting_category_hover_border")

                                    onClicked: {
                                        if (selectAnchorButton.checked) {
                                            bcListAnchors.model.surfaceType = 1;
                                            loadColumn.iconsEnabled();
                                        }
                                        if (selectLoadButton.checked) {
                                            bcListForces.model.surfaceType = 1;
                                            loadColumn.iconsEnabled();
                                        }
                                    }
                                }

                                UM.SimpleButton {
                                    id: concaveFace
                                    width: height
                                    height: comboDialogType.height

                                    iconSource: "media/concave.png"
                                    visible: true
                                    enabled: true

                                    hoverColor: UM.Theme.getColor("setting_category_hover_border")

                                    onClicked: {
                                        if (selectAnchorButton.checked) {
                                            bcListAnchors.model.surfaceType = 2;
                                            loadColumn.iconsEnabled();
                                        }
                                        if (selectLoadButton.checked) {
                                            bcListForces.model.surfaceType = 2;
                                            loadColumn.iconsEnabled();
                                        }
                                    }
                                }

                                UM.SimpleButton {
                                    id: convexFace
                                    width: height
                                    height: comboDialogType.height

                                    iconSource: "media/convex.png"
                                    visible: true
                                    enabled: true

                                    hoverColor: UM.Theme.getColor("setting_category_hover_border")

                                    onClicked: {
                                        if (selectAnchorButton.checked) {
                                            bcListAnchors.model.surfaceType = 3;
                                            loadColumn.iconsEnabled();
                                        }
                                        if (selectLoadButton.checked) {
                                            bcListForces.model.surfaceType = 3;
                                            loadColumn.iconsEnabled();
                                        }
                                    }
                                }
                            }

                            Row {
                                visible: selectLoadButton.checked

                                anchors {
                                    left: parent.left
                                    topMargin: UM.Theme.getSize("default_margin").width
                                    leftMargin: UM.Theme.getSize("default_margin").width
                                }

                                width: childrenRect.width
                                spacing: UM.Theme.getSize("default_margin").width

                                UM.SimpleButton {
                                    id: normalLoad
                                    width: height
                                    height: comboDialogType.height

                                    iconSource: "media/load_normal.png"
                                    visible: true
                                    enabled: true

                                    hoverColor: UM.Theme.getColor("setting_category_hover_border")

                                    onClicked: {
                                        bcListForces.model.loadType = 1;
                                        loadColumn.iconsEnabled();
                                    }
                                }

                                UM.SimpleButton {
                                    id: parallelLoad
                                    width: height
                                    height: comboDialogType.height

                                    iconSource: "media/load_parallel.png"
                                    visible: true
                                    enabled: true

                                    hoverColor: UM.Theme.getColor("setting_category_hover_border")

                                    onClicked: {
                                        bcListForces.model.loadType = 2;
                                        loadColumn.iconsEnabled();
                                    }
                                }
                            }

                            Row {
                                visible: selectLoadButton.checked

                                anchors {
                                    left: parent.left
                                    topMargin: UM.Theme.getSize("default_margin").width
                                    leftMargin: UM.Theme.getSize("default_margin").width
                                }

                                width: childrenRect.width
                                height: childrenRect.height
                                spacing: UM.Theme.getSize("default_margin").width

                                UM.SimpleButton {
                                    id: flipIcon
                                    width: height
                                    height: comboDialogType.height

                                    iconSource: "media/flip.png"
                                    visible: true
                                    enabled: true

                                    hoverColor: UM.Theme.getColor("setting_category_hover_border")

                                    onClicked: {
                                        bcListForces.model.loadDirection = !bcListForces.model.loadDirection;
                                        loadColumn.iconsEnabled();
                                    }
                                }
                            }
                        }

                        Column {
                            anchors {
                                    left: contentColumn.left
                                    right: contentColumn.right
                                    top: iconsColumn.bottom
                                    margins: UM.Theme.getSize("default_margin").width
                                }

                                width: contentColumn.width

                                visible: selectLoadButton.checked

                                spacing: UM.Theme.getSize("default_margin").width

                            Label {
                                id: labelLoadDialogMagnitude

                                visible: selectLoadButton.checked

                                font.bold: true
                                renderType: Text.NativeRendering

                                text: "Magnitude:"
                            }

                            TextField {
                                id: textLoadDialogMagnitude

                                visible: selectLoadButton.checked

                                style: UM.Theme.styles.text_field

                                function loadHelperStep(value) {
                                    for (var i = 0; i < loadHelperData.textLoadDialogConverter.length - 1; i++){
                                        if (value >= loadHelperData.textLoadDialogConverter[i] && value <= loadHelperData.textLoadDialogConverter[i + 1]) {
                                            return value * loadHelperData.textLoadMultiplier[i] + loadHelperData.textLoadOffset[i];
                                        }
                                    }
                                    return value;
                                }

                                anchors {
                                    left: parent.left
                                    topMargin: UM.Theme.getSize("default_margin").height
                                    leftMargin: UM.Theme.getSize("default_margin").width
                                }

                                onTextChanged: {
                                    var value = parseFloat(text)
                                    if (value >= 0.0) {
                                        bcListForces.model.loadMagnitude = text;
                                        loadHelper.value = loadHelperStep(text)
                                    }
                                }

                                onEditingFinished: {
                                    bcListForces.model.loadMagnitude = text;
                                }

                                validator: DoubleValidator {bottom: 0.0}
                                inputMethodHints: Qt.ImhFormattedNumbersOnly
                                text:  bcListForces.model.loadMagnitude

                                property string unit: "[N]";
                            }

                            Rectangle {
                                id: sliderRect

                                visible: selectLoadButton.checked

                                anchors {
                                    left: parent.left
                                    right: parent.right
                                    top: textLoadDialogMagnitude.bottom
                                    topMargin: UM.Theme.getSize("default_margin").width
                                }

                                QTC.Slider {
                                    id: loadHelper
                                    from: 0
                                    to: loadHelperData.maxValue
                                    stepSize: 1

                                    anchors {
                                        left: parent.left
                                        right: parent.right
                                        topMargin: UM.Theme.getSize("default_margin").width
                                    }


                                    background:
                                        Rectangle {
                                            function indexHelper(index) {
                                                if (index === 3) {
                                                    return loadHelper.availableWidth * (index + 1) / (tickmarks.model + 1) - 3;
                                                };
                                                return loadHelper.availableWidth * (index + 1) / (tickmarks.model + 1);
                                            }
                                            x: indexHelper(index)
                                            y: loadHelper.topPadding + loadHelper.availableHeight / 2 - height / 2
                                            height: UM.Theme.getSize("print_setup_slider_groove").height
                                            width: loadHelper.width - UM.Theme.getSize("print_setup_slider_handle").width
                                            color: loadHelper.enabled ? UM.Theme.getColor("quality_slider_available") : UM.Theme.getColor("quality_slider_unavailable")
                                            anchors {
                                                horizontalCenter: parent.horizontalCenter
                                                verticalCenter: parent.verticalCenter
                                            }

                                        Repeater {
                                            id: tickmarks
                                            model: loadHelperData.maxValue / loadHelperData.stepSize -1
                                            Rectangle {
                                                function indexHelper(index) {
                                                    if (index === 3) {
                                                        return loadHelper.availableWidth * (index + 1) / (tickmarks.model + 1) - 3;
                                                    };
                                                    return loadHelper.availableWidth * (index + 1) / (tickmarks.model + 1);
                                                }
                                                x: indexHelper(index)
                                                y: loadHelper.topPadding + loadHelper.availableHeight / 2 - height / 2
                                                color: loadHelper.enabled ? UM.Theme.getColor("quality_slider_available") : UM.Theme.getColor("quality_slider_unavailable")
                                                implicitWidth: UM.Theme.getSize("print_setup_slider_tickmarks").width
                                                implicitHeight: UM.Theme.getSize("print_setup_slider_tickmarks").height
                                                anchors.verticalCenter: parent.verticalCenter
                                                radius: Math.round(implicitWidth / 2)
                                            }
                                        }
                                    }

                                    handle: Rectangle {
                                        id: handleButton
                                        x: loadHelper.leftPadding + loadHelper.visualPosition * (loadHelper.availableWidth - width)
                                        y: loadHelper.topPadding + loadHelper.availableHeight / 2 - height / 2
                                        color: loadHelper.enabled ? UM.Theme.getColor("primary") : UM.Theme.getColor("quality_slider_unavailable")
                                        implicitWidth: UM.Theme.getSize("print_setup_slider_handle").width
                                        implicitHeight: implicitWidth
                                        radius: Math.round(implicitWidth)
                                    }

                                    onMoved: {
                                        function loadMagnitudeStep(value){
                                            for (var i = 0; i < loadHelperData.loadStepFunction.length; i++) {
                                                if (loadHelperData.loadStepFunction[i] === value) {
                                                    return value / loadHelperData.loadStepDivision[i];
                                                }
                                            }
                                        }
                                        var roundedSliderValue = Math.round(loadHelper.value / loadHelperData.stepSize) * loadHelperData.stepSize
                                        loadHelper.value = roundedSliderValue
                                        textLoadDialogMagnitude.text = loadMagnitudeStep(roundedSliderValue)
                                    }
                                }
                            }
                        }
                    }
                    Rectangle {
                        id: loadHelperImageRect

                        function isVis() {
                            if (selectLoadButton.checked) {
                                for (var i = 1; i < loadHelperData.loadStepFunction.length - 1; i++) {
                                    if (loadHelperData.loadStepFunction[i] === loadHelper.value) {
                                        return true;
                                    }
                                }
                            }
                            return false;
                        }

                        function imageData(image) {
                            if (selectLoadButton.checked) {
                                for (var i = 1; i < loadHelperData.loadStepFunction.length - 1; i++) {
                                    if (loadHelperData.loadStepFunction[i] === loadHelper.value) {
                                        return image[i - 1];
                                    }
                                }
                            }
                            return "";
                        }

                        color: UM.Theme.getColor("main_background")
                        border.width: UM.Theme.getSize("default_lining").width
                        border.color: UM.Theme.getColor("lining")
                        anchors.left: contentColumn.right
                        anchors.leftMargin: UM.Theme.getSize("default_margin").width
                        radius: UM.Theme.getSize("default_radius").width

                        height: contentColumn.height //- UM.Theme.getSize("default_margin").width
                        width: contentColumn.width

                        anchors.top: contentColumn.top
                        anchors.topMargin: - UM.Theme.getSize("default_margin").width
                        visible: isVis()

                        Label {
                            id: topText
                            anchors {
                                top:parent.top
                                topMargin: UM.Theme.getSize("default_margin").width
                                left: parent.left
                                leftMargin: UM.Theme.getSize("default_margin").width
                            }
                            renderType: Text.NativeRendering
                            font: UM.Theme.getFont("default")
                            text: "<b>Example:</b>"
                        }

                        Image {
                            id: loadHelperImage
                            mipmap: true

                            anchors {
                                top: topText.bottom
                                right: parent.right
                                rightMargin: UM.Theme.getSize("default_margin").width
                                left: parent.left
                                leftMargin: UM.Theme.getSize("default_margin").width
                                bottom: loadHelperSeparator.top
                            }

                            fillMode: Image.PreserveAspectFit
                            source: loadHelperImageRect.imageData(loadHelperData.imageLocation)
                        }

                        Rectangle {
                            id: loadHelperSeparator
                            border.color: UM.Theme.getColor("lining")
                            color: UM.Theme.getColor("lining")

                            anchors {
                                bottom: imageType.top
                                bottomMargin: UM.Theme.getSize("default_margin").width / 2
                                right: parent.right
                                left: parent.left
                            }

                            width: parent.width
                            height: 1
                        }

                        Text {
                            id: imageType

                            anchors {
                                bottom: weight.top
                                topMargin: UM.Theme.getSize("default_margin").width / 2
                                left: parent.left
                                leftMargin: UM.Theme.getSize("default_margin").width
                            }

                            font: UM.Theme.getFont("default")
                            renderType: Text.NativeRendering
                            text: loadHelperImageRect.imageData(loadHelperData.imageType)
                        }

                        Text {
                            id: weight

                            anchors {
                                bottom: parent.bottom
                                bottomMargin: UM.Theme.getSize("default_margin").width / 2
                                topMargin: UM.Theme.getSize("default_margin").width / 2
                                left: parent.left
                                leftMargin: UM.Theme.getSize("default_margin").width
                            }

                            font: UM.Theme.getFont("default")
                            renderType: Text.NativeRendering
                            text: loadHelperImageRect.imageData(loadHelperData.loadHelperEquivalentValue)
                        }
                    }
                }
            }
        }
    }
}
