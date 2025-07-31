import os
import random
import qtawesome
from pathlib import Path
from utils.lrc_parser import parse_lrc_line

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFileDialog, QProgressBar, QMessageBox, QStatusBar, QSplitter, 
                             QInputDialog, QFrame, QLineEdit, QPushButton)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Property, QUrl
from PySide6.QtGui import QColor
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices

from core.downloader import (SingleDownloadThread, BatchDownloadThread, PlaylistImportThread,
                             SearchThread, SongDetailsThread)
from core.playlist_manager import PlaylistManager
from core.constants import PlaybackMode, HIGHLIGHT_COLOR, BASE_BG_COLOR, ANIMATION_DURATION
from ui.components.search_widget import SearchWidget
from ui.components.playlist_widget import PlaylistWidget
from ui.components.player_controls import PlayerControls

class MusicDownloader(QMainWindow):
    VERSION = "1.2.0"

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"音乐下载器 v{self.VERSION}")
        self.setMinimumSize(900, 750)
        self.setWindowIcon(qtawesome.icon('fa5s.music', color='#cdd6f4'))

        # Load Stylesheet
        try:
            with open("ui/resources/style.qss", "r") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            print("Warning: Stylesheet 'ui/resources/style.qss' not found.")

        self.init_components()
        self.init_player()
        self.init_state()
        self.setup_ui()
        self.connect_signals()
        self.initialize_data()

    def init_components(self):
        self.playlist_manager = PlaylistManager()
        self.download_dir = Path.home() / "Music" / "Downloads"
        self.active_threads = set()

    def _register_thread(self, thread):
        """统一的线程注册和清理管理"""
        def cleanup_thread():
            self.active_threads.discard(thread)  # 使用discard避免KeyError
            thread.deleteLater()  # 确保线程对象被正确释放
        
        thread.finished.connect(cleanup_thread)
        self.active_threads.add(thread)
        return thread

    def init_player(self):
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        
        self.volume_animation = QPropertyAnimation(self.audio_output, b"volume")
        self.volume_animation.setDuration(400)
        self.volume_animation.setEasingCurve(QEasingCurve.Linear)
        
        self.audio_output.setVolume(0.7)
        
        # 设置定时器定期检查音频设备变化（解决声卡切换问题）
        self._current_audio_device = QMediaDevices.defaultAudioOutput()
        self._device_check_timer = QTimer(self)
        self._device_check_timer.timeout.connect(self._check_audio_device_change)
        self._device_check_timer.start(2000)  # 每2秒检查一次

    def _check_audio_device_change(self):
        """定期检查默认音频输出设备是否变化"""
        try:
            current_device = QMediaDevices.defaultAudioOutput()
            if current_device and self._current_audio_device:
                # 比较设备ID或名称来判断设备是否变化
                if (current_device.id() != self._current_audio_device.id() or 
                    current_device.description() != self._current_audio_device.description()):
                    self._on_audio_device_changed(current_device)
                    self._current_audio_device = current_device
        except Exception as e:
            print(f"检查音频设备变化时出错: {e}")

    def _on_audio_device_changed(self, new_device):
        """处理音频输出设备变化，确保音频输出到正确的设备"""
        try:
            # 保存当前状态
            current_volume = self.audio_output.volume()
            was_playing = self.player.playbackState() == QMediaPlayer.PlayingState
            current_position = self.player.position()
            current_media = self.player.source()
            
            # 停止动画以避免干扰
            self.volume_animation.stop()
            
            # 创建新的音频输出实例，使用新的默认设备
            old_audio_output = self.audio_output
            self.audio_output = QAudioOutput(new_device)  # 使用新设备
            self.audio_output.setVolume(current_volume)
            
            # 重新绑定到播放器
            self.player.setAudioOutput(self.audio_output)
            
            # 重新创建音量动画对象
            self.volume_animation = QPropertyAnimation(self.audio_output, b"volume")
            self.volume_animation.setDuration(400)
            self.volume_animation.setEasingCurve(QEasingCurve.Linear)
            
            # 如果之前在播放，恢复播放状态
            if was_playing and current_media.isValid():
                self.player.setPosition(current_position)
                self.player.play()
            
            # 清理旧的音频输出对象
            old_audio_output.deleteLater()
            
            device_name = new_device.description() if new_device else "未知设备"
            self.status_bar.showMessage(f"音频输出已切换到: {device_name}", 3000)
            
        except Exception as e:
            print(f"音频设备切换失败: {e}")
            self.status_bar.showMessage("音频设备切换失败", 3000)

    def init_state(self):
        playlist_names = self.playlist_manager.get_playlist_names()
        self.current_playlist_name = playlist_names[0] if playlist_names else None
        self.currently_playing_song_info = None
        self.currently_playing_item_ref = None
        self.animations = QPropertyAnimation(self, b'highlight_color')
        
        # Player state
        self.playback_mode = PlaybackMode.LIST_LOOP
        self.is_playing_from_playlist = False
        self.current_playing_row = -1
        
        # Lyrics state
        self.current_lyrics = []
        self.current_lyric_line = -1
        self.lyrics_html_cache = ""  # 缓存完整的歌词HTML
        self.lyric_timer = QTimer(self)
        self.lyric_timer.setInterval(250)  # 降低刷新频率从100ms到250ms
        self.lyric_timer.timeout.connect(self.update_lyrics_display)

    def setup_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        self.setCentralWidget(main_widget)

        # 搜索组件
        self.search_widget = SearchWidget()
        
        # 主内容区域
        content_area = QSplitter(Qt.Horizontal)
        content_area.setHandleWidth(2)
        content_area.setChildrenCollapsible(False)
        main_layout.addWidget(content_area, 1)

        # 添加搜索组件到分割器
        content_area.addWidget(self.search_widget)

        # 播放列表组件
        self.playlist_widget = PlaylistWidget()
        content_area.addWidget(self.playlist_widget)
        content_area.setSizes([500, 400])

        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setObjectName("separator")
        main_layout.addWidget(separator)

        # 播放器控制组件
        self.player_controls = PlayerControls()
        main_layout.addWidget(self.player_controls)

        # 下载区域
        self._setup_download_area(main_layout)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("准备就绪")

    def _setup_download_area(self, main_layout):
        download_area = QWidget()
        download_layout = QVBoxLayout(download_area)
        download_layout.setContentsMargins(0, 0, 0, 0)
        download_layout.setSpacing(10)
        
        # 下载路径
        path_layout = QHBoxLayout()
        path_layout.setSpacing(10)
        
        path_label = QLabel("下载路径:")
        path_label.setMinimumWidth(80)
        
        self.path_display = QLineEdit(str(self.download_dir))
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

    def connect_signals(self):
        # Player connections
        self.player.playbackStateChanged.connect(self.update_on_playback_state_change)
        self.player.positionChanged.connect(self.player_controls.update_position)
        self.player.durationChanged.connect(self.player_controls.update_duration)
        self.player.mediaStatusChanged.connect(self.handle_media_status_changed)
        self.player.errorOccurred.connect(self.handle_player_error)

        # Player controls connections
        self.player_controls.play_pause_clicked.connect(self.toggle_play_pause)
        self.player_controls.previous_clicked.connect(self.play_previous)
        self.player_controls.next_clicked.connect(self.play_next)
        self.player_controls.playback_mode_changed.connect(self._on_playback_mode_changed)
        self.player_controls.volume_changed.connect(self.change_volume)
        self.player_controls.volume_slider_released.connect(self.restore_volume_animation_duration)
        self.player_controls.seek_requested.connect(self.seek_playback)
        self.player_controls.lyrics_view_toggled.connect(self.toggle_lyrics_view)

        # Search widget connections
        self.search_widget.search_requested.connect(self.run_search)
        self.search_widget.song_preview_requested.connect(self.preview_song)
        self.search_widget.song_download_requested.connect(self.download_song)
        self.search_widget.song_add_to_playlist_requested.connect(self.add_song_to_playlist)

        # Playlist widget connections
        self.playlist_widget.playlist_selected.connect(self.select_playlist)
        self.playlist_widget.playlist_created.connect(self._on_playlist_created)
        self.playlist_widget.playlist_deleted.connect(self._on_playlist_deleted)
        self.playlist_widget.playlist_renamed.connect(self._on_playlist_renamed)
        self.playlist_widget.playlist_played.connect(self.play_playlist)
        self.playlist_widget.playlist_downloaded.connect(self.download_playlist)
        self.playlist_widget.song_preview_requested.connect(self.preview_playlist_song)
        self.playlist_widget.song_download_requested.connect(self.download_song)
        self.playlist_widget.song_removed_from_playlist.connect(self.remove_song_from_playlist)
        self.playlist_widget.lyrics_view_toggled.connect(self.toggle_lyrics_view)

    def initialize_data(self):
        self.search_widget.set_playlist_manager(self.playlist_manager)
        self.playlist_widget.set_playlist_manager(self.playlist_manager)
        self.update_playlist_list()
        self.update_playlist_songs_table()
        self.player_controls.update_playback_mode_button()

    def _on_playback_mode_changed(self):
        self.playback_mode = self.player_controls.playback_mode
        self.status_bar.showMessage(f"播放模式: {PlaybackMode.ICONS[self.playback_mode][1]}", 2000)

    def _on_playlist_created(self, name):
        if not self.playlist_manager.create(name):
            QMessageBox.warning(self, "错误", "该名称的播放列表已存在。")
        else:
            self.current_playlist_name = name
            self.update_playlist_list()
            self.update_playlist_songs_table()

    def _on_playlist_deleted(self, name):
        if not self.playlist_manager.delete(name):
            QMessageBox.warning(self, "错误", "无法删除最后一个播放列表。")
        else:
            if self.current_playlist_name == name:
                self.current_playlist_name = self.playlist_manager.get_playlist_names()[0]
            self.update_playlist_list()
            self.update_playlist_songs_table()

    def _on_playlist_renamed(self, old_name, new_name):
        if not self.playlist_manager.rename(old_name, new_name):
            QMessageBox.warning(self, "错误", "新名称已存在或无效。")
        else:
            self.current_playlist_name = new_name
            self.update_playlist_list()

    def set_search_controls_enabled(self, enabled):
        self.search_widget.set_search_controls_enabled(enabled)

    def run_search(self, query):
        if query.isdigit():
            self.import_playlist(query)
            return
        
        self.set_search_controls_enabled(False)
        self.status_bar.showMessage("正在搜索...")
        search_thread = SearchThread(query)
        search_thread.finished_signal.connect(self.handle_search_finished)
        search_thread.status_signal.connect(self.status_bar.showMessage)
        search_thread.finished.connect(lambda: self.set_search_controls_enabled(True))
        
        self._register_thread(search_thread)
        search_thread.start()

    def handle_search_finished(self, songs):
        self.search_widget.update_search_results(songs)
        self.status_bar.showMessage(f"找到 {len(songs)} 首歌曲")

    def update_playlist_list(self):
        names = self.playlist_manager.get_playlist_names()
        if not names:
            self.playlist_manager.create("默认列表")
            names = self.playlist_manager.get_playlist_names()

        if self.current_playlist_name not in names:
            self.current_playlist_name = names[0]

        self.playlist_widget.update_playlist_list(names, self.current_playlist_name)

    def update_playlist_songs_table(self):
        if not self.current_playlist_name:
            return
        songs = self.playlist_manager.get_playlist_songs(self.current_playlist_name)
        self.playlist_widget.update_songs_table(songs)

    def select_playlist(self, playlist_name):
        self.current_playlist_name = playlist_name
        self.update_playlist_songs_table()

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
            if self.is_song_playing(song_info):
                self.toggle_play_pause()
            else:
                self.play_song(song_info, self.playlist_widget.songs_table, row)

    def preview_song(self, song_info, table, row):
        self.is_playing_from_playlist = False
        if self.is_song_playing(song_info):
            self.toggle_play_pause()
        else:
            self.play_song(song_info, table, row)

    def play_song(self, song_info, table, row):
        self.status_bar.showMessage(f"正在获取 {song_info['title']} 的播放地址...", 2000)

        details_thread = SongDetailsThread(song_info, table, row)
        details_thread.finished_signal.connect(self.handle_song_details_finished)
        details_thread.status_signal.connect(self.status_bar.showMessage)
        
        self._register_thread(details_thread)
        details_thread.start()

    def handle_song_details_finished(self, details, song_info, table, row):
        if details and 'url' in details and details['url']:
            self.player.setSource(QUrl(details['url']))
            self.fade_in_and_play()
            
            self.currently_playing_song_info = song_info
            self.status_bar.showMessage(f"正在播放: {song_info['title']}")
            self.set_playing_indicator(table, row, animated=True)
            
            # 更新正在播放信息
            artist_info = song_info.get('singer', '未知歌手')
            self.player_controls.update_now_playing(f"{song_info['title']} - {artist_info}")

            # 歌词处理
            self._handle_lyrics(details)
        else:
            self.status_bar.showMessage("无法获取播放地址", 3000)
            self.clear_playing_indicator()
            self.player_controls.update_now_playing("无播放内容")
            self.lyric_timer.stop()
            self.player_controls.set_lyrics_button_enabled(False)

    def _handle_lyrics(self, details):
        self.lyric_timer.stop()
        self.current_lyrics.clear()
        self.current_lyric_line = -1
        self.lyrics_html_cache = ""  # 清空歌词HTML缓存

        if details.get('lyric'):
            lyric_text = details['lyric']
            for line in lyric_text.strip().split('\n'):
                parsed = parse_lrc_line(line)
                if parsed and parsed[1]:
                    self.current_lyrics.append({'time': parsed[0], 'text': parsed[1]})
            
            if self.current_lyrics:
                # 使用新的缓存构建方法
                self._build_lyrics_html()
                self.playlist_widget.update_lyrics(self.lyrics_html_cache)
                self.lyric_timer.start()
                self.player_controls.set_lyrics_button_enabled(True)
            else:
                self.playlist_widget.update_lyrics("<center>无歌词或歌词格式不正确</center>")
                self.player_controls.set_lyrics_button_enabled(True)
        else:
            self.playlist_widget.update_lyrics("<center>未找到歌词</center>")
            self.player_controls.set_lyrics_button_enabled(True)

    def update_on_playback_state_change(self, state):
        is_playing = state == QMediaPlayer.PlayingState
        self.player_controls.update_play_pause_button(is_playing)

        is_playlist_mode = self.is_playing_from_playlist
        self.player_controls.set_navigation_enabled(is_playlist_mode)

        if state == QMediaPlayer.StoppedState:
            self.clear_playing_indicator()
            self.player_controls.reset_ui()
            self.lyric_timer.stop()
            self.player_controls.set_lyrics_button_enabled(False)

    def is_song_playing(self, song_info):
        if not self.currently_playing_song_info:
            return False
        
        return (self.currently_playing_song_info.get('raw_title') == song_info.get('raw_title') and 
                self.currently_playing_song_info.get('singer') == song_info.get('singer'))
            
    def set_playing_indicator(self, table, row, animated=False):
        self.clear_playing_indicator()
        if table and row is not None and hasattr(table, 'set_playing_indicator'):
            self.currently_playing_item_ref = (table, row)
            table.set_playing_indicator(row, True)
            if animated:
                self.animations = QPropertyAnimation(self, b'highlight_color')
                self.animations.setStartValue(BASE_BG_COLOR)
                self.animations.setEndValue(HIGHLIGHT_COLOR)
                self.animations.setDuration(ANIMATION_DURATION)
                self.animations.setEasingCurve(QEasingCurve.InOutQuad)
                self.animations.start()

    def clear_playing_indicator(self):
        if self.currently_playing_item_ref:
            table, row = self.currently_playing_item_ref
            if hasattr(table, 'set_playing_indicator'):
                table.set_playing_indicator(row, False)
        self.currently_playing_item_ref = None

    @Property(QColor)
    def highlight_color(self):
        return QColor(BASE_BG_COLOR)

    @highlight_color.setter
    def highlight_color(self, color):
        if self.currently_playing_item_ref:
            table, row = self.currently_playing_item_ref
            if hasattr(table, 'set_playing_indicator'):
                table.set_playing_indicator(row, True)

    def browse_download_path(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择下载目录", str(self.download_dir))
        if dir_path:
            self.download_dir = Path(dir_path)  # 保持Path类型
            self.path_display.setText(dir_path)

    def download_song(self, song_info):
        self.progress_bar.setValue(0)
        download_thread = SingleDownloadThread(song_info, self.download_dir)
        download_thread.progress_signal.connect(self.progress_bar.setValue)
        download_thread.status_signal.connect(self.status_bar.showMessage)
        download_thread.finished_signal.connect(
            lambda s, msg: QMessageBox.information(self, "下载完成", msg) if s 
            else QMessageBox.warning(self, "下载失败", msg)
        )
        
        self._register_thread(download_thread)
        download_thread.start()

    def download_playlist(self, playlist_name):
        songs = self.playlist_manager.get_playlist_songs(playlist_name)
        if not songs:
            QMessageBox.information(self, "提示", "此播放列表为空。")
            return
        
        reply = QMessageBox.question(
            self, "确认下载", f"准备下载 '{playlist_name}' 中的 {len(songs)} 首歌曲。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if reply == QMessageBox.No:
            return
        
        batch_download_thread = BatchDownloadThread(songs, self.download_dir)
        batch_download_thread.batch_progress_signal.connect(self.update_batch_progress)
        batch_download_thread.status_signal.connect(self.status_bar.showMessage)
        batch_download_thread.batch_finished_signal.connect(self.handle_batch_finish)
        
        self._register_thread(batch_download_thread)
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
        if event.key() == Qt.Key_Space and not self.search_widget.search_input.hasFocus():
            if self.currently_playing_song_info:
                self.toggle_play_pause()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """优雅关闭程序，确保所有线程安全结束"""
        # 保存播放列表数据
        self.playlist_manager.save()
        
        # 停止播放器和相关定时器
        self.player.stop()
        if hasattr(self, 'lyric_timer'):
            self.lyric_timer.stop()
        if hasattr(self, 'volume_animation'):
            self.volume_animation.stop()
        
        # 等待所有活跃线程完成
        if self.active_threads:
            self.status_bar.showMessage("正在等待后台任务完成...")
            
            # 请求所有线程中断（如果支持的话）
            for thread in list(self.active_threads):
                if hasattr(thread, 'requestInterruption'):
                    thread.requestInterruption()
            
            # 等待线程完成，最多等待5秒
            remaining_threads = list(self.active_threads)
            for thread in remaining_threads:
                if thread.isRunning():
                    thread.wait(5000)  # 等待最多5秒
                    if thread.isRunning():
                        print(f"警告: 线程 {thread} 未能在5秒内完成")
        
        # 停止音频设备检查定时器
        if hasattr(self, '_device_check_timer'):
            self._device_check_timer.stop()
        
        super().closeEvent(event)

    # Player control methods
    def fade_in_and_play(self):
        self.volume_animation.stop()
        target_volume = self.player_controls.volume_slider.value() / 100.0

        if self.player.playbackState() != QMediaPlayer.PlayingState:
            self.audio_output.setVolume(0)
            self.player.play()
        
        self.volume_animation.setStartValue(self.audio_output.volume())
        self.volume_animation.setEndValue(target_volume)
        
        # 断开之前的finished连接，避免重复连接
        try:
            self.volume_animation.finished.disconnect()
        except (RuntimeError, TypeError):
            pass  # 忽略没有连接时的警告
        self.volume_animation.start()

    def fade_out_and_pause(self):
        self.volume_animation.stop()
        self.volume_animation.setStartValue(self.audio_output.volume())
        self.volume_animation.setEndValue(0)

        # 断开之前的finished连接，避免重复连接
        try:
            self.volume_animation.finished.disconnect()
        except (RuntimeError, TypeError):
            pass  # 忽略没有连接时的警告
        self.volume_animation.finished.connect(self.player.pause)
        self.volume_animation.start()

    def toggle_play_pause(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.fade_out_and_pause()
        elif self.player.playbackState() == QMediaPlayer.PausedState:
            self.fade_in_and_play()
        elif self.currently_playing_song_info:
            if self.is_playing_from_playlist and self.current_playing_row != -1:
                self.preview_playlist_song(self.current_playing_row)
            else:
                if hasattr(self, 'currently_playing_item_ref') and self.currently_playing_item_ref:
                    self.play_song(self.currently_playing_song_info, 
                                 self.currently_playing_item_ref[0], 
                                 self.currently_playing_item_ref[1])

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
            next_row = self.current_playing_row

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

    def handle_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.playback_mode == PlaybackMode.SINGLE_LOOP:
                self.player.setPosition(0)
                self.player.play()
            elif self.is_playing_from_playlist:
                self.play_next()
            else:
                self.clear_playing_indicator()
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self.handle_player_error(QMediaPlayer.ResourceError, "媒体资源无效")
        elif status == QMediaPlayer.MediaStatus.NoMedia:
            self.clear_playing_indicator()

    def handle_player_error(self, error, error_string):
        """处理播放器错误，提供用户友好的错误信息"""
        error_messages = {
            QMediaPlayer.NoError: "无错误",
            QMediaPlayer.ResourceError: "媒体资源错误：可能是网络问题或文件损坏",
            QMediaPlayer.FormatError: "媒体格式不支持",
            QMediaPlayer.NetworkError: "网络连接错误：请检查网络连接",
            QMediaPlayer.AccessDeniedError: "访问被拒绝：可能是权限问题"
        }
        
        user_message = error_messages.get(error, f"播放错误: {error_string}")
        self.status_bar.showMessage(user_message, 5000)
        
        # 清除播放指示器
        self.clear_playing_indicator()
        
        # 如果是播放列表模式且是网络错误，尝试播放下一首
        if (error in [QMediaPlayer.NetworkError, QMediaPlayer.ResourceError] and 
            self.is_playing_from_playlist and 
            self.playback_mode != PlaybackMode.SINGLE_LOOP):
            self.status_bar.showMessage("播放失败，正在尝试下一首...", 3000)
            QTimer.singleShot(1500, self.play_next)  # 延迟1.5秒后播放下一首
        
        print(f"播放器错误: {error} - {error_string}")

    def seek_playback(self, position):
        self.player.setPosition(position)

    def change_volume(self, value):
        target_volume = value / 100.0

        if (self.volume_animation.duration() == 400 and 
            self.volume_animation.state() == QPropertyAnimation.Running):
            self.volume_animation.stop()

        if self.player_controls.volume_slider.isSliderDown():
            self.volume_animation.setDuration(50)
            self.volume_animation.setStartValue(self.audio_output.volume())
            self.volume_animation.setEndValue(target_volume)
            self.volume_animation.start()
        else:
            self.audio_output.setVolume(target_volume)
    
    def restore_volume_animation_duration(self):
        self.volume_animation.setDuration(400)

    def import_playlist(self, playlist_id):
        playlist_names = self.playlist_manager.get_playlist_names()
        new_playlist_option = ">>> 新建播放列表..."
        items = playlist_names + [new_playlist_option]
        
        target_playlist_name, ok = QInputDialog.getItem(
            self, "选择播放列表", "请选择要将歌曲导入到哪个播放列表:", items, 0, False
        )
        
        if not ok:
            return

        if target_playlist_name == new_playlist_option:
            new_name, ok = QInputDialog.getText(self, "新建播放列表", "请输入新列表名称:")
            if ok and new_name:
                if not self.playlist_manager.create(new_name):
                    QMessageBox.warning(self, "错误", "该名称的播放列表已存在。")
                    return
                target_playlist_name = new_name
                self.update_playlist_list()
            else:
                return
        
        self.set_search_controls_enabled(False)
        self.status_bar.showMessage(f"准备导入到 '{target_playlist_name}'...")
        
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(100)
        
        existing_songs = self.playlist_manager.get_playlist_songs(target_playlist_name)
        
        import_thread = PlaylistImportThread(playlist_id, target_playlist_name, existing_songs)
        import_thread.status_signal.connect(self.status_bar.showMessage)
        import_thread.progress_signal.connect(self.update_import_progress)
        import_thread.finished_signal.connect(self.handle_import_finished)
        import_thread.finished.connect(lambda: (
            self.set_search_controls_enabled(True),
            self.progress_bar.setValue(0)
        ))
        
        self._register_thread(import_thread)
        import_thread.start()

    def update_import_progress(self, current, total):
        percentage = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(percentage)

    def handle_import_finished(self, success, playlist_name, matched_songs):
        if not success:
            QMessageBox.warning(self, "导入失败", "无法导入歌单，请检查歌单ID是否正确或网络连接。")
            return
        
        if not matched_songs:
            QMessageBox.information(self, "导入提示", "没有新的歌曲被添加到歌单。")
            return
        
        added_count = 0
        for song in matched_songs:
            if self.playlist_manager.add_song(playlist_name, song):
                added_count += 1
        
        self.current_playlist_name = playlist_name
        self.update_playlist_list()
        self.update_playlist_songs_table()
        
        QMessageBox.information(self, "导入完成", 
                              f"成功添加 {added_count} 首新歌曲到歌单 '{playlist_name}'。")
        self.progress_bar.setValue(0)

    def play_playlist(self, playlist_name):
        if self.current_playlist_name != playlist_name:
            self.select_playlist(playlist_name)
            self.playlist_widget.update_playlist_list(
                self.playlist_manager.get_playlist_names(), playlist_name
            )
        
        songs = self.playlist_manager.get_playlist_songs(playlist_name)
        if not songs:
            self.status_bar.showMessage("歌单为空，无法播放。", 3000)
            return
        
        self.playback_mode = PlaybackMode.LIST_LOOP
        self.player_controls.playback_mode = self.playback_mode
        self.player_controls.update_playback_mode_button()
        self.preview_playlist_song(0)

    def update_lyrics_display(self):
        if not self.player or not self.current_lyrics:
            return

        position = self.player.position()
        
        # 优化：使用二分查找快速定位当前歌词行
        new_line_index = self._find_current_lyric_line(position)
        
        # 只有当歌词行变化时才更新UI
        if new_line_index != self.current_lyric_line:
            self.current_lyric_line = new_line_index
            self._update_lyrics_highlight()

    def _find_current_lyric_line(self, position):
        """使用二分查找快速定位当前歌词行"""
        if not self.current_lyrics:
            return -1
            
        left, right = 0, len(self.current_lyrics) - 1
        result = -1
        
        while left <= right:
            mid = (left + right) // 2
            if self.current_lyrics[mid]['time'] <= position:
                result = mid
                left = mid + 1
            else:
                right = mid - 1
        
        return result

    def _build_lyrics_html(self):
        """构建完整的歌词HTML，只在歌曲切换时调用"""
        if not self.current_lyrics:
            return ""
            
        html = []
        for i, line in enumerate(self.current_lyrics):
            text = line['text']
            html.append(f'<p id="lyric-{i}">{text}</p>')
        
        self.lyrics_html_cache = f"<center>{''.join(html)}</center>"
        return self.lyrics_html_cache

    def _update_lyrics_highlight(self):
        """仅更新高亮显示，避免重建整个HTML"""
        if not self.lyrics_html_cache:
            # 如果缓存为空，重建HTML
            self._build_lyrics_html()
            self.playlist_widget.update_lyrics(self.lyrics_html_cache)
        
        # 使用CSS样式更新而不是重建HTML
        highlight_style = f"color: {HIGHLIGHT_COLOR.name()}; font-weight: bold; font-size: 16px;"
        
        # 构建样式更新的JavaScript
        script = f"""
        <style>
        .current-lyric {{ {highlight_style} }}
        .normal-lyric {{ color: #cdd6f4; font-weight: normal; font-size: 14px; }}
        </style>
        <script>
        // 移除之前的高亮
        var prev = document.querySelector('.current-lyric');
        if (prev) prev.className = 'normal-lyric';
        
        // 添加新的高亮
        var current = document.getElementById('lyric-{self.current_lyric_line}');
        if (current) {{
            current.className = 'current-lyric';
            current.scrollIntoView({{behavior: 'smooth', block: 'center'}});
        }}
        </script>
        """
        
        # 简化版：直接重建HTML但优化性能
        html = []
        for i, line in enumerate(self.current_lyrics):
            text = line['text']
            if i == self.current_lyric_line:
                html.append(f'<a name="current"></a><p style="{highlight_style}">{text}</p>')
            else:
                html.append(f'<p style="color: #cdd6f4; font-weight: normal; font-size: 14px;">{text}</p>')
        
        self.playlist_widget.update_lyrics(f"<center>{''.join(html)}</center>")
        self.playlist_widget.scroll_to_lyric_line("current")

    def toggle_lyrics_view(self):
        if self.playlist_widget.is_lyrics_view_active():
            self.playlist_widget.show_playlist_view()
            self.player_controls.update_lyrics_button_icon(False)
        else:
            self.playlist_widget.show_lyrics_view()
            self.player_controls.update_lyrics_button_icon(True)