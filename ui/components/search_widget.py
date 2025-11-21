from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel
from PySide6.QtCore import Signal, Qt
import qtawesome

from ui.components.music_table import SearchResultTable

class SearchWidget(QWidget):
    search_requested = Signal(str)
    song_preview_requested = Signal(dict, object, int)  # song_info, table, row
    song_download_requested = Signal(dict)
    song_add_to_playlist_requested = Signal(dict, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.song_list = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 10, 0)
        layout.setSpacing(10)

        # 搜索输入区域
        search_layout = QHBoxLayout()
        search_layout.setSpacing(10)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入歌曲名、歌手名搜索，或输入歌单ID(QQ音乐)导入整个歌单...")
        self.search_input.returnPressed.connect(self._on_search)
        self.search_input.setMinimumHeight(40)
        
        self.search_button = QPushButton(qtawesome.icon('fa5s.search', color='#1e1e2e'), "")
        self.search_button.setToolTip("立即搜索")
        self.search_button.clicked.connect(self._on_search)
        self.search_button.setMinimumHeight(40)
        self.search_button.setMaximumWidth(50)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)

        # 搜索结果区域
        search_header = QLabel("搜索结果")
        search_header.setObjectName("section_header")
        search_header.setAlignment(Qt.AlignLeft)
        
        self.result_table = SearchResultTable()
        self.result_table.song_getter = self.get_song_at_row
        self.result_table.song_preview_requested.connect(self._on_song_preview)
        self.result_table.song_download_requested.connect(self.song_download_requested.emit)
        self.result_table.song_add_to_playlist_requested.connect(self.song_add_to_playlist_requested.emit)
        
        layout.addLayout(search_layout)
        layout.addWidget(search_header)
        layout.addWidget(self.result_table)

    def _on_search(self):
        query = self.search_input.text().strip()
        if query:
            self.search_requested.emit(query)

    def _on_song_preview(self, row):
        if 0 <= row < len(self.song_list):
            song_info = self.song_list[row]
            self.song_preview_requested.emit(song_info, self.result_table, row)

    def update_search_results(self, songs):
        self.song_list = songs
        self.result_table.clear()
        for row, song in enumerate(songs):
            self.result_table.add_song(row, song.get('id'), song.get('title'), song.get('singer'))

    def set_search_controls_enabled(self, enabled):
        self.search_input.setEnabled(enabled)
        self.search_button.setEnabled(enabled)

    def get_song_at_row(self, row):
        if 0 <= row < len(self.song_list):
            return self.song_list[row]
        return None

    def set_playlist_manager(self, manager):
        self.result_table.playlist_manager = manager