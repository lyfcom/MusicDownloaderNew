from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, 
                             QStackedWidget, QPushButton, QTextBrowser, QMenu,
                             QInputDialog, QMessageBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
import qtawesome

from ui.components.music_table import PlaylistSongTable

class PlaylistWidget(QWidget):
    playlist_selected = Signal(str)
    playlist_created = Signal(str)
    playlist_deleted = Signal(str)
    playlist_renamed = Signal(str, str)
    playlist_played = Signal(str)
    playlist_downloaded = Signal(str)
    song_preview_requested = Signal(int)
    song_download_requested = Signal(dict)
    song_removed_from_playlist = Signal(int)
    lyrics_view_toggled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.playlist_manager = None
        self.current_playlist_name = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(10)
        
        playlist_header = QLabel("播放列表")
        playlist_header.setObjectName("section_header")
        playlist_header.setAlignment(Qt.AlignLeft)
        layout.addWidget(playlist_header)

        # 堆叠窗口用于切换播放列表和歌词视图
        self.stack = QStackedWidget()
        
        # 播放列表页面
        self._setup_playlist_page()
        
        # 歌词页面
        self._setup_lyrics_page()
        
        layout.addWidget(self.stack)

    def _setup_playlist_page(self):
        playlist_page = QWidget()
        layout = QVBoxLayout(playlist_page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # 播放列表选择器
        self.playlist_list = QListWidget()
        self.playlist_list.itemClicked.connect(self._on_playlist_selected)
        self.playlist_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.playlist_list.customContextMenuRequested.connect(self._show_playlist_context_menu)
        self.playlist_list.setMaximumHeight(120)
        layout.addWidget(self.playlist_list)
        
        # 歌曲标题
        songs_header = QLabel("歌曲")
        songs_header.setObjectName("subsection_header")
        layout.addWidget(songs_header)
        
        # 播放列表歌曲表格
        self.songs_table = PlaylistSongTable()
        self.songs_table.song_getter = self._get_song_at_row
        self.songs_table.song_preview_requested.connect(self.song_preview_requested.emit)
        self.songs_table.song_download_requested.connect(self.song_download_requested.emit)
        self.songs_table.song_remove_requested.connect(self.song_removed_from_playlist.emit)
        layout.addWidget(self.songs_table)
        
        self.stack.addWidget(playlist_page)

    def _setup_lyrics_page(self):
        lyrics_page = QWidget()
        layout = QVBoxLayout(lyrics_page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # 返回按钮
        back_layout = QHBoxLayout()
        back_button = QPushButton(qtawesome.icon('fa5s.arrow-left', color='#cdd6f4'), " 返回播放列表")
        back_button.clicked.connect(self.lyrics_view_toggled.emit)
        back_layout.addWidget(back_button)
        back_layout.addStretch()
        
        # 歌词显示
        self.lyrics_display = QTextBrowser()
        self.lyrics_display.setReadOnly(True)
        self.lyrics_display.setObjectName("lyrics_display")

        layout.addLayout(back_layout)
        layout.addWidget(self.lyrics_display)
        self.stack.addWidget(lyrics_page)

    def _on_playlist_selected(self, item):
        playlist_name = item.text()
        self.current_playlist_name = playlist_name
        self.playlist_selected.emit(playlist_name)

    def _show_playlist_context_menu(self, pos):
        item = self.playlist_list.itemAt(pos)
        
        menu = QMenu(self)
        
        # 新建播放列表
        create_action = QAction(qtawesome.icon('fa5s.plus-square', color='#f0f0f0'), "新建播放列表", self)
        create_action.triggered.connect(self._create_playlist)
        menu.addAction(create_action)
        
        if item:
            playlist_name = item.text()
            
            # 播放此歌单
            play_action = QAction(qtawesome.icon('fa5s.play-circle', color='#f0f0f0'), "播放此歌单", self)
            play_action.triggered.connect(lambda: self.playlist_played.emit(playlist_name))
            menu.addAction(play_action)
            
            menu.addSeparator()
            
            # 重命名
            rename_action = QAction(qtawesome.icon('fa5s.edit', color='#f0f0f0'), "重命名", self)
            rename_action.triggered.connect(lambda: self._rename_playlist(playlist_name))
            menu.addAction(rename_action)
            
            # 删除
            delete_action = QAction(qtawesome.icon('fa5s.trash-alt', color='#f0f0f0'), "删除", self)
            delete_action.triggered.connect(lambda: self._delete_playlist(playlist_name))
            menu.addAction(delete_action)
            
            menu.addSeparator()
            
            # 下载此列表
            download_action = QAction(qtawesome.icon('fa5s.cloud-download-alt', color='#f0f0f0'), "下载此列表", self)
            download_action.triggered.connect(lambda: self.playlist_downloaded.emit(playlist_name))
            menu.addAction(download_action)
        
        menu.exec(self.playlist_list.mapToGlobal(pos))

    def _create_playlist(self):
        name, ok = QInputDialog.getText(self, "新建播放列表", "请输入列表名称:")
        if not ok:
            return
        name = name.strip()
        if name:
            self.playlist_created.emit(name)
        else:
            QMessageBox.warning(self, "无效名称", "播放列表名称不能为空。")

    def _rename_playlist(self, old_name):
        new_name, ok = QInputDialog.getText(self, "重命名播放列表", "请输入新名称:", text=old_name)
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name:
            QMessageBox.warning(self, "无效名称", "播放列表名称不能为空。")
            return
        if new_name != old_name:
            self.playlist_renamed.emit(old_name, new_name)

    def _delete_playlist(self, name):
        reply = QMessageBox.question(self, "确认删除", f"确定要删除播放列表 '{name}' 吗？",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.playlist_deleted.emit(name)

    def _get_song_at_row(self, row):
        if self.playlist_manager and self.current_playlist_name:
            songs = self.playlist_manager.get_playlist_songs(self.current_playlist_name)
            if 0 <= row < len(songs):
                return songs[row]
        return None

    def set_playlist_manager(self, manager):
        self.playlist_manager = manager
        self.songs_table.playlist_manager = manager

    def update_playlist_list(self, names, current_name=None):
        self.playlist_list.clear()
        self.playlist_list.addItems(names)
        
        if current_name:
            self.current_playlist_name = current_name
            for i in range(self.playlist_list.count()):
                item = self.playlist_list.item(i)
                if item.text() == current_name:
                    item.setSelected(True)
                    break

    def update_songs_table(self, songs):
        self.songs_table.clear()
        for row, song_info in enumerate(songs):
            self.songs_table.add_song(row, song_info.get('title'), song_info.get('singer'))

    def show_lyrics_view(self):
        self.stack.setCurrentIndex(1)

    def show_playlist_view(self):
        self.stack.setCurrentIndex(0)

    def is_lyrics_view_active(self):
        return self.stack.currentIndex() == 1

    def update_lyrics(self, lyrics_html):
        self.lyrics_display.setHtml(lyrics_html)

    def scroll_to_lyric_line(self, anchor):
        self.lyrics_display.scrollToAnchor(anchor)

    def set_playing_indicator(self, row, highlight=True):
        self.songs_table.set_playing_indicator(row, highlight)

    def clear_playing_indicators(self):
        self.songs_table.clear_all_indicators()
