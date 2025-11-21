import requests
import urllib.parse

class MusicAPI:
    def __init__(self, platform="tencent"):
        self.base_url = f"https://api.vkeys.cn/v2/music/{platform}"

    def search_music(self, keyword):
        """
        搜索歌曲，返回歌曲列表
        """
        params = {
            "word": keyword
        }
        encoded_params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        url = f"{self.base_url}?{encoded_params}"
        try:
            response = requests.get(url)
            data = response.json()
            if data.get("code") == 200 and isinstance(data.get("data"), list):
                return data.get("data")
            else:
                return []
        except Exception as e:
            print(f"解析响应时出错: {e}")
            return []

    def get_music_info_by_id(self, song_id):
        """
        通过歌曲ID获取歌曲详细信息（含播放地址）
        """
        params = {
            "id": song_id
        }
        encoded_params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        url = f"{self.base_url}?{encoded_params}"
        try:
            response = requests.get(url)
            data = response.json()
            if data.get("code") == 200 and isinstance(data.get("data"), dict):
                return data.get("data")
            else:
                return None
        except Exception as e:
            print(f"解析响应时出错: {e}")
            return None

def main():
    music_api = MusicAPI(platform="tencent")
    keyword = input("请输入歌曲关键词：")
    results = music_api.search_music(keyword)
    if not results:
        print("未找到相关歌曲。")
    else:
        print("\n搜索结果：")
        for idx, song in enumerate(results, 1):
            name = song.get("song") or song.get("name")
            singer = song.get("singer")
            album = song.get("album", "")
            print(f"{idx}. 歌曲：{name} | 歌手：{singer} | 专辑：{album}")

        # 用户选择
        while True:
            try:
                choice = int(input(f"\n请输入要播放的歌曲序号（1-{len(results)}，0取消）："))
                if choice == 0:
                    print("已取消。")
                    break
                if 1 <= choice <= len(results):
                    selected_song = results[choice - 1]
                    song_id = selected_song.get("id")
                    info = music_api.get_music_info_by_id(song_id)
                    if info:
                        url = info.get("url")
                        name = info.get("song") or info.get("name")
                        singer = info.get("singer")
                        print(f"\n歌曲：{name}\n歌手：{singer}\n歌曲播放地址：{url if url else '无'}")
                        if not url:
                            print("未找到相关歌曲的播放地址。")
                    else:
                        print("未找到相关歌曲。")
                    break
                else:
                    print("输入序号超出范围，请重新输入。")
            except ValueError:
                print("请输入有效的数字。")


if __name__ == "__main__":
    while True:
        main()