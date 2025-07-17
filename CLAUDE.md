# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Application
```bash
python main.py
```

### Installing Dependencies
```bash
pip install -r requirements.txt
```
Required packages: PySide6, requests, mutagen, qtawesome, simplejson

### Building with Nuitka
```bash
python -m nuitka --standalone --assume-yes-for-downloads --enable-plugin=pyside6 --include-qt-plugins=multimedia --windows-console-mode=disable --output-dir=dist --include-data-dir=ui/resources=ui/resources --windows-icon-from-ico=icon.ico --windows-company-name=XHZX --windows-product-name="音乐下载器" --windows-file-version=1.1.0 --windows-product-version=1.1.0 --output-filename=MusicDownloader.exe main.py
```

### Creating Installer (Inno Setup required)
```bash
iscc inno_setup.iss
```

## Architecture Overview

This is a **PySide6-based desktop music downloader application** that follows a modular architecture with clear separation of concerns:

### Core Architecture Patterns
- **Threading Model**: All network operations (search, download, playlist import) run in background QThread workers to prevent UI blocking
- **Signal-Slot Communication**: Qt's signal-slot mechanism handles all inter-component communication between threads and UI
- **Robust API Strategy**: Implements a two-tier fallback system for song matching - content-based matching first, then index-based as backup

### Module Structure

#### `core/` - Business Logic Layer
- **`api.py`**: Single API endpoint wrapper with robust song detail fetching
  - `search_music()`: Returns songs with both `raw_title` (original) and `title` (cleaned) variants
  - `get_song_details_robust()`: Primary function using content-based matching with index fallback
- **`downloader.py`**: Background thread workers for all async operations
  - `SearchThread`, `SongDetailsThread`: Non-blocking search operations
  - `SingleDownloadThread`, `BatchDownloadThread`: File download with progress tracking
  - `PlaylistImportThread`: Handles playlist import with deduplication and incremental matching
- **`playlist_manager.py`**: Playlist CRUD operations with JSON persistence
- **`fetch_playlist.py`**: External playlist import functionality

#### `ui/` - Presentation Layer
- **`main_window.py`**: Main Qt application window
  - Uses `QStackedWidget` for playlist/lyrics view switching
  - Implements audio playback with `QMediaPlayer` and volume animations
  - Real-time lyrics synchronization with `QTimer`
- **`resources/style.qss`**: Custom QSS stylesheet for UI theming

#### `utils/` - Utility Functions
- **`lrc_parser.py`**: LRC lyrics format parsing and time synchronization

### Key Technical Details

#### Threading and UI Safety
- All network operations run in separate QThread instances
- UI updates only occur through Qt signal emissions from worker threads
- Main thread handles all Qt widget operations

#### Audio and Metadata Handling
- Uses Mutagen library for MP3 metadata embedding (ID3 tags, cover art, lyrics)
- PySide6's QMediaPlayer handles audio playback with fade in/out animations
- Supports both plain text and synchronized LRC lyrics

#### Playlist Management
- JSON-based persistence in `playlists.json`
- Deduplication based on `raw_title` and `singer` comparison
- Incremental import reduces API calls for large playlists

#### Build System
- **Nuitka** (not PyInstaller) for creating standalone executables
- Inno Setup for Windows installer generation
- GitHub Actions CI/CD pipeline for automated builds
- Qt multimedia plugins explicitly included for audio support

### Important Implementation Notes

#### API Robustness Strategy
The `get_song_details_robust()` function in `core/api.py:73-76` implements a critical reliability pattern:
1. Primary: Search using cleaned title + singer, then exact match against results
2. Fallback: Use original query + song index if primary method fails

This ensures playlist longevity even when API indices change.

#### Threading Architecture
Background threads emit progress and status signals that the main window connects to via Qt's signal-slot system. Never directly modify UI elements from worker threads.

#### Resource Handling
UI resources must be included in builds using `--include-data-dir=ui/resources=ui/resources` for Nuitka, and explicitly copied post-build if needed.