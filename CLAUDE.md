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
    --windows-file-version=1.1.0 \
    --windows-product-version=1.1.0 \
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
│   ├── main_window.py        # 主窗口（720行，核心UI逻辑）
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

#### `ui/main_window.py` - 主界面控制器（720行）
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

### 常见问题
1. **样式表无法加载**: 检查 `ui/resources/style.qss` 路径
2. **音频无法播放**: 确认Qt多媒体插件已正确包含
3. **网络请求失败**: 检查API端点可用性和网络连接
4. **线程相关错误**: 确保UI更新只在主线程中进行

### 调试建议
1. 启用控制台输出查看详细错误信息
2. 使用Qt Creator的调试器进行断点调试
3. 检查 `playlists.json` 文件格式是否正确
4. 验证所有依赖库版本兼容性