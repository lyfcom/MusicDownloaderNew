import os
import re
import mimetypes
import requests
from urllib.parse import urlparse

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QTableWidget
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TPE1, TIT2, TALB, USLT, SYLT, ID3NoHeaderError

from utils.lrc_parser import parse_lrc_line
from core.api import get_song_details_robust, search_music
from core.fetch_playlist import fetch_qq_playlist

class BaseDownloader(QThread):
    """Base class for downloader threads to share common methods."""
    status_signal = Signal(str)
    progress_signal = Signal(int)

    def download_file(self, url, file_path, progress_callback=None):
        """Downloads a file to a specified path, with progress reporting."""
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if progress_callback and total_size > 0:
                            progress = int((downloaded_size / total_size) * 100)
                            progress_callback(progress)
            return True
        except requests.RequestException as e:
            self.status_signal.emit(f"文件下载失败: {e}")
            return False

    def embed_metadata(self, audio_file_path, song_details, temp_cover_path=None):
        """Embeds metadata (lyrics, cover, etc.) into the audio file."""
        try:
            try:
                audio = MP3(audio_file_path, ID3=ID3)
            except ID3NoHeaderError:
                audio = MP3(audio_file_path)
                audio.add_tags()

            # Add basic tags
            tags = audio.tags
            tags.add(TPE1(encoding=3, text=song_details.get('singer', '')))
            title = song_details.get('title', '')
            if '[' in title and ']' in title:
                 title = title.rsplit('[', 1)[0].strip()
            tags.add(TIT2(encoding=3, text=title))
            tags.add(TALB(encoding=3, text=song_details.get('album', '')))
            
            # Embed lyrics
            lyric = song_details.get('lyric')
            if lyric:
                plain_lyrics = re.sub(r'\[\d{2}:\d{2}(\.\d{2,3})?\]', '', lyric).strip()
                tags.add(USLT(encoding=3, lang='chi', desc='', text=plain_lyrics))
                
                sylt_frames = []
                for line in lyric.strip().split('\n'):
                    parsed = parse_lrc_line(line)
                    if parsed and parsed[1]:
                        sylt_frames.append((parsed[1], parsed[0]))
                if sylt_frames:
                    tags.add(SYLT(encoding=3, lang='chi', type=1, format=2, desc='Lyrics', sync=sylt_frames))
            
            # Embed cover
            if temp_cover_path and os.path.exists(temp_cover_path):
                mime = mimetypes.guess_type(temp_cover_path)[0] or 'image/jpeg'
                with open(temp_cover_path, 'rb') as f:
                    cover_data = f.read()
                tags.add(APIC(encoding=3, mime=mime, type=3, desc='Cover', data=cover_data))

            audio.save()
        except Exception as e:
            self.status_signal.emit(f"嵌入元数据失败: {e}")
        finally:
            if temp_cover_path and os.path.exists(temp_cover_path):
                os.remove(temp_cover_path)

    def process_song(self, song_details, download_dir, progress_callback=None):
        """Main logic to download audio, cover, and embed metadata for a single song."""
        url = song_details.get('url')
        if not url:
            self.status_signal.emit(f"歌曲 '{song_details.get('title')}' 无有效链接，跳过。")
            return None

        os.makedirs(download_dir, exist_ok=True)
        
        # Clean filename
        title = song_details.get('title', '未知歌名')
        if '[' in title and ']' in title:
            title = title.rsplit('[', 1)[0].strip()
        singer = song_details.get('singer', '未知歌手')
        filename_prefix = re.sub(r'[\\/*?:"<>|]', '', f"{title} - {singer}")

        # Determine file extension
        try:
            response = requests.head(url, allow_redirects=True, timeout=5)
            content_type = response.headers.get('Content-Type', '').lower()
            ext = mimetypes.guess_extension(content_type) or '.mp3'
        except requests.RequestException:
            ext = '.mp3'
        
        final_path = os.path.join(download_dir, f"{filename_prefix}{ext}")
        if os.path.exists(final_path):
            self.status_signal.emit(f"文件 '{os.path.basename(final_path)}' 已存在。")
            return final_path # Indicate that it exists, no need to re-download.

        temp_audio_path = os.path.join(download_dir, f"temp_{os.urandom(8).hex()}{ext}")
        
        # Download audio
        self.status_signal.emit(f"正在下载: {title}...")
        if not self.download_file(url, temp_audio_path, progress_callback):
            if os.path.exists(temp_audio_path): os.remove(temp_audio_path)
            return None

        # Download cover
        temp_cover_path = None
        cover_url = song_details.get('cover')
        if cover_url:
            temp_cover_path = os.path.join(download_dir, f"temp_cover_{os.urandom(8).hex()}.jpg")
            if not self.download_file(cover_url, temp_cover_path):
                temp_cover_path = None

        # Embed metadata
        self.status_signal.emit(f"正在嵌入元数据...")
        self.embed_metadata(temp_audio_path, song_details, temp_cover_path)

        # Rename to final filename
        try:
            os.rename(temp_audio_path, final_path)
            self.status_signal.emit(f"下载完成: {os.path.basename(final_path)}")
            return final_path
        except OSError as e:
            self.status_signal.emit(f"重命名文件失败: {e}")
            if os.path.exists(temp_audio_path): os.remove(temp_audio_path)
            return None


class SearchThread(QThread):
    """
    后台线程，用于执行音乐搜索，避免UI阻塞。
    """
    finished_signal = Signal(list)
    status_signal = Signal(str)

    def __init__(self, query, parent=None):
        super().__init__(parent)
        self.query = query

    def run(self):
        try:
            songs = search_music(self.query)
            self.finished_signal.emit(songs)
        except Exception as e:
            self.status_signal.emit(f"搜索失败: {e}")
            self.finished_signal.emit([])


class SongDetailsThread(QThread):
    """
    后台线程，用于获取单曲的详细信息（包括播放URL和歌词），避免UI阻塞。
    """
    finished_signal = Signal(dict, dict, QTableWidget, int) # details, song_info, table, row
    status_signal = Signal(str)

    def __init__(self, song_info, table, row, parent=None):
        super().__init__(parent)
        self.song_info = song_info
        self.table = table
        self.row = row

    def run(self):
        try:
            details = get_song_details_robust(self.song_info)
            self.finished_signal.emit(details, self.song_info, self.table, self.row)
        except Exception as e:
            self.status_signal.emit(f"获取歌曲详情失败: {e}")
            self.finished_signal.emit({}, self.song_info, self.table, self.row)


class SingleDownloadThread(BaseDownloader):
    """Thread for downloading a single song."""
    finished_signal = Signal(bool, str) # success, message/filepath
    progress_signal = Signal(int)

    def __init__(self, song_info, download_dir, parent=None):
        super().__init__(parent)
        self.song_info = song_info
        self.download_dir = download_dir

    def run(self):
        details = get_song_details_robust(self.song_info)
        if not details:
            msg = f"无法获取 '{self.song_info['title']}' 的详细信息。"
            self.status_signal.emit(msg)
            self.finished_signal.emit(False, msg)
            return

        final_path = self.process_song(details, self.download_dir, self.progress_signal.emit)
        if final_path:
            self.finished_signal.emit(True, final_path)
        else:
            self.finished_signal.emit(False, f"下载 '{self.song_info['title']}' 失败。")


class BatchDownloadThread(BaseDownloader):
    """Thread for downloading a playlist of songs."""
    batch_finished_signal = Signal(bool, str) # success, message
    single_finished_signal = Signal(str) # song title
    batch_progress_signal = Signal(int, int) # current, total

    def __init__(self, playlist, download_dir):
        super().__init__()
        self.playlist = playlist
        self.download_dir = download_dir

    def run(self):
        total = len(self.playlist)
        for i, song_info in enumerate(self.playlist):
            self.batch_progress_signal.emit(i + 1, total)
            
            details = get_song_details_robust(song_info)
            if not details:
                self.status_signal.emit(f"无法获取 '{song_info.get('title')}' 详情，跳过。")
                continue

            self.process_song(details, self.download_dir)
            self.single_finished_signal.emit(song_info['title'])
        
        self.batch_finished_signal.emit(True, "批量下载完成！")


class PlaylistImportThread(QThread):
    """用于处理歌单导入的线程，避免UI卡顿"""
    status_signal = Signal(str)
    progress_signal = Signal(int, int)  # current, total
    finished_signal = Signal(bool, str, list)  # success, playlist_name, imported_songs
    
    def __init__(self, playlist_id):
        super().__init__()
        self.playlist_id = playlist_id
        self.imported_songs = []
        self.new_playlist_name = ""
    
    def run(self):
        import random
        import string
        
        # 获取歌单内容
        self.status_signal.emit(f"正在获取歌单 ID: {self.playlist_id} 的内容...")
        songs = fetch_qq_playlist(self.playlist_id)
        
        if not songs:
            self.status_signal.emit(f"无法导入歌单，可能ID无效或网络问题")
            self.finished_signal.emit(False, "", [])
            return
        
        # 创建随机名称的新歌单
        random_suffix = ''.join(random.choice(string.ascii_letters) for _ in range(5))
        self.new_playlist_name = f"导入歌单_{random_suffix}"
        
        # 逐一处理歌单中的歌曲
        imported_count = 0
        total_count = len(songs)
        
        for i, song in enumerate(songs):
            title = song.get('title', '')
            singer = song.get('singer', '')
            
            # 通知进度
            self.progress_signal.emit(i + 1, total_count)
            self.status_signal.emit(f"正在匹配: {title} - {singer}")
            
            # 使用歌名和歌手搜索
            search_query = f"{title} {singer}"
            search_results = search_music(search_query)
            
            if search_results:
                matched_song = None
                
                # 先尝试完全匹配（去除标签后）
                for result in search_results:
                    cleaned_title = title
                    # 去除可能的标签，如[酷我]等
                    if '[' in cleaned_title and ']' in cleaned_title:
                        cleaned_title = cleaned_title.split('[', 1)[0].strip()
                    
                    cleaned_result_title = result.get('title', '')
                    
                    # 比较清理后的歌名和歌手
                    if cleaned_title.lower() == cleaned_result_title.lower() and singer.lower() in result.get('singer', '').lower():
                        matched_song = result
                        break
                
                # 如果没有完全匹配，默认使用第一个结果
                if not matched_song and search_results:
                    matched_song = search_results[0]
                
                # 添加到导入列表
                if matched_song:
                    self.imported_songs.append(matched_song)
                    imported_count += 1
        
        # 完成导入
        self.status_signal.emit(f"已匹配 {imported_count}/{total_count} 首歌曲")
        self.finished_signal.emit(True, self.new_playlist_name, self.imported_songs) 