// net.js — PeerJS P2P 联机（无需服务器，手机直连手机）
// 用法:
//   HF.net.createRoom()              创建房间，生成房间号，等待对手加入
//   HF.net.joinRoom(code)            加入房间
//   HF.net.sendAction(action)        发送动作给对手
//   HF.net.onAction = (action) => {} 接收对手动作回调
//   HF.net.onLeave = () => {}        对手离开回调
//   HF.net.onReady = () => {}        连接建立可开始
//   HF.net.onStatus = (msg) => {}    状态文案更新
//   HF.net.disconnect()              断开
(function () {
  'use strict';
  const HF = (window.HF = window.HF || {});

  const PEER_PREFIX = 'hf-chess-';  // PeerJS peer ID 前缀，避免与其他应用冲突

  HF.net = {
    peer: null,           // PeerJS 实例
    conn: null,           // DataConnection
    role: null,           // 'A' | 'B'  A=创建者, B=加入者
    roomCode: null,       // 房间号
    connected: false,
    lastSeen: 0,          // 最后收到数据的时间戳（心跳超时检测）
    heartbeatTimer: null, // 心跳定时器ID
    onAction: null,
    onLeave: null,
    onReady: null,
    onStatus: null,
  };

  // 生成 4 位房间号（大写字母+数字）
  function genRoomCode() {
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';  // 去除易混淆字符
    let code = '';
    for (let i = 0; i < 4; i++) code += chars[Math.floor(Math.random() * chars.length)];
    return code;
  }

  function setStatus(msg) {
    if (HF.net.onStatus) HF.net.onStatus(msg);
  }

  // 创建房间（A 方）
  HF.net.createRoom = function () {
    return new Promise((resolve, reject) => {
      const code = genRoomCode();
      const peerId = PEER_PREFIX + code;
      setStatus('正在创建房间...');
      try {
        const peer = new Peer(peerId, { debug: 1 });
        HF.net.peer = peer;
        HF.net.roomCode = code;
        HF.net.role = 'A';

        peer.on('open', (id) => {
          setStatus('房间已创建，房间号 ' + code + '，等待对手加入...');
          resolve({ code, peerId: id });
        });

        peer.on('connection', (conn) => {
          // 收到对手连接
          HF.net.conn = conn;
          setupConnection(conn);
        });

        peer.on('error', (err) => {
          setStatus('创建房间失败: ' + (err.type || err.message || err));
          if (err.type === 'unavailable-id') {
            setStatus('房间号 ' + code + ' 已被占用，请重试');
          }
          reject(err);
        });

        // 信令服务器断开（可重连）
        peer.on('disconnected', () => {
          setStatus('与信令服务器断开，尝试重连...');
          try { peer.reconnect(); } catch (e) {}
        });
      } catch (e) {
        setStatus('PeerJS 未加载，请检查网络');
        reject(e);
      }
    });
  };

  // 加入房间（B 方）
  HF.net.joinRoom = function (code) {
    return new Promise((resolve, reject) => {
      const targetId = PEER_PREFIX + code.toUpperCase();
      setStatus('正在连接房间 ' + code + '...');
      let settled = false;  // 防止 resolve/reject 后重复触发
      try {
        // B 也需要创建自己的 peer（用随机 ID）
        const peer = new Peer({ debug: 1 });
        HF.net.peer = peer;
        HF.net.role = 'B';
        HF.net.roomCode = code.toUpperCase();

        // 连接超时保护（15秒）
        const timeoutId = setTimeout(() => {
          if (!settled) {
            settled = true;
            setStatus('连接超时，对方可能不在线');
            reject(new Error('timeout'));
          }
        }, 15000);

        peer.on('open', (myId) => {
          if (settled) return;
          setStatus('正在连接对方...');
          const conn = peer.connect(targetId, { reliable: true });
          HF.net.conn = conn;
          setupConnection(conn);
          // B 端连接真正建立后 resolve（conn.on('open')）
          conn.on('open', () => {
            if (settled) return;
            settled = true;
            clearTimeout(timeoutId);
            resolve({ code: code.toUpperCase(), myId });
          });
        });

        peer.on('error', (err) => {
          if (settled) return;
          settled = true;
          clearTimeout(timeoutId);
          if (err.type === 'peer-unavailable') {
            setStatus('房间 ' + code + ' 不存在或对方已离开');
          } else {
            setStatus('连接失败: ' + (err.type || err.message || err));
          }
          reject(err);
        });

        peer.on('disconnected', () => {
          setStatus('与信令服务器断开，尝试重连...');
          try { peer.reconnect(); } catch (e) {}
        });
      } catch (e) {
        setStatus('PeerJS 未加载，请检查网络');
        reject(e);
      }
    });
  };

  // 设置 DataConnection 回调
  function setupConnection(conn) {
    conn.on('open', () => {
      HF.net.connected = true;
      HF.net.lastSeen = Date.now();
      startHeartbeat();
      setStatus('已连接对手！');
      // A 收到连接即 ready，B 连接建立即 ready
      if (HF.net.onReady) HF.net.onReady();
    });

    conn.on('data', (data) => {
      if (!data) return;
      HF.net.lastSeen = Date.now();  // 更新最后收到数据时间
      // PeerJS 自动反序列化对象
      if (data.type === 'action' && HF.net.onAction) {
        HF.net.onAction(data.action);
      } else if (data.type === 'leave' && HF.net.onLeave) {
        HF.net.onLeave();
      } else if (data.type === 'ping') {
        // 收到心跳，回复 pong
        try { HF.net.conn.send({ type: 'pong' }); } catch (e) {}
      }
      // pong 类型无需处理，lastSeen 已更新
    });

    conn.on('close', () => {
      HF.net.connected = false;
      stopHeartbeat();
      setStatus('对手已断开连接');
      if (HF.net.onLeave) HF.net.onLeave();
    });

    conn.on('error', (err) => {
      setStatus('连接错误: ' + (err.message || err));
      HF.net.connected = false;
      stopHeartbeat();
      if (HF.net.onLeave) HF.net.onLeave();
    });
  }

  // 心跳保活：每15秒发ping，60秒无响应判定断线
  function startHeartbeat() {
    stopHeartbeat();
    HF.net.heartbeatTimer = setInterval(() => {
      if (!HF.net.conn || !HF.net.connected) return;
      // 超过60秒未收到任何数据，判定断线
      if (Date.now() - HF.net.lastSeen > 60000) {
        setStatus('连接超时（对手无响应）');
        HF.net.connected = false;
        stopHeartbeat();
        if (HF.net.onLeave) HF.net.onLeave();
        return;
      }
      try { HF.net.conn.send({ type: 'ping' }); } catch (e) {}
    }, 15000);
  }

  function stopHeartbeat() {
    if (HF.net.heartbeatTimer) {
      clearInterval(HF.net.heartbeatTimer);
      HF.net.heartbeatTimer = null;
    }
  }

  // 发送动作给对手
  HF.net.sendAction = function (action) {
    if (!HF.net.conn || !HF.net.connected) return false;
    try {
      HF.net.conn.send({ type: 'action', action: action });
      return true;
    } catch (e) {
      return false;
    }
  };

  // 断开连接
  HF.net.disconnect = function () {
    stopHeartbeat();
    if (HF.net.conn) {
      try { HF.net.conn.send({ type: 'leave' }); } catch (e) {}
      try { HF.net.conn.close(); } catch (e) {}
      HF.net.conn = null;
    }
    if (HF.net.peer) {
      try { HF.net.peer.destroy(); } catch (e) {}
      HF.net.peer = null;
    }
    HF.net.connected = false;
    HF.net.role = null;
    HF.net.roomCode = null;
  };
})();
