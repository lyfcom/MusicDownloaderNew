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


class QualityLevel:
    """音质等级定义"""

    DEFAULT_QUALITY = 9  # HQ高音质增强（默认推荐）

    # 音质分组定义
    BASIC = [
        (0, '试听音质', '仅用于快速预览，音质较低'),
        (4, '标准音质', '文件小，适合移动网络和存储空间有限'),
        (8, 'HQ高音质', '平衡音质与文件大小，适合大多数用户')
    ]

    LOSSLESS = [
        (9, 'HQ高音质增强', '增强版高音质，推荐作为默认选项'),
        (10, 'SQ无损音质', '无损压缩，高保真音质，文件较大'),
        (11, 'Hi-Res音质', '超高分辨率音频，适合发烧友，文件很大')
    ]

    SPATIAL = [
        (12, '杜比全景声', '沉浸式3D音效，需要支持的设备'),
        (13, '臻品全景声', '顶级空间音频体验'),
        (14, '臻品母带2.0', '专业母带级音质，最高质量')
    ]

    @staticmethod
    def get_combobox_items():
        """返回用于QComboBox的音质选项列表

        Returns:
            List[Tuple]: [(quality_value, display_text, is_separator), ...]
        """
        items = []

        # 基础音质组
        items.append((None, '--- 基础音质 ---', True))
        for value, name, desc in QualityLevel.BASIC:
            items.append((value, name, False))

        # 无损音质组
        items.append((None, '--- 无损音质 ---', True))
        for value, name, desc in QualityLevel.LOSSLESS:
            items.append((value, name, False))

        # 空间音频组
        items.append((None, '--- 空间音频 ---', True))
        for value, name, desc in QualityLevel.SPATIAL:
            items.append((value, name, False))

        return items

    @staticmethod
    def get_tooltip(quality_value):
        """根据音质值获取工具提示文本

        Args:
            quality_value: 音质值(0-14)

        Returns:
            str: 工具提示文本
        """
        # 构建音质映射字典
        tooltip_map = {}
        for value, name, desc in QualityLevel.BASIC + QualityLevel.LOSSLESS + QualityLevel.SPATIAL:
            tooltip_map[value] = f"{name} - {desc}"

        return tooltip_map.get(quality_value, '未知音质')

    @staticmethod
    def get_quality_name(quality_value):
        """根据音质值获取音质名称

        Args:
            quality_value: 音质值(0-14)

        Returns:
            str: 音质名称
        """
        # 构建音质名称映射字典
        name_map = {}
        for value, name, desc in QualityLevel.BASIC + QualityLevel.LOSSLESS + QualityLevel.SPATIAL:
            name_map[value] = name

        return name_map.get(quality_value, '未知音质')