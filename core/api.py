import requests
import urllib.parse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 新API端点（腾讯QQ音乐平台）
BASE_URL = "https://api.vkeys.cn/v2/music/tencent"
LYRIC_URL = "https://api.vkeys.cn/v2/music/tencent/lyric"

# 创建全局Session用于连接重用和统一配置
_session = None

def get_session():
    """获取或创建全局Session实例，配置连接重用、超时和重试策略"""
    global _session
    if _session is None:
        _session = requests.Session()

        # 配置重试策略
        retry_strategy = Retry(
            total=3,  # 最多重试3次
            backoff_factor=0.5,  # 重试间隔指数退避
            status_forcelist=[429, 500, 502, 503, 504],  # 这些状态码会触发重试
        )

        # 为HTTP和HTTPS配置适配器
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,  # 连接池大小
            pool_maxsize=20       # 每个连接池的最大连接数
        )
        _session.mount("http://", adapter)
        _session.mount("https://", adapter)

        # 设置默认超时和请求头
        _session.timeout = (5, 15)  # 连接超时5s，读取超时15s
        _session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Safari/537.36'
        })

    return _session

def request_api(url, params):
    """
    发送API请求并处理基本错误
    使用Session进行连接重用和统一配置
    """
    try:
        session = get_session()
        # URL编码参数
        encoded_params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        full_url = f"{url}?{encoded_params}"

        response = session.get(full_url, timeout=(5, 15))
        response.raise_for_status()  # 抛出HTTP错误异常
        return response.json()
    except requests.exceptions.Timeout:
        print("API请求超时，请检查网络连接")
        return None
    except requests.exceptions.ConnectionError:
        print("网络连接错误，请检查网络设置")
        return None
    except (requests.exceptions.RequestException, ValueError) as e:
        print(f"API请求或JSON解析失败: {e}")
        return None

def search_music(query):
    """
    根据关键词搜索歌曲列表

    Args:
        query: 搜索关键词

    Returns:
        歌曲列表，每首歌包含: id, title, singer, album
        返回空列表如果搜索失败
    """
    params = {'word': query}
    data = request_api(BASE_URL, params)

    if data and isinstance(data, dict) and data.get('code') == 200:
        song_list = data.get('data', [])
        if isinstance(song_list, list):
            songs = []
            for item in song_list:
                song_id = item.get('id')
                # 优先使用song字段，备选name字段
                title = item.get('song') or item.get('name', '未知')
                singer = item.get('singer', '未知')
                album = item.get('album', '')

                if song_id:
                    songs.append({
                        'id': song_id,
                        'title': title,
                        'singer': singer,
                        'album': album
                    })
            return songs

    return []

def get_song_details(song_id, quality=9):
    """
    根据歌曲ID获取详细信息（包括播放地址、封面等）

    Args:
        song_id: 歌曲ID
        quality: 音质等级 (0-14)，默认9（HQ高音质增强）

    Returns:
        歌曲详细信息字典，包含url、cover等
        返回None如果获取失败
    """
    params = {'id': song_id, 'quality': quality}
    data = request_api(BASE_URL, params)

    if data and isinstance(data, dict) and data.get('code') == 200:
        details = data.get('data')
        if isinstance(details, dict):
            return details

    return None

def get_song_details_robust(song_info, quality=9):
    """
    健壮地获取歌曲详情

    主策略：使用 "title singer" 重新搜索，然后精确匹配 title 和 singer
    备用策略：直接使用 song_info 中的 id 获取详情

    Args:
        song_info: 包含 id, title, singer 的歌曲信息字典
        quality: 音质等级 (0-14)，默认9

    Returns:
        歌曲详细信息字典或None
    """
    # --- 主策略：重新搜索匹配 ---
    try:
        new_query = f"{song_info['title']} {song_info['singer']}"
        search_results = search_music(new_query)

        if search_results:
            # 标准化比较（去除空格、转小写）
            target_title = song_info['title'].replace(' ', '').lower()
            target_singer = song_info['singer'].replace(' ', '').lower()

            for result_song in search_results:
                result_title = result_song['title'].replace(' ', '').lower()
                result_singer = result_song['singer'].replace(' ', '').lower()

                # 精确匹配 title 和 singer
                if result_title == target_title and result_singer == target_singer:
                    # 找到可靠的匹配！
                    details = get_song_details(result_song['id'], quality=quality)
                    if details:
                        return details
    except Exception as e:
        # 静默失败，继续使用备用策略
        print(f"主策略失败: {e}")
        pass

    # --- 备用策略：直接使用ID ---
    if 'id' in song_info and song_info['id']:
        return get_song_details(song_info['id'], quality=quality)

    return None

def get_lyric(song_id):
    """
    获取歌曲歌词（包括普通歌词、逐字歌词、翻译、音译）

    Args:
        song_id: 歌曲ID

    Returns:
        歌词字典，包含:
        - lrc: 普通LRC歌词
        - yrc: 逐字歌词（可用于逐字高亮动画）
        - trans: 翻译歌词
        - roma: 罗马音/音译
        返回None如果获取失败
    """
    params = {'id': song_id}
    data = request_api(LYRIC_URL, params)

    if data and isinstance(data, dict) and data.get('code') == 200:
        lyric_data = data.get('data')
        if isinstance(lyric_data, dict):
            return {
                'lrc': lyric_data.get('lrc', ''),
                'yrc': lyric_data.get('yrc', ''),
                'trans': lyric_data.get('trans', ''),
                'roma': lyric_data.get('roma', '')
            }

    return None
