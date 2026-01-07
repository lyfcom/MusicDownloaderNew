import json
from pathlib import Path
from core.constants import QualityLevel


class ConfigManager:
    """应用配置管理器

    负责管理应用的配置文件，包括：
    - 音质设置
    - 下载目录
    - 其他用户偏好设置

    配置文件存储在用户的AppData目录中，避免权限问题
    """

    def __init__(self, config_file=None):
        """初始化配置管理器

        Args:
            config_file: 配置文件路径（可选），默认使用AppData目录
        """
        if config_file is None:
            # 将配置存储在用户的AppData/Roaming目录中
            config_dir = Path.home() / "AppData" / "Roaming" / "MusicDownloader"
            config_dir.mkdir(parents=True, exist_ok=True)
            self.config_file = config_dir / "config.json"
        else:
            self.config_file = Path(config_file)

        self.config = self._load()

    def _load(self):
        """加载配置文件

        Returns:
            dict: 配置字典
        """
        if self.config_file.exists():
            try:
                with self.config_file.open('r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 验证并返回配置
                    return config
            except (json.JSONDecodeError, IOError) as e:
                print(f"配置文件加载失败: {e}，使用默认配置")

        # 返回默认配置
        return self._get_default_config()

    def _get_default_config(self):
        """获取默认配置

        Returns:
            dict: 默认配置字典
        """
        return {
            'quality': QualityLevel.DEFAULT_QUALITY,
            'last_download_dir': str(Path.home() / "Music" / "Downloads"),
            'version': '2.0.0'
        }

    def save(self):
        """保存配置到文件

        Returns:
            bool: 保存是否成功
        """
        try:
            with self.config_file.open('w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except IOError as e:
            print(f"配置文件保存失败: {e}")
            return False

    def get_quality(self):
        """获取音质配置

        Returns:
            int: 音质值（0-14），默认9
        """
        quality = self.config.get('quality', QualityLevel.DEFAULT_QUALITY)

        # 验证有效性
        valid_qualities = [0, 4, 8, 9, 10, 11, 12, 13, 14]
        if quality not in valid_qualities:
            quality = QualityLevel.DEFAULT_QUALITY
            # 修正配置
            self.config['quality'] = quality
            self.save()

        return quality

    def set_quality(self, quality_value):
        """设置音质配置

        Args:
            quality_value: 音质值（0-14）

        Returns:
            bool: 保存是否成功
        """
        self.config['quality'] = quality_value
        return self.save()

    def get_last_download_dir(self):
        """获取上次下载目录

        Returns:
            str: 下载目录路径
        """
        default_dir = str(Path.home() / "Music" / "Downloads")
        return self.config.get('last_download_dir', default_dir)

    def set_last_download_dir(self, dir_path):
        """设置下载目录

        Args:
            dir_path: 下载目录路径（Path或str）

        Returns:
            bool: 保存是否成功
        """
        self.config['last_download_dir'] = str(dir_path)
        return self.save()

    def get(self, key, default=None):
        """获取任意配置项

        Args:
            key: 配置键名
            default: 默认值

        Returns:
            配置值或默认值
        """
        return self.config.get(key, default)

    def set(self, key, value):
        """设置任意配置项

        Args:
            key: 配置键名
            value: 配置值

        Returns:
            bool: 保存是否成功
        """
        self.config[key] = value
        return self.save()
