from PyQt6.QtWidgets import QSlider, QStyle, QStyleOptionSlider
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QMouseEvent


class JumpSlider(QSlider):
    """Seek immediately on click and keep dragging relative to the handle."""

    def _value_at(self, position):
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        handle = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider, option,
            QStyle.SubControl.SC_SliderHandle, self,
        )
        horizontal = self.orientation() == Qt.Orientation.Horizontal
        handle_size = handle.width() if horizontal else handle.height()
        length = self.width() if horizontal else self.height()
        coordinate = position.x() if horizontal else position.y()
        return QStyle.sliderValueFromPosition(
            self.minimum(), self.maximum(), int(coordinate - handle_size / 2),
            max(1, length - handle_size), option.upsideDown,
        )

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self.setSliderDown(True)
            self.setSliderPosition(self._value_at(event.position()))
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.isSliderDown():
            self.setSliderPosition(self._value_at(event.position()))
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.isSliderDown():
            self.setSliderPosition(self._value_at(event.position()))
            self.setSliderDown(False)
            event.accept()
        else:
            super().mouseReleaseEvent(event)
