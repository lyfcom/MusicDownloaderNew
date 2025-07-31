import json
from pathlib import Path

class PlaylistManager:
    def __init__(self, playlist_file=None):
        if playlist_file is None:
            # 将playlist.json存储在用户的AppData/Roaming目录中，避免权限问题
            app_data_dir = Path.home() / "AppData" / "Roaming" / "MusicDownloader"
            app_data_dir.mkdir(parents=True, exist_ok=True)  # 确保目录存在
            self.playlist_file = app_data_dir / "playlists.json"
            
            # 数据迁移：检查旧位置的playlist.json并迁移到新位置
            self._migrate_old_data()
        else:
            self.playlist_file = Path(playlist_file)
        self.playlists = self.load()

    def _migrate_old_data(self):
        """迁移旧位置的playlist.json到新的AppData目录"""
        # 检查可能的旧位置
        old_locations = [
            Path("playlists.json"),  # 当前工作目录
            Path.cwd() / "playlists.json",  # 程序运行目录
        ]
        
        # 如果新位置已经有文件，跳过迁移
        if self.playlist_file.exists():
            return
        
        # 查找并迁移第一个找到的旧文件
        for old_path in old_locations:
            if old_path.exists() and old_path != self.playlist_file:
                try:
                    # 读取旧文件内容
                    with old_path.open('r', encoding='utf-8') as f:
                        old_data = json.load(f)
                    
                    # 写入新位置
                    with self.playlist_file.open('w', encoding='utf-8') as f:
                        json.dump(old_data, f, indent=4, ensure_ascii=False)
                    
                    # 迁移成功后，可选择删除旧文件（为安全起见，这里不删除）
                    print(f"✅ 歌单数据已从 {old_path} 迁移到 {self.playlist_file}")
                    break
                    
                except (json.JSONDecodeError, IOError) as e:
                    print(f"⚠️ 迁移歌单数据时出错: {e}")
                    continue

    def load(self):
        """Loads playlists from the JSON file."""
        if self.playlist_file.exists():
            try:
                with self.playlist_file.open('r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                # If file is corrupted or unreadable, start with an empty structure
                return {"默认列表": []}
        return {"默认列表": []}

    def save(self):
        """Saves the current playlists to the JSON file."""
        try:
            with self.playlist_file.open('w', encoding='utf-8') as f:
                json.dump(self.playlists, f, indent=4, ensure_ascii=False)
            return True
        except IOError:
            return False

    def get_playlist_names(self):
        """Returns a list of all playlist names."""
        return list(self.playlists.keys())

    def get_playlist_songs(self, name):
        """Returns the list of songs for a given playlist name."""
        return self.playlists.get(name, [])

    def create(self, name):
        """Creates a new, empty playlist. Returns False if it already exists."""
        if name in self.playlists:
            return False
        self.playlists[name] = []
        self.save()
        return True

    def delete(self, name):
        """Deletes a playlist. Returns False if it doesn't exist."""
        if name in self.playlists:
            # Prevent deletion of the last playlist
            if len(self.playlists) == 1:
                return False
            del self.playlists[name]
            self.save()
            return True
        return False
        
    def rename(self, old_name, new_name):
        """Renames a playlist. Returns False if new name exists or old name doesn't."""
        if old_name not in self.playlists or new_name in self.playlists:
            return False
        self.playlists[new_name] = self.playlists.pop(old_name)
        self.save()
        return True

    def add_song(self, playlist_name, song_info):
        """Adds a song to a playlist. Returns False if the song is already there."""
        if playlist_name not in self.playlists:
            return False
            
        playlist = self.playlists[playlist_name]
        # Prevent duplicates based on raw_title and singer
        for song in playlist:
            if song.get('raw_title') == song_info.get('raw_title') and song.get('singer') == song_info.get('singer'):
                return False

        # Only store necessary info to keep the file clean
        info_to_store = {
            'n': song_info.get('n'),
            'raw_title': song_info.get('raw_title'),
            'title': song_info.get('title'),
            'singer': song_info.get('singer'),
            'query': song_info.get('query')
        }
        playlist.insert(0, info_to_store)
        self.save()
        return True

    def remove_song(self, playlist_name, song_index):
        """Removes a song from a playlist by its index."""
        if playlist_name not in self.playlists:
            return False
        
        playlist = self.playlists[playlist_name]
        if 0 <= song_index < len(playlist):
            playlist.pop(song_index)
            self.save()
            return True
        return False 