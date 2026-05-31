"""通过 ACC UDP 广播协议打印赛道名称及进站用时系数。"""

import sys
import time
import signal

sys.path.insert(0, r"C:\Users\hzq\Desktop\overlay\src")
from accapi.client import AccClient

# 默认圈速参考（秒），key 为 ACC 广播协议返回的赛道名
DEFAULT_LAP_TIMES = {
    "Misano World Circuit": "1:34.35",
    "Silverstone Circuit": "1:59.85",
    "Circuit Paul Ricard": "1:54.75",
    "Circuit de Barcelona-Catalunya": "1:46.59",
    "Brands Hatch": "1:26.70",
    "Hungaroring": "1:46.08",
    "Autodromo Nazionale Monza": "1:48.63",
    "Nürburgring Grand Prix Circuit": "1:55.77",
    "Circuit de Spa-Francorchamps": "2:18.72",
    "Circuit Zandvoort": "1:37.41",
    "Circuit Zolder": "1:29.76",
    "Kyalami Grand Prix Circuit": "1:42.00",
    "Suzuka Circuit": "2:01.38",
    "WeatherTech Raceway Laguna Seca": "1:23.13",
    "Mount Panorama Circuit, Bathurst": "2:02.40",
    "Autodromo Enzo e Dino Ferrari (Imola)": "1:41.49",
    "Donington Park": "1:28.74",
    "Oulton Park": "1:29.25",
    "Snetterton Circuit": "1:48.12",
    "Watkins Glen International": "1:45.06",
    "Circuit of the Americas (COTA)": "2:09.54",
    "Indianapolis Motor Speedway": "1:36.90",
    "Circuit Ricardo Tormo (Valencia)": "1:32.31",
    "Red Bull Ring": "1:29.25",
    "Nürburgring 24h Circuit": "8:14.70",
}

# 进站维修区耗时（秒）
PIT_LANE_TIMES = {
    "Circuit de Spa-Francorchamps": 71.6,
    "Silverstone Circuit": 69.8,
    "Circuit Zandvoort": 52.6,
    "Circuit Ricardo Tormo (Valencia)": 47.3,
    "Circuit de Barcelona-Catalunya": 39.5,
    "Autodromo Enzo e Dino Ferrari (Imola)": 39.5,
    "Misano World Circuit": 30.0,
    "Circuit Zolder": 29.0,
    "Suzuka Circuit": 28.4,
    "Kyalami Grand Prix Circuit": 27.2,
    "Circuit Paul Ricard": 27.0,
    "Circuit of the Americas (COTA)": 25.0,
    "Donington Park": 25.0,
    "Brands Hatch Circuit": 25.0,
    "Autodromo Nazionale Monza": 24.3,
    "Nürburgring Grand Prix Circuit": 22.5,
    "Nürburgring 24h Circuit": 22.5,
    "Hungaroring": 21.9,
    "Red Bull Ring": 20.3,
    "WeatherTech Raceway Laguna Seca": 20.0,
    "Mount Panorama Circuit, Bathurst": 20.0,
    "Watkins Glen International": 20.0,
    "Indianapolis Motor Speedway": 20.0,
    "Snetterton Circuit": 19.0,
    "Oulton Park": 13.0,
}

# 通用词表 — 匹配时忽略
_GENERIC = {
    "circuit", "circuito", "autodromo", "nazionale", "track", "raceway",
    "grand", "prix", "international", "world", "park", "de", "del", "di",
    "of", "the", "mount", "panorama", "weathertech", "cota",
    "enzo", "e", "dino", "speedway", "centre", "center",
    "ricardo", "tormo", "ferrari",
}


def _normalize(name):
    """提取赛道名的关键特征词，忽略通用词"""
    s = name.lower()
    # 替换分隔符为空格
    for ch in "-_'.,:;!?()[]":
        s = s.replace(ch, " ")
    words = s.split()
    return frozenset(w for w in words if w not in _GENERIC and len(w) > 1)


# 构建归一化 → 原始 key 的索引（圈速）
_NORM_INDEX = {}
for key in DEFAULT_LAP_TIMES:
    sig = _normalize(key)
    _NORM_INDEX[sig] = key

# 归一化 → 原始 key 的索引（维修区耗时）
_PIT_NORM_INDEX = {}
for key in PIT_LANE_TIMES:
    sig = _normalize(key)
    _PIT_NORM_INDEX[sig] = key


def _resolve_index(idx, raw):
    """通过归一化特征词匹配，在索引中查找 key"""
    sig = _normalize(raw)
    return idx.get(sig)


def resolve_track_name(raw):
    """将 ACC 赛道名转为 DEFAULT_LAP_TIMES 中的 key"""
    return _resolve_index(_NORM_INDEX, raw) or raw


def resolve_pit_key(raw):
    """将 ACC 赛道名转为 PIT_LANE_TIMES 中的 key"""
    return _resolve_index(_PIT_NORM_INDEX, raw) or raw


def parse_laptime(t):
    """将 '1:46.59' 格式转为秒数 float"""
    parts = t.replace(",", ".").split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    return float(parts[0])


def main():
    HOST = "127.0.0.1"
    PORT = 9000
    PASSWORD = "asd"

    client = None
    last_poll = 0.0
    last_name = ""

    def on_track_data(event):
        nonlocal last_name
        raw_name = event.content.trackName
        if not raw_name:
            return
        name = resolve_track_name(raw_name)
        if name == last_name:
            return
        last_name = name
        lap = DEFAULT_LAP_TIMES.get(name)
        pit_key = resolve_pit_key(raw_name)
        pit_time = PIT_LANE_TIMES.get(pit_key)
        if lap and pit_time:
            secs = parse_laptime(lap)
            total = pit_time + 30.0
            coeff = total / secs
            print(f"{name}  {coeff:.3f}  ({total:.1f}s / {secs:.1f}s)")
        elif lap:
            secs = parse_laptime(lap)
            coeff = 30.0 / secs
            print(f"{name}  {coeff:.3f}  (30s / {secs:.1f}s)")
        else:
            print(raw_name)

    def on_connection(event):
        if event.content == "established":
            print(f"已连接至 {HOST}:{PORT}")

    def start_client():
        nonlocal client
        c = AccClient()
        c.onTrackDataUpdate.subscribe(on_track_data)
        c.onConnectionStateChange.subscribe(on_connection)
        c.start(HOST, PORT, PASSWORD)
        client = c

    print(f"连接 ACC 广播服务 {HOST}:{PORT}…")
    start_client()

    def cleanup(*_):
        print("\n正在退出…")
        if client and client.isAlive:
            client.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    while True:
        time.sleep(0.5)

        if client is None or client.connectionState == "lost":
            print("连接丢失，3 秒后重连…")
            time.sleep(3)
            start_client()
            last_poll = 0.0

        if client.isAlive and client._connectionId is not None:
            now = time.time()
            if now - last_poll >= 5:
                client._request_track_data()
                last_poll = now


if __name__ == "__main__":
    main()
