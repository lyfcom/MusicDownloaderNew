import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_URL = "https://www.hhlqilongzhu.cn/api/joox/juhe_music.php"

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

def request_api(params):
    """
    Sends an API request and handles basic errors.
    使用Session进行连接重用和统一配置。
    """
    try:
        session = get_session()
        response = session.get(API_URL, params=params, timeout=(5, 15))
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json()
    except requests.exceptions.Timeout:
        print("API请求超时，请检查网络连接")
        return None
    except requests.exceptions.ConnectionError:
        print("网络连接错误，请检查网络设置")
        return None
    except (requests.exceptions.RequestException, ValueError) as e:
        print(f"API request or JSON decoding failed: {e}")
        return None

def search_music(query):
    """
    Searches for a list of songs by keyword.
    Now returns a more detailed dictionary for each song.
    """
    params = {'msg': query, 'type': 'json'}
    data = request_api(params)
    
    if isinstance(data, list):
        songs = []
        for item in data:
            index = item.get('n')
            raw_title = item.get('title', '未知')
            singer = item.get('singer', '未知')

            # Create both raw and cleaned titles
            cleaned_title = raw_title
            if isinstance(raw_title, str) and '[' in raw_title and ']' in raw_title:
                cleaned_title = raw_title.rsplit('[', 1)[0].strip()

            if index is not None:
                songs.append({
                    'n': index,
                    'raw_title': raw_title,
                    'title': cleaned_title, # The cleaned title
                    'singer': singer,
                    'query': query # The original search query
                })
        return songs
    
    return []

def get_song_details(query, song_number):
    """
    Gets detailed information for a specific song using a query and index.
    This is now primarily a helper function for get_song_details_robust.
    """
    params = {'msg': query, 'n': song_number, 'type': 'json'}
    data = request_api(params)

    if isinstance(data, dict) and 'data' in data:
        details_data = data['data']
        if isinstance(details_data, dict) and details_data.get('code') == 200:
            return details_data
            
    return None

def get_song_details_robust(song_info):
    """
    Robustly gets song details.
    Primary method: Searches "title singer" and does an exact match on raw_title and singer.
    Fallback method: Uses the original search query and 'n' index.
    """
    # --- Primary Method ---
    try:
        new_query = f"{song_info['title']} {song_info['singer']}"
        search_results = search_music(new_query)
        if search_results:
            for result_song in search_results:
                # Exact match on raw title and singer
                if result_song['raw_title'] == song_info['raw_title'] and result_song['singer'] == song_info['singer']:
                    # Found a reliable match!
                    details = get_song_details(new_query, result_song['n'])
                    if details:
                        # print("Robust retrieval: Primary method successful.")
                        return details
    except Exception:
        # Silently fail and proceed to fallback
        pass

    # --- Fallback Method ---
    # print("Robust retrieval: Primary method failed, using fallback.")
    return get_song_details(song_info['query'], song_info['n']) 