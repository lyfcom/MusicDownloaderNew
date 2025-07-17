from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QMenu
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QAction
import qtawesome

HIGHLIGHT_COLOR = QColor("#89b4fa")
BASE_BG_COLOR = QColor("#313244")

class MusicTable(QTableWidget):
    song_preview_requested = Signal(int)  # row
    song_download_requested = Signal(dict)  # song_info
    song_add_to_playlist_requested = Signal(dict, str)  # song_info, playlist_name
    song_remove_requested = Signal(int)  # row

    def __init__(self, headers, parent=None):
        super().__init__(0, len(headers), parent)
        self.setHorizontalHeaderLabels(headers)
        self.playlist_manager = None
        self.song_getter = None  # Function to get song at row
        self.setup_table()
        self.setup_context_menu()

    def setup_table(self):
        # 设置表格属性
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        if self.columnCount() > 1:
            self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        if self.columnCount() > 2:
            self.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        
        # 双击事件
        self.itemDoubleClicked.connect(self._on_item_double_clicked)

    def setup_context_menu(self):
        pass  # Will be overridden in subclasses if needed

    def _on_item_double_clicked(self, item):
        self.song_preview_requested.emit(item.row())

    def show_context_menu(self, pos):
        item = self.itemAt(pos)
        if not item or not self.song_getter:
            return
        
        row = item.row()
        song_info = self.song_getter(row)
        if not song_info:
            return
        
        menu = QMenu(self)
        
        # 预览/暂停
        preview_action = QAction(qtawesome.icon('fa5s.play', color='#f0f0f0'), "预览/暂停", self)
        preview_action.triggered.connect(lambda: self.song_preview_requested.emit(row))
        menu.addAction(preview_action)
        
        # 下载
        download_action = QAction(qtawesome.icon('fa5s.download', color='#f0f0f0'), "下载", self)
        download_action.triggered.connect(lambda: self.song_download_requested.emit(song_info))
        menu.addAction(download_action)
        
        # 添加到播放列表 (只在搜索结果中显示)
        if self.playlist_manager and hasattr(self, '_show_add_to_playlist'):
            add_to_menu = QMenu("添加到...", self)
            add_to_menu.setIcon(qtawesome.icon('fa5s.plus', color='#f0f0f0'))
            
            for name in self.playlist_manager.get_playlist_names():
                action = QAction(name, self)
                action.triggered.connect(lambda checked=False, s_info=song_info, p_name=name: 
                                       self.song_add_to_playlist_requested.emit(s_info, p_name))
                add_to_menu.addAction(action)
            
            menu.addMenu(add_to_menu)
        
        # 从播放列表移除 (只在播放列表中显示)
        if hasattr(self, '_show_remove_from_playlist'):
            remove_action = QAction(qtawesome.icon('fa5s.trash', color='#f0f0f0'), "从此列表移除", self)
            remove_action.triggered.connect(lambda: self.song_remove_requested.emit(row))
            menu.addAction(remove_action)
        
        menu.exec(self.mapToGlobal(pos))

    def add_song(self, row, *items):
        if row >= self.rowCount():
            self.setRowCount(row + 1)
        
        for col, item in enumerate(items):
            if col < self.columnCount():
                self.setItem(row, col, QTableWidgetItem(str(item)))

    def clear(self):
        self.setRowCount(0)

    def set_playing_indicator(self, row, highlight=True):
        color = HIGHLIGHT_COLOR if highlight else BASE_BG_COLOR
        for col in range(self.columnCount()):
            item = self.item(row, col)
            if item:
                item.setBackground(color)

    def clear_all_indicators(self):
        for row in range(self.rowCount()):
            self.set_playing_indicator(row, False)

class SearchResultTable(MusicTable):
    def __init__(self, parent=None):
        super().__init__(["序号", "歌曲名", "歌手"], parent)
        self._show_add_to_playlist = True

class PlaylistSongTable(MusicTable):
    def __init__(self, parent=None):
        super().__init__(["歌曲名", "歌手"], parent)
        self._show_remove_from_playlist = True
        
        # 设置播放列表表格的特殊列宽
        header_view = self.horizontalHeader()
        header_view.setSectionResizeMode(QHeaderView.Interactive)
        header_view.setStretchLastSection(True)
        header_view.resizeSection(0, 200)