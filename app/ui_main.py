from __future__ import annotations

import calendar
import datetime
import os
import sys
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import QSettings, QSize, Qt, QTimer
from PyQt6.QtGui import (
    QAction,
    QColor,
    QDragEnterEvent,
    QDropEvent,
    QIcon,
    QImageReader,
    QKeySequence,
    QPixmap,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from metadata import (
    SUPPORTED_EXTENSIONS,
    PhotoMetadata,
    apply_photo_date,
    read_photo_dates,
    restore_photo_dates,
)


MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr",
    "May", "Jun", "Jul", "Aug",
    "Sep", "Oct", "Nov", "Dec",
]

FULL_MONTH_NAMES = [
    "January", "February", "March", "April",
    "May", "June", "July", "August",
    "September", "October", "November", "December",
]

DECADES = [1910, 1920, 1930, 1940, 1950, 1960, 1970, 1980, 1990, 2000, 2010, 2020]


@dataclass
class UndoEntry:
    """Stores a single apply operation (possibly across multiple files) for Undo."""

    changes: list[tuple[str, PhotoMetadata]]


def load_pixmap_oriented(path: str, max_size: Optional[QSize] = None) -> QPixmap:
    """Load an image with EXIF auto-orientation and optional fast scaled decoding."""
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    if max_size is not None and reader.size().isValid():
        scaled = reader.size().scaled(max_size, Qt.AspectRatioMode.KeepAspectRatio)
        reader.setScaledSize(scaled)
    image = reader.read()
    if image.isNull():
        return QPixmap()
    return QPixmap.fromImage(image)


class ImagePreviewLabel(QLabel):
    """QLabel that smoothly scales its current QPixmap to fit available space."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._source_pixmap = QPixmap()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(260, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_photo(self, pixmap: QPixmap) -> None:
        self._source_pixmap = pixmap
        self._update_scaled()

    def clear_photo(self, text: str = "") -> None:
        self._source_pixmap = QPixmap()
        super().clear()
        if text:
            self.setText(text)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._update_scaled()

    def _update_scaled(self) -> None:
        if self._source_pixmap.isNull():
            return
        target_size = self.size() - QSize(16, 16)
        if target_size.width() <= 0 or target_size.height() <= 0:
            return
        scaled = self._source_pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        super().setPixmap(scaled)


class PhotoDateChangerWindow(QMainWindow):
    """Clean, fast UI for dating scanned photos individually or in batches."""

    def __init__(self, initial_paths: Optional[list[str]] = None) -> None:
        super().__init__()
        self.setWindowTitle("Photo Date Changer")
        if hasattr(sys, "_MEIPASS"):
            icon_path = os.path.join(sys._MEIPASS, "assets", "app_icon.ico")
        else:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            icon_path = os.path.join(project_root, "assets", "app_icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.resize(1180, 740)
        self.setMinimumSize(940, 620)
        self.setAcceptDrops(True)

        self._photo_paths: list[str] = []
        self._metadata_cache: dict[str, PhotoMetadata] = {}
        self._undo_stack: list[UndoEntry] = []
        self._recent_dates: list[tuple[datetime.datetime, str]] = []
        self._settings = QSettings("PhotoDateChanger", "PhotoDateChanger")
        self._dark_mode: bool = self._settings.value("dark_mode", False, type=bool)

        # Picker state
        self._selected_decade: int = 1970
        self._selected_year: int = 1970
        self._selected_month: Optional[int] = None  # 1..12 or None
        self._selected_day: Optional[int] = None    # 1..31 or None
        self._precision_hint: str = "decade"        # "decade" | "year" | "month" | "day"

        self._build_ui()
        self._apply_styles()
        self._bind_shortcuts()
        self._sync_picker_ui()

        if initial_paths:
            QTimer.singleShot(50, lambda: self.add_paths(initial_paths))

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(10)

        # Top toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title_lbl = QLabel("Photo Date Changer")
        title_lbl.setObjectName("appTitle")
        subtitle_lbl = QLabel("Drag & drop photos or folders, pick a decade, year, or date, and apply.")
        subtitle_lbl.setObjectName("appSubtitle")
        title_box.addWidget(title_lbl)
        title_box.addWidget(subtitle_lbl)
        toolbar.addLayout(title_box)

        toolbar.addStretch()

        self.btn_add_photos = QPushButton("+ Add Photos")
        self.btn_add_photos.clicked.connect(self._on_add_photos)
        toolbar.addWidget(self.btn_add_photos)

        self.btn_open_folder = QPushButton("Open Folder")
        self.btn_open_folder.clicked.connect(self._on_open_folder)
        toolbar.addWidget(self.btn_open_folder)

        self.btn_clear_list = QPushButton("Clear List")
        self.btn_clear_list.clicked.connect(self._on_clear_list)
        self.btn_clear_list.setEnabled(False)
        toolbar.addWidget(self.btn_clear_list)

        self.btn_undo = QPushButton("Undo")
        self.btn_undo.setToolTip("Undo last date change (Ctrl+Z)")
        self.btn_undo.clicked.connect(self._on_undo)
        self.btn_undo.setEnabled(False)
        toolbar.addWidget(self.btn_undo)

        self.btn_theme = QPushButton("Light Mode" if self._dark_mode else "Dark Mode")
        self.btn_theme.setToolTip("Switch between Light and Dark theme")
        self.btn_theme.clicked.connect(self._on_toggle_theme)
        toolbar.addWidget(self.btn_theme)

        root.addLayout(toolbar)

        # Main 3-pane splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(6)
        root.addWidget(splitter, stretch=1)

        # 1. Left Pane: Photo List
        left_panel = QFrame()
        left_panel.setObjectName("card")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)

        list_header = QHBoxLayout()
        self.lbl_count = QLabel("0 photos")
        self.lbl_count.setObjectName("sectionTitle")
        list_header.addWidget(self.lbl_count)
        list_header.addStretch()

        self.btn_select_all = QPushButton("All")
        self.btn_select_all.setObjectName("smallBtn")
        self.btn_select_all.setToolTip("Select all photos (Ctrl+A)")
        self.btn_select_all.clicked.connect(self._on_select_all)
        list_header.addWidget(self.btn_select_all)

        self.btn_select_undated = QPushButton("Undated")
        self.btn_select_undated.setObjectName("smallBtn")
        self.btn_select_undated.setToolTip("Select all photos without an EXIF date")
        self.btn_select_undated.clicked.connect(self._on_select_undated)
        list_header.addWidget(self.btn_select_undated)
        left_layout.addLayout(list_header)

        self.photo_list = QListWidget()
        self.photo_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.photo_list.setIconSize(QSize(48, 48))
        self.photo_list.setSpacing(3)
        self.photo_list.setUniformItemSizes(False)
        self.photo_list.itemSelectionChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self.photo_list, stretch=1)

        splitter.addWidget(left_panel)

        # 2. Center Pane: Preview & Info
        center_panel = QFrame()
        center_panel.setObjectName("card")
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(10, 10, 10, 10)
        center_layout.setSpacing(8)

        self.batch_banner = QLabel("")
        self.batch_banner.setObjectName("batchBanner")
        self.batch_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.batch_banner.hide()
        center_layout.addWidget(self.batch_banner)

        preview_mat = QFrame()
        preview_mat.setObjectName("previewMat")
        mat_layout = QVBoxLayout(preview_mat)
        mat_layout.setContentsMargins(6, 6, 6, 6)
        self.preview_label = ImagePreviewLabel()
        self.preview_label.setObjectName("previewText")
        self.preview_label.clear_photo("Drop photos or a folder here\nto get started")
        mat_layout.addWidget(self.preview_label)
        center_layout.addWidget(preview_mat, stretch=1)

        # Metadata & navigation footer
        info_row = QHBoxLayout()
        info_row.setSpacing(10)

        meta_col = QVBoxLayout()
        meta_col.setSpacing(2)
        self.lbl_filename = QLabel("No photo selected")
        self.lbl_filename.setObjectName("metaFilename")
        self.lbl_meta_dates = QLabel("")
        self.lbl_meta_dates.setObjectName("metaDates")
        meta_col.addWidget(self.lbl_filename)
        meta_col.addWidget(self.lbl_meta_dates)
        info_row.addLayout(meta_col, stretch=1)

        self.btn_prev = QPushButton("← Prev")
        self.btn_prev.clicked.connect(self._on_prev_photo)
        self.btn_prev.setEnabled(False)
        info_row.addWidget(self.btn_prev)

        self.btn_next = QPushButton("Next →")
        self.btn_next.clicked.connect(self._on_next_photo)
        self.btn_next.setEnabled(False)
        info_row.addWidget(self.btn_next)

        center_layout.addLayout(info_row)
        splitter.addWidget(center_panel)

        # 3. Right Pane: Quick Date Picker
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        right_panel = QFrame()
        right_panel.setObjectName("card")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(14, 12, 14, 12)
        right_layout.setSpacing(12)

        # Section 1: Decade
        decade_hdr = QLabel("1. Decade")
        decade_hdr.setObjectName("sectionTitle")
        right_layout.addWidget(decade_hdr)

        decade_grid = QGridLayout()
        decade_grid.setSpacing(5)
        self.decade_buttons: dict[int, QPushButton] = {}
        for idx, dec in enumerate(DECADES):
            btn = QPushButton(f"{dec}s")
            btn.setCheckable(True)
            btn.setObjectName("pillBtn")
            btn.clicked.connect(lambda _checked, d=dec: self._on_decade_clicked(d))
            self.decade_buttons[dec] = btn
            decade_grid.addWidget(btn, idx // 4, idx % 4)
        right_layout.addLayout(decade_grid)

        # Section 2: Year
        year_hdr_row = QHBoxLayout()
        year_hdr = QLabel("2. Year")
        year_hdr.setObjectName("sectionTitle")
        year_hdr_row.addWidget(year_hdr)
        year_hdr_row.addStretch()

        self.spin_year = QSpinBox()
        self.spin_year.setRange(1800, 2099)
        self.spin_year.setValue(self._selected_year)
        self.spin_year.setFixedWidth(84)
        self.spin_year.valueChanged.connect(self._on_year_spin_changed)
        year_hdr_row.addWidget(self.spin_year)
        right_layout.addLayout(year_hdr_row)

        year_grid = QGridLayout()
        year_grid.setSpacing(5)
        self.year_buttons: list[QPushButton] = []
        for idx in range(10):
            btn = QPushButton(str(self._selected_decade + idx))
            btn.setCheckable(True)
            btn.setObjectName("pillBtn")
            btn.clicked.connect(lambda _checked, offset=idx: self._on_year_btn_clicked(offset))
            self.year_buttons.append(btn)
            year_grid.addWidget(btn, idx // 5, idx % 5)
        right_layout.addLayout(year_grid)

        # Section 3: Month (Optional)
        month_hdr_row = QHBoxLayout()
        month_hdr = QLabel("3. Month (optional)")
        month_hdr.setObjectName("sectionTitle")
        month_hdr_row.addWidget(month_hdr)
        month_hdr_row.addStretch()

        self.btn_clear_month = QPushButton("Clear")
        self.btn_clear_month.setObjectName("linkBtn")
        self.btn_clear_month.clicked.connect(self._on_clear_month)
        month_hdr_row.addWidget(self.btn_clear_month)
        right_layout.addLayout(month_hdr_row)

        month_grid = QGridLayout()
        month_grid.setSpacing(5)
        self.month_buttons: dict[int, QPushButton] = {}
        for m_idx, name in enumerate(MONTH_NAMES, start=1):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setObjectName("pillBtn")
            btn.clicked.connect(lambda _checked, m=m_idx: self._on_month_clicked(m))
            self.month_buttons[m_idx] = btn
            month_grid.addWidget(btn, (m_idx - 1) // 4, (m_idx - 1) % 4)
        right_layout.addLayout(month_grid)

        # Section 4: Day (Optional)
        day_row = QHBoxLayout()
        day_hdr = QLabel("4. Day (optional)")
        day_hdr.setObjectName("sectionTitle")
        day_row.addWidget(day_hdr)
        day_row.addStretch()

        self.combo_day = QComboBox()
        self.combo_day.setFixedWidth(135)
        self._populate_day_combo()
        self.combo_day.currentIndexChanged.connect(self._on_day_changed)
        day_row.addWidget(self.combo_day)
        right_layout.addLayout(day_row)

        # Date Preview Card
        preview_card = QFrame()
        preview_card.setObjectName("datePreviewCard")
        pv_layout = QVBoxLayout(preview_card)
        pv_layout.setContentsMargins(12, 10, 12, 10)
        pv_layout.setSpacing(2)

        pv_caption = QLabel("Date to apply:")
        pv_caption.setObjectName("datePreviewCaption")
        self.lbl_target_date = QLabel("1970-01-01")
        self.lbl_target_date.setObjectName("datePreviewValue")
        self.lbl_target_desc = QLabel("1970s (approx. Jan 1, 1970)")
        self.lbl_target_desc.setObjectName("datePreviewDesc")
        pv_layout.addWidget(pv_caption)
        pv_layout.addWidget(self.lbl_target_date)
        pv_layout.addWidget(self.lbl_target_desc)
        right_layout.addWidget(preview_card)

        # Recent Dates
        self.recent_container = QWidget()
        recent_layout = QVBoxLayout(self.recent_container)
        recent_layout.setContentsMargins(0, 0, 0, 0)
        recent_layout.setSpacing(4)
        recent_hdr = QLabel("Recent dates:")
        recent_hdr.setObjectName("smallMuted")
        recent_layout.addWidget(recent_hdr)
        self.recent_buttons_row = QHBoxLayout()
        self.recent_buttons_row.setSpacing(5)
        recent_layout.addLayout(self.recent_buttons_row)
        self.recent_container.hide()
        right_layout.addWidget(self.recent_container)

        # Options
        self.chk_file_times = QCheckBox("Also update file Created & Modified dates")
        self.chk_file_times.setChecked(True)
        right_layout.addWidget(self.chk_file_times)

        right_layout.addStretch()

        # Action Buttons
        self.btn_apply_next = QPushButton("Apply && Next →")
        self.btn_apply_next.setObjectName("primaryBtn")
        self.btn_apply_next.setMinimumHeight(40)
        self.btn_apply_next.setToolTip("Apply date and advance to next photo (Ctrl+Enter)")
        self.btn_apply_next.clicked.connect(lambda: self._apply_to_selection(advance=True))
        self.btn_apply_next.setEnabled(False)
        right_layout.addWidget(self.btn_apply_next)

        self.btn_apply = QPushButton("Apply to Selected")
        self.btn_apply.setMinimumHeight(34)
        self.btn_apply.setToolTip("Apply date to selected photo(s) (Ctrl+S)")
        self.btn_apply.clicked.connect(lambda: self._apply_to_selection(advance=False))
        self.btn_apply.setEnabled(False)
        right_layout.addWidget(self.btn_apply)

        right_scroll.setWidget(right_panel)
        right_scroll.setMinimumWidth(330)
        right_scroll.setMaximumWidth(390)
        splitter.addWidget(right_scroll)

        splitter.setSizes([270, 540, 340])

        # Status bar
        self.statusBar().showMessage("Ready — drag & drop photos or open a folder.")

    def _on_toggle_theme(self) -> None:
        self._dark_mode = not self._dark_mode
        self._settings.setValue("dark_mode", self._dark_mode)
        self.btn_theme.setText("Light Mode" if self._dark_mode else "Dark Mode")
        self._apply_styles()
        for i in range(self.photo_list.count()):
            item = self.photo_list.item(i)
            path = item.data(Qt.ItemDataRole.UserRole)
            meta = self._metadata_cache.get(path)
            if meta is not None:
                self._format_list_item(item, path, meta)

    def _apply_styles(self) -> None:
        if self._dark_mode:
            c = {
                "bg": "#111317",
                "fg": "#E5E7EB",
                "card_bg": "#1A1D24",
                "card_border": "#2B303B",
                "mat_bg": "#0B0D10",
                "preview_text": "#6B7280",
                "title": "#F9FAFB",
                "subtitle": "#9CA3AF",
                "section": "#D1D5DB",
                "muted": "#9CA3AF",
                "meta_fn": "#F3F4F6",
                "meta_dates": "#9CA3AF",
                "batch_bg": "#1E293B",
                "batch_fg": "#93C5FD",
                "batch_border": "#334155",
                "pv_bg": "#172554",
                "pv_border": "#1E40AF",
                "pv_cap": "#93C5FD",
                "pv_val": "#EFF6FF",
                "pv_desc": "#BFDBFE",
                "btn_bg": "#232730",
                "btn_border": "#374151",
                "btn_fg": "#E5E7EB",
                "btn_hover_bg": "#2D333F",
                "btn_hover_border": "#4B5563",
                "btn_pressed": "#1F242D",
                "btn_dis_fg": "#6B7280",
                "btn_dis_bg": "#181B21",
                "btn_dis_border": "#262A33",
                "pri_bg": "#2563EB",
                "pri_border": "#1D4ED8",
                "pri_hover": "#3B82F6",
                "pri_dis_bg": "#1E3A8A",
                "pri_dis_fg": "#93C5FD",
                "pill_bg": "#232730",
                "pill_border": "#323846",
                "pill_hover_bg": "#1E293B",
                "pill_hover_border": "#3B82F6",
                "link_fg": "#60A5FA",
                "list_bg": "#15181E",
                "list_border": "#2B303B",
                "list_sel_bg": "#1E3A8A",
                "list_sel_fg": "#EFF6FF",
                "input_bg": "#15181E",
                "input_border": "#374151",
            }
        else:
            c = {
                "bg": "#F4F5F7",
                "fg": "#1F2328",
                "card_bg": "#FFFFFF",
                "card_border": "#E1E4E8",
                "mat_bg": "#1C1F24",
                "preview_text": "#9BA3AF",
                "title": "#111827",
                "subtitle": "#6B7280",
                "section": "#374151",
                "muted": "#6B7280",
                "meta_fn": "#111827",
                "meta_dates": "#4B5563",
                "batch_bg": "#EFF6FF",
                "batch_fg": "#1D4ED8",
                "batch_border": "#BFDBFE",
                "pv_bg": "#F0F7FF",
                "pv_border": "#BAE6FD",
                "pv_cap": "#0369A1",
                "pv_val": "#0C4A6E",
                "pv_desc": "#0369A1",
                "btn_bg": "#FFFFFF",
                "btn_border": "#D1D5DB",
                "btn_fg": "#1F2937",
                "btn_hover_bg": "#F9FAFB",
                "btn_hover_border": "#9CA3AF",
                "btn_pressed": "#F3F4F6",
                "btn_dis_fg": "#9CA3AF",
                "btn_dis_bg": "#F9FAFB",
                "btn_dis_border": "#E5E7EB",
                "pri_bg": "#2563EB",
                "pri_border": "#1D4ED8",
                "pri_hover": "#1D4ED8",
                "pri_dis_bg": "#93C5FD",
                "pri_dis_fg": "#FFFFFF",
                "pill_bg": "#F9FAFB",
                "pill_border": "#E5E7EB",
                "pill_hover_bg": "#EFF6FF",
                "pill_hover_border": "#93C5FD",
                "link_fg": "#2563EB",
                "list_bg": "#FFFFFF",
                "list_border": "#E5E7EB",
                "list_sel_bg": "#DBEAFE",
                "list_sel_fg": "#1E3A8A",
                "input_bg": "#FFFFFF",
                "input_border": "#D1D5DB",
            }

        self.setStyleSheet(
            f"""
            QMainWindow, QWidget {{
                background-color: {c['bg']};
                color: {c['fg']};
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 13px;
            }}
            QFrame#card {{
                background-color: {c['card_bg']};
                border: 1px solid {c['card_border']};
                border-radius: 10px;
            }}
            QFrame#previewMat {{
                background-color: {c['mat_bg']};
                border-radius: 8px;
            }}
            QLabel#previewText {{
                color: {c['preview_text']};
                font-size: 15px;
                background: transparent;
            }}
            QLabel#appTitle {{
                font-size: 18px;
                font-weight: 700;
                color: {c['title']};
            }}
            QLabel#appSubtitle {{
                font-size: 12px;
                color: {c['subtitle']};
            }}
            QLabel#sectionTitle {{
                font-size: 13px;
                font-weight: 600;
                color: {c['section']};
                background: transparent;
            }}
            QLabel#smallMuted {{
                font-size: 11px;
                color: {c['muted']};
                background: transparent;
            }}
            QLabel#metaFilename {{
                font-size: 13px;
                font-weight: 600;
                color: {c['meta_fn']};
                background: transparent;
            }}
            QLabel#metaDates {{
                font-size: 12px;
                color: {c['meta_dates']};
                background: transparent;
            }}
            QLabel#batchBanner {{
                background-color: {c['batch_bg']};
                color: {c['batch_fg']};
                border: 1px solid {c['batch_border']};
                border-radius: 6px;
                padding: 5px 10px;
                font-weight: 600;
            }}
            QFrame#datePreviewCard {{
                background-color: {c['pv_bg']};
                border: 1px solid {c['pv_border']};
                border-radius: 8px;
            }}
            QLabel#datePreviewCaption {{
                font-size: 11px;
                font-weight: 600;
                color: {c['pv_cap']};
                background: transparent;
            }}
            QLabel#datePreviewValue {{
                font-size: 20px;
                font-weight: 700;
                color: {c['pv_val']};
                background: transparent;
            }}
            QLabel#datePreviewDesc {{
                font-size: 12px;
                color: {c['pv_desc']};
                background: transparent;
            }}
            QPushButton {{
                background-color: {c['btn_bg']};
                border: 1px solid {c['btn_border']};
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 500;
                color: {c['btn_fg']};
            }}
            QPushButton:hover {{
                background-color: {c['btn_hover_bg']};
                border-color: {c['btn_hover_border']};
            }}
            QPushButton:pressed {{
                background-color: {c['btn_pressed']};
            }}
            QPushButton:disabled {{
                color: {c['btn_dis_fg']};
                background-color: {c['btn_dis_bg']};
                border-color: {c['btn_dis_border']};
            }}
            QPushButton#primaryBtn {{
                background-color: {c['pri_bg']};
                border: 1px solid {c['pri_border']};
                color: #FFFFFF;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton#primaryBtn:hover {{
                background-color: {c['pri_hover']};
            }}
            QPushButton#primaryBtn:disabled {{
                background-color: {c['pri_dis_bg']};
                border-color: {c['pri_dis_bg']};
                color: {c['pri_dis_fg']};
            }}
            QPushButton#pillBtn {{
                padding: 6px 4px;
                border-radius: 6px;
                background-color: {c['pill_bg']};
                border: 1px solid {c['pill_border']};
                font-size: 12px;
            }}
            QPushButton#pillBtn:hover {{
                background-color: {c['pill_hover_bg']};
                border-color: {c['pill_hover_border']};
            }}
            QPushButton#pillBtn:checked {{
                background-color: {c['pri_bg']};
                border-color: {c['pri_border']};
                color: #FFFFFF;
                font-weight: 600;
            }}
            QPushButton#smallBtn {{
                padding: 3px 8px;
                font-size: 11px;
            }}
            QPushButton#linkBtn {{
                border: none;
                background: transparent;
                color: {c['link_fg']};
                padding: 2px 4px;
                font-size: 12px;
            }}
            QPushButton#linkBtn:hover {{
                text-decoration: underline;
            }}
            QListWidget {{
                border: 1px solid {c['list_border']};
                border-radius: 6px;
                background-color: {c['list_bg']};
                outline: none;
            }}
            QListWidget::item {{
                padding: 4px 6px;
                border-radius: 4px;
            }}
            QListWidget::item:selected {{
                background-color: {c['list_sel_bg']};
                color: {c['list_sel_fg']};
            }}
            QSpinBox, QComboBox {{
                background-color: {c['input_bg']};
                border: 1px solid {c['input_border']};
                border-radius: 6px;
                padding: 4px 8px;
                color: {c['fg']};
            }}
            QComboBox QAbstractItemView {{
                background-color: {c['card_bg']};
                color: {c['fg']};
                selection-background-color: {c['list_sel_bg']};
                selection-color: {c['list_sel_fg']};
            }}
            QCheckBox {{
                background: transparent;
                spacing: 6px;
            }}
            QStatusBar {{
                background-color: {c['bg']};
                color: {c['muted']};
            }}
            """
        )

    def _bind_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(
            lambda: self._apply_to_selection(advance=True)
        )
        QShortcut(QKeySequence("Ctrl+Enter"), self).activated.connect(
            lambda: self._apply_to_selection(advance=True)
        )
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(
            lambda: self._apply_to_selection(advance=False)
        )
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self._on_undo)
        QShortcut(QKeySequence("Ctrl+A"), self).activated.connect(self._on_select_all)

    # ------------------------------------------------------------------
    # Drag & Drop
    # ------------------------------------------------------------------
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # type: ignore[override]
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls if u.isLocalFile()]
        if paths:
            self.add_paths(paths)

    # ------------------------------------------------------------------
    # Loading Photos
    # ------------------------------------------------------------------
    def _on_add_photos(self) -> None:
        ext_filter = "Images (" + " ".join(f"*{ext}" for ext in sorted(SUPPORTED_EXTENSIONS)) + ")"
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Photos",
            "",
            f"{ext_filter};;All Files (*)",
        )
        if files:
            self.add_paths(files)

    def _on_open_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Folder of Photos")
        if folder:
            self.add_paths([folder])

    def _on_clear_list(self) -> None:
        self._photo_paths.clear()
        self._metadata_cache.clear()
        self.photo_list.clear()
        self.preview_label.clear_photo("Drop photos or a folder here\nto get started")
        self.lbl_filename.setText("No photo selected")
        self.lbl_meta_dates.setText("")
        self.batch_banner.hide()
        self._update_counts_and_buttons()

    def add_paths(self, paths: list[str]) -> None:
        discovered: list[str] = []
        for p in paths:
            if os.path.isdir(p):
                for root_dir, _dirs, files in os.walk(p):
                    for fname in sorted(files):
                        if os.path.splitext(fname)[1].lower() in SUPPORTED_EXTENSIONS:
                            discovered.append(os.path.join(root_dir, fname))
            elif os.path.isfile(p):
                if os.path.splitext(p)[1].lower() in SUPPORTED_EXTENSIONS:
                    discovered.append(p)

        existing = set(self._photo_paths)
        added = 0
        for path in discovered:
            norm = os.path.normpath(path)
            if norm in existing:
                continue
            existing.add(norm)
            self._photo_paths.append(norm)
            meta = read_photo_dates(norm)
            self._metadata_cache[norm] = meta
            self._add_list_item(norm, meta)
            added += 1

        if added > 0 and self.photo_list.count() > 0 and not self.photo_list.selectedItems():
            self.photo_list.setCurrentRow(0)

        self._update_counts_and_buttons()
        self.statusBar().showMessage(f"Added {added} photo(s). Total: {len(self._photo_paths)}.")

    def _add_list_item(self, path: str, meta: PhotoMetadata) -> None:
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, path)
        thumb = load_pixmap_oriented(path, QSize(48, 48))
        if not thumb.isNull():
            item.setIcon(QIcon(thumb))
        self._format_list_item(item, path, meta)
        self.photo_list.addItem(item)

    def _format_list_item(self, item: QListWidgetItem, path: str, meta: PhotoMetadata) -> None:
        name = os.path.basename(path)
        date_str = meta.display_date
        item.setText(f"{name}\n{date_str}")
        if meta.primary_exif_date:
            item.setForeground(QColor("#4ADE80" if self._dark_mode else "#15803D"))
        else:
            item.setForeground(QColor("#9CA3AF" if self._dark_mode else "#6B7280"))

    # ------------------------------------------------------------------
    # Selection & Preview
    # ------------------------------------------------------------------
    def _on_select_all(self) -> None:
        self.photo_list.selectAll()

    def _on_select_undated(self) -> None:
        self.photo_list.clearSelection()
        first_undated: Optional[int] = None
        for i in range(self.photo_list.count()):
            item = self.photo_list.item(i)
            path = item.data(Qt.ItemDataRole.UserRole)
            meta = self._metadata_cache.get(path)
            if meta and not meta.primary_exif_date:
                item.setSelected(True)
                if first_undated is None:
                    first_undated = i
        if first_undated is not None:
            self.photo_list.scrollToItem(self.photo_list.item(first_undated))

    def _selected_rows(self) -> list[int]:
        return sorted(idx.row() for idx in self.photo_list.selectedIndexes())

    def _on_selection_changed(self) -> None:
        rows = self._selected_rows()
        if not rows:
            self.preview_label.clear_photo("Select a photo to preview")
            self.lbl_filename.setText("No photo selected")
            self.lbl_meta_dates.setText("")
            self.batch_banner.hide()
            self._update_counts_and_buttons()
            return

        if len(rows) > 1:
            self.batch_banner.setText(f"Batch Mode: {len(rows)} photos selected — date will apply to all")
            self.batch_banner.show()
        else:
            self.batch_banner.hide()

        primary_row = self.photo_list.currentRow()
        if primary_row not in rows:
            primary_row = rows[0]

        path = self.photo_list.item(primary_row).data(Qt.ItemDataRole.UserRole)
        pix = load_pixmap_oriented(path, QSize(1400, 1400))
        if pix.isNull():
            self.preview_label.clear_photo("Unable to preview this image")
        else:
            self.preview_label.set_photo(pix)

        meta = self._metadata_cache.get(path) or read_photo_dates(path)
        self.lbl_filename.setText(os.path.basename(path))
        mod_str = meta.file_modified.strftime("%Y-%m-%d") if meta.file_modified else "Unknown"
        exif_str = meta.display_date
        self.lbl_meta_dates.setText(f"EXIF Date: {exif_str}   •   File Modified: {mod_str}")

        self._update_counts_and_buttons()

    def _on_prev_photo(self) -> None:
        row = self.photo_list.currentRow()
        if row > 0:
            self.photo_list.setCurrentRow(row - 1)

    def _on_next_photo(self) -> None:
        row = self.photo_list.currentRow()
        if row < self.photo_list.count() - 1:
            self.photo_list.setCurrentRow(row + 1)

    # ------------------------------------------------------------------
    # Date Picker State & Sync
    # ------------------------------------------------------------------
    def _on_decade_clicked(self, decade: int) -> None:
        self._selected_decade = decade
        self._selected_year = decade
        self._selected_month = None
        self._selected_day = None
        self._precision_hint = "decade"
        self._sync_picker_ui()

    def _on_year_btn_clicked(self, offset: int) -> None:
        self._selected_year = self._selected_decade + offset
        self._precision_hint = self._infer_precision(default="year")
        self._sync_picker_ui()

    def _on_year_spin_changed(self, value: int) -> None:
        self._selected_year = value
        self._selected_decade = (value // 10) * 10
        self._precision_hint = self._infer_precision(default="year")
        self._sync_picker_ui()

    def _on_month_clicked(self, month: int) -> None:
        if self._selected_month == month:
            self._selected_month = None
            self._selected_day = None
            self._precision_hint = "year"
        else:
            self._selected_month = month
            self._precision_hint = "day" if self._selected_day is not None else "month"
        self._sync_picker_ui()

    def _on_clear_month(self) -> None:
        self._selected_month = None
        self._selected_day = None
        self._precision_hint = "year"
        self._sync_picker_ui()

    def _on_day_changed(self, idx: int) -> None:
        if idx <= 0:
            self._selected_day = None
            self._precision_hint = "month" if self._selected_month is not None else "year"
        else:
            self._selected_day = idx
            if self._selected_month is None:
                self._selected_month = 1
            self._precision_hint = "day"
        self._update_date_preview()

    def _infer_precision(self, default: str) -> str:
        if self._selected_day is not None:
            return "day"
        if self._selected_month is not None:
            return "month"
        return default

    def _populate_day_combo(self) -> None:
        prev_day = self._selected_day
        self.combo_day.blockSignals(True)
        self.combo_day.clear()
        self.combo_day.addItem("Unknown (1st)")
        month = self._selected_month or 1
        max_days = calendar.monthrange(self._selected_year, month)[1]
        for d in range(1, max_days + 1):
            self.combo_day.addItem(str(d))
        if prev_day is not None:
            clamped = min(prev_day, max_days)
            self._selected_day = clamped
            self.combo_day.setCurrentIndex(clamped)
        else:
            self.combo_day.setCurrentIndex(0)
        self.combo_day.blockSignals(False)

    def _sync_picker_ui(self) -> None:
        # Decade buttons
        for dec, btn in self.decade_buttons.items():
            btn.setChecked(dec == self._selected_decade)

        # Year spinbox
        self.spin_year.blockSignals(True)
        self.spin_year.setValue(self._selected_year)
        self.spin_year.blockSignals(False)

        # Year buttons for the active decade (if within 1800..2099)
        base_decade = (self._selected_year // 10) * 10
        self._selected_decade = base_decade
        for offset, btn in enumerate(self.year_buttons):
            yr = base_decade + offset
            btn.setText(str(yr))
            btn.setChecked(yr == self._selected_year)

        # Month buttons
        for m_idx, btn in self.month_buttons.items():
            btn.setChecked(self._selected_month == m_idx)
        self.btn_clear_month.setVisible(self._selected_month is not None)

        # Day combo
        self._populate_day_combo()
        self._update_date_preview()

    def _target_datetime_and_desc(self) -> tuple[datetime.datetime, str]:
        year = self._selected_year
        month = self._selected_month or 1
        day = self._selected_day or 1
        max_days = calendar.monthrange(year, month)[1]
        day = min(day, max_days)
        dt = datetime.datetime(year, month, day, 12, 0, 0)

        if self._selected_day is not None and self._selected_month is not None:
            desc = f"Exact date: {FULL_MONTH_NAMES[month - 1]} {day}, {year}"
        elif self._selected_month is not None:
            desc = f"{FULL_MONTH_NAMES[month - 1]} {year} (approx. 1st of month)"
        elif self._precision_hint == "decade" and year % 10 == 0:
            desc = f"{year}s (approx. Jan 1, {year})"
        else:
            desc = f"Year {year} (approx. Jan 1, {year})"
        return dt, desc

    def _update_date_preview(self) -> None:
        dt, desc = self._target_datetime_and_desc()
        self.lbl_target_date.setText(dt.strftime("%Y-%m-%d"))
        self.lbl_target_desc.setText(desc)

    # ------------------------------------------------------------------
    # Recent Dates
    # ------------------------------------------------------------------
    def _record_recent_date(self, dt: datetime.datetime) -> None:
        label = dt.strftime("%Y-%m-%d")
        self._recent_dates = [(d, lbl) for d, lbl in self._recent_dates if lbl != label]
        self._recent_dates.insert(0, (dt, label))
        self._recent_dates = self._recent_dates[:5]
        self._rebuild_recent_buttons()

    def _rebuild_recent_buttons(self) -> None:
        while self.recent_buttons_row.count():
            child = self.recent_buttons_row.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not self._recent_dates:
            self.recent_container.hide()
            return

        for dt, label in self._recent_dates:
            btn = QPushButton(label)
            btn.setObjectName("smallBtn")
            btn.clicked.connect(lambda _c, target=dt: self._apply_recent_preset(target))
            self.recent_buttons_row.addWidget(btn)
        self.recent_buttons_row.addStretch()
        self.recent_container.show()

    def _apply_recent_preset(self, dt: datetime.datetime) -> None:
        self._selected_year = dt.year
        self._selected_decade = (dt.year // 10) * 10
        self._selected_month = dt.month
        self._selected_day = dt.day
        self._precision_hint = "day"
        self._sync_picker_ui()

    # ------------------------------------------------------------------
    # Apply & Undo
    # ------------------------------------------------------------------
    def _apply_to_selection(self, advance: bool) -> None:
        rows = self._selected_rows()
        if not rows:
            return

        target_dt, _ = self._target_datetime_and_desc()
        update_file_times = self.chk_file_times.isChecked()

        undo_changes: list[tuple[str, PhotoMetadata]] = []
        errors: list[str] = []

        for row in rows:
            item = self.photo_list.item(row)
            path = item.data(Qt.ItemDataRole.UserRole)
            try:
                prev = apply_photo_date(path, target_dt, update_file_times=update_file_times)
                undo_changes.append((path, prev))
                new_meta = read_photo_dates(path)
                self._metadata_cache[path] = new_meta
                self._format_list_item(item, path, new_meta)
            except Exception as exc:
                errors.append(f"{os.path.basename(path)}: {exc}")

        if undo_changes:
            self._undo_stack.append(UndoEntry(changes=undo_changes))
            self._record_recent_date(target_dt)
            self.statusBar().showMessage(
                f"Applied {target_dt.strftime('%Y-%m-%d')} to {len(undo_changes)} photo(s)."
            )

        if errors:
            QMessageBox.warning(
                self,
                "Some Photos Could Not Be Updated",
                "\n".join(errors[:10]),
            )

        if advance and rows:
            last_row = rows[-1]
            if last_row + 1 < self.photo_list.count():
                self.photo_list.clearSelection()
                self.photo_list.setCurrentRow(last_row + 1)
            else:
                self._on_selection_changed()
        else:
            self._on_selection_changed()

        self._update_counts_and_buttons()

    def _on_undo(self) -> None:
        if not self._undo_stack:
            return
        entry = self._undo_stack.pop()
        restored = 0
        errors: list[str] = []

        path_to_row = {
            self.photo_list.item(i).data(Qt.ItemDataRole.UserRole): i
            for i in range(self.photo_list.count())
        }

        for path, snapshot in entry.changes:
            try:
                restore_photo_dates(path, snapshot)
                new_meta = read_photo_dates(path)
                self._metadata_cache[path] = new_meta
                if path in path_to_row:
                    self._format_list_item(self.photo_list.item(path_to_row[path]), path, new_meta)
                restored += 1
            except Exception as exc:
                errors.append(f"{os.path.basename(path)}: {exc}")

        self._on_selection_changed()
        self._update_counts_and_buttons()
        self.statusBar().showMessage(f"Undid changes on {restored} photo(s).")

        if errors:
            QMessageBox.warning(self, "Undo Warning", "\n".join(errors[:10]))

    def _update_counts_and_buttons(self) -> None:
        total = len(self._photo_paths)
        dated = sum(1 for p in self._photo_paths if self._metadata_cache.get(p) and self._metadata_cache[p].primary_exif_date)
        self.lbl_count.setText(f"{total} photo{'s' if total != 1 else ''} ({dated} dated)")

        rows = self._selected_rows()
        has_sel = len(rows) > 0
        self.btn_apply.setEnabled(has_sel)
        self.btn_apply_next.setEnabled(has_sel)
        self.btn_clear_list.setEnabled(total > 0)
        self.btn_undo.setEnabled(len(self._undo_stack) > 0)

        if len(rows) > 1:
            self.btn_apply.setText(f"Apply to {len(rows)} Selected")
        else:
            self.btn_apply.setText("Apply to Selected")

        curr = self.photo_list.currentRow()
        self.btn_prev.setEnabled(curr > 0)
        self.btn_next.setEnabled(0 <= curr < self.photo_list.count() - 1)
