# server.py — 局域网联机 WebSocket 服务器（零依赖，纯 Python 标准库）
# 用法: python server.py [端口]
# 默认端口 8765。客户端连接 ws://<本机IP>:8765
#
# 协议:
#   客户端 -> 服务器: JSON 消息 {type, room, ...}
#   服务器 -> 客户端: JSON 消息 {type, ...}
# 消息类型:
#   join    {type:'join', room:'ABCD'}           加入房间，两人配对后双方收到 {type:'paired', role:'A'|'B', room}
#   action  {type:'action', action:{...}}        转发动作给对手
#   leave   {type:'leave'}                       离开房间
#   ping/pong 心跳保活

import sys
import json
import socket
import struct
import hashlib
import base64
import os
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765

# ===== 房间管理 =====
# room_code -> {clients: [conn1, conn2], lock: Lock}
rooms = {}
rooms_lock = threading.Lock()

def gen_room_code():
    """生成 4 位房间号"""
    return ''.join([chr(ord('A') + (b % 26)) for b in os.urandom(4)])

def find_or_create_room(conn):
    """新连接先等待第一个空闲房间，没有则创建"""
    with rooms_lock:
        # 找一个只有 1 人的房间
        for code, room in list(rooms.items()):
            if len(room['clients']) == 1 and not room['clients'][0]['closed']:
                room['clients'].append(conn)
                return code, 'B'  # 第二个加入的是 B
        # 没有可加入的房间，创建新房间
        code = gen_room_code()
        while code in rooms:
            code = gen_room_code()
        rooms[code] = {'clients': [conn], 'lock': threading.Lock()}
        return code, 'A'  # 第一个是 A

def remove_from_room(code, conn):
    """从房间移除连接"""
    with rooms_lock:
        if code in rooms:
            room = rooms[code]
            if conn in room['clients']:
                room['clients'].remove(conn)
            if not room['clients']:
                del rooms[code]

def broadcast_to_room(code, sender, msg):
    """转发消息给房间内除发送者外的客户端"""
    with rooms_lock:
        if code not in rooms:
            return
        room = rooms[code]
        for c in room['clients']:
            if c is not sender and not c['closed']:
                try:
                    send_msg(c, msg)
                except Exception:
                    pass

# ===== WebSocket 帧编解码 =====
def send_msg(conn, msg):
    """发送 JSON 消息（文本帧，服务器→客户端不 mask）"""
    data = json.dumps(msg).encode('utf-8')
    header = bytearray()
    header.append(0x81)  # FIN + text frame
    payload_len = len(data)
    if payload_len < 126:
        header.append(payload_len)  # 不设 mask 位
    elif payload_len < 65536:
        header.append(126)
        header.extend(struct.pack('>H', payload_len))
    else:
        header.append(127)
        header.extend(struct.pack('>Q', payload_len))
    conn['sock'].sendall(bytes(header) + data)

def recv_msg(conn):
    """接收一帧，返回解析后的 dict 或 None（连接关闭）"""
    sock = conn['sock']
    # 读前 2 字节
    hdr = recv_n(sock, 2)
    if not hdr:
        return None
    b1, b2 = hdr[0], hdr[1]
    fin = b1 & 0x80
    opcode = b1 & 0x0F
    masked = b2 & 0x80
    payload_len = b2 & 0x7F
    if payload_len == 126:
        ext = recv_n(sock, 2)
        payload_len = struct.unpack('>H', ext)[0]
    elif payload_len == 127:
        ext = recv_n(sock, 8)
        payload_len = struct.unpack('>Q', ext)[0]
    if masked:
        mask_key = recv_n(sock, 4)
    payload = recv_n(sock, payload_len) if payload_len > 0 else b''
    if masked and payload:
        payload = bytes([payload[i] ^ mask_key[i % 4] for i in range(len(payload))])
    if opcode == 0x8:  # close
        return None
    if opcode == 0x9:  # ping
        send_pong(conn, payload)
        return {'type': 'ping'}
    if opcode == 0xA:  # pong
        return {'type': 'pong'}
    if opcode == 0x1:  # text
        try:
            return json.loads(payload.decode('utf-8'))
        except Exception:
            return None
    return None

def send_pong(conn, payload):
    header = bytearray()
    header.append(0x8A)  # FIN + pong
    header.append(len(payload))
    conn['sock'].sendall(bytes(header) + payload)

def recv_n(sock, n):
    """精确读取 n 字节"""
    buf = b''
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf

# ===== WebSocket 握手 =====
def do_handshake(sock):
    """完成 HTTP 升级握手，返回请求数据"""
    data = b''
    while b'\r\n\r\n' not in data:
        chunk = sock.recv(1024)
        if not chunk:
            return None
        data += chunk
    req = data.decode('utf-8', errors='ignore')
    # 提取 Sec-WebSocket-Key
    key = None
    for line in req.split('\r\n'):
        if line.lower().startswith('sec-websocket-key:'):
            key = line.split(':', 1)[1].strip()
            break
    if not key:
        return None
    # 计算_accept
    GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
    accept = base64.b64encode(
        hashlib.sha1((key + GUID).encode('utf-8')).digest()
    ).decode('utf-8')
    resp = (
        'HTTP/1.1 101 Switching Protocols\r\n'
        'Upgrade: websocket\r\n'
        'Connection: Upgrade\r\n'
        f'Sec-WebSocket-Accept: {accept}\r\n'
        '\r\n'
    )
    sock.sendall(resp.encode('utf-8'))
    return req

# ===== 连接处理 =====
def handle_client(sock, addr):
    print(f'[+] 新连接: {addr}')
    # 1. 握手
    if not do_handshake(sock):
        print(f'[-] 握手失败: {addr}')
        sock.close()
        return
    conn = {'sock': sock, 'addr': addr, 'closed': False}
    # 2. 加入房间
    code, role = find_or_create_room(conn)
    print(f'[+] {addr} 加入房间 {code} 角色 {role}')
    # 通知角色分配
    send_msg(conn, {'type': 'paired', 'role': role, 'room': code})
    # 如果房间满 2 人，通知 A 方可以开始
    with rooms_lock:
        if code in rooms and len(rooms[code]['clients']) == 2:
            for c in rooms[code]['clients']:
                send_msg(c, {'type': 'ready', 'room': code})
    # 3. 消息循环
    try:
        while not conn['closed']:
            msg = recv_msg(conn)
            if msg is None:
                break
            if msg.get('type') == 'ping':
                continue
            if msg.get('type') == 'leave':
                break
            if msg.get('type') == 'action':
                broadcast_to_room(code, conn, {'type': 'action', 'action': msg.get('action')})
    except Exception as e:
        print(f'[!] 连接异常 {addr}: {e}', flush=True)
    finally:
        conn['closed'] = True
        # 通知对手
        broadcast_to_room(code, conn, {'type': 'opponent_left'})
        remove_from_room(code, conn)
        try:
            sock.close()
        except Exception:
            pass
        print(f'[-] 断开: {addr} (房间 {code})')

# ===== HTTP 状态页（可选，访问 http://host:port/ 查看状态） =====
class StatusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        with rooms_lock:
            room_info = [{'code': c, 'players': len(r['clients'])} for c, r in rooms.items()]
        body = json.dumps({
            'rooms': room_info,
            'total_clients': sum(len(r['clients']) for r in rooms.values()),
        }, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *args):
        pass  # 静默

def start_status_http(http_port):
    server = HTTPServer(('0.0.0.0', http_port), StatusHandler)
    server.serve_forever()

# ===== 主入口 =====
def get_local_ip():
    """获取本机局域网 IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'

def main():
    # WebSocket TCP 服务器
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp.bind(('0.0.0.0', PORT))
    tcp.listen(16)
    # HTTP 状态页（端口 + 1）
    http_port = PORT + 1
    threading.Thread(target=start_status_http, args=(http_port,), daemon=True).start()

    local_ip = get_local_ip()
    print('=' * 50)
    print(f'  隐函数战局 - 局域网联机服务器')
    print('=' * 50)
    print(f'  WebSocket: ws://{local_ip}:{PORT}')
    print(f'  状态页:    http://{local_ip}:{http_port}')
    print(f'  本机:      ws://127.0.0.1:{PORT}')
    print('=' * 50)
    print(f'  把 ws://{local_ip}:{PORT} 告诉对方')
    print(f'  按 Ctrl+C 停止')
    print('=' * 50)

    try:
        while True:
            sock, addr = tcp.accept()
            t = threading.Thread(target=handle_client, args=(sock, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print('\n[!] 服务器关闭')
        tcp.close()

if __name__ == '__main__':
    main()
