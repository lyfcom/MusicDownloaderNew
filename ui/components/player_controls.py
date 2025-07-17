from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton
from PySide6.QtCore import Qt, QSize, Signal
import qtawesome

from core.constants import PlaybackMode

class PlayerControls(QWidget):
    play_pause_clicked = Signal()
    previous_clicked = Signal()
    next_clicked = Signal()
    playback_mode_changed = Signal()
    volume_changed = Signal(int)
    volume_slider_released = Signal()
    seek_requested = Signal(int)
    lyrics_view_toggled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.playback_mode = PlaybackMode.LIST_LOOP
        self.setup_ui()

    def setup_ui(self):
        self.setObjectName("player_widget")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(8)

        # 当前播放信息
        self._setup_now_playing(layout)
        
        # 进度条和时间
        self._setup_progress_controls(layout)
        
        # 控制按钮
        self._setup_control_buttons(layout)

    def _setup_now_playing(self, layout):
        now_playing_layout = QHBoxLayout()
        now_playing_label = QLabel("正在播放:")
        now_playing_label.setObjectName("now_playing_label")
        now_playing_label.setMinimumWidth(80)
        
        self.now_playing_info = QLabel("无播放内容")
        self.now_playing_info.setObjectName("now_playing_info")
        
        now_playing_layout.addWidget(now_playing_label)
        now_playing_layout.addWidget(self.now_playing_info, 1)
        layout.addLayout(now_playing_layout)

    def _setup_progress_controls(self, layout):
        progress_layout = QHBoxLayout()
        
        self.time_label = QLabel("00:00")
        self.time_label.setObjectName("time_label")
        self.time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setObjectName("progress_slider")
        self.progress_slider.sliderMoved.connect(self.seek_requested.emit)
        
        self.duration_label = QLabel("00:00")
        self.duration_label.setObjectName("duration_label")
        self.duration_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        progress_layout.addWidget(self.time_label)
        progress_layout.addWidget(self.progress_slider, 1)
        progress_layout.addWidget(self.duration_label)
        layout.addLayout(progress_layout)

    def _setup_control_buttons(self, layout):
        controls_layout = QHBoxLayout()
        controls_layout.setAlignment(Qt.AlignCenter)
        controls_layout.setSpacing(20)
        
        button_size = QSize(36, 36)
        
        # 播放模式按钮
        self.playback_mode_button = QPushButton()
        self.playback_mode_button.setObjectName("playback_mode_button")
        self.playback_mode_button.clicked.connect(self._on_playback_mode_clicked)
        self.playback_mode_button.setIconSize(QSize(16, 16))
        self.playback_mode_button.setFixedSize(button_size)
        
        # 上一首
        self.prev_button = QPushButton(qtawesome.icon('fa5s.step-backward', color='#cdd6f4'), "")
        self.prev_button.setObjectName("prev_button")
        self.prev_button.setToolTip("上一首")
        self.prev_button.clicked.connect(self.previous_clicked.emit)
        self.prev_button.setIconSize(QSize(16, 16))
        self.prev_button.setFixedSize(button_size)
        
        # 播放/暂停
        self.play_pause_button = QPushButton(qtawesome.icon('fa5s.play', color='#cdd6f4'), "")
        self.play_pause_button.setObjectName("play_pause_button")
        self.play_pause_button.setToolTip("播放/暂停")
        self.play_pause_button.clicked.connect(self.play_pause_clicked.emit)
        self.play_pause_button.setIconSize(QSize(20, 20))
        self.play_pause_button.setFixedSize(QSize(48, 48))
        
        # 下一首
        self.next_button = QPushButton(qtawesome.icon('fa5s.step-forward', color='#cdd6f4'), "")
        self.next_button.setObjectName("next_button")
        self.next_button.setToolTip("下一首")
        self.next_button.clicked.connect(self.next_clicked.emit)
        self.next_button.setIconSize(QSize(16, 16))
        self.next_button.setFixedSize(button_size)
        
        # 歌词按钮
        self.lyrics_button = QPushButton(qtawesome.icon('fa5s.music', color='#cdd6f4'), "")
        self.lyrics_button.setObjectName("lyrics_button")
        self.lyrics_button.setToolTip("查看歌词")
        self.lyrics_button.clicked.connect(self.lyrics_view_toggled.emit)
        self.lyrics_button.setIconSize(QSize(16, 16))
        self.lyrics_button.setFixedSize(button_size)
        self.lyrics_button.setEnabled(False)
        
        # 音量控制
        volume_label = QLabel()
        volume_label.setPixmap(qtawesome.icon('fa5s.volume-up', color='#cdd6f4').pixmap(16, 16))
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setObjectName("volume_slider")
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setMaximumWidth(100)
        self.volume_slider.valueChanged.connect(self.volume_changed.emit)
        self.volume_slider.sliderReleased.connect(self.volume_slider_released.emit)
        
        controls_layout.addStretch()
        controls_layout.addWidget(self.playback_mode_button)
        controls_layout.addWidget(self.prev_button)
        controls_layout.addWidget(self.play_pause_button)
        controls_layout.addWidget(self.next_button)
        controls_layout.addWidget(self.lyrics_button)
        controls_layout.addStretch()
        controls_layout.addWidget(volume_label)
        controls_layout.addWidget(self.volume_slider)
        
        layout.addLayout(controls_layout)

    def _on_playback_mode_clicked(self):
        self.playback_mode = (self.playback_mode + 1) % len(PlaybackMode.ICONS)
        self.update_playback_mode_button()
        self.playback_mode_changed.emit()

    def update_playback_mode_button(self):
        icon_name, tooltip = PlaybackMode.ICONS[self.playback_mode]
        self.playback_mode_button.setIcon(qtawesome.icon(icon_name, color='white'))
        self.playback_mode_button.setToolTip(tooltip)

    def update_play_pause_button(self, is_playing):
        icon_name = 'fa5s.pause' if is_playing else 'fa5s.play'
        self.play_pause_button.setIcon(qtawesome.icon(icon_name, color='#cdd6f4'))

    def update_position(self, position):
        self.progress_slider.setValue(position)
        self.time_label.setText(self._format_time(position))

    def update_duration(self, duration):
        self.progress_slider.setRange(0, duration)
        self.duration_label.setText(self._format_time(duration))

    def update_now_playing(self, text):
        self.now_playing_info.setText(text)

    def set_navigation_enabled(self, enabled):
        self.next_button.setEnabled(enabled)
        self.prev_button.setEnabled(enabled)

    def set_lyrics_button_enabled(self, enabled):
        self.lyrics_button.setEnabled(enabled)

    def update_lyrics_button_icon(self, show_lyrics):
        if show_lyrics:
            self.lyrics_button.setIcon(qtawesome.icon('fa5s.list', color='#cdd6f4'))
            self.lyrics_button.setToolTip("查看播放列表")
        else:
            self.lyrics_button.setIcon(qtawesome.icon('fa5s.music', color='#cdd6f4'))
            self.lyrics_button.setToolTip("查看歌词")

    def reset_ui(self):
        self.time_label.setText("00:00")
        self.duration_label.setText("00:00")
        self.progress_slider.setValue(0)
        self.now_playing_info.setText("无播放内容")

    def _format_time(self, ms):
        seconds = ms // 1000
        minutes = seconds // 60
        seconds %= 60
        return f"{minutes:02}:{seconds:02}"