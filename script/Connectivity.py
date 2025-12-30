import requests
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

proxy_list = ["socks5://121.31.233.63:20202"]
r_proxy_list = []

result_proxy = {
    "con": "",
    "Score": 0.0,
    "Anonymity": "",
    "Agreement": "",
    "ip": "",
    "ms": 0.0,
    "mbps": 0.0,
    "country": "",
    "city": "",
}

LATENCY_WEIGHT = 0.4
ANONYMITY_WEIGHT = 0.3
SPEED_WEIGHT = 0.3


def calc_latency_score(latency_s):
    if latency_s <= 0.5:
        return 100
    if latency_s <= 1.0:
        return 80
    if latency_s <= 2.0:
        return 60
    if latency_s <= 5.0:
        return 40
    return 20


def calc_anonymity_score(anonymity):
    if anonymity == "Elite":
        return 100
    if anonymity == "Anonymous":
        return 70
    if anonymity == "Transparent":
        return 40
    return 0


def calc_speed_score(mbps):
    if mbps <= 0:
        return 0
    if mbps >= 50:
        return 100
    if mbps >= 10:
        return 80
    if mbps >= 5:
        return 60
    return 40


validation_targets = {
    "anonymity_check": "http://httpbin.org/get?show_env=1",
    "latency_check": "https://www.baidu.com",
    "speed_check": "https://www.baidu.com",
    "geo_check": "https://myip.ipip.net/",
}

timeout = 3
validation_mode = "online"

public_ip = None
try:
    session = requests.Session()
    res_public = session.get(validation_targets["anonymity_check"], timeout=timeout)
    res_public.raise_for_status()
    data_public = res_public.json()
    origin_ips_str_public = data_public.get("headers", {}).get(
        "X-Forwarded-For", data_public.get("origin", "")
    )
    origin_ips_public = [ip.strip() for ip in origin_ips_str_public.split(",") if ip.strip()]
    if origin_ips_public:
        public_ip = origin_ips_public[0]
except requests.RequestException:
    public_ip = None


def test_connectivity(proxy, max_retries=3):
    """快速测试代理连通性和延迟（带重试）"""
    for attempt in range(max_retries):
        session = requests.Session()
        try:
            start_time = time.time()
            response = session.get(
                "https://www.baidu.com",
                proxies={"http": proxy, "https": proxy, "socks5": proxy},
                timeout=2,
            )
            if response.status_code == 200:
                latency_ms = (time.time() - start_time) * 1000
                return True, latency_ms
        except:
            if attempt < max_retries - 1:
                time.sleep(0.5)  # 重试前等待0.5秒
                continue
    return False, 0


def get_geo_info(proxy, max_retries=3):
    """获取地理位置信息（带重试）"""
    for attempt in range(max_retries):
        session = requests.Session()
        try:
            response = session.get(
                validation_targets["geo_check"],
                proxies={"http": proxy, "https": proxy, "socks5": proxy},
                timeout=3,
            )
            if response.status_code == 200:
                response_area_messages = re.search(
                    r"来自于：(\S+)\s+(\S+\s+\S+)", response.text.strip()
                )
                if response_area_messages:
                    country = response_area_messages.group(1)
                    city = response_area_messages.group(2)
                    return country, city
        except:
            if attempt < max_retries - 1:
                time.sleep(0.5)
                continue
    return "", ""


def get_anonymity(proxy, max_retries=3):
    """检测匿名度（带重试）"""
    for attempt in range(max_retries):
        session = requests.Session()
        try:
            res_anon = session.get(
                validation_targets["anonymity_check"],
                proxies={"http": proxy, "https": proxy, "socks5": proxy},
                timeout=3,
            )
            res_anon.raise_for_status()
            data = res_anon.json()
            origin_ips_str = data.get("headers", {}).get(
                "X-Forwarded-For", data.get("origin", "")
            )
            origin_ips = [
                ip.strip() for ip in origin_ips_str.split(",") if ip.strip()
            ]

            if public_ip and any(public_ip in ip for ip in origin_ips):
                return "Transparent"
            elif len(origin_ips) > 1 or "Via" in data.get("headers", {}):
                return "Anonymous"
            else:
                return "Elite"
        except:
            if attempt < max_retries - 1:
                time.sleep(0.5)
                continue
    return ""


def get_speed(proxy, latency_s, max_retries=3):
    """测试速度（仅对延迟较低的代理，带重试）"""
    if latency_s > 5.0:
        return 0.0
    
    for attempt in range(max_retries):
        session = requests.Session()
        try:
            start_speed = time.time()
            speed_response = session.get(
                validation_targets["latency_check"],
                proxies={"http": proxy, "https": proxy, "socks5": proxy},
                timeout=10,
                stream=True,
            )
            speed_response.raise_for_status()

            content_size = 0
            for chunk in speed_response.iter_content(chunk_size=8192):
                content_size += len(chunk)

            speed_duration = time.time() - start_speed
            if speed_duration > 0 and content_size > 0:
                mbps = (content_size / speed_duration) * 8 / (1000**2) * 1000
                return round(mbps, 1)
        except:
            if attempt < max_retries - 1:
                time.sleep(0.5)
                continue
    return 0.0


def test_single_proxy(proxy):
    """测试单个代理（优化版）"""
    proxy_address = proxy.split("://", 1)[1] if "://" in proxy else proxy
    protocol = proxy.split("://", 1)[0] if "://" in proxy else ""
    
    current_result = result_proxy.copy()
    current_result["ip"] = proxy_address
    current_result["Agreement"] = protocol
    
    # 第一步：快速测试连通性
    is_connected, latency_ms = test_connectivity(proxy)
    
    if not is_connected:
        current_result["con"] = "fail"
        return current_result
    
    # 连通性测试通过
    current_result["con"] = "success"
    current_result["ms"] = round(latency_ms, 1)
    latency_s = latency_ms / 1000.0
    
    # 第二步：并行获取详细信息（地理位置和匿名度）
    with ThreadPoolExecutor(max_workers=2) as executor:
        geo_future = executor.submit(get_geo_info, proxy)
        anon_future = executor.submit(get_anonymity, proxy)
        
        country, city = geo_future.result()
        anonymity = anon_future.result()
    
    current_result["country"] = country
    current_result["city"] = city
    current_result["Anonymity"] = anonymity
    
    # 第三步：测试速度（可选，仅对低延迟代理）
    if latency_s <= 5.0:
        speed = get_speed(proxy, latency_s)
        current_result["mbps"] = speed
    
    # 计算分数
    latency_score = calc_latency_score(latency_s)
    anonymity_score = calc_anonymity_score(anonymity)
    speed_score = calc_speed_score(current_result["mbps"])
    score = latency_score + anonymity_score + speed_score
    current_result["Score"] = round(score, 1)
    
    return current_result



def test_proxies(proxy_list_input, progress_callback=None):
    """
    并发测试多个代理（优化版）
    
    Args:
        proxy_list_input: 代理列表
        progress_callback: 进度回调函数，接收 (completed, total, result) 参数
    
    Returns:
        测试结果列表
    """
    results = []
    total = len(proxy_list_input)
    completed = 0
    
    # 使用线程池并发测试，提升到50个并发
    with ThreadPoolExecutor(max_workers=50) as executor:
        # 提交所有任务
        future_to_proxy = {executor.submit(test_single_proxy, proxy): proxy for proxy in proxy_list_input}
        
        # 使用 as_completed 按完成顺序处理结果
        for future in as_completed(future_to_proxy):
            try:
                result = future.result()
                results.append(result)
                completed += 1
                
                # 调用进度回调
                if progress_callback:
                    progress_callback(completed, total, result)
                    
            except Exception as e:
                print(f"测试代理时出错: {e}")
                completed += 1
                if progress_callback:
                    progress_callback(completed, total, None)
    
    return results
