import json
from pathlib import Path

class PlaylistManager:
    def __init__(self, playlist_file="playlists.json"):
        self.playlist_file = Path(playlist_file)
        self.playlists = self.load()

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