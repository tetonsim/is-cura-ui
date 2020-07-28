import QtQuick 2.7
import QtQuick.Controls 1.5
import QtQuick.Controls.Styles 1.2
import QtQuick.Controls 2.2
import QtQuick.Layouts 1.3
import QtGraphicalEffects 1.0

import UM 1.2 as UM
import Cura 1.0 as Cura

import SmartSlice 1.0 as SmartSlice

Item {
    id: resultsTable

    property int implicitHeight: 200

    width: 400
    height: tableArea.height + draggableArea.height + topDragArea.height

    property int centerX: 0.5 * (parent.width - width)
    property int centerY: 0.5 * (parent.height - height)

    property var handler: SmartSlice.Cloud.resultsTableDialog

    property bool locationSet: handler.positionSet

    property int xLocation: handler.xPosition
    property int yLocation: handler.yPosition

    x: {
        if (locationSet) {
            return xLocation
        }
        return centerX
    }

    y: {
        if (locationSet) {
            return yLocation
        }
        return centerY
    }

    Column {
        id: resultTableColumn

        anchors.fill: parent

        MouseArea {
            cursorShape: Qt.SizeAllCursor

            height: topDragArea.height
            width: parent.width

            property var clickPos: Qt.point(0, 0)
            property bool dragging: false

            onPressed: {
                clickPos = Qt.point(mouse.x, mouse.y);
                dragging = true
            }
            onPositionChanged: {
                if(dragging) {
                    var posX = resultsTable.x + mouse.x - clickPos.x
                    var posY = resultsTable.y + mouse.y - clickPos.y

                    if (posX <= smartSliceMain.x) {
                        posX = smartSliceMain.x
                    }
                    if (posX + resultsTable.width >= smartSliceMain.x + smartSliceMain.width) {
                        posX = smartSliceMain.x + smartSliceMain.width - resultsTable.width
                    }

                    if (posY <= smartSliceMain.y) {
                        posY = smartSliceMain.y
                    }
                    if (posY + resultsTable.height >= smartSliceMain.y + smartSliceMain.height) {
                        posY = smartSliceMain.y + smartSliceMain.height - resultsTable.height
                    }

                    resultsTable.x = posX
                    resultsTable.y = posY
                    resultsTable.handler.setPosition(posX, posY)
                }
            }
            onReleased: {
                dragging = false
            }

            onDoubleClicked: {
                dragging = false
                resultsTable.x = resultsTable.centerX
                resultsTable.y = resultsTable.centerY
                resultsTable.handler.setPosition(resultsTable.centerX, resultsTable.centerY)
            }

            Rectangle {
                id: topDragArea
                width: parent.width
                height: 2 * UM.Theme.getSize("default_margin").height
                // color: UM.Theme.getColor("secondary")
                color: "transparent"
            }
        }

        TableView {

            id: tableArea

            implicitHeight: resultsTable.implicitHeight
            width: parent.width

            property int tableHeight: resultsTable.handler.height
            property bool heightSet: resultsTable.handler.heightSet

            height: {
                if (heightSet) {
                    return tableHeight
                }
                return implicitHeight
            }

            horizontalScrollBarPolicy: Qt.ScrollBarAlwaysOff

            model: SmartSlice.Cloud.resultsTable

            property int selectedRow: model.selectedRow

            property int sortColumn: model.sortColumn
            property int sortOrder: model.sortOrder

            sortIndicatorVisible: true
            headerVisible: true
            visible: resultsTable.visible

            selectionMode: SelectionMode.SingleSelection

            TableViewColumn {
                role: "rank"
                title: "Rank"
                movable: false
                resizable: false
                width: 0.1 * tableArea.width
            }
            TableViewColumn {
                role: "time"
                title: "Print Time"
                movable: false
                resizable: false
                width: 0.2 * tableArea.width
            }
            TableViewColumn {
                role: "mass"
                title: "Mass"
                movable: false
                resizable: false
                width: 0.1 * tableArea.width
            }
            TableViewColumn {
                role: "strength"
                title: "Factor of Safety"
                movable: false
                resizable: false
                width: 0.25 * tableArea.width
            }
            TableViewColumn {
                role: "displacement"
                title: "Max Displacement"
                movable: false
                resizable: false
                width: 0.25 * tableArea.width
            }
            TableViewColumn {
                movable: false
                resizable: false
                width: 0.11 * tableArea.width
            }

            style: TableViewStyle {
                decrementControl: Item { }
                incrementControl: Item { }

                transientScrollBars: false

                scrollBarBackground: Rectangle {
                    id: scrollViewBackground
                    implicitWidth: UM.Theme.getSize("scrollbar").width
                    radius: Math.round(implicitWidth / 2)
                    color: UM.Theme.getColor("scrollbar_background")
                }

                handle: Rectangle {
                    id: scrollViewHandle
                    implicitWidth: UM.Theme.getSize("scrollbar").width
                    radius: Math.round(implicitWidth / 2)

                    color: styleData.pressed ? UM.Theme.getColor("scrollbar_handle_down") : styleData.hovered ? UM.Theme.getColor("scrollbar_handle_hover") : UM.Theme.getColor("scrollbar_handle")
                    Behavior on color { ColorAnimation { duration: 50; } }
                }

                rowDelegate: Rectangle {
                    height: UM.Theme.getSize("default_arrow").height + 3 * UM.Theme.getSize("thin_margin").height
                    SystemPalette {
                        id: myPalette;
                        colorGroup: SystemPalette.Active
                    }
                    color: {
                        var baseColor = styleData.alternate ? myPalette.alternateBase : myPalette.base
                        return tableArea.selectedRow == styleData.row ? UM.Theme.getColor("setting_control_border_highlight") : baseColor
                    }
                }

                itemDelegate: Item {
                    id: itemLayout

                    Text {
                        anchors {
                            fill: itemLayout
                        }
                        text: styleData.value
                        renderType: Text.NativeRendering
                        font: UM.Theme.getFont("default")
                        horizontalAlignment: TextInput.AlignHCenter
                        verticalAlignment: TextInput.AlignVCenter
                        visible: styleData.column < tableArea.columnCount - 1
                    }

                    MouseArea {
                        width: previewImage.width
                        height: previewImage.height

                        anchors.centerIn: itemLayout

                        hoverEnabled: true
                        enabled: previewImage.visible

                        UM.RecolorImage {
                            id: previewImage

                            source: "../images/preview.png"
                            color: UM.Theme.getColor("main_background")

                            width: 1.5 * height
                            height: 0.5 * itemLayout.height
                            visible: styleData.column == tableArea.columnCount - 1 && styleData.row == tableArea.selectedRow
                        }

                        onEntered: {
                            previewImage.color = UM.Theme.getColor("setting_category_hover")
                        }
                        onExited: {
                            previewImage.color = UM.Theme.getColor("main_background")
                        }
                        onClicked: {
                            if (previewImage.visible) {
                                tableArea.model.previewClicked()
                            }
                        }
                    }
                }

                // Have to hack the headerDelegate with a TextField because Rectangle won't work
                headerDelegate: TextField {
                    height: UM.Theme.getSize("default_arrow").height + 2 * UM.Theme.getSize("default_margin").height

                    background: Rectangle {
                        color: UM.Theme.getColor("main_window_header_background")
                    }

                    text: styleData.value
                    readOnly: true
                    renderType: Text.NativeRendering
                    font: UM.Theme.getFont("medium_bold")
                    color: UM.Theme.getColor("main_window_header_background")

                    RowLayout {
                        spacing: 4
                        height: parent.height

                        anchors {
                            centerIn: parent
                        }

                        Layout.alignment: Qt.AlignHCenter | Qt.AlignVCenter

                        Column {
                            width: UM.Theme.getSize("default_arrow").width
                            height: parent.height

                            anchors {
                                bottomMargin: UM.Theme.getSize("thin_margin").height
                                topMargin: UM.Theme.getSize("thin_margin").height
                            }

                            spacing: 2

                            Layout.alignment: Qt.AlignRight | Qt.AlignVCenter

                            anchors.rightMargin: 0
                            padding: 0

                            UM.RecolorImage {
                                source: "../images/triangle_up.png"
                                color: UM.Theme.getColor("main_background")

                                width: UM.Theme.getSize("default_arrow").width
                                height: UM.Theme.getSize("default_arrow").height
                                visible: styleData.column < tableArea.columnCount - 1 && styleData.column == tableArea.sortColumn && tableArea.sortOrder == Qt.AscendingOrder
                            }

                            UM.RecolorImage {
                                source: "../images/triangle_up.png"
                                color: UM.Theme.getColor("main_window_header_background")

                                width: UM.Theme.getSize("default_arrow").width
                                height: UM.Theme.getSize("default_arrow").height
                                visible: tableArea.sortOrder == Qt.DescendingOrder
                            }

                            UM.RecolorImage {
                                source: "../images/triangle_down.png"
                                color: UM.Theme.getColor("main_background")

                                width: UM.Theme.getSize("default_arrow").width
                                height: UM.Theme.getSize("default_arrow").height
                                visible: styleData.column < tableArea.columnCount - 1 && styleData.column == tableArea.sortColumn && tableArea.sortOrder == Qt.DescendingOrder
                            }

                            UM.RecolorImage {
                                source: "../images/triangle_down.png"
                                color: UM.Theme.getColor("main_window_header_background")

                                width: UM.Theme.getSize("default_arrow").width
                                height: UM.Theme.getSize("default_arrow").height
                                visible: tableArea.sortOrder == Qt.AscendingOrder
                            }
                        }

                        Text {
                            text: styleData.value
                            renderType: Text.NativeRendering
                            font: UM.Theme.getFont("medium_bold")
                            color: UM.Theme.getColor("main_background")
                            horizontalAlignment: TextInput.AlignLeft
                            verticalAlignment: TextInput.AlignVCenter
                        }
                    }
                }
            }

            Connections {
                onSortIndicatorColumnChanged: {
                    tableArea.model.sortByColumn(tableArea.sortIndicatorColumn)
                }
                onSortIndicatorOrderChanged: {
                    tableArea.model.sortByColumn(tableArea.sortIndicatorColumn)
                }
                onSelectedRowChanged: {
                    tableArea.selection.clear()
                    tableArea.selection.select(tableArea.selectedRow)
                }
                onVisibleChanged: {
                    if (tableArea.visible) {
                        tableArea.selection.clear()
                        tableArea.selection.select(tableArea.selectedRow)
                    }
                }
            }

            onClicked: {
                if (tableArea.selectedRow != tableArea.currentRow) {
                    tableArea.model.rowClicked(tableArea.currentRow)
                }
            }

            Component.onCompleted: {
                if (tableArea.visible) {
                    tableArea.selection.clear()
                    tableArea.selection.select(tableArea.selectedRow)
                }
            }
        }

        //Invisible area at the bottom with which you can resize the panel.
        MouseArea {
            id: draggableArea

            height: childrenRect.height
            width: parent.width

            cursorShape: Qt.SplitVCursor

            drag {
                target: parent
                axis: Drag.YAxis
            }

            property var clickPos: Qt.point(0, 0)
            property var tableTop: resultsTable.y
            property var tableHeight: tableArea.height

            onPressed: {
                clickPos = Qt.point(mouse.x, mouse.y);
                tableTop = resultsTable.y;
                tableHeight = tableArea.height;
            }
            onMouseYChanged: {
                var absoluteMinimumHeight = 0.15 * smartSliceMain.height;

                if (drag.active) {
                    var h = mouseY + tableArea.height | 0
                    var bottom = tableTop + topDragArea.height + h + draggableArea.height

                    if (bottom <= smartSliceMain.y) {
                        h = smartSliceMain.y - tableTop - topDragArea.height - draggableArea.height;
                    }
                    h = Math.max(absoluteMinimumHeight, h);

                    resultsTable.y = tableTop;
                    tableArea.height = h;
                    resultsTable.height = h + draggableArea.height + topDragArea.height;
                    resultTableColumn.forceLayout()

                    resultsTable.handler.setHeight(h)
                }
            }

            Rectangle {
                width: parent.width
                height: UM.Theme.getSize("narrow_margin").height
                color: UM.Theme.getColor("secondary")

                Rectangle {
                    anchors.bottom: parent.top
                    width: parent.width
                    height: UM.Theme.getSize("default_lining").height
                    color: UM.Theme.getColor("lining")
                }

                UM.RecolorImage {
                    width: UM.Theme.getSize("drag_icon").width
                    height: UM.Theme.getSize("drag_icon").height
                    anchors.centerIn: parent

                    source: UM.Theme.getIcon("resize")
                    color: UM.Theme.getColor("small_button_text")
                }
            }
        }
    }
}
