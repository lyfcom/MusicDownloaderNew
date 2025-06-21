import os
import sys
import random
import qtawesome
import re
from utils.lrc_parser import parse_lrc_line

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QLabel, 
                             QFileDialog, QProgressBar, QMessageBox, QStatusBar, QSplitter, 
                             QListWidget, QInputDialog, QMenu, QSlider, QFrame, QStackedWidget, QTextBrowser)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QSequentialAnimationGroup, Property, QUrl, QSize
from PySide6.QtGui import QAction, QColor, QIcon
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from core.api import search_music, get_song_details_robust
from core.downloader import (SingleDownloadThread, BatchDownloadThread, PlaylistImportThread,
                             SearchThread, SongDetailsThread)
from core.playlist_manager import PlaylistManager

# --- Constants ---
HIGHLIGHT_COLOR = QColor("#89b4fa")  # 更新为新的主题色
BASE_BG_COLOR = QColor("#313244")    # 更新为新的背景色
ANIMATION_DURATION = 300 # ms，稍微延长动画时间以增强体验

class PlaybackMode:
    LIST_LOOP = 0
    RANDOM = 1
    SINGLE_LOOP = 2
    
    ICONS = {
        LIST_LOOP: ('fa5s.redo', "列表循环"),
        RANDOM: ('fa5s.random', "随机播放"),
        SINGLE_LOOP: ('fa5s.retweet', "单曲循环")
    }

class MusicDownloader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("音乐下载器")
        self.setMinimumSize(900, 750)  # 稍微增加窗口大小
        self.setWindowIcon(qtawesome.icon('fa5s.music', color='#cdd6f4'))

        # Load Stylesheet
        try:
            with open("ui/resources/style.qss", "r") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            print("Warning: Stylesheet 'ui/resources/style.qss' not found.")

        self.playlist_manager = PlaylistManager()
        self.download_dir = os.path.join(os.path.expanduser("~"), "Music", "Downloads")
        
        self.song_list = []
        playlist_names = self.playlist_manager.get_playlist_names()
        self.current_playlist_name = playlist_names[0] if playlist_names else None
        self.currently_playing_song_info = None
        self.currently_playing_item_ref = None # Stores (table, row) of playing item
        self.animations = QSequentialAnimationGroup(self)
        self.active_threads = set() # 用于存储所有活动线程的引用
        
        # Player state
        self.playback_mode = PlaybackMode.LIST_LOOP
        self.is_playing_from_playlist = False
        self.current_playing_row = -1
        
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.playbackStateChanged.connect(self.update_on_playback_state_change)
        self.player.positionChanged.connect(self.update_slider_position)
        self.player.durationChanged.connect(self.update_duration)
        self.player.mediaStatusChanged.connect(self.handle_media_status_changed)

        self.volume_animation = QPropertyAnimation(self.audio_output, b"volume")
        self.volume_animation.setDuration(400) # ms
        self.volume_animation.setEasingCurve(QEasingCurve.Linear)

        # Lyrics state
        self.current_lyrics = []
        self.current_lyric_line = -1
        self.lyric_timer = QTimer(self)
        self.lyric_timer.setInterval(100)
        self.lyric_timer.timeout.connect(self.update_lyrics_display)

        self.setup_ui()
        self.update_playlist_list()
        self.update_playlist_songs_table()
        self.update_playback_mode_button() # Set initial icon

    def setup_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)  # 增加边距
        main_layout.setSpacing(15)  # 增加组件间距
        self.setCentralWidget(main_widget)

        # 搜索区域
        search_layout = QHBoxLayout()
        search_layout.setSpacing(10)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入歌曲名、歌手名搜索，或输入歌单ID(QQ音乐)导入整个歌单...")
        self.search_input.returnPressed.connect(self.run_search)
        self.search_input.setMinimumHeight(40)  # 增加高度
        
        self.search_button = QPushButton(qtawesome.icon('fa5s.search', color='#1e1e2e'), "")
        self.search_button.setToolTip("立即搜索")
        self.search_button.clicked.connect(self.run_search)
        self.search_button.setMinimumHeight(40)  # 增加高度
        self.search_button.setMaximumWidth(50)  # 限制宽度
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)
        main_layout.addLayout(search_layout)

        # 主内容区域
        content_area = QSplitter(Qt.Horizontal)
        content_area.setHandleWidth(2)
        content_area.setChildrenCollapsible(False)
        main_layout.addWidget(content_area, 1)  # 使内容区域占据大部分空间

        # 搜索结果区域
        search_widget = QWidget()
        search_layout_v = QVBoxLayout(search_widget)
        search_layout_v.setContentsMargins(0, 0, 10, 0)
        search_layout_v.setSpacing(10)
        
        search_header = QLabel("搜索结果")
        search_header.setObjectName("section_header")
        search_header.setAlignment(Qt.AlignLeft)
        search_layout_v.addWidget(search_header)
        
        self.result_table = self.create_table(["序号", "歌曲名", "歌手"], self.show_search_context_menu)
        self.result_table.itemDoubleClicked.connect(lambda item: self.preview_song(self.song_list[item.row()], self.result_table, item.row()))
        self.result_table.setAlternatingRowColors(True)  # 交替行颜色
        search_layout_v.addWidget(self.result_table)
        content_area.addWidget(search_widget)

        # 播放列表区域
        playlist_widget = QWidget()
        playlist_layout = QVBoxLayout(playlist_widget)
        playlist_layout.setContentsMargins(10, 0, 0, 0)
        playlist_layout.setSpacing(10)
        
        playlist_header = QLabel("播放列表")
        playlist_header.setObjectName("section_header")
        playlist_header.setAlignment(Qt.AlignLeft)
        playlist_layout.addWidget(playlist_header)

        # --- Right-side Stack for Playlist/Lyrics ---
        self.right_stack = QStackedWidget()
        
        # Page 1: Playlist View
        playlist_page_widget = QWidget()
        playlist_page_layout = QVBoxLayout(playlist_page_widget)
        playlist_page_layout.setContentsMargins(0, 0, 0, 0)
        playlist_page_layout.setSpacing(10)

        # 播放列表选择器
        self.playlist_list_widget = QListWidget()
        self.playlist_list_widget.itemClicked.connect(self.select_playlist)
        self.playlist_list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.playlist_list_widget.customContextMenuRequested.connect(self.show_playlist_list_context_menu)
        self.playlist_list_widget.setMaximumHeight(120)  # 限制高度
        playlist_page_layout.addWidget(self.playlist_list_widget)
        
        # 播放列表歌曲
        playlist_songs_header = QLabel("歌曲")
        playlist_songs_header.setObjectName("subsection_header")
        playlist_page_layout.addWidget(playlist_songs_header)
        
        self.playlist_songs_table = self.create_table(["歌曲名", "歌手"], self.show_playlist_song_context_menu)
        
        # 允许用户手动调整列宽，并设置一个合理的初始拉伸行为
        playlist_header_view = self.playlist_songs_table.horizontalHeader()
        playlist_header_view.setSectionResizeMode(QHeaderView.Interactive)
        playlist_header_view.setStretchLastSection(True)

        self.playlist_songs_table.itemDoubleClicked.connect(lambda item: self.preview_playlist_song(item.row()))
        self.playlist_songs_table.setAlternatingRowColors(True)  # 交替行颜色
        playlist_page_layout.addWidget(self.playlist_songs_table)
        self.right_stack.addWidget(playlist_page_widget)

        # Page 2: Lyrics View
        lyrics_page_widget = QWidget()
        lyrics_page_layout = QVBoxLayout(lyrics_page_widget)
        lyrics_page_layout.setContentsMargins(0, 0, 0, 0)
        lyrics_page_layout.setSpacing(10)

        back_button_layout = QHBoxLayout()
        back_to_playlist_button = QPushButton(qtawesome.icon('fa5s.arrow-left', color='#cdd6f4'), " 返回播放列表")
        back_to_playlist_button.clicked.connect(self.toggle_lyrics_view)
        back_button_layout.addWidget(back_to_playlist_button)
        back_button_layout.addStretch()
        
        self.lyrics_display = QTextBrowser()
        self.lyrics_display.setReadOnly(True)
        self.lyrics_display.setObjectName("lyrics_display")

        lyrics_page_layout.addLayout(back_button_layout)
        lyrics_page_layout.addWidget(self.lyrics_display)
        self.right_stack.addWidget(lyrics_page_widget)

        playlist_layout.addWidget(self.right_stack)
        
        content_area.addWidget(playlist_widget)
        content_area.setSizes([500, 400])  # 设置初始分割比例

        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setObjectName("separator")
        main_layout.addWidget(separator)

        # 播放器控制区域
        self.setup_player_controls(main_layout)

        # 下载区域
        download_area = QWidget()
        download_layout = QVBoxLayout(download_area)
        download_layout.setContentsMargins(0, 0, 0, 0)
        download_layout.setSpacing(10)
        
        # 下载路径
        path_layout = QHBoxLayout()
        path_layout.setSpacing(10)
        
        path_label = QLabel("下载路径:")
        path_label.setMinimumWidth(80)
        
        self.path_display = QLineEdit(self.download_dir)
        self.path_display.setReadOnly(True)
        
        browse_button = QPushButton(qtawesome.icon('fa5s.folder-open', color='#1e1e2e'), "")
        browse_button.setToolTip("选择下载目录")
        browse_button.clicked.connect(self.browse_download_path)
        browse_button.setMaximumWidth(50)
        
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_display)
        path_layout.addWidget(browse_button)
        download_layout.addLayout(path_layout)
        
        # 下载进度条
        progress_layout = QHBoxLayout()
        progress_label = QLabel("下载进度:")
        progress_label.setMinimumWidth(80)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        
        progress_layout.addWidget(progress_label)
        progress_layout.addWidget(self.progress_bar)
        download_layout.addLayout(progress_layout)
        
        main_layout.addWidget(download_area)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("准备就绪")
        
    def setup_player_controls(self, main_layout):
        player_widget = QWidget()
        player_widget.setObjectName("player_widget")
        player_layout = QVBoxLayout(player_widget)
        player_layout.setContentsMargins(0, 10, 0, 10)
        player_layout.setSpacing(8)
        
        # 当前播放信息
        now_playing_layout = QHBoxLayout()
        now_playing_label = QLabel("正在播放:")
        now_playing_label.setObjectName("now_playing_label")
        now_playing_label.setMinimumWidth(80)
        
        self.now_playing_info = QLabel("无播放内容")
        self.now_playing_info.setObjectName("now_playing_info")
        
        now_playing_layout.addWidget(now_playing_label)
        now_playing_layout.addWidget(self.now_playing_info, 1)
        player_layout.addLayout(now_playing_layout)
        
        # 进度条和时间
        progress_layout = QHBoxLayout()
        
        self.time_label = QLabel("00:00")
        self.time_label.setObjectName("time_label")
        self.time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setObjectName("progress_slider")
        self.progress_slider.sliderMoved.connect(self.seek_playback)
        
        self.duration_label = QLabel("00:00")
        self.duration_label.setObjectName("duration_label")
        self.duration_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        progress_layout.addWidget(self.time_label)
        progress_layout.addWidget(self.progress_slider, 1)
        progress_layout.addWidget(self.duration_label)
        player_layout.addLayout(progress_layout)
        
        # 控制按钮
        controls_layout = QHBoxLayout()
        controls_layout.setAlignment(Qt.AlignCenter)
        controls_layout.setSpacing(20)
        
        # 设置按钮大小
        button_size = QSize(36, 36)
        
        self.prev_button = QPushButton(qtawesome.icon('fa5s.step-backward', color='#cdd6f4'), "")
        self.prev_button.setObjectName("prev_button")
        self.prev_button.setToolTip("上一首")
        self.prev_button.clicked.connect(self.play_previous)
        self.prev_button.setIconSize(QSize(16, 16))
        self.prev_button.setFixedSize(button_size)
        
        self.play_pause_button = QPushButton(qtawesome.icon('fa5s.play', color='#cdd6f4'), "")
        self.play_pause_button.setObjectName("play_pause_button")
        self.play_pause_button.setToolTip("播放/暂停")
        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        self.play_pause_button.setIconSize(QSize(20, 20))
        self.play_pause_button.setFixedSize(QSize(48, 48))  # 播放按钮稍大
        
        self.next_button = QPushButton(qtawesome.icon('fa5s.step-forward', color='#cdd6f4'), "")
        self.next_button.setObjectName("next_button")
        self.next_button.setToolTip("下一首")
        self.next_button.clicked.connect(self.play_next)
        self.next_button.setIconSize(QSize(16, 16))
        self.next_button.setFixedSize(button_size)
        
        self.playback_mode_button = QPushButton()
        self.playback_mode_button.setObjectName("playback_mode_button")
        self.playback_mode_button.clicked.connect(self.change_playback_mode)
        self.playback_mode_button.setIconSize(QSize(16, 16))
        self.playback_mode_button.setFixedSize(button_size)
        
        # 添加查看歌词按钮
        self.lyrics_button = QPushButton(qtawesome.icon('fa5s.music', color='#cdd6f4'), "")
        self.lyrics_button.setObjectName("lyrics_button")
        self.lyrics_button.setToolTip("查看歌词")
        self.lyrics_button.clicked.connect(self.toggle_lyrics_view)
        self.lyrics_button.setIconSize(QSize(16, 16))
        self.lyrics_button.setFixedSize(button_size)
        self.lyrics_button.setEnabled(False)  # 初始状态下禁用
        
        # 音量控制
        volume_label = QLabel()
        volume_label.setPixmap(qtawesome.icon('fa5s.volume-up', color='#cdd6f4').pixmap(16, 16))
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setObjectName("volume_slider")
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)  # 默认音量
        self.volume_slider.setMaximumWidth(100)
        self.volume_slider.valueChanged.connect(self.change_volume)
        self.audio_output.setVolume(0.7)  # 设置初始音量
        
        controls_layout.addStretch()
        controls_layout.addWidget(self.playback_mode_button)
        controls_layout.addWidget(self.prev_button)
        controls_layout.addWidget(self.play_pause_button)
        controls_layout.addWidget(self.next_button)
        controls_layout.addWidget(self.lyrics_button)  # 添加歌词按钮
        controls_layout.addStretch()
        controls_layout.addWidget(volume_label)
        controls_layout.addWidget(self.volume_slider)
        
        player_layout.addLayout(controls_layout)
        main_layout.addWidget(player_widget)

    def create_table(self, headers, context_menu_handler):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        if len(headers) > 1:
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        if len(headers) > 2:
            table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(context_menu_handler)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)
        return table

    def create_action(self, text, icon_name, callback, parent_menu):
        action = QAction(qtawesome.icon(icon_name, color='#f0f0f0'), text, parent_menu)
        action.triggered.connect(callback)
        return action

    def show_search_context_menu(self, pos):
        item = self.result_table.itemAt(pos)
        if not item: return
        
        row = item.row()
        song_info = self.song_list[row]
        menu = QMenu(self)
        
        state = self.player.playbackState()
        is_playing = self.currently_playing_song_info and self.currently_playing_song_info['title'] == song_info['title']
        play_icon = 'fa5s.pause' if is_playing and state == QMediaPlayer.PlayingState else 'fa5s.play'
        
        menu.addAction(self.create_action("预览/暂停", play_icon, lambda: self.preview_song(song_info, self.result_table, row), menu))
        menu.addAction(self.create_action("下载", "fa5s.download", lambda: self.download_song(song_info), menu))
        
        add_to_menu = QMenu("添加到...", self)
        add_to_menu.setIcon(qtawesome.icon('fa5s.plus', color='#f0f0f0'))
        
        for name in self.playlist_manager.get_playlist_names():
            action = QAction(name, self)
            action.triggered.connect(lambda checked=False, s_info=song_info, p_name=name: self.add_song_to_playlist(s_info, p_name))
            add_to_menu.addAction(action)
        
        menu.addMenu(add_to_menu)
        menu.exec(self.result_table.mapToGlobal(pos))

    def show_playlist_song_context_menu(self, pos):
        item = self.playlist_songs_table.itemAt(pos)
        if not item: return

        row = item.row()
        songs = self.playlist_manager.get_playlist_songs(self.current_playlist_name)
        song_info = songs[row]

        menu = QMenu(self)
        state = self.player.playbackState()
        is_playing_this_song = self.is_song_playing(song_info)
        play_icon = 'fa5s.pause' if is_playing_this_song and state == QMediaPlayer.PlayingState else 'fa5s.play'

        menu.addAction(self.create_action("播放/暂停", play_icon, lambda: self.preview_playlist_song(row), menu))
        menu.addAction(self.create_action("下载", "fa5s.download", lambda: self.download_song(song_info), menu))
        menu.addAction(self.create_action("从此列表移除", "fa5s.trash", lambda: self.remove_song_from_playlist(row), menu))
        menu.exec(self.playlist_songs_table.mapToGlobal(pos))

    def show_playlist_list_context_menu(self, pos):
        item = self.playlist_list_widget.itemAt(pos)
        
        menu = QMenu(self)
        menu.addAction(self.create_action("新建播放列表", "fa5s.plus-square", self.create_playlist, menu))
        if item:
            playlist_name = item.text()
            menu.addAction(self.create_action("播放此歌单", "fa5s.play-circle", lambda: self.play_playlist(playlist_name), menu))
            menu.addSeparator()
            menu.addAction(self.create_action("重命名", "fa5s.edit", lambda: self.rename_playlist(playlist_name), menu))
            menu.addAction(self.create_action("删除", "fa5s.trash-alt", lambda: self.delete_playlist(playlist_name), menu))
            menu.addSeparator()
            menu.addAction(self.create_action("下载此列表", "fa5s.cloud-download-alt", lambda: self.download_playlist(playlist_name), menu))
        menu.exec(self.playlist_list_widget.mapToGlobal(pos))

    def set_search_controls_enabled(self, enabled):
        """Enable or disable search-related controls."""
        self.search_input.setEnabled(enabled)
        self.search_button.setEnabled(enabled)

    def run_search(self):
        query = self.search_input.text().strip()
        if not query: return
        
        # 检查是否为纯数字 (歌单ID)
        if query.isdigit():
            self.import_playlist(query)
            return
        
        self.set_search_controls_enabled(False)
        self.status_bar.showMessage("正在搜索...")
        search_thread = SearchThread(query)
        search_thread.finished_signal.connect(self.handle_search_finished)
        search_thread.status_signal.connect(self.status_bar.showMessage)
        
        def on_search_finish():
            if search_thread in self.active_threads:
                self.active_threads.remove(search_thread)
            self.set_search_controls_enabled(True)

        search_thread.finished.connect(on_search_finish)
        self.active_threads.add(search_thread)
        search_thread.start()

    def handle_search_finished(self, songs):
        self.song_list = songs
        self.populate_search_results()
        self.status_bar.showMessage(f"找到 {len(self.song_list)} 首歌曲")

    def populate_search_results(self):
        self.result_table.setRowCount(0) # Clear table
        self.result_table.setRowCount(len(self.song_list))
        for row, song in enumerate(self.song_list):
            self.result_table.setItem(row, 0, QTableWidgetItem(str(song.get('n'))))
            self.result_table.setItem(row, 1, QTableWidgetItem(song.get('title')))
            self.result_table.setItem(row, 2, QTableWidgetItem(song.get('singer')))
    
    def update_playlist_list(self):
        self.playlist_list_widget.clear()
        names = self.playlist_manager.get_playlist_names()
        if not names:
            self.playlist_manager.create("默认列表")
            names = self.playlist_manager.get_playlist_names()

        self.playlist_list_widget.addItems(names)
        
        if self.current_playlist_name not in names:
            self.current_playlist_name = names[0]

        for i in range(self.playlist_list_widget.count()):
            item = self.playlist_list_widget.item(i)
            if item.text() == self.current_playlist_name:
                item.setSelected(True)
                break

    def update_playlist_songs_table(self):
        if not self.current_playlist_name: return
        songs = self.playlist_manager.get_playlist_songs(self.current_playlist_name)
        self.playlist_songs_table.setRowCount(0)
        self.playlist_songs_table.setRowCount(len(songs))
        for row, song_info in enumerate(songs):
            self.playlist_songs_table.setItem(row, 0, QTableWidgetItem(song_info.get('title')))
            self.playlist_songs_table.setItem(row, 1, QTableWidgetItem(song_info.get('singer')))

    def select_playlist(self, item):
        self.current_playlist_name = item.text()
        self.update_playlist_songs_table()

    def create_playlist(self):
        name, ok = QInputDialog.getText(self, "新建播放列表", "请输入列表名称:")
        if ok and name:
            if not self.playlist_manager.create(name):
                QMessageBox.warning(self, "错误", "该名称的播放列表已存在。")
            else:
                self.current_playlist_name = name
                self.update_playlist_list()
                self.update_playlist_songs_table()

    def delete_playlist(self, name):
        reply = QMessageBox.question(self, "确认删除", f"确定要删除播放列表 '{name}' 吗？",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            if not self.playlist_manager.delete(name):
                QMessageBox.warning(self, "错误", "无法删除最后一个播放列表。")
            else:
                # Select a new current playlist if the deleted one was active
                if self.current_playlist_name == name:
                    self.current_playlist_name = self.playlist_manager.get_playlist_names()[0]
                self.update_playlist_list()
                self.update_playlist_songs_table()
    
    def rename_playlist(self, old_name):
        new_name, ok = QInputDialog.getText(self, "重命名播放列表", "请输入新名称:", text=old_name)
        if ok and new_name and new_name != old_name:
            if not self.playlist_manager.rename(old_name, new_name):
                 QMessageBox.warning(self, "错误", "新名称已存在或无效。")
            else:
                self.current_playlist_name = new_name
                self.update_playlist_list()

    def add_song_to_playlist(self, song_info, playlist_name):
        if not self.playlist_manager.add_song(playlist_name, song_info):
            self.status_bar.showMessage(f"'{song_info.get('title')}' 已存在于 '{playlist_name}'")
        else:
            self.status_bar.showMessage(f"已添加 '{song_info.get('title')}' 到 '{playlist_name}'")
            if playlist_name == self.current_playlist_name:
                self.update_playlist_songs_table()

    def remove_song_from_playlist(self, row):
        if self.playlist_manager.remove_song(self.current_playlist_name, row):
            self.update_playlist_songs_table()

    def preview_playlist_song(self, row):
        self.is_playing_from_playlist = True
        self.current_playing_row = row
        songs = self.playlist_manager.get_playlist_songs(self.current_playlist_name)
        if 0 <= row < len(songs):
            song_info = songs[row]
            # If this song is already playing, toggle pause/play, else play it
            if self.is_song_playing(song_info):
                self.toggle_play_pause()
            else:
                self.play_song(song_info, self.playlist_songs_table, row)

    def preview_song(self, song_info, table, row):
        """Previews a song from the search result list."""
        self.is_playing_from_playlist = False
        # If this song is already playing, toggle pause/play, else play it
        if self.is_song_playing(song_info):
            self.toggle_play_pause()
        else:
            self.play_song(song_info, table, row)

    def play_song(self, song_info, table, row):
        self.status_bar.showMessage(f"正在获取 {song_info['title']} 的播放地址...", 2000)

        details_thread = SongDetailsThread(song_info, table, row)
        details_thread.finished_signal.connect(self.handle_song_details_finished)
        details_thread.status_signal.connect(self.status_bar.showMessage)
        details_thread.finished.connect(lambda: self.active_threads.remove(details_thread))
        self.active_threads.add(details_thread)
        details_thread.start()

    def handle_song_details_finished(self, details, song_info, table, row):
        if details and 'url' in details and details['url']:
            self.player.setSource(QUrl(details['url']))
            
            # Instead of self.player.play(), call the fade-in helper
            self.fade_in_and_play()
            
            self.currently_playing_song_info = song_info
            self.status_bar.showMessage(f"正在播放: {song_info['title']}")
            self.set_playing_indicator(table, row, animated=True)
            
            # 更新正在播放信息
            artist_info = song_info.get('singer', '未知歌手')
            self.now_playing_info.setText(f"{song_info['title']} - {artist_info}")

            # --- Lyrics Handling ---
            self.lyric_timer.stop()
            self.current_lyrics.clear()
            self.current_lyric_line = -1

            if details.get('lyric'):
                lyric_text = details['lyric']
                for line in lyric_text.strip().split('\n'):
                    parsed = parse_lrc_line(line)
                    if parsed and parsed[1]: # text is not empty
                        self.current_lyrics.append({'time': parsed[0], 'text': parsed[1]})
                
                if self.current_lyrics:
                    # Display all lyrics statically first
                    full_lyrics_html = "<br>".join([line['text'] for line in self.current_lyrics])
                    self.lyrics_display.setHtml(f"<center>{full_lyrics_html}</center>")
                    # self.right_stack.setCurrentIndex(1) # Switch to lyrics view
                    self.lyric_timer.start()
                    self.lyrics_button.setEnabled(True)  # 启用歌词按钮
                else:
                    self.lyrics_display.setHtml("<center>无歌词或歌词格式不正确</center>")
                    # self.right_stack.setCurrentIndex(1)
                    self.lyrics_button.setEnabled(True)  # 即使没有歌词也启用按钮，显示无歌词提示
            else:
                self.lyrics_display.setHtml("<center>未找到歌词</center>")
                # self.right_stack.setCurrentIndex(1) # Show "no lyrics" message
                self.lyrics_button.setEnabled(True)  # 即使没有歌词也启用按钮，显示无歌词提示
        else:
            self.status_bar.showMessage("无法获取播放地址", 3000)
            self.clear_playing_indicator()
            self.now_playing_info.setText("无播放内容")
            self.lyric_timer.stop()
            self.lyrics_button.setEnabled(False)  # 停止播放时禁用歌词按钮

    def update_on_playback_state_change(self, state):
        icon_name = 'fa5s.pause' if state == QMediaPlayer.PlayingState else 'fa5s.play'
        self.play_pause_button.setIcon(qtawesome.icon(icon_name, color='#cdd6f4'))

        is_playlist_mode = self.is_playing_from_playlist
        self.next_button.setEnabled(is_playlist_mode)
        self.prev_button.setEnabled(is_playlist_mode)

        if state == QMediaPlayer.StoppedState:
            self.clear_playing_indicator()
            self.time_label.setText("00:00")
            self.duration_label.setText("00:00")
            self.progress_slider.setValue(0)
            self.now_playing_info.setText("无播放内容")
            self.lyric_timer.stop()
            self.lyrics_button.setEnabled(False)  # 停止播放时禁用歌词按钮

    def is_song_playing(self, song_info):
        if not self.currently_playing_song_info:
            return False
        
        # Robust check using raw_title and singer for uniqueness
        return (self.currently_playing_song_info.get('raw_title') == song_info.get('raw_title') and 
                self.currently_playing_song_info.get('singer') == song_info.get('singer'))
            
    def set_playing_indicator(self, table, row, animated=False):
        self.clear_playing_indicator()
        if table and row is not None and row < table.rowCount():
            self.currently_playing_item_ref = (table, row)
            if animated:
                self.animations = QPropertyAnimation(self, b'highlight_color')
                self.animations.setStartValue(BASE_BG_COLOR)
                self.animations.setEndValue(HIGHLIGHT_COLOR)
                self.animations.setDuration(ANIMATION_DURATION)
                self.animations.setEasingCurve(QEasingCurve.InOutQuad)
                self.animations.start()
            else:
                self.change_row_color(table, row, HIGHLIGHT_COLOR)

    def clear_playing_indicator(self):
        if self.currently_playing_item_ref:
            table, row = self.currently_playing_item_ref
            if row < table.rowCount():
                self.change_row_color(table, row, BASE_BG_COLOR)
        self.currently_playing_item_ref = None

    def change_row_color(self, table, row, color):
        for col in range(table.columnCount()):
            item = table.item(row, col)
            if item: item.setBackground(color)

    # Dummy property for color animation
    @Property(QColor)
    def highlight_color(self):
        return QColor(BASE_BG_COLOR)

    @highlight_color.setter
    def highlight_color(self, color):
        self.change_row_color(self.currently_playing_item_ref[0], self.currently_playing_item_ref[1], color)

    def browse_download_path(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择下载目录", self.download_dir)
        if dir_path:
            self.download_dir = dir_path
            self.path_display.setText(dir_path)

    def download_song(self, song_info):
        self.progress_bar.setValue(0)
        download_thread = SingleDownloadThread(song_info, self.download_dir)
        download_thread.progress_signal.connect(self.progress_bar.setValue)
        download_thread.status_signal.connect(self.status_bar.showMessage)
        download_thread.finished_signal.connect(lambda s, msg: QMessageBox.information(self, "下载完成", msg) if s else QMessageBox.warning(self, "下载失败", msg))
        
        # 正确管理线程生命周期
        download_thread.finished.connect(lambda: self.active_threads.remove(download_thread))
        self.active_threads.add(download_thread)
        
        download_thread.start()

    def download_playlist(self, playlist_name):
        songs = self.playlist_manager.get_playlist_songs(playlist_name)
        if not songs:
            QMessageBox.information(self, "提示", "此播放列表为空。")
            return
        
        reply = QMessageBox.question(self, "确认下载", f"准备下载 '{playlist_name}' 中的 {len(songs)} 首歌曲。",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply == QMessageBox.No: return
        
        batch_download_thread = BatchDownloadThread(songs, self.download_dir)
        batch_download_thread.batch_progress_signal.connect(self.update_batch_progress)
        batch_download_thread.status_signal.connect(self.status_bar.showMessage)
        batch_download_thread.batch_finished_signal.connect(self.handle_batch_finish)
        
        # 正确管理线程生命周期
        batch_download_thread.finished.connect(lambda: self.active_threads.remove(batch_download_thread))
        self.active_threads.add(batch_download_thread)
        
        batch_download_thread.start()

    def handle_batch_finish(self, success, message):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        if success:
            QMessageBox.information(self, "批量下载完成", message)
        else:
            QMessageBox.warning(self, "批量下载出错", message)

    def update_batch_progress(self, current, total):
        self.progress_bar.setValue(current)
        self.progress_bar.setMaximum(total)

    def keyPressEvent(self, event):
        """Handle key presses for global shortcuts."""
        # Allow space to toggle play/pause unless an input field has focus
        if event.key() == Qt.Key_Space and not self.search_input.hasFocus():
            if self.currently_playing_song_info:
                self.toggle_play_pause()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self.playlist_manager.save()
        self.player.stop()
        super().closeEvent(event)

    # --- New Player Methods ---

    def fade_in_and_play(self):
        """Helper to fade in volume and play."""
        self.volume_animation.stop()
        target_volume = self.volume_slider.value() / 100.0

        if self.player.playbackState() != QMediaPlayer.PlayingState:
            self.audio_output.setVolume(0)
            self.player.play()
        
        self.volume_animation.setStartValue(self.audio_output.volume())
        self.volume_animation.setEndValue(target_volume)
        
        try: self.volume_animation.finished.disconnect()
        except RuntimeError: pass # No connection to disconnect
        self.volume_animation.start()

    def fade_out_and_pause(self):
        """Helper to fade out volume and pause."""
        self.volume_animation.stop()
        self.volume_animation.setStartValue(self.audio_output.volume())
        self.volume_animation.setEndValue(0)

        # Pause the player after the animation finishes
        try: self.volume_animation.finished.disconnect()
        except RuntimeError: pass # No connection to disconnect
        self.volume_animation.finished.connect(self.player.pause)
        self.volume_animation.start()

    def toggle_play_pause(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.fade_out_and_pause()
        elif self.player.playbackState() == QMediaPlayer.PausedState:
            self.fade_in_and_play()
        elif self.currently_playing_song_info:
            # This can happen if stopped but a song is "loaded". Re-play it.
             if self.is_playing_from_playlist and self.current_playing_row != -1:
                self.preview_playlist_song(self.current_playing_row)
             else: # Should be a search result song
                self.play_song(self.currently_playing_song_info, self.result_table, self.currently_playing_item_ref[1])

    def play_next(self):
        if not self.is_playing_from_playlist:
            return
        
        playlist_songs = self.playlist_manager.get_playlist_songs(self.current_playlist_name)
        if not playlist_songs:
            return

        total_songs = len(playlist_songs)
        if total_songs == 0:
            return

        next_row = -1
        if self.playback_mode == PlaybackMode.LIST_LOOP:
            next_row = (self.current_playing_row + 1) % total_songs
        elif self.playback_mode == PlaybackMode.RANDOM:
            next_row = random.randint(0, total_songs - 1)
        elif self.playback_mode == PlaybackMode.SINGLE_LOOP:
            next_row = self.current_playing_row # Will be handled by EndOfMedia to replay

        if next_row != -1:
            self.preview_playlist_song(next_row)
            
    def play_previous(self):
        if not self.is_playing_from_playlist:
            return

        playlist_songs = self.playlist_manager.get_playlist_songs(self.current_playlist_name)
        if not playlist_songs:
            return
            
        total_songs = len(playlist_songs)
        if total_songs == 0:
            return

        prev_row = (self.current_playing_row - 1 + total_songs) % total_songs
        self.preview_playlist_song(prev_row)

    def change_playback_mode(self):
        self.playback_mode = (self.playback_mode + 1) % len(PlaybackMode.ICONS)
        self.update_playback_mode_button()

    def update_playback_mode_button(self):
        icon_name, tooltip = PlaybackMode.ICONS[self.playback_mode]
        self.playback_mode_button.setIcon(qtawesome.icon(icon_name, color='white'))
        self.playback_mode_button.setToolTip(tooltip)
        self.status_bar.showMessage(f"播放模式: {tooltip}", 2000)

    def handle_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.playback_mode == PlaybackMode.SINGLE_LOOP:
                self.player.setPosition(0)
                self.player.play()
            elif self.is_playing_from_playlist:
                self.play_next()
            else:
                # Song from search result ended, just stop
                self.clear_playing_indicator()

    def update_slider_position(self, position):
        self.progress_slider.setValue(position)
        self.time_label.setText(self.format_time(position))

    def update_duration(self, duration):
        self.progress_slider.setRange(0, duration)
        self.duration_label.setText(self.format_time(duration))

    def seek_playback(self, position):
        self.player.setPosition(position)

    def format_time(self, ms):
        seconds = ms // 1000
        minutes = seconds // 60
        seconds %= 60
        return f"{minutes:02}:{seconds:02}"

    def change_volume(self, value):
        volume = value / 100.0
        
        if self.volume_animation.state() == QPropertyAnimation.Running:
            self.volume_animation.stop()

        self.audio_output.setVolume(volume)

    def import_playlist(self, playlist_id):
        """当输入纯数字时，将其视为歌单ID并导入歌单"""
        # Step 1: Let user choose a playlist or create a new one
        playlist_names = self.playlist_manager.get_playlist_names()
        new_playlist_option = ">>> 新建播放列表..."
        items = playlist_names + [new_playlist_option]
        
        target_playlist_name, ok = QInputDialog.getItem(self, "选择播放列表", "请选择要将歌曲导入到哪个播放列表:", items, 0, False)
        
        if not ok:
            return # User cancelled

        # If user chose to create a new one
        if target_playlist_name == new_playlist_option:
            new_name, ok = QInputDialog.getText(self, "新建播放列表", "请输入新列表名称:")
            if ok and new_name:
                if not self.playlist_manager.create(new_name):
                    QMessageBox.warning(self, "错误", "该名称的播放列表已存在。")
                    return
                target_playlist_name = new_name
                self.update_playlist_list()
            else:
                return # User cancelled new playlist creation
        
        self.set_search_controls_enabled(False)
        self.status_bar.showMessage(f"准备导入到 '{target_playlist_name}'...")
        
        # Reset progress bar
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(100)
        
        # Get existing songs to avoid duplicates
        existing_songs = self.playlist_manager.get_playlist_songs(target_playlist_name)
        
        # Create and start the import thread
        import_thread = PlaylistImportThread(playlist_id, target_playlist_name, existing_songs)
        import_thread.status_signal.connect(self.status_bar.showMessage)
        import_thread.progress_signal.connect(self.update_import_progress)
        import_thread.finished_signal.connect(self.handle_import_finished)
        
        def on_import_finish():
            if import_thread in self.active_threads:
                self.active_threads.remove(import_thread)
            self.set_search_controls_enabled(True)
            self.progress_bar.setValue(0) # Reset progress bar on finish

        import_thread.finished.connect(on_import_finish)
        self.active_threads.add(import_thread)
        import_thread.start()

    def update_import_progress(self, current, total):
        """更新导入进度"""
        percentage = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(percentage)

    def handle_import_finished(self, success, playlist_name, matched_songs):
        """处理歌单导入完成事件"""
        if not success:
            QMessageBox.warning(self, "导入失败", "无法导入歌单，请检查歌单ID是否正确或网络连接。")
            return
        
        if not matched_songs:
             QMessageBox.information(self, "导入提示", "没有新的歌曲被添加到歌单。")
             return

        # Add all matched songs to the playlist
        added_count = 0
        for song in matched_songs:
            if self.playlist_manager.add_song(playlist_name, song):
                added_count += 1
        
        # Select and show the playlist
        self.current_playlist_name = playlist_name
        self.update_playlist_list()
        self.update_playlist_songs_table()
        
        # Show completion message
        QMessageBox.information(self, "导入完成", 
                              f"成功添加 {added_count} 首新歌曲到歌单 '{playlist_name}'。")
        self.progress_bar.setValue(0)

    def play_playlist(self, playlist_name):
        """播放整个歌单"""
        # 确保选中的是当前要播放的歌单
        if self.current_playlist_name != playlist_name:
             for i in range(self.playlist_list_widget.count()):
                item = self.playlist_list_widget.item(i)
                if item.text() == playlist_name:
                    item.setSelected(True)
                    self.select_playlist(item)
                    break
        
        songs = self.playlist_manager.get_playlist_songs(playlist_name)
        if not songs:
            self.status_bar.showMessage("歌单为空，无法播放。", 3000)
            return
        
        # 设置为列表循环模式并从第一首开始播放
        self.playback_mode = PlaybackMode.LIST_LOOP
        self.update_playback_mode_button()
        self.preview_playlist_song(0)

    def update_lyrics_display(self):
        if not self.player or not self.current_lyrics:
            return

        position = self.player.position()
        
        # Find current line
        new_line_index = -1
        for i, line in enumerate(self.current_lyrics):
            if position >= line['time']:
                new_line_index = i
            else:
                break
        
        if new_line_index != self.current_lyric_line:
            self.current_lyric_line = new_line_index
            
            # Rebuild HTML with highlighted line
            html = []
            for i, line in enumerate(self.current_lyrics):
                text = line['text']
                if i == self.current_lyric_line:
                    html.append(f'<a name="current"></a><p style="color: {HIGHLIGHT_COLOR.name()}; font-weight: bold; font-size: 16px;">{text}</p>')
                else:
                    html.append(f'<p>{text}</p>')
            
            self.lyrics_display.setHtml(f"<center>{''.join(html)}</center>")
            self.lyrics_display.scrollToAnchor("current")

    def toggle_lyrics_view(self):
        """切换歌词视图和播放列表视图"""
        if self.right_stack.currentIndex() == 0:  # 当前是播放列表视图
            self.right_stack.setCurrentIndex(1)   # 切换到歌词视图
            self.lyrics_button.setIcon(qtawesome.icon('fa5s.list', color='#cdd6f4'))
            self.lyrics_button.setToolTip("查看播放列表")
        else:  # 当前是歌词视图
            self.right_stack.setCurrentIndex(0)   # 切换到播放列表视图
            self.lyrics_button.setIcon(qtawesome.icon('fa5s.music', color='#cdd6f4'))
            self.lyrics_button.setToolTip("查看歌词")