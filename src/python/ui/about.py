from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QDialog, QGraphicsView, QLabel,
    QSizePolicy, QWidget, QVBoxLayout, QGraphicsScene, QGraphicsPixmapItem) 
import os

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setupUi(self) 

    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"About")
        Dialog.resize(400, 250)

        # self.scene = QGraphicsScene(self)
        # current_dir = os.path.dirname(__file__)
        # image_path = os.path.join(current_dir, "CoraMetixLogo_TextWhite.png")
        # self.pixmap = QPixmap(image_path)

        # self.graphicsView = QGraphicsView(Dialog)
        # self.graphicsView.setObjectName(u"graphicsView")
        # self.graphicsView.setGeometry(QRect(70, 0, 256, 71))

        # self.pixmap_item = QGraphicsPixmapItem(self.pixmap)
        # self.scene.addItem(self.pixmap_item)
        # self.graphicsView.setScene(self.scene)
        # self.graphicsView.fitInView(self.pixmap_item.boundingRect(), Qt.KeepAspectRatio)

        self.imgLabel = QLabel(Dialog)
        imgPixmap = QPixmap("src/python/media/CoraMetixLogo.png")
        self.imgLabel.setPixmap(imgPixmap)
        self.imgLabel.setAlignment(Qt.AlignCenter)
        self.imgLabel.setGeometry(QRect(67, 20, 267, 50))
        self.imgLabel.setScaledContents(True)

        self.label = QLabel(Dialog)
        self.label.setObjectName(u"label")
        self.label.setGeometry(QRect(90, 70, 221, 41))
        font = QFont()
        font.setPointSize(12)
        self.label.setFont(font)
        self.label.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_2 = QLabel(Dialog)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setGeometry(QRect(138, 120, 121, 20))
        self.label_2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_3 = QLabel(Dialog)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setGeometry(QRect(120, 150, 161, 41))
        self.label_3.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_4 = QLabel(Dialog)
        self.label_4.setObjectName(u"label_4")
        self.label_4.setGeometry(QRect(110, 180, 191, 31))
        self.label_4.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.retranslateUi(Dialog) 
        QMetaObject.connectSlotsByName(Dialog) 
    # setupUi

    def retranslateUi(self, Dialog): 
        Dialog.setWindowTitle(QCoreApplication.translate("About", u"About FibreScope", None)) 
        self.label.setText(QCoreApplication.translate("About", u"FibreScope", None))
        self.label_2.setText(QCoreApplication.translate("About", u"Version:     1.0.1", None))
        self.label_3.setText(QCoreApplication.translate("About", u"Author: Yangtian Yan", None))
