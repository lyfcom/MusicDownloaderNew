import os
import re
import mimetypes
import requests
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QTableWidget
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.id3 import ID3, APIC, TPE1, TIT2, TALB, USLT, SYLT, ID3NoHeaderError
from mutagen import File as MutagenFile

from utils.lrc_parser import parse_lrc_line
from core.api import get_song_details_robust, search_music, get_session, get_lyric
from core.fetch_playlist import fetch_qq_playlist

class BaseDownloader(QThread):
    """Base class for downloader threads to share common methods."""
    status_signal = Signal(str)
    progress_signal = Signal(int)

    def download_file(self, url, file_path, progress_callback=None):
        """Downloads a file to a specified path, with progress reporting."""
        try:
            session = get_session()
            response = session.get(url, stream=True, timeout=(10, 30))  # 下载使用更长超时
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
        except requests.exceptions.Timeout:
            self.status_signal.emit("文件下载超时，请检查网络连接")
            return False
        except requests.exceptions.ConnectionError:
            self.status_signal.emit("网络连接错误，请检查网络设置")
            return False
        except requests.RequestException as e:
            self.status_signal.emit(f"文件下载失败: {e}")
            return False

    def embed_metadata(self, audio_file_path, song_details, temp_cover_path=None):
        """Embeds metadata (lyrics, cover, etc.) into the audio file.

        Supports multiple audio formats: MP3, FLAC, M4A, etc.
        """
        try:
            audio_path = Path(audio_file_path)
            file_ext = audio_path.suffix.lower()

            # 获取标准化的元数据
            title = song_details.get('title', '')
            if '[' in title and ']' in title:
                title = title.rsplit('[', 1)[0].strip()
            singer = song_details.get('singer', '')
            album = song_details.get('album', '')
            lyric = song_details.get('lyric', '')

            # 根据文件格式选择处理方式
            if file_ext in ['.mp3', '.mp2', '.mp1']:
                self._embed_metadata_mp3(audio_file_path, title, singer, album, lyric, temp_cover_path)
            elif file_ext in ['.flac']:
                self._embed_metadata_flac(audio_file_path, title, singer, album, lyric, temp_cover_path)
            elif file_ext in ['.m4a', '.mp4', '.m4b', '.m4p']:
                self._embed_metadata_mp4(audio_file_path, title, singer, album, lyric, temp_cover_path)
            else:
                # 对于其他格式，尝试使用mutagen自动识别
                try:
                    audio = MutagenFile(audio_file_path, easy=True)
                    if audio is not None:
                        audio['title'] = title
                        audio['artist'] = singer
                        audio['album'] = album
                        audio.save()
                except:
                    self.status_signal.emit(f"不支持的音频格式: {file_ext}，跳过元数据嵌入")

        except Exception as e:
            self.status_signal.emit(f"嵌入元数据失败: {e}")

    def _embed_metadata_mp3(self, audio_file_path, title, singer, album, lyric, cover_path):
        """为MP3文件嵌入元数据"""
        try:
            try:
                audio = MP3(audio_file_path, ID3=ID3)
            except ID3NoHeaderError:
                audio = MP3(audio_file_path)
                audio.add_tags()

            tags = audio.tags
            tags.add(TPE1(encoding=3, text=singer))
            tags.add(TIT2(encoding=3, text=title))
            tags.add(TALB(encoding=3, text=album))

            # Embed lyrics
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
            if cover_path and os.path.exists(cover_path):
                mime = mimetypes.guess_type(cover_path)[0] or 'image/jpeg'
                with open(cover_path, 'rb') as f:
                    cover_data = f.read()
                tags.add(APIC(encoding=3, mime=mime, type=3, desc='Cover', data=cover_data))

            audio.save()
        except Exception as e:
            raise Exception(f"MP3元数据嵌入失败: {e}")

    def _embed_metadata_flac(self, audio_file_path, title, singer, album, lyric, cover_path):
        """为FLAC文件嵌入元数据"""
        try:
            audio = FLAC(audio_file_path)

            audio['title'] = title
            audio['artist'] = singer
            audio['album'] = album

            # FLAC的歌词存储为LYRICS标签
            if lyric:
                plain_lyrics = re.sub(r'\[\d{2}:\d{2}(\.\d{2,3})?\]', '', lyric).strip()
                audio['lyrics'] = plain_lyrics

            # Embed cover for FLAC
            if cover_path and os.path.exists(cover_path):
                from mutagen.flac import Picture
                import imghdr

                picture = Picture()
                with open(cover_path, 'rb') as f:
                    picture.data = f.read()

                picture.type = 3  # Cover (front)
                picture.mime = 'image/jpeg'
                img_type = imghdr.what(cover_path)
                if img_type:
                    picture.mime = f'image/{img_type}'

                audio.add_picture(picture)

            audio.save()
        except Exception as e:
            raise Exception(f"FLAC元数据嵌入失败: {e}")

    def _embed_metadata_mp4(self, audio_file_path, title, singer, album, lyric, cover_path):
        """为MP4/M4A文件嵌入元数据"""
        try:
            from mutagen.mp4 import MP4, MP4Cover

            audio = MP4(audio_file_path)

            audio['\xa9nam'] = title  # Title
            audio['\xa9ART'] = singer  # Artist
            audio['\xa9alb'] = album  # Album

            # MP4的歌词
            if lyric:
                plain_lyrics = re.sub(r'\[\d{2}:\d{2}(\.\d{2,3})?\]', '', lyric).strip()
                audio['\xa9lyr'] = plain_lyrics

            # Embed cover for MP4
            if cover_path and os.path.exists(cover_path):
                with open(cover_path, 'rb') as f:
                    cover_data = f.read()

                # 判断图片格式
                if cover_path.lower().endswith('.png'):
                    cover_format = MP4Cover.FORMAT_PNG
                else:
                    cover_format = MP4Cover.FORMAT_JPEG

                audio['covr'] = [MP4Cover(cover_data, imageformat=cover_format)]

            audio.save()
        except Exception as e:
            raise Exception(f"MP4元数据嵌入失败: {e}")

    def process_song(self, song_details, download_dir, progress_callback=None):
        """Main logic to download audio, cover, and embed metadata for a single song."""
        url = song_details.get('url')
        if not url:
            # API详情返回的是'song'字段，不是'title'
            song_name = song_details.get('song') or song_details.get('title', '未知歌名')
            self.status_signal.emit(f"歌曲 '{song_name}' 无有效链接，跳过。")
            return None

        download_path = Path(download_dir)
        download_path.mkdir(parents=True, exist_ok=True)

        # Clean filename - API详情返回的字段是'song'而不是'title'
        title = song_details.get('song') or song_details.get('title', '未知歌名')
        if '[' in title and ']' in title:
            title = title.rsplit('[', 1)[0].strip()
        singer = song_details.get('singer', '未知歌手')
        filename_prefix = re.sub(r'[\\/*?:"<>|]', '', f"{title} - {singer}")

        # Determine file extension
        # 优先从URL中提取扩展名（更可靠），因为服务器返回的Content-Type可能不准确
        parsed_url = urlparse(url)
        url_path = parsed_url.path
        url_ext = os.path.splitext(url_path)[1].lower()

        if url_ext in ['.mp3', '.flac', '.m4a', '.ogg', '.wav', '.aac', '.wma']:
            # URL中有明确的音频格式扩展名，直接使用
            ext = url_ext
        else:
            # URL中没有扩展名，尝试从Content-Type判断
            try:
                session = get_session()
                response = session.head(url, allow_redirects=True, timeout=(5, 10))
                content_type = response.headers.get('Content-Type', '').lower()
                ext = mimetypes.guess_extension(content_type) or '.mp3'
            except requests.RequestException:
                ext = '.mp3'

        final_path = download_path / f"{filename_prefix}{ext}"
        if final_path.exists():
            self.status_signal.emit(f"文件 '{final_path.name}' 已存在。")
            return str(final_path)  # Indicate that it exists, no need to re-download.

        temp_audio_path = download_path / f"temp_{os.urandom(8).hex()}{ext}"
        temp_cover_path = None

        try:
            # Download audio
            self.status_signal.emit(f"正在下载: {title}...")
            if not self.download_file(url, temp_audio_path, progress_callback):
                return None

            # Download cover
            cover_url = song_details.get('cover')
            if cover_url:
                temp_cover_path = download_path / f"temp_cover_{os.urandom(8).hex()}.jpg"
                if not self.download_file(cover_url, temp_cover_path, None):
                    # 封面下载失败不影响主流程，但要清理临时文件
                    if temp_cover_path and temp_cover_path.exists():
                        temp_cover_path.unlink()
                    temp_cover_path = None

            # 获取歌词（新API需要单独请求）
            song_id = song_details.get('songID') or song_details.get('id')
            if song_id:
                lyric_data = get_lyric(song_id)
                if lyric_data and lyric_data.get('lrc'):
                    song_details['lyric'] = lyric_data['lrc']

            # 标准化字段名：将'song'字段复制为'title'以便元数据嵌入使用
            if 'song' in song_details and 'title' not in song_details:
                song_details['title'] = song_details['song']

            # Embed metadata
            self.status_signal.emit(f"正在嵌入元数据...")
            self.embed_metadata(temp_audio_path, song_details, temp_cover_path)

            # Rename to final filename
            try:
                temp_audio_path.rename(final_path)
                temp_audio_path = None  # 重命名成功，不需要清理
                self.status_signal.emit(f"下载完成: {final_path.name}")
                return str(final_path)
            except OSError as e:
                self.status_signal.emit(f"重命名文件失败: {e}")
                return None

        except Exception as e:
            self.status_signal.emit(f"处理歌曲时发生错误: {e}")
            return None
        finally:
            # 确保清理所有临时文件（重命名成功的文件不会被清理）
            self._cleanup_temp_files(temp_audio_path, temp_cover_path)

    def _cleanup_temp_files(self, *temp_paths):
        """清理临时文件的统一方法"""
        for temp_path in temp_paths:
            if temp_path:
                try:
                    # 支持Path对象和字符串路径
                    path_obj = Path(temp_path) if not isinstance(temp_path, Path) else temp_path
                    if path_obj.exists():
                        path_obj.unlink()
                except OSError as e:
                    print(f"清理临时文件失败 {temp_path}: {e}")


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

    def __init__(self, song_info, table, row, quality=9, parent=None):
        super().__init__(parent)
        self.song_info = song_info
        self.table = table
        self.row = row
        self.quality = quality

    def run(self):
        try:
            details = get_song_details_robust(self.song_info, quality=self.quality)
            self.finished_signal.emit(details, self.song_info, self.table, self.row)
        except Exception as e:
            self.status_signal.emit(f"获取歌曲详情失败: {e}")
            self.finished_signal.emit({}, self.song_info, self.table, self.row)


class SingleDownloadThread(BaseDownloader):
    """Thread for downloading a single song."""
    finished_signal = Signal(bool, str) # success, message/filepath
    progress_signal = Signal(int)

    def __init__(self, song_info, download_dir, quality=9, parent=None):
        super().__init__(parent)
        self.song_info = song_info
        self.download_dir = download_dir
        self.quality = quality

    def run(self):
        details = get_song_details_robust(self.song_info, quality=self.quality)
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

    def __init__(self, playlist, download_dir, quality=9):
        super().__init__()
        self.playlist = playlist
        self.download_dir = download_dir
        self.quality = quality

    def run(self):
        total = len(self.playlist)
        for i, song_info in enumerate(self.playlist):
            self.batch_progress_signal.emit(i + 1, total)

            details = get_song_details_robust(song_info, quality=self.quality)
            if not details:
                self.status_signal.emit(f"无法获取 '{song_info.get('title')}' 详情，跳过。")
                continue

            self.process_song(details, self.download_dir)
            self.single_finished_signal.emit(song_info['title'])

        self.batch_finished_signal.emit(True, "批量下载完成！")


class PlaylistImportThread(QThread):
    """
    后台线程，用于从 QQ 音乐导入歌单，并进行预匹配和去重。
    """
    finished_signal = Signal(bool, str, list) # success, target_playlist_name, matched_songs
    status_signal = Signal(str)
    progress_signal = Signal(int, int) # current, total

    def __init__(self, playlist_id, target_playlist_name, existing_songs, parent=None):
        super().__init__(parent)
        self.playlist_id = playlist_id
        self.target_playlist_name = target_playlist_name
        self.existing_songs = existing_songs

    def run(self):
        try:
            self.status_signal.emit("正在获取歌单信息...")
            raw_songs = fetch_qq_playlist(self.playlist_id)
            if not raw_songs:
                self.status_signal.emit("无法获取歌单或歌单为空")
                self.finished_signal.emit(False, self.target_playlist_name, [])
                return

            self.status_signal.emit("检查重复歌曲...")
            
            # Create a set of existing songs for efficient lookup
            # Use a simplified title (removing tags) for comparison
            existing_set = set()
            for song in self.existing_songs:
                title = song.get('title', '').strip()
                if '[' in title and ']' in title:
                    title = title.rsplit('[', 1)[0].strip()
                # 预处理：去除空格，转小写，替换'/'为'&'
                title = title.replace(' ', '').lower().replace('/', '&')
                singer = song.get('singer', '').replace(' ', '').lower().replace('/', '&')
                existing_set.add((title, singer))

            # Filter out songs that already exist
            new_songs_to_match = []
            for song in raw_songs:
                title = song.get('title', '').strip()
                if '[' in title and ']' in title:
                     title = title.rsplit('[', 1)[0].strip()
                # 预处理：去除空格，转小写，替换'/'为'&'
                processed_title = title.replace(' ', '').lower().replace('/', '&')
                processed_singer = song.get('singer', '').replace(' ', '').lower().replace('/', '&')
                if (processed_title, processed_singer) not in existing_set:
                    new_songs_to_match.append(song)
            
            if not new_songs_to_match:
                self.status_signal.emit("歌单中的所有歌曲已存在于目标播放列表。")
                self.finished_signal.emit(True, self.target_playlist_name, [])
                return

            # Match the remaining new songs
            matched_songs = []
            total = len(new_songs_to_match)
            for i, song in enumerate(new_songs_to_match):
                self.status_signal.emit(f"正在匹配: {song['title']} ({i+1}/{total})")
                query = f"{song['title']} {song['singer']}"
                search_results = search_music(query)
                if search_results:
                    # Heuristic: Pick the first result as the best match.
                    # This is a reasonable assumption for a specific "title artist" query.
                    # 插入头部
                    matched_songs.insert(0, search_results[0])
                self.progress_signal.emit(i + 1, total)

            self.finished_signal.emit(True, self.target_playlist_name, matched_songs)

        except Exception as e:
            self.status_signal.emit(f"导入歌单时出错: {e}")
            self.finished_signal.emit(False, self.target_playlist_name, []) 