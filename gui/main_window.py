import sys
import json
import shutil
import subprocess
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QCheckBox, QPushButton, QTextEdit, QLabel,
    QLineEdit, QFrame, QGraphicsDropShadowEffect, QProgressBar,
    QStackedWidget, QListWidget, QListWidgetItem, QMessageBox
)
from PyQt6.QtCore import Qt, QPoint, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import (
    QFont, QFontDatabase, QPixmap, QPainter, QColor, QCursor, QMovie,
    QPen, QPainterPath
)

from launcher.api import get_version_list
from launcher.launcher_core import get_offline_uuid
import minecraft_launcher_lib as mll

SETTINGS_PATH = Path(__file__).parent.parent / "launcher_settings.json"


def load_settings() -> dict:
    if SETTINGS_PATH.exists():
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    return {"java_path": "", "window_width": 1000, "window_height": 600, "ram": "2G"}


def save_settings(data: dict):
    SETTINGS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_installed_versions_list(mc_dir: Path) -> list[str]:
    try:
        return [v["id"] for v in mll.utils.get_installed_versions(str(mc_dir))]
    except Exception:
        return []


# ─── Threads ───

class InstallThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, version: str, username: str, mc_dir: Path, settings: dict, parent=None):
        super().__init__(parent)
        self.version = version
        self.username = username
        self.mc_dir = mc_dir
        self.settings = settings
        self._max = 100

    def run(self):
        try:
            def set_status(s: str):
                self.log_signal.emit(f"   ...{s}")
            def set_max(m: int):
                self._max = max(m, 1)
                self.progress_signal.emit(0, self._max)
            def set_progress(p: int):
                self.progress_signal.emit(p, self._max)

            mll.install.install_minecraft_version(
                self.version, str(self.mc_dir),
                callback={"setStatus": set_status, "setMax": set_max, "setProgress": set_progress}
            )
            self.log_signal.emit("✅ Файлы готовы")

            options = {
                "username": self.username,
                "uuid": get_offline_uuid(self.username),
                "token": "0",
                "launcherName": "Amaterasu",
                "launcherVersion": "1.0",
                "gameDirectory": str(self.mc_dir),
                "jvmArguments": [f"-Xmx{self.settings.get('ram','2G')}"],
            }
            if self.settings.get("java_path"):
                options["executablePath"] = self.settings["java_path"]

            cmd = mll.command.get_minecraft_command(self.version, str(self.mc_dir), options)
            self.log_signal.emit(f"☕ Java: {Path(cmd[0]).name}")
            self.log_signal.emit("🚀 Запуск Minecraft...")
            subprocess.Popen(cmd, cwd=str(self.mc_dir))
            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))


class DownloadThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, version: str, mc_dir: Path, parent=None):
        super().__init__(parent)
        self.version = version
        self.mc_dir = mc_dir
        self._max = 100

    def run(self):
        try:
            def set_status(s: str):
                self.log_signal.emit(f"   ...{s}")
            def set_max(m: int):
                self._max = max(m, 1)
                self.progress_signal.emit(0, self._max)
            def set_progress(p: int):
                self.progress_signal.emit(p, self._max)

            mll.install.install_minecraft_version(
                self.version, str(self.mc_dir),
                callback={"setStatus": set_status, "setMax": set_max, "setProgress": set_progress}
            )
            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))


# ─── Rounded Popup Menu ───

class RoundedMenu(QFrame):
    page_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("""
            RoundedMenu {
                background-color: #1a0808;
                border: 1px solid #5a2020;
                border-radius: 8px;
            }
            QPushButton {
                background: transparent;
                border: none;
                color: #c0a0a0;
                padding: 9px 18px;
                font-size: 13px;
                text-align: left;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3a1515;
                color: #ffd6d6;
            }
        """)
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(2)

        for idx, label in [(1, "Менеджер версий"), (2, "Настройки лаунчера")]:
            btn = QPushButton(label)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.clicked.connect(lambda checked, i=idx: self.page_selected.emit(i))
            v.addWidget(btn)

        v.addSpacing(4)
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #3a1515;")
        v.addWidget(sep)
        lbl = QLabel("Amaterasu v1.0")
        lbl.setStyleSheet("color:#5a3030;font-size:10px;padding:2px 4px;")
        v.addWidget(lbl)
        self.adjustSize()


# ─── Vector Icon Button ───

class IconBtn(QPushButton):
    def __init__(self, icon_type: str, tooltip: str, parent=None):
        super().__init__(parent)
        self.icon_type = icon_type
        self.setFixedSize(30, 30)
        self.setToolTip(tooltip)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setStyleSheet("background: transparent; border: none;")
        self._hover = False

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)
    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QColor(220, 50, 50) if self._hover else QColor(140, 80, 80)
        painter.setPen(QPen(c, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        r = self.rect().adjusted(4, 4, -4, -4)
        cx, cy = r.center().x(), r.center().y()

        if self.icon_type == "info":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(r)
            painter.setPen(QPen(c, 2))
            painter.drawPoint(cx, cy - 2)
            painter.drawLine(cx, cy, cx, cy + 4)
        elif self.icon_type == "folder":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(r.x(), r.y() + 5, r.width(), r.height() - 5)
            p = QPainterPath()
            p.moveTo(r.x(), r.y() + 5)
            p.lineTo(r.x() + r.width() * 0.38, r.y() + 5)
            p.lineTo(r.x() + r.width() * 0.48, r.y())
            p.lineTo(r.x() + r.width(), r.y())
            p.lineTo(r.x() + r.width(), r.y() + 5)
            painter.drawPath(p)
        elif self.icon_type == "refresh":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(r.x(), r.y(), r.width(), r.height(), 30 * 16, 280 * 16)
            ax = int(r.x() + r.width() * 0.78)
            ay = int(r.y() + r.height() * 0.22)
            painter.drawLine(ax, ay, ax + 4, ay - 3)
            painter.drawLine(ax, ay, ax + 1, ay + 4)
        elif self.icon_type == "menu":
            painter.setPen(QPen(c, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for i in range(3):
                y = int(r.y() + 3 + i * r.height() * 0.34)
                painter.drawLine(r.x(), y, r.x() + r.width(), y)
        painter.end()


# ─── Background ───

class GifBg(QWidget):
    def __init__(self, image_path: Path, parent=None):
        super().__init__(parent)
        self.pixmap = None
        self.movie_label = None
        for ext in (".gif", ".png", ".jpg", ".jpeg"):
            p = image_path.with_suffix(ext)
            if p.exists():
                if ext == ".gif":
                    self.movie_label = QLabel(self)
                    movie = QMovie(str(p))
                    self.movie_label.setMovie(movie)
                    self.movie_label.setScaledContents(True)
                    movie.start()
                else:
                    self.pixmap = QPixmap(str(p))
                break

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.movie_label:
            self.movie_label.setGeometry(self.rect())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(10, 2, 2))
        if self.pixmap and not self.pixmap.isNull():
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            scaled = self.pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                        Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap((self.width() - scaled.width()) // 3,
                               (self.height() - scaled.height()) // 2, scaled)
        painter.end()


# ─── Stylesheet ───

def stylesheet() -> str:
    return """
    QWidget{color:#ffd6d6;font-family:"Segoe UI";font-size:13px;}
    #LeftPanel{background-color:rgba(12,3,3,235);border:none;border-right:1px solid rgba(160,30,30,60);border-radius:12px;}
    #RightPanel{background-color:#0a0202;border:none;border-left:1px solid rgba(160,30,30,60);border-radius:12px;}
    #CenterBg{border-radius:12px;}
    #TopBar{background-color:rgba(10,2,2,245);border-bottom:1px solid rgba(160,30,30,90);}
    QLineEdit{background-color:rgba(30,6,6,200);border:1px solid rgba(150,40,40,130);border-radius:6px;padding:6px 10px;color:#ffd6d6;font-size:13px;}
    QLineEdit:focus{border:1px solid #c04040;}
    QComboBox{background-color:rgba(30,6,6,200);border:1px solid rgba(150,40,40,130);border-radius:6px;padding:6px 10px;padding-right:28px;color:#ffd6d6;font-size:13px;}
    QComboBox::drop-down{background:transparent;border:none;width:24px;}
    QComboBox::down-arrow{image:none;border-left:5px solid transparent;border-right:5px solid transparent;border-top:7px solid #b03030;width:0;height:0;margin-top:2px;}
    QComboBox QAbstractItemView{background:#140505;border:1px solid #5a1515;selection-background-color:#3a1010;color:#ffd6d6;padding:4px;}
    QCheckBox{spacing:8px;color:#c08080;font-size:12px;}
    QCheckBox::indicator{width:16px;height:16px;border-radius:3px;border:1px solid #7b2020;background:rgba(25,6,6,180);}
    QCheckBox::indicator:checked{background:#d03030;border:1px solid #ff3d3d;}
    QProgressBar{background-color:rgba(30,6,6,200);border:1px solid rgba(150,40,40,130);border-radius:5px;color:#ffd6d6;text-align:center;font-size:11px;max-height:18px;}
    QProgressBar::chunk{background-color:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #5a1212,stop:1 #e03030);border-radius:4px;}
    #LaunchBtn{background-color:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #5a1212,stop:1 #2a0606);border:1px solid #901515;border-radius:8px;padding:14px;font-size:15px;font-weight:bold;color:#fff;margin:4px 0;}
    #LaunchBtn:hover{background-color:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #7a1a1a,stop:1 #4a0a0a);border:1px solid #cc2222;}
    #LaunchBtn:pressed{background-color:#1a0404;padding-top:15px;padding-bottom:13px;}
    #LaunchBtn:disabled{background-color:#2a1212;color:#7b5050;border:1px solid #4a1515;}
    QTextEdit#Log{background-color:rgba(8,2,2,200);border:1px solid rgba(140,40,40,60);border-radius:6px;color:#ff9999;font-family:Consolas;font-size:11px;padding:6px;}
    #WinBtn{background:transparent;border:none;color:#a06060;font-size:15px;padding:2px 10px;border-radius:4px;}
    #WinBtn:hover{background-color:rgba(150,30,30,50);color:#fff;}
    #CloseBtn{background:transparent;border:none;color:#a06060;font-size:15px;padding:2px 10px;border-radius:4px;}
    #CloseBtn:hover{background-color:#aa0000;color:#fff;}
    QListWidget{background-color:rgba(20,5,5,200);border:1px solid rgba(150,40,40,100);border-radius:6px;color:#ffd6d6;outline:none;}
    QListWidget::item{padding:7px 10px;border-bottom:1px solid rgba(150,40,40,30);}
    QListWidget::item:selected{background-color:#5a1212;color:#fff;border-radius:4px;}
    QListWidget::item:hover{background-color:rgba(80,15,15,60);}
    #ActBtn{background-color:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #4a1010,stop:1 #2a0505);border:1px solid #701515;border-radius:6px;padding:8px 16px;color:#ffd6d6;font-size:13px;}
    #ActBtn:hover{background-color:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #6a1a1a,stop:1 #3a0808);border:1px solid #a02020;color:#fff;}
    #PageTitle{font-size:20px;font-weight:bold;color:#e03030;padding-bottom:8px;}
    """


# ─── Main Window ───

class MainWindow(QMainWindow):
    BASE_WIDTH = 960
    EXPANDED_WIDTH = 1340

    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(self.BASE_WIDTH, 580)
        self.setMinimumSize(820, 480)
        self._drag_pos = None

        self.mc_dir = Path(__file__).parent.parent / ".minecraft"
        self.mc_dir.mkdir(exist_ok=True)

        # ─── Загрузка Minecraft шрифта ───
        font_path = Path(__file__).parent.parent / "assets" / "minecraft-rus.ttf"
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            self.mc_font = families[0] if families else "Segoe UI"
        else:
            self.mc_font = "Segoe UI"

        central = QWidget()
        self.setCentralWidget(central)
        main_h = QHBoxLayout(central)
        main_h.setContentsMargins(0, 40, 0, 0)
        main_h.setSpacing(0)

        # LEFT PANEL
        left = QFrame()
        left.setObjectName("LeftPanel")
        left.setFixedWidth(300)
        v = QVBoxLayout(left)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(10)

        lbl = QLabel("AMATERASU")
        lbl.setFont(QFont(self.mc_font, 22, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #e03030;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(lbl)
        v.addSpacing(6)

        v.addWidget(QLabel("Ник:", styleSheet="color:#b07070;font-size:12px;"))
        self.nick_edit = QLineEdit()
        self.nick_edit.setText("Steve")
        self.nick_edit.setMaxLength(16)
        v.addWidget(self.nick_edit)

        v.addWidget(QLabel("Версия:", styleSheet="color:#b07070;font-size:12px;"))
        self.version_combo = QComboBox()
        self.version_combo.setEditable(False)
        v.addWidget(self.version_combo)

        self.chk_def = QCheckBox("Отложенный запуск")
        v.addWidget(self.chk_def)
        self.chk_upd = QCheckBox("Обновить клиент")
        self.chk_upd.setChecked(True)
        v.addWidget(self.chk_upd)

        self.play_progress = QProgressBar()
        self.play_progress.setMaximumHeight(18)
        self.play_progress.setTextVisible(True)
        self.play_progress.setVisible(False)
        v.addWidget(self.play_progress)

        self.play_btn = QPushButton("▶  ЗАПУСТИТЬ")
        self.play_btn.setObjectName("LaunchBtn")
        self.play_btn.setFont(QFont(self.mc_font, 14, QFont.Weight.Bold))
        self.play_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.play_btn.clicked.connect(self._on_play)

        glow = QGraphicsDropShadowEffect(self.play_btn)
        glow.setColor(QColor(200, 30, 30, 180))
        glow.setBlurRadius(22)
        glow.setOffset(0, 0)
        self.play_btn.setGraphicsEffect(glow)
        v.addWidget(self.play_btn)

        v.addWidget(QLabel("Консоль:", styleSheet="color:#905050;font-size:11px;margin-top:2px;"))
        self.log_edit = QTextEdit()
        self.log_edit.setObjectName("Log")
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumHeight(90)
        v.addWidget(self.log_edit)

        icons_h = QHBoxLayout()
        icons_h.setSpacing(6)
        icons_h.addStretch(1)

        self.btn_info = IconBtn("info", "Информация")
        self.btn_info.clicked.connect(lambda: self.log("Amaterasu Launcher v1.0"))

        self.btn_folder = IconBtn("folder", "Открыть .minecraft")
        self.btn_folder.clicked.connect(self._open_folder)

        self.btn_refresh = IconBtn("refresh", "Обновить версии")
        self.btn_refresh.clicked.connect(self.refresh_main_versions)

        self.btn_menu = IconBtn("menu", "Меню")
        self.btn_menu.clicked.connect(self._show_menu)

        for b in (self.btn_info, self.btn_folder, self.btn_refresh, self.btn_menu):
            icons_h.addWidget(b)
        icons_h.addStretch(1)
        v.addLayout(icons_h)
        v.addStretch(0)

        main_h.addWidget(left)

        # CENTER (GIF)
        bg_path = Path(__file__).parent.parent / "assets" / "bg_amaterasu"
        self.center_gif = GifBg(bg_path)
        self.center_gif.setObjectName("CenterBg")
        main_h.addWidget(self.center_gif, 1)

        # RIGHT PANEL (initially hidden)
        self.right_panel = QFrame()
        self.right_panel.setObjectName("RightPanel")
        self.right_panel.setFixedWidth(360)
        self.right_panel.setVisible(False)

        rv = QVBoxLayout(self.right_panel)
        rv.setContentsMargins(14, 14, 14, 14)
        rv.setSpacing(10)

        self.right_stack = QStackedWidget()
        rv.addWidget(self.right_stack, 1)

        # Right pages
        self._build_right_pages()

        main_h.addWidget(self.right_panel, 0)

        # MENU POPUP
        self.popup = RoundedMenu(self)
        self.popup.page_selected.connect(self._switch_page)

        # TOP BAR
        self._build_title_bar()

        self.setStyleSheet(stylesheet())
        self.refresh_main_versions()

        # ─── Если нет установленных версий — сразу открыть менеджер ───
        if self.version_combo.count() == 0 or self.version_combo.itemText(0) == "Нет установленных":
            QTimer.singleShot(50, lambda: self._switch_page(1))

    def _build_right_pages(self):
        # 0 placeholder
        self.right_stack.addWidget(QWidget())

        # 1: Versions
        ver_page = QWidget()
        vv = QVBoxLayout(ver_page)
        vv.setContentsMargins(0, 0, 0, 0)
        vv.setSpacing(10)

        title = QLabel("Менеджер версий")
        title.setFont(QFont(self.mc_font, 20, QFont.Weight.Bold))
        title.setStyleSheet("color:#e03030;padding-bottom:8px;")
        vv.addWidget(title)

        self.ver_search = QLineEdit()
        self.ver_search.setPlaceholderText("Поиск версии...")
        self.ver_search.textChanged.connect(self._filter_versions)
        vv.addWidget(self.ver_search)

        self.all_versions_list = QListWidget()
        vv.addWidget(self.all_versions_list, 1)

        btn_h = QHBoxLayout()
        btn_back_v = QPushButton("← Назад")
        btn_back_v.setObjectName("ActBtn")
        btn_back_v.clicked.connect(lambda: self._switch_page(0))
        btn_h.addWidget(btn_back_v)
        btn_h.addStretch(1)

        self.btn_download = QPushButton("Скачать выбранную")
        self.btn_download.setObjectName("ActBtn")
        self.btn_download.clicked.connect(self._on_download_version)
        btn_h.addWidget(self.btn_download)
        vv.addLayout(btn_h)

        self.ver_progress = QProgressBar()
        self.ver_progress.setMaximumHeight(18)
        self.ver_progress.setTextVisible(True)
        self.ver_progress.setVisible(False)
        vv.addWidget(self.ver_progress)

        self.ver_status = QLabel("")
        self.ver_status.setStyleSheet("color:#905050;font-size:12px;")
        vv.addWidget(self.ver_status)
        self.right_stack.addWidget(ver_page)

        # 2: Settings
        set_page = QWidget()
        sv = QVBoxLayout(set_page)
        sv.setContentsMargins(0, 0, 0, 0)
        sv.setSpacing(12)

        title2 = QLabel("Настройки")
        title2.setFont(QFont(self.mc_font, 20, QFont.Weight.Bold))
        title2.setStyleSheet("color:#e03030;padding-bottom:8px;")
        sv.addWidget(title2)

        sv.addWidget(QLabel("Путь к Java (пусто = авто):", styleSheet="color:#b07070;font-size:12px;"))
        self.set_java = QLineEdit()
        self.set_java.setText(self.settings.get("java_path", ""))
        sv.addWidget(self.set_java)

        sv.addWidget(QLabel("RAM:", styleSheet="color:#b07070;font-size:12px;"))
        self.set_ram = QComboBox()
        self.set_ram.addItems(["1G","2G","3G","4G","6G","8G","12G","16G"])
        self.set_ram.setCurrentText(self.settings.get("ram", "2G"))
        sv.addWidget(self.set_ram)

        dim = QHBoxLayout()
        dim.addWidget(QLabel("Ширина окна MC:", styleSheet="color:#b07070;font-size:12px;"))
        self.set_w = QLineEdit()
        self.set_w.setText(str(self.settings.get("window_width", 1000)))
        self.set_w.setFixedWidth(80)
        dim.addWidget(self.set_w)
        dim.addWidget(QLabel("Высота:", styleSheet="color:#b07070;font-size:12px;"))
        self.set_h = QLineEdit()
        self.set_h.setText(str(self.settings.get("window_height", 600)))
        self.set_h.setFixedWidth(80)
        dim.addStretch(1)
        sv.addLayout(dim)

        btn_h = QHBoxLayout()
        btn_back_s = QPushButton("← Назад")
        btn_back_s.setObjectName("ActBtn")
        btn_back_s.clicked.connect(lambda: self._switch_page(0))
        btn_save = QPushButton("Сохранить")
        btn_save.setObjectName("ActBtn")
        btn_save.clicked.connect(self._save_settings)
        btn_h.addWidget(btn_back_s)
        btn_h.addWidget(btn_save)
        btn_h.addStretch(1)
        sv.addLayout(btn_h)
        sv.addStretch(1)
        self.right_stack.addWidget(set_page)

        self._all_versions_raw = []
        self._load_releases()

    def _build_title_bar(self):
        self.title_bar = QWidget(self.centralWidget())
        self.title_bar.setObjectName("TopBar")
        self.title_bar.setGeometry(0, 0, self.width(), 40)

        h = QHBoxLayout(self.title_bar)
        h.setContentsMargins(14, 0, 6, 0)
        h.setSpacing(0)

        lbl = QLabel("Amaterasu Launcher")
        lbl.setStyleSheet("color:#e03030;font-size:14px;font-weight:bold;")
        h.addWidget(lbl)
        h.addStretch(1)

        btn_min = QPushButton("−")
        btn_min.setObjectName("WinBtn")
        btn_min.setFixedSize(40, 30)
        btn_min.clicked.connect(self.showMinimized)

        btn_close = QPushButton("✕")
        btn_close.setObjectName("CloseBtn")
        btn_close.setFixedSize(40, 30)
        btn_close.clicked.connect(self.close)

        for b in (btn_min, btn_close):
            h.addWidget(b)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "title_bar"):
            self.title_bar.setFixedWidth(self.width())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 40:
            self._drag_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self._drag_pos = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def _show_menu(self):
        pos = self.btn_menu.mapToGlobal(QPoint(-170, self.btn_menu.height() + 4))
        self.popup.move(pos)
        self.popup.show()

    def _switch_page(self, idx: int):
        self.popup.hide()
        if idx == 0:
            if self.right_panel.isVisible():
                self.right_panel.setVisible(False)
                geo = self.geometry()
                self.setGeometry(geo.x() + (geo.width() - self.BASE_WIDTH)//2, geo.y(),
                                 self.BASE_WIDTH, geo.height())
        else:
            self.right_stack.setCurrentIndex(idx)
            if not self.right_panel.isVisible():
                self.right_panel.setVisible(True)
                geo = self.geometry()
                self.setGeometry(geo.x() + (geo.width() - self.EXPANDED_WIDTH)//2, geo.y(),
                                 self.EXPANDED_WIDTH, geo.height())

    def log(self, text: str):
        self.log_edit.append(text)
        self.log_edit.verticalScrollBar().setValue(self.log_edit.verticalScrollBar().maximum())

    def _open_folder(self):
        import os
        os.startfile(self.mc_dir)
        self.log(f"📁 {self.mc_dir}")

    def refresh_main_versions(self):
        self.version_combo.clear()
        installed = get_installed_versions_list(self.mc_dir)
        if installed:
            self.version_combo.addItems(installed)
            self.log(f"📋 Установлено: {len(installed)}")
        else:
            self.version_combo.addItem("Нет установленных")
            self.log("⚠️ Нет установленных — скачай в Менеджере версий")

    def _on_play(self):
        version = self.version_combo.currentText().strip()
        username = self.nick_edit.text().strip()
        if not version or version.startswith("Нет") or not username:
            self.log("⚠️ Заполни версию и ник")
            return

        self.log(f"📦 {version}...")
        self.play_btn.setEnabled(False)
        self.play_btn.setText("⏳  ЗАГРУЗКА...")
        self.play_progress.setVisible(True)
        self.play_progress.setMaximum(0)
        self.play_progress.setValue(0)
        self.play_progress.setFormat("Подготовка...")

        self.inst_thread = InstallThread(version, username, self.mc_dir, self.settings, self)
        self.inst_thread.log_signal.connect(self.log)
        self.inst_thread.progress_signal.connect(self._on_play_progress)
        self.inst_thread.finished_signal.connect(self._on_play_done)
        self.inst_thread.error_signal.connect(self._on_play_error)
        self.inst_thread.start()

    def _on_play_progress(self, cur: int, tot: int):
        if tot > 0:
            self.play_progress.setMaximum(tot)
            self.play_progress.setValue(cur)
            self.play_progress.setFormat(f"%p%  ({cur}/{tot})")
        else:
            self.play_progress.setFormat("Загрузка...")

    def _on_play_done(self):
        self.play_btn.setEnabled(True)
        self.play_btn.setText("▶  ЗАПУСТИТЬ")
        self.play_progress.setVisible(False)

    def _on_play_error(self, msg: str):
        self.log(f"❌ {msg}")
        self.play_btn.setEnabled(True)
        self.play_btn.setText("▶  ЗАПУСТИТЬ")
        self.play_progress.setVisible(False)

    def _load_releases(self):
        self.all_versions_list.clear()
        self._all_versions_raw = []
        try:
            for v in get_version_list():
                if v.get("type") == "release":
                    self._all_versions_raw.append(v)
                    self.all_versions_list.addItem(v["id"])
            self.ver_status.setText(f"Загружено {len(self._all_versions_raw)} релизов")
        except Exception as e:
            self.ver_status.setText(f"Ошибка: {e}")

    def _filter_versions(self, text: str):
        self.all_versions_list.clear()
        for v in self._all_versions_raw:
            if text.lower() in v["id"].lower():
                self.all_versions_list.addItem(v["id"])

    def _on_download_version(self):
        item = self.all_versions_list.currentItem()
        if not item:
            self.ver_status.setText("Выбери версию из списка")
            return
        ver = item.text()
        self.ver_status.setText(f"Скачивание {ver}...")
        self.btn_download.setEnabled(False)
        self.ver_progress.setVisible(True)
        self.ver_progress.setMaximum(0)
        self.ver_progress.setValue(0)

        # ─── БЛОКИРУЕМ кнопку ЗАПУСТИТЬ пока идёт загрузка ───
        self.play_btn.setEnabled(False)
        self.play_btn.setText("⏳  Ожидание загрузки...")

        self.dl_thread = DownloadThread(ver, self.mc_dir, self)
        self.dl_thread.log_signal.connect(self.log)
        self.dl_thread.progress_signal.connect(self._on_ver_progress)
        self.dl_thread.finished_signal.connect(lambda: (
            self.ver_status.setText(f"✅ {ver} установлена"),
            self.ver_progress.setVisible(False),
            self.btn_download.setEnabled(True),
            self.play_btn.setEnabled(True),
            self.play_btn.setText("▶  ЗАПУСТИТЬ"),
            self.refresh_main_versions()
        ))
        self.dl_thread.error_signal.connect(lambda msg: (
            self.ver_status.setText(f"❌ {msg}"),
            self.ver_progress.setVisible(False),
            self.btn_download.setEnabled(True),
            self.play_btn.setEnabled(True),
            self.play_btn.setText("▶  ЗАПУСТИТЬ")
        ))
        self.dl_thread.start()

    def _on_ver_progress(self, cur: int, tot: int):
        if tot > 0:
            self.ver_progress.setMaximum(tot)
            self.ver_progress.setValue(cur)
            self.ver_progress.setFormat(f"%p%  ({cur}/{tot})")
        else:
            self.ver_progress.setFormat("Загрузка...")

    def _save_settings(self):
        self.settings["java_path"] = self.set_java.text().strip()
        self.settings["ram"] = self.set_ram.currentText()
        try:
            self.settings["window_width"] = int(self.set_w.text())
            self.settings["window_height"] = int(self.set_h.text())
        except ValueError:
            pass
        save_settings(self.settings)
        self.log("💾 Настройки сохранены")
        self._switch_page(0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
