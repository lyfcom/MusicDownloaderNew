# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## 项目概述

这是一个基于 **PySide6** 构建的现代化桌面音乐下载工具，具有完整的搜索、预览、下载、播放列表管理和音频播放功能。项目采用模块化架构，遵循现代Qt应用程序的最佳实践。

## 开发环境配置

### 快速启动
```bash
# 安装依赖
pip install -r requirements.txt

# 运行应用程序
python main.py
```

### 项目依赖
```txt
PySide6         # Qt6 Python绑定 - 主要GUI框架
requests        # HTTP请求库 - API调用和文件下载
mutagen         # 音频元数据库 - MP3 ID3标签、封面、歌词嵌入
qtawesome       # 图标库 - FontAwesome图标支持
simplejson      # JSON处理库 - 更好的JSON解析
```

### 构建和打包

#### 使用 Nuitka 构建独立可执行文件
```bash
python -m nuitka \
    --standalone \
    --assume-yes-for-downloads \
    --enable-plugin=pyside6 \
    --include-qt-plugins=multimedia \
    --windows-console-mode=disable \
    --output-dir=dist \
    --include-data-dir=ui/resources=ui/resources \
    --windows-icon-from-ico=icon.ico \
    --windows-company-name=XHZX \
    --windows-product-name="音乐下载器" \
    --windows-file-version=1.2.0 \
    --windows-product-version=1.2.0 \
    --output-filename=MusicDownloader.exe \
    main.py
```

#### 创建Windows安装程序 (需要Inno Setup)
```bash
iscc inno_setup.iss
```

## 核心架构

### 架构设计原则

1. **模块化分离**: 核心逻辑、UI组件和工具函数完全分离
2. **线程安全**: 所有网络操作在后台QThread中执行，保持UI响应性
3. **信号槽通信**: 使用Qt信号槽机制处理跨线程通信
4. **健壮的API策略**: 内容优先匹配 + 索引备用的双重保障机制
5. **现代UI设计**: 基于Catppuccin主题的自定义QSS样式系统

### 项目结构详解

```
MusicDownloaderNew/
├── main.py                    # 应用程序入口点
├── requirements.txt           # Python依赖清单
├── icon.ico                   # 应用程序图标
├── inno_setup.iss            # Windows安装程序配置
├── Chinese.isl               # 中文安装界面
│
├── core/                     # 核心业务逻辑层
│   ├── __init__.py
│   ├── api.py                # 音乐API封装和健壮匹配策略
│   ├── constants.py          # 应用常量和播放模式定义
│   ├── downloader.py         # 后台线程工作器（搜索、下载、导入）
│   ├── fetch_playlist.py     # QQ音乐歌单获取
│   └── playlist_manager.py   # 播放列表CRUD和JSON持久化
│
├── ui/                       # 用户界面层
│   ├── __init__.py
│   ├── main_window.py        # 主窗口（900+行，核心UI逻辑）
│   ├── main_window_backup.py # 主窗口备份
│   ├── components/           # 模块化UI组件
│   │   ├── __init__.py
│   │   ├── music_table.py    # 音乐列表表格组件
│   │   ├── player_controls.py # 播放控制面板
│   │   ├── playlist_widget.py # 播放列表管理组件
│   │   └── search_widget.py  # 搜索界面组件
│   └── resources/
│       └── style.qss         # 自定义QSS主题样式（400行）
│
└── utils/                    # 通用工具库
    ├── __init__.py
    └── lrc_parser.py         # LRC歌词格式解析器
```

### 核心模块详解

#### `core/api.py` - API抽象层
```python
API_URL = "https://www.hhlqilongzhu.cn/api/joox/juhe_music.php"

# 核心函数：
- search_music(query) -> List[Dict]
  # 返回包含 raw_title（原始标题）和 title（清理标题）的歌曲列表
  
- get_song_details_robust(song_info) -> Dict
  # ⭐ 关键实现：双重匹配策略
  # 1. 主策略：使用 "title singer" 搜索并精确匹配 raw_title + singer
  # 2. 备用策略：使用原始 query + n 索引获取详情
  # 确保API索引变化时播放列表仍然有效
```

#### `core/downloader.py` - 后台线程架构
```python
# 基类
BaseDownloader(QThread)
  ├── download_file()         # 带进度回调的文件下载
  └── embed_metadata()        # MP3元数据嵌入（封面、歌词、ID3标签）

# 具体实现类
├── SearchThread            # 非阻塞搜索
├── SongDetailsThread       # 歌曲详情获取
├── SingleDownloadThread    # 单曲下载
├── BatchDownloadThread     # 批量下载
└── PlaylistImportThread    # 歌单导入（支持去重和增量匹配）
```

#### `core/playlist_manager.py` - 数据持久化
```python
PlaylistManager:
  ├── load()/save()          # JSON文件读写
  ├── create()/delete()      # 播放列表CRUD
  ├── add_song()            # 基于 raw_title + singer 去重
  └── playlists.json        # 数据存储格式
```

#### `ui/main_window.py` - 主界面控制器（900+行）
```python
MusicDownloader(QMainWindow):
  ├── init_components()      # 组件初始化
  ├── init_player()         # QMediaPlayer + QAudioOutput
  ├── setup_ui()           # UI布局构建
  ├── connect_signals()     # 信号槽连接
  │
  ├── 播放器功能：
  │   ├── QStackedWidget    # 播放列表/歌词视图切换
  │   ├── QPropertyAnimation # 音量淡入淡出动画
  │   ├── QTimer           # 歌词同步定时器
  │   └── 播放模式支持      # 列表循环/随机/单曲循环
  │
  └── 线程管理：
      ├── active_threads    # 活跃线程集合管理
      └── 信号槽处理        # 线程完成信号的UI更新
```

#### `ui/resources/style.qss` - 主题系统（400行）
```css
/* 基于 Catppuccin Mocha 主题的现代化UI */
基础配色:
  ├── 背景色: #1e1e2e (深蓝灰)
  ├── 主色调: #89b4fa (亮蓝)
  ├── 文本色: #cdd6f4 (浅灰)
  └── 强调色: #74c7ec (青色)

组件样式:
  ├── 自定义滚动条 (圆角、悬停效果)
  ├── 现代化按钮 (圆角、渐变动画)
  ├── 美化表格 (交替行颜色、选中高亮)
  ├── 优雅滑块 (进度条、音量控制)
  └── 统一的焦点状态处理
```

#### `utils/lrc_parser.py` - 歌词处理
```python
parse_lrc_line(line) -> Tuple[int, str]
  # 解析 [mm:ss.xx] 时间戳格式
  # 返回 (毫秒时间戳, 歌词文本)
  # 支持毫秒精度的同步显示
```

## 关键技术实现

### 1. 线程安全架构
- **原则**: UI线程只处理界面更新，所有网络操作在工作线程中执行
- **通信**: 使用Qt信号槽机制确保线程间安全通信
- **资源管理**: `active_threads` 集合跟踪所有活跃线程，防止内存泄漏

### 2. 健壮的歌曲匹配策略
```python
# core/api.py:64-89 的核心实现
def get_song_details_robust(song_info):
    # 主策略：内容匹配（推荐）
    new_query = f"{song_info['title']} {song_info['singer']}"
    search_results = search_music(new_query)
    for result in search_results:
        if exact_match(result, song_info):
            return get_song_details(new_query, result['n'])
    
    # 备用策略：索引匹配
    return get_song_details(song_info['query'], song_info['n'])
```

### 3. 音频和元数据处理
- **播放**: `QMediaPlayer` + `QAudioOutput` (Qt6 多媒体架构)
- **元数据**: `Mutagen` 库处理 MP3 ID3 标签、封面图片、歌词嵌入
- **动画**: `QPropertyAnimation` 实现音量淡入淡出效果
- **歌词同步**: `QTimer` 驱动的实时歌词高亮显示

### 4. 播放列表管理
- **存储格式**: JSON文件 (`playlists.json`)
- **去重策略**: 基于 `raw_title` + `singer` 的内容匹配
- **增量导入**: 歌单导入时只处理新歌曲，减少API调用

### 5. 外部歌单支持
```python
# core/fetch_playlist.py
fetch_qq_playlist(playlist_id) -> List[Dict]:
  # 支持QQ音乐歌单ID导入
  # 返回标准化的 {title, singer} 格式
  # 自动处理多歌手分隔和名称清理
```

## 最新稳定性改进 (v1.2.0)

### 音频设备热切换解决方案
```python
# ui/main_window.py:72-128
# 问题：PySide6中不存在 QMediaDevices.defaultAudioOutputChanged 信号
# 解决：使用定时器检查方式
class MusicDownloader:
    def init_player(self):
        self._current_audio_device = QMediaDevices.defaultAudioOutput()
        self._device_check_timer = QTimer(self)
        self._device_check_timer.timeout.connect(self._check_audio_device_change)
        self._device_check_timer.start(2000)  # 每2秒检查一次

    def _check_audio_device_change(self):
        current_device = QMediaDevices.defaultAudioOutput()
        if current_device.id() != self._current_audio_device.id():
            self._on_audio_device_changed(current_device)
            self._current_audio_device = current_device
```

### 统一线程管理机制
```python
# ui/main_window.py:49-57
def _register_thread(self, thread):
    """统一的线程注册和清理管理"""
    def cleanup_thread():
        self.active_threads.discard(thread)  # 使用discard避免KeyError
        thread.deleteLater()  # 确保线程对象被正确释放
    thread.finished.connect(cleanup_thread)
    self.active_threads.add(thread)
    return thread

# 使用示例：
search_thread = self._register_thread(SearchThread(query))
```

### 优雅关闭处理
```python
# ui/main_window.py:553-580
def closeEvent(self, event):
    # 1. 保存数据
    self.playlist_manager.save()
    
    # 2. 停止播放器和定时器
    self.player.stop()
    if hasattr(self, 'lyric_timer'): self.lyric_timer.stop()
    if hasattr(self, 'volume_animation'): self.volume_animation.stop()
    
    # 3. 优雅关闭所有线程
    if self.active_threads:
        for thread in list(self.active_threads):
            if hasattr(thread, 'requestInterruption'):
                thread.requestInterruption()
        for thread in list(self.active_threads):
            if thread.isRunning():
                thread.wait(5000)  # 最多等待5秒
    
    # 4. 停止设备检查定时器
    if hasattr(self, '_device_check_timer'):
        self._device_check_timer.stop()
```

### 网络性能优化架构
```python
# core/api.py:10-38
# 全局Session管理，支持连接池和重试策略
_session = None

def get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        # 重试策略：3次重试，指数退避，特定状态码
        retry_strategy = Retry(
            total=3, 
            backoff_factor=0.5, 
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,    # 连接池大小
            pool_maxsize=20        # 每个连接池的最大连接数
        )
        _session.mount("http://", adapter)
        _session.mount("https://", adapter)
        _session.timeout = (5, 15)  # 连接5s，读取15s
    return _session
```

### 歌词显示性能优化
```python
# ui/main_window.py:806-877
# 问题：频繁的HTML重建导致性能问题
# 解决：缓存 + 二分查找 + 降频
class MusicDownloader:
    def __init__(self):
        self.lyric_timer.setInterval(250)  # 从100ms优化到250ms
        self.lyrics_html_cache = ""        # HTML缓存

    def _find_current_lyric_line(self, position):
        """使用二分查找快速定位当前歌词行"""
        if not self.lyrics:
            return -1
        left, right = 0, len(self.lyrics) - 1
        while left <= right:
            mid = (left + right) // 2
            if self.lyrics[mid][0] <= position:
                left = mid + 1
            else:
                right = mid - 1
        return right

    def _build_lyrics_html(self):
        """只在歌词变化时重建HTML缓存"""
        # 生成完整HTML并缓存
        
    def _update_lyrics_highlight(self):
        """只更新高亮状态，不重建HTML"""
        # 使用JavaScript动态更新高亮
```

### 临时文件统一清理
```python
# core/downloader.py:165-176
def _cleanup_temp_files(self, *temp_paths):
    """统一的临时文件清理机制"""
    for temp_path in temp_paths:
        if temp_path:
            path_obj = Path(temp_path) if not isinstance(temp_path, Path) else temp_path
            if path_obj.exists():
                try:
                    path_obj.unlink()
                except OSError as e:
                    print(f"清理临时文件失败 {temp_path}: {e}")

# 使用try-finally确保清理
def process_song(self, song_details, download_dir, progress_callback=None):
    temp_audio_path = None
    temp_cover_path = None
    try:
        # ... 处理逻辑 ...
    except Exception as e:
        self.status_signal.emit(f"处理歌曲时发生错误: {e}")
        return None
    finally:
        self._cleanup_temp_files(temp_audio_path, temp_cover_path)
```

### 跨平台路径处理
```python
# 全项目迁移到pathlib.Path
from pathlib import Path

# 替代模式：
# 旧：os.path.join(dir, filename)
# 新：Path(dir) / filename

# 旧：os.makedirs(path, exist_ok=True)
# 新：Path(path).mkdir(parents=True, exist_ok=True)

# 旧：os.path.exists(path)
# 新：Path(path).exists()

# UI组件兼容性处理：
self.path_display = QLineEdit(str(self.download_dir))  # Path对象转字符串
```

## 开发最佳实践

### 代码结构原则
1. **单一职责**: 每个模块只处理一类功能
2. **依赖注入**: 组件间通过构造函数传递依赖
3. **信号优先**: 使用Qt信号槽而非直接调用实现解耦
4. **错误处理**: 网络操作包含完整的异常处理

### UI开发指南
1. **组件化**: 复杂UI拆分为独立的组件类
2. **样式分离**: 所有视觉样式在 `style.qss` 中统一管理
3. **响应式设计**: 使用Qt布局管理器适应窗口大小变化
4. **无障碍支持**: 提供工具提示和键盘快捷键

### 性能优化要点
1. **懒加载**: 歌曲详情只在需要时获取
2. **缓存策略**: 搜索结果和歌曲详情适当缓存
3. **异步处理**: 所有耗时操作移至后台线程
4. **内存管理**: 及时清理不再使用的线程和临时文件

## 构建和部署

### Nuitka配置要点
- `--enable-plugin=pyside6`: 启用PySide6插件支持
- `--include-qt-plugins=multimedia`: 包含音频播放所需的Qt插件
- `--include-data-dir=ui/resources=ui/resources`: 确保样式表等资源文件包含
- `--windows-console-mode=disable`: Windows下隐藏控制台窗口

### Inno Setup配置
- 64位模式安装: `ArchitecturesInstallIn64BitMode=x64compatible`
- 中文界面支持: `MessagesFile: "Chinese.isl"`
- 自动关联文件类型: `ChangesAssociations=yes`

## 扩展指南

### 添加新的音乐源
1. 在 `core/api.py` 中添加新的API端点
2. 实现统一的搜索和详情获取接口
3. 更新 `get_song_details_robust` 支持新源

### UI主题自定义
1. 修改 `ui/resources/style.qss` 中的颜色变量
2. 调整 `core/constants.py` 中的UI常量
3. 测试所有组件的视觉一致性

### 新功能集成
1. 在 `core/` 中实现业务逻辑
2. 在 `ui/components/` 中创建对应UI组件
3. 在 `main_window.py` 中集成并连接信号槽

## 故障排除

### 常见问题及解决方案
1. **音频设备切换问题**: 
   - **症状**: Windows下切换声卡后音频仍从旧设备输出
   - **解决**: v1.2.0已修复，程序会自动检测设备变化并切换音频输出

2. **程序长时间运行后崩溃**:
   - **症状**: 使用几小时后出现意外关闭
   - **解决**: v1.2.0已修复线程管理和内存泄漏问题

3. **歌词显示卡顿**:
   - **症状**: 歌词滚动时界面卡顿
   - **解决**: 已优化为缓存+二分查找机制，大幅提升性能

4. **网络请求超时**:
   - **症状**: 搜索或下载时频繁超时
   - **解决**: 引入连接池和智能重试机制，提升网络稳定性

5. **Path对象类型错误**:
   - **症状**: `TypeError: 'PySide6.QtWidgets.QLineEdit.__init__' called with wrong argument types: WindowsPath`
   - **解决**: 确保传递给Qt组件的路径参数为字符串：`str(path_object)`

6. **RuntimeWarning信号断开连接**:
   - **症状**: `Failed to disconnect (None) from signal "finished()"`
   - **解决**: 使用`try-except (RuntimeError, TypeError)`捕获断开连接异常

7. **样式表无法加载**: 检查 `ui/resources/style.qss` 路径
8. **音频无法播放**: 确认Qt多媒体插件已正确包含
9. **线程相关错误**: 确保UI更新只在主线程中进行

### 调试建议
1. **性能分析**: 
   - 使用任务管理器监控内存使用情况
   - 检查CPU占用率，特别是歌词播放时
   
2. **网络问题排查**:
   - 检查防火墙设置和代理配置
   - 验证API端点可用性：`https://www.hhlqilongzhu.cn/api/joox/juhe_music.php`
   
3. **线程调试**:
   - 启用控制台输出查看线程创建和销毁信息
   - 关注`active_threads`集合的大小变化
   
4. **日志记录**:
   - 启用PySide6日志：`export QT_LOGGING_RULES="qt.pyside.libpyside.warning=true"`
   - 检查 `playlists.json` 文件格式是否正确
   
5. **依赖检查**:
   - 验证所有依赖库版本兼容性：`pip list`
   - 确保PySide6版本 >= 6.0.0