import requests
import json

def fetch_qq_playlist(playlist_id):
    """
    通过 QQ 音乐歌单 API 获取歌单内所有歌曲信息
    """
    # API URL, a more reliable way to fetch playlist data
    url = f"https://c.y.qq.com/qzone/fcg-bin/fcg_ucc_getcdinfo_byids_cp.fcg?disstid={playlist_id}&type=1&json=1&utf8=1&onlysong=0&format=json"

    # Set request headers to mimic a browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Safari/537.36',
        'Referer': 'https://y.qq.com/',
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes

        data = response.json()
        
        songs = []
        if 'cdlist' in data and data['cdlist']:
            song_list = data['cdlist'][0].get('songlist', [])
            for song_item in song_list:
                song_title = song_item.get('songname', '')
                
                # Extract singer names, which might be multiple
                singers = song_item.get('singer', [])
                singer_names = ' / '.join([s.get('name', '') for s in singers])
                
                if song_title and singer_names:
                    songs.append({
                        'title': song_title,
                        'singer': singer_names,
                    })
        return songs

    except requests.exceptions.RequestException as e:
        print(f"Error during API request: {e}")
        return []
    except json.JSONDecodeError:
        print("Failed to parse JSON data")
        return []

# For testing purposes
if __name__ == '__main__':
    playlist_id = '9521850610'  # Example playlist ID from user
    song_list = fetch_qq_playlist(playlist_id)
    if song_list:
        print(f"Successfully fetched {len(song_list)} songs:")
        for i, song in enumerate(song_list, 1):  # Print all songs
            print(f"  {i}. {song['title']} - {song['singer']}")
    else:
        print("Could not fetch any songs.")