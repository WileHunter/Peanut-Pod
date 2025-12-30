import socket
import select
import threading
import struct
import logging
import os
import yaml

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 读取配置文件
def load_config():
    """加载配置文件"""
    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), './assets/config.yaml')
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config.get('socks5_port', 1080), config.get('http_port', 1081)
    except Exception as e:
        logging.warning(f"读取配置文件失败，使用默认端口: {e}")
        return 1080, 1081

# 获取配置的端口
SOCKS5_PORT, HTTP_PORT = load_config()

class ProxyServer:
    def __init__(self, local_host='127.0.0.1', local_port=1800):
        self.local_host = local_host
        self.local_port = local_port
        self.server_socket = None
        self.running = False
        self.upstream_proxy = None
        self.log_callback = None
        
    def set_upstream_proxy(self, proxy_address, proxy_protocol='socks5'):
        """
        设置上游代理
        
        Args:
            proxy_address: 代理地址，格式为 "host:port"
            proxy_protocol: 代理协议，支持 socks5, http
        """
        if proxy_address and ':' in proxy_address:
            host, port = proxy_address.rsplit(':', 1)
            self.upstream_proxy = {
                'host': host,
                'port': int(port),
                'protocol': proxy_protocol.lower()
            }
            self.log(f"设置上游代理: {proxy_protocol}://{proxy_address}")
        else:
            self.upstream_proxy = None
            self.log("清除上游代理")
    
    def set_log_callback(self, callback):
        """设置日志回调函数"""
        self.log_callback = callback
    
    def log(self, message):
        """输出日志"""
        logging.info(message)
        if self.log_callback:
            self.log_callback(message)
    
    def start(self):
        """启动代理服务器"""
        if self.running:
            self.log("代理服务器已在运行")
            return False
        
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.local_host, self.local_port))
            self.server_socket.listen(5)
            self.running = True
            
            self.log(f"代理服务器启动成功: {self.local_host}:{self.local_port}")
            
            # 在新线程中接受连接
            accept_thread = threading.Thread(target=self._accept_connections, daemon=True)
            accept_thread.start()
            
            return True
        except Exception as e:
            self.log(f"启动代理服务器失败: {e}")
            return False
    
    def stop(self):
        """停止代理服务器"""
        if not self.running:
            return
        
        self.running = False
        self.log("代理服务器正在停止...")
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None
        
        self.log("代理服务器已停止")
    
    def _accept_connections(self):
        """接受客户端连接"""
        while self.running:
            try:
                self.server_socket.settimeout(1.0)  # 设置超时，便于检查 running 状态
                try:
                    client_socket, client_address = self.server_socket.accept()
                except socket.timeout:
                    continue
                
                if not self.running:
                    client_socket.close()
                    break
                
                self.log(f"新连接: {client_address[0]}:{client_address[1]}")
                
                # 为每个连接创建新线程
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, client_address),
                    daemon=True
                )
                client_thread.start()
            except Exception as e:
                if self.running:
                    self.log(f"接受连接错误: {e}")
    
    def _handle_client(self, client_socket, client_address):
        """处理客户端请求"""
        try:
            # 检查服务器是否还在运行
            if not self.running:
                client_socket.close()
                return
            
            # SOCKS5 握手
            version = client_socket.recv(1)
            if not version or version != b'\x05':
                if self.running:
                    self.log(f"不支持的SOCKS版本: {client_address}")
                client_socket.close()
                return
            
            # 读取认证方法
            nmethods_data = client_socket.recv(1)
            if not nmethods_data:
                client_socket.close()
                return
            
            nmethods = ord(nmethods_data)
            methods = client_socket.recv(nmethods)
            
            if not self.running:
                client_socket.close()
                return
            
            # 回复：无需认证
            client_socket.sendall(b'\x05\x00')
            
            # 读取请求
            request_data = client_socket.recv(4)
            if len(request_data) < 4:
                client_socket.close()
                return
            
            version, cmd, _, address_type = struct.unpack('!BBBB', request_data)
            
            if cmd != 1:  # 只支持CONNECT命令
                client_socket.sendall(b'\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00')
                client_socket.close()
                return
            
            # 解析目标地址
            if address_type == 1:  # IPv4
                address_data = client_socket.recv(4)
                if len(address_data) < 4:
                    client_socket.close()
                    return
                address = socket.inet_ntoa(address_data)
            elif address_type == 3:  # 域名
                domain_length_data = client_socket.recv(1)
                if not domain_length_data:
                    client_socket.close()
                    return
                domain_length = ord(domain_length_data)
                address_data = client_socket.recv(domain_length)
                if len(address_data) < domain_length:
                    client_socket.close()
                    return
                address = address_data.decode('utf-8')
            else:
                client_socket.sendall(b'\x05\x08\x00\x01\x00\x00\x00\x00\x00\x00')
                client_socket.close()
                return
            
            port_data = client_socket.recv(2)
            if len(port_data) < 2:
                client_socket.close()
                return
            
            port = struct.unpack('!H', port_data)[0]
            
            if not self.running:
                client_socket.close()
                return
            
            self.log(f"请求连接: {address}:{port}")
            
            # 连接到目标（通过上游代理或直连）
            if self.upstream_proxy:
                remote_socket = self._connect_via_proxy(address, port)
            else:
                remote_socket = self._connect_direct(address, port)
            
            if not remote_socket:
                client_socket.sendall(b'\x05\x05\x00\x01\x00\x00\x00\x00\x00\x00')
                client_socket.close()
                return
            
            # 回复成功
            client_socket.sendall(b'\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00')
            
            # 开始转发数据
            self._forward_data(client_socket, remote_socket)
            
        except Exception as e:
            if self.running:
                self.log(f"处理客户端错误: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass
    
    def _connect_direct(self, address, port):
        """直接连接到目标"""
        try:
            remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            remote_socket.connect((address, port))
            return remote_socket
        except Exception as e:
            self.log(f"直连失败 {address}:{port} - {e}")
            return None
    
    def _connect_via_proxy(self, address, port):
        """通过上游代理连接"""
        try:
            proxy = self.upstream_proxy
            
            if proxy['protocol'] == 'socks5':
                return self._connect_via_socks5(address, port, proxy['host'], proxy['port'])
            elif proxy['protocol'] in ['http', 'https']:
                return self._connect_via_http(address, port, proxy['host'], proxy['port'])
            else:
                self.log(f"不支持的代理协议: {proxy['protocol']}")
                return None
        except Exception as e:
            self.log(f"通过代理连接失败: {e}")
            return None
    
    def _connect_via_socks5(self, target_host, target_port, proxy_host, proxy_port):
        """通过SOCKS5代理连接"""
        try:
            if not self.running:
                return None
            
            # 连接到SOCKS5代理
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((proxy_host, proxy_port))
            
            # SOCKS5握手
            sock.sendall(b'\x05\x01\x00')
            response = sock.recv(2)
            if not response or len(response) < 2 or response != b'\x05\x00':
                raise Exception("SOCKS5握手失败")
            
            # 发送连接请求
            if target_host.replace('.', '').isdigit():  # IP地址
                request = b'\x05\x01\x00\x01' + socket.inet_aton(target_host)
            else:  # 域名
                request = b'\x05\x01\x00\x03' + bytes([len(target_host)]) + target_host.encode('utf-8')
            
            request += struct.pack('!H', target_port)
            sock.sendall(request)
            
            # 读取响应
            response = sock.recv(10)
            if not response or len(response) < 2:
                raise Exception("SOCKS5响应不完整")
            
            if response[1] != 0:
                raise Exception(f"SOCKS5连接失败，错误码: {response[1]}")
            
            if self.running:
                self.log(f"通过SOCKS5代理连接成功: {target_host}:{target_port}")
            return sock
        except Exception as e:
            if self.running:
                self.log(f"SOCKS5代理连接失败: {e}")
            return None
    
    def _connect_via_http(self, target_host, target_port, proxy_host, proxy_port):
        """通过HTTP代理连接"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((proxy_host, proxy_port))
            
            # 发送CONNECT请求
            connect_request = f"CONNECT {target_host}:{target_port} HTTP/1.1\r\n"
            connect_request += f"Host: {target_host}:{target_port}\r\n"
            connect_request += "Connection: keep-alive\r\n\r\n"
            
            sock.sendall(connect_request.encode('utf-8'))
            
            # 读取响应
            response = sock.recv(4096).decode('utf-8')
            if '200' not in response.split('\r\n')[0]:
                raise Exception("HTTP代理连接失败")
            
            self.log(f"通过HTTP代理连接成功: {target_host}:{target_port}")
            return sock
        except Exception as e:
            self.log(f"HTTP代理连接失败: {e}")
            return None
    
    def _forward_data(self, client_socket, remote_socket):
        """双向转发数据"""
        try:
            sockets = [client_socket, remote_socket]
            while True:
                readable, _, _ = select.select(sockets, [], [], 1)
                
                if not readable:
                    continue
                
                for sock in readable:
                    try:
                        data = sock.recv(4096)
                        if not data:
                            return
                        
                        if sock is client_socket:
                            remote_socket.sendall(data)
                        else:
                            client_socket.sendall(data)
                    except:
                        return
        except Exception as e:
            self.log(f"数据转发错误: {e}")
        finally:
            try:
                remote_socket.close()
            except:
                pass


class HTTPProxyServer(ProxyServer):
    """HTTP代理服务器"""
    
    def _handle_client(self, client_socket, client_address):
        """处理HTTP代理请求"""
        try:
            if not self.running:
                client_socket.close()
                return
            
            # 读取HTTP请求
            request_data = b''
            while b'\r\n\r\n' not in request_data:
                chunk = client_socket.recv(4096)
                if not chunk:
                    client_socket.close()
                    return
                request_data += chunk
                if len(request_data) > 8192:  # 防止请求过大
                    break
            
            request_str = request_data.decode('utf-8', errors='ignore')
            lines = request_str.split('\r\n')
            
            if not lines:
                client_socket.close()
                return
            
            # 解析请求行
            request_line = lines[0]
            parts = request_line.split(' ')
            
            if len(parts) < 2:
                client_socket.close()
                return
            
            method = parts[0]
            url = parts[1]
            
            # 处理CONNECT方法（HTTPS）
            if method == 'CONNECT':
                self._handle_connect(client_socket, url)
            else:
                # 处理普通HTTP请求
                self._handle_http(client_socket, request_data, url)
                
        except Exception as e:
            if self.running:
                self.log(f"HTTP代理处理错误: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass
    
    def _handle_connect(self, client_socket, url):
        """处理CONNECT请求（用于HTTPS）"""
        try:
            # 解析目标地址
            if ':' in url:
                address, port = url.rsplit(':', 1)
                port = int(port)
            else:
                address = url
                port = 443
            
            if not self.running:
                client_socket.close()
                return
            
            self.log(f"HTTP CONNECT: {address}:{port}")
            
            # 连接到目标
            if self.upstream_proxy:
                remote_socket = self._connect_via_proxy(address, port)
            else:
                remote_socket = self._connect_direct(address, port)
            
            if not remote_socket:
                client_socket.sendall(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
                client_socket.close()
                return
            
            # 回复连接成功
            client_socket.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            
            # 开始转发数据
            self._forward_data(client_socket, remote_socket)
            
        except Exception as e:
            if self.running:
                self.log(f"CONNECT处理错误: {e}")
    
    def _handle_http(self, client_socket, request_data, url):
        """处理普通HTTP请求"""
        try:
            # 解析URL获取主机和端口
            if url.startswith('http://'):
                url = url[7:]
            
            if '/' in url:
                host_port, path = url.split('/', 1)
                path = '/' + path
            else:
                host_port = url
                path = '/'
            
            if ':' in host_port:
                address, port = host_port.rsplit(':', 1)
                port = int(port)
            else:
                address = host_port
                port = 80
            
            if not self.running:
                client_socket.close()
                return
            
            self.log(f"HTTP请求: {address}:{port}{path}")
            
            # 连接到目标
            if self.upstream_proxy:
                remote_socket = self._connect_via_proxy(address, port)
            else:
                remote_socket = self._connect_direct(address, port)
            
            if not remote_socket:
                client_socket.sendall(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
                client_socket.close()
                return
            
            # 转发请求
            remote_socket.sendall(request_data)
            
            # 转发响应
            while True:
                data = remote_socket.recv(4096)
                if not data:
                    break
                client_socket.sendall(data)
            
        except Exception as e:
            if self.running:
                self.log(f"HTTP请求处理错误: {e}")


# 全局代理服务器实例
_socks5_server_instance = None
_http_server_instance = None

def get_server_ports():
    """获取服务器端口配置"""
    return SOCKS5_PORT, HTTP_PORT

def start_proxy_server(upstream_proxy_address, proxy_protocol='socks5', log_callback=None):
    """
    启动代理服务器（同时启动SOCKS5和HTTP）
    
    Args:
        upstream_proxy_address: 上游代理地址，格式为 "host:port"
        proxy_protocol: 代理协议
        log_callback: 日志回调函数
    
    Returns:
        成功返回True，失败返回False
    """
    global _socks5_server_instance, _http_server_instance
    
    if (_socks5_server_instance and _socks5_server_instance.running) or \
       (_http_server_instance and _http_server_instance.running):
        if log_callback:
            log_callback("[服务器] 代理服务器已在运行")
        return False
    
    # 启动SOCKS5服务器
    _socks5_server_instance = ProxyServer(local_port=SOCKS5_PORT)
    _socks5_server_instance.set_log_callback(log_callback)
    _socks5_server_instance.set_upstream_proxy(upstream_proxy_address, proxy_protocol)
    
    socks5_success = _socks5_server_instance.start()
    if not socks5_success:
        return False
    
    # 启动HTTP服务器
    _http_server_instance = HTTPProxyServer(local_port=HTTP_PORT)
    _http_server_instance.set_log_callback(log_callback)
    _http_server_instance.set_upstream_proxy(upstream_proxy_address, proxy_protocol)
    
    http_success = _http_server_instance.start()
    if not http_success:
        # 如果HTTP启动失败，停止SOCKS5
        _socks5_server_instance.stop()
        return False
    
    return True

def stop_proxy_server():
    """停止代理服务器"""
    global _socks5_server_instance, _http_server_instance
    
    if _socks5_server_instance:
        _socks5_server_instance.stop()
        _socks5_server_instance = None
    
    if _http_server_instance:
        _http_server_instance.stop()
        _http_server_instance = None

def switch_upstream_proxy(upstream_proxy_address, proxy_protocol='socks5'):
    """
    动态切换上游代理
    
    Args:
        upstream_proxy_address: 新的上游代理地址
        proxy_protocol: 代理协议
    
    Returns:
        成功返回True，失败返回False
    """
    global _socks5_server_instance, _http_server_instance
    
    success = False
    if _socks5_server_instance and _socks5_server_instance.running:
        _socks5_server_instance.set_upstream_proxy(upstream_proxy_address, proxy_protocol)
        success = True
    
    if _http_server_instance and _http_server_instance.running:
        _http_server_instance.set_upstream_proxy(upstream_proxy_address, proxy_protocol)
        success = True
    
    return success
