from PySide6.QtGui import QColor

# UI Constants
HIGHLIGHT_COLOR = QColor("#89b4fa")
BASE_BG_COLOR = QColor("#313244")
ANIMATION_DURATION = 300  # ms

class PlaybackMode:
    LIST_LOOP = 0
    RANDOM = 1
    SINGLE_LOOP = 2
    
    ICONS = {
        LIST_LOOP: ('fa5s.redo', "列表循环"),
        RANDOM: ('fa5s.random', "随机播放"),
        SINGLE_LOOP: ('fa5s.retweet', "单曲循环")
    }