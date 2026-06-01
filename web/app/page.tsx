'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Camera, Hand, MousePointer2, Info, Play, Square, Wifi, WifiOff, Monitor, Trash2, ChevronLeft, ChevronRight } from 'lucide-react';

interface GestureData {
  image: string | null;
  gesture: string | null;
  distance: number;
  is_mouse_active: boolean;
  hands_detected: number;
  fps: number;
  gesture_confidence: number;
  swipe_gesture: string;
  mouse_control?: {
    mouse_controlled: boolean;
    cursor_position?: { x: number; y: number };
    clicked: boolean;
    gesture: string | null;
    is_active: boolean;
  } | null;
  error?: string;
}

interface LogEntry {
  id: number;
  timestamp: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
}

interface GesturePreset {
  name: string;
  icon: string;
  description: string;
  color: string;
}

const GESTURE_PRESETS: GesturePreset[] = [
  { name: '数字 1', icon: '1', description: '仅食指伸直', color: 'from-blue-500 to-cyan-500' },
  { name: '数字 2', icon: '2', description: '食指和中指伸直', color: 'from-green-500 to-emerald-500' },
  { name: '数字 3', icon: '3', description: '三指伸直', color: 'from-purple-500 to-pink-500' },
  { name: '数字 4', icon: '4', description: '四指伸直', color: 'from-indigo-500 to-blue-500' },
  { name: '手掌', icon: '5', description: '五指全部伸直', color: 'from-yellow-500 to-amber-500' },
  { name: '拳头', icon: 'F', description: '五指全部弯曲', color: 'from-red-500 to-orange-500' },
  { name: 'OK', icon: 'O', description: '拇指食指成圈', color: 'from-teal-500 to-green-500' },
  { name: '点赞', icon: 'T', description: '拇指向上伸直', color: 'from-pink-500 to-rose-500' },
  { name: '摇滚', icon: 'R', description: '食指和小指伸直', color: 'from-violet-500 to-purple-500' },
  { name: '左翻页', icon: '←', description: '手掌向左滑动', color: 'from-sky-500 to-blue-500' },
  { name: '右翻页', icon: '→', description: '手掌向右滑动', color: 'from-orange-500 to-red-500' },
];

const PAGES = [
  {
    title: '系统概述',
    content: '基于 MediaPipe 的智能手势识别系统，支持实时手势检测、虚拟鼠标控制与手势翻页功能。',
    items: ['自定义几何特征手势识别', '虚拟鼠标控制（2帧确认防误触）', '手势滑动翻页控制', '实时 WebSocket 通信', '640x480@30fps 视频流'],
  },
  {
    title: '手势识别',
    content: '系统支持 9 种静态手势识别与 2 种动态滑动检测，基于手指伸展状态与几何距离特征进行分类。',
    items: ['数字 1-5：基于手指伸展数量', '拳头/OK/点赞/摇滚：特定手指组合', '左翻页/右翻页：手掌水平滑动检测', '滑动阈值可配置，防抖冷却机制'],
  },
  {
    title: '虚拟鼠标',
    content: '通过食指位置控制光标移动，食指与中指并拢触发点击，支持平滑滤波与灵敏度调节。',
    items: ['食指控制光标移动', '食指+中指并拢触发点击', '2帧确认防止误触', '可调节点击阈值与平滑系数'],
  },
  {
    title: '使用技巧',
    content: '确保环境光线充足均匀，手部与摄像头保持 30-50cm 距离，避免背景过于复杂。',
    items: ['手势动作要清晰明确', '翻页时手掌水平滑动幅度要大', '鼠标控制时保持手部稳定', '可在设置中调节灵敏度参数'],
  },
];

export default function Home() {
  const [isConnected, setIsConnected] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [gestureData, setGestureData] = useState<GestureData | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [videoReady, setVideoReady] = useState(false);
  const [isMouseControlEnabled, setIsMouseControlEnabled] = useState(false);
  const [showGuide, setShowGuide] = useState(false);
  const [currentPage, setCurrentPage] = useState(0);
  const [pageDirection, setPageDirection] = useState(0);
  const [isPageAnimating, setIsPageAnimating] = useState(false);
  
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const websocketRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const logIdRef = useRef(0);
  const lastFrameTimeRef = useRef<number>(0);
  const frameIntervalRef = useRef<number>(50); // ~20fps，平衡延迟和流畅度
  const isRunningRef = useRef<boolean>(false);
  const lastSwipeGestureRef = useRef<string>('');
  const isSendingRef = useRef<boolean>(false); // 防止帧堆积

  const addLog = useCallback((message: string, type: LogEntry['type'] = 'info') => {
    const now = new Date();
    const timestamp = now.toLocaleTimeString('zh-CN', { 
      hour12: false, 
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit' 
    });
    
    setLogs(prev => {
      const newLogs = [...prev, {
        id: logIdRef.current++,
        timestamp,
        message,
        type
      }];
      return newLogs.slice(-30);
    });
  }, []);

  const goToPage = useCallback((page: number, direction: number = 0) => {
    if (page >= 0 && page < PAGES.length && !isPageAnimating) {
      setPageDirection(direction);
      setIsPageAnimating(true);
      setCurrentPage(page);
      setTimeout(() => setIsPageAnimating(false), 300);
    }
  }, [isPageAnimating]);

  const initCamera = useCallback(async () => {
    try {
      addLog('正在启动摄像头...', 'info');
      
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 640 },
          height: { ideal: 480 },
          facingMode: 'user'
        }
      });
      
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        streamRef.current = stream;
        addLog('摄像头已启动', 'success');
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '未知错误';
      setCameraError(`摄像头启动失败：${errorMessage}`);
      addLog(`摄像头启动失败：${errorMessage}`, 'error');
    }
  }, [addLog]);

  const handleVideoLoaded = useCallback(() => {
    setVideoReady(true);
    addLog('视频已加载', 'success');
  }, [addLog]);

  const connectWebSocket = useCallback(() => {
    try {
      addLog('正在连接服务器...', 'info');
      const ws = new WebSocket('ws://localhost:8000/ws/gesture');
      
      ws.onopen = () => {
        addLog('已连接到服务器', 'success');
        setIsConnected(true);
      };
      
      ws.onclose = () => {
        addLog('与服务器断开连接', 'warning');
        setIsConnected(false);
      };
      
      ws.onerror = () => {
        addLog('WebSocket 连接错误', 'error');
      };
      
      ws.onmessage = (event) => {
        try {
          const data: GestureData = JSON.parse(event.data);
          // 收到响应，允许发送下一帧
          isSendingRef.current = false;
          setGestureData(data);
          
          if (data.swipe_gesture && data.swipe_gesture !== '无滑动') {
            if (data.swipe_gesture !== lastSwipeGestureRef.current) {
              lastSwipeGestureRef.current = data.swipe_gesture;
              
              if (data.swipe_gesture === '左翻页') {
                setCurrentPage(prev => {
                  const next = Math.max(0, prev - 1);
                  if (next !== prev) {
                    setPageDirection(-1);
                    setIsPageAnimating(true);
                    setTimeout(() => setIsPageAnimating(false), 300);
                    addLog('手势翻页：上一页', 'success');
                  }
                  return next;
                });
              } else if (data.swipe_gesture === '右翻页') {
                setCurrentPage(prev => {
                  const next = Math.min(PAGES.length - 1, prev + 1);
                  if (next !== prev) {
                    setPageDirection(1);
                    setIsPageAnimating(true);
                    setTimeout(() => setIsPageAnimating(false), 300);
                    addLog('手势翻页：下一页', 'success');
                  }
                  return next;
                });
              }
            }
          } else {
            lastSwipeGestureRef.current = '';
          }
          
          if (data.mouse_control?.clicked) {
            addLog('鼠标点击', 'success');
          }
          
          if (data.error) {
            addLog(`处理错误：${data.error}`, 'error');
          }
        } catch (error) {
          console.error('解析响应失败:', error);
        }
      };
      
      websocketRef.current = ws;
    } catch (error) {
      addLog('WebSocket 连接失败', 'error');
    }
  }, [addLog]);

  const disconnectWebSocket = useCallback(() => {
    if (websocketRef.current) {
      websocketRef.current.close();
      websocketRef.current = null;
      setIsConnected(false);
      addLog('已断开连接', 'info');
    }
  }, [addLog]);

  const sendFrame = useCallback(() => {
    if (!websocketRef.current || websocketRef.current.readyState !== WebSocket.OPEN) {
      animationFrameRef.current = requestAnimationFrame(sendFrame);
      return;
    }
    
    // 防止帧堆积：如果上一帧还没处理完，跳过
    if (isSendingRef.current) {
      animationFrameRef.current = requestAnimationFrame(sendFrame);
      return;
    }
    
    const now = Date.now();
    if (now - lastFrameTimeRef.current < frameIntervalRef.current) {
      animationFrameRef.current = requestAnimationFrame(sendFrame);
      return;
    }
    
    lastFrameTimeRef.current = now;
    isSendingRef.current = true;
    
    if (videoRef.current && canvasRef.current) {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      const ctx = canvas.getContext('2d');
      
      if (ctx && video.readyState === 4) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        ctx.drawImage(video, 0, 0);
        
        const frameData = canvas.toDataURL('image/jpeg', 0.8).split(',')[1];
        
        try {
          websocketRef.current.send(JSON.stringify({ frame: frameData }));
        } catch (error) {
          console.error('发送帧失败:', error);
          isSendingRef.current = false;
        }
      } else {
        isSendingRef.current = false;
      }
    } else {
      isSendingRef.current = false;
    }
    
    animationFrameRef.current = requestAnimationFrame(sendFrame);
  }, []);

  const handleStart = useCallback(() => {
    if (!isConnected) {
      addLog('请先连接服务器', 'warning');
      return;
    }
    
    if (!isRunning && websocketRef.current) {
      websocketRef.current.send(JSON.stringify({ command: 'start' }));
      setIsRunning(true);
      isRunningRef.current = true;
      addLog('手势识别已启动', 'success');
      animationFrameRef.current = requestAnimationFrame(sendFrame);
    }
  }, [isConnected, isRunning, sendFrame, addLog]);

  const handleStop = useCallback(() => {
    if (websocketRef.current) {
      websocketRef.current.send(JSON.stringify({ command: 'stop' }));
      setIsRunning(false);
      isRunningRef.current = false;
      addLog('手势识别已停止', 'info');
      
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
    }
  }, [addLog]);

  const handleToggleMouseControl = useCallback(() => {
    if (!isConnected || !websocketRef.current) {
      addLog('请先连接服务器', 'warning');
      return;
    }
    
    if (isMouseControlEnabled) {
      websocketRef.current.send(JSON.stringify({ command: 'disable_mouse' }));
      setIsMouseControlEnabled(false);
      addLog('虚拟鼠标控制已禁用', 'info');
    } else {
      websocketRef.current.send(JSON.stringify({ command: 'enable_mouse' }));
      setIsMouseControlEnabled(true);
      addLog('虚拟鼠标控制已启用', 'success');
    }
  }, [isConnected, isMouseControlEnabled, addLog]);

  const handleClearLogs = useCallback(() => {
    setLogs([]);
    addLog('日志已清除', 'info');
  }, [addLog]);

  useEffect(() => {
    initCamera();
    connectWebSocket();
    
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      if (websocketRef.current) {
        websocketRef.current.close();
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
    };
  }, [initCamera, connectWebSocket]);

  const getGesturePreset = (gestureName: string | null): GesturePreset | undefined => {
    return GESTURE_PRESETS.find(p => p.name === gestureName);
  };

  const getGestureStatusStyle = () => {
    if (!gestureData?.gesture) return 'text-gray-400';
    const preset = getGesturePreset(gestureData.gesture);
    return preset ? `text-transparent bg-clip-text bg-gradient-to-r ${preset.color}` : 'text-gray-400';
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.9) return 'text-green-500';
    if (confidence >= 0.7) return 'text-yellow-500';
    return 'text-red-500';
  };

  return (
    <div className="h-screen flex flex-col bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 overflow-hidden">
      <header className="bg-white/80 backdrop-blur-sm shadow-sm border-b border-gray-200 flex-shrink-0">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-12">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg flex items-center justify-center shadow-lg">
                <Hand className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-base font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                  智能手势识别系统
                </h1>
              </div>
            </div>
            
            <div className="flex items-center space-x-2">
              <div className={`flex items-center space-x-1 px-2 py-1 rounded-lg text-xs ${
                isConnected ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
              }`}>
                {isConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
                <span className="font-medium">{isConnected ? '已连接' : '未连接'}</span>
              </div>
              
              <div className={`flex items-center space-x-1 px-2 py-1 rounded-lg text-xs ${
                isRunning ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-700'
              }`}>
                {isRunning ? <Monitor className="w-3 h-3" /> : <Square className="w-3 h-3" />}
                <span className="font-medium">{isRunning ? '运行中' : '已停止'}</span>
              </div>
              
              {isMouseControlEnabled && (
                <div className="flex items-center space-x-1 px-2 py-1 rounded-lg text-xs bg-purple-100 text-purple-700">
                  <MousePointer2 className="w-3 h-3" />
                  <span className="font-medium">鼠标控制</span>
                </div>
              )}
              
              {gestureData?.fps != null && (
                <div className="text-xs text-gray-600">
                  FPS: <span className="font-mono font-bold text-green-600">{Number(gestureData.fps).toFixed(1)}</span>
                </div>
              )}
              
              <button onClick={() => setShowGuide(!showGuide)} className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors" title="使用指南">
                <Info className="w-4 h-4 text-gray-600" />
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="flex-shrink-0 bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2 flex items-center gap-2">
          <button
            onClick={handleStart}
            disabled={!isConnected || isRunning}
            className="flex items-center space-x-1 px-4 py-1.5 bg-gradient-to-r from-green-500 to-emerald-600 text-white rounded-lg text-sm font-medium
                     hover:from-green-600 hover:to-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm"
          >
            <Play className="w-4 h-4" />
            <span>启动</span>
          </button>
          
          <button
            onClick={handleStop}
            disabled={!isRunning}
            className="flex items-center space-x-1 px-4 py-1.5 bg-gradient-to-r from-red-500 to-rose-600 text-white rounded-lg text-sm font-medium
                     hover:from-red-600 hover:to-rose-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm"
          >
            <Square className="w-4 h-4" />
            <span>停止</span>
          </button>
          
          <button
            onClick={handleToggleMouseControl}
            disabled={!isConnected}
            className={`flex items-center space-x-1 px-4 py-1.5 rounded-lg text-sm font-medium transition-all shadow-sm
                     ${isMouseControlEnabled 
                       ? 'bg-gradient-to-r from-purple-500 to-pink-600 text-white hover:from-purple-600 hover:to-pink-700' 
                       : 'bg-gradient-to-r from-blue-500 to-cyan-600 text-white hover:from-blue-600 hover:to-cyan-700'
                     } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            <MousePointer2 className="w-4 h-4" />
            <span>{isMouseControlEnabled ? '鼠标已启用' : '鼠标控制'}</span>
          </button>

          <div className="flex-1" />

          <div className="flex items-center space-x-1 text-xs text-gray-500">
            <span>翻页：</span>
            <span className="px-1.5 py-0.5 bg-sky-100 text-sky-700 rounded font-medium">← 左滑</span>
            <span className="px-1.5 py-0.5 bg-orange-100 text-orange-700 rounded font-medium">右滑 →</span>
          </div>
        </div>
      </div>

      <main className="flex-1 min-h-0 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-3">
        <div className="grid grid-cols-12 gap-3 h-full">
          <div className="col-span-7 flex flex-col gap-3 min-h-0">
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden flex-1 min-h-0 flex flex-col">
              <div className="bg-gradient-to-r from-blue-500 to-indigo-600 px-4 py-2 flex-shrink-0">
                <h2 className="text-sm font-semibold text-white flex items-center space-x-1">
                  <Camera className="w-4 h-4" />
                  <span>实时视频流</span>
                </h2>
              </div>
              
              <div className="flex-1 bg-gray-900 flex items-center justify-center relative min-h-0 overflow-hidden">
                {/* 原始摄像头画面：后端未返回处理帧时显示 */}
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className={`absolute inset-0 w-full h-full object-contain ${isRunning && gestureData?.image ? 'opacity-0' : 'opacity-100'}`}
                  onLoadedData={handleVideoLoaded}
                />
                <canvas ref={canvasRef} className="hidden" />
                
                {/* 骨架叠加层：后端返回的处理帧（含骨架+文字） */}
                {isRunning && gestureData?.image && (
                  <img
                    src={`data:image/jpeg;base64,${gestureData.image}`}
                    alt="Gesture Recognition"
                    className="absolute inset-0 w-full h-full object-contain"
                  />
                )}
                
                {/* 信息叠加 */}
                {!gestureData?.image && !videoReady && (
                  <div className="absolute inset-0 flex items-center justify-center text-gray-400 z-10">
                    <div className="text-center">
                      <Camera className="w-12 h-12 mx-auto mb-2 opacity-50" />
                      <p className="text-sm font-medium">正在加载摄像头...</p>
                    </div>
                  </div>
                )}
                
                <div className="absolute bottom-2 right-2 bg-green-500/90 backdrop-blur-sm text-white text-xs px-2 py-1 rounded-full font-medium shadow-lg z-10">
                  {isRunning ? '手势识别中' : '摄像头就绪'}
                </div>
              </div>
              
              {gestureData && (
                <div className="bg-gray-50 px-4 py-2 border-t border-gray-200 flex-shrink-0">
                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center space-x-3">
                      <span className="text-gray-600">
                        手部：<span className="font-semibold text-blue-600">{gestureData.hands_detected ?? 0}</span>
                      </span>
                      <span className="text-gray-600">
                        距离：<span className="font-mono text-purple-600">{Number(gestureData.distance ?? 0).toFixed(4)}</span>
                      </span>
                    </div>
                    {gestureData.swipe_gesture && gestureData.swipe_gesture !== '无滑动' && (
                      <span className={`font-medium px-2 py-0.5 rounded-full text-xs ${
                        gestureData.swipe_gesture === '左翻页' ? 'bg-sky-100 text-sky-700' : 'bg-orange-100 text-orange-700'
                      }`}>
                        {gestureData.swipe_gesture}
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden flex-shrink-0" style={{ height: '140px' }}>
              <div className="bg-gradient-to-r from-gray-700 to-gray-800 px-4 py-1.5 flex items-center justify-between">
                <h2 className="text-xs font-semibold text-white flex items-center space-x-1">
                  <Info className="w-3 h-3" />
                  <span>系统日志</span>
                </h2>
                <button onClick={handleClearLogs} className="p-1 hover:bg-white/10 rounded transition-colors" title="清除日志">
                  <Trash2 className="w-3 h-3 text-white" />
                </button>
              </div>
              <div className="h-[100px] overflow-y-auto bg-gray-900 p-2 font-mono text-xs">
                {logs.length === 0 ? (
                  <div className="text-gray-500 text-center py-4">暂无日志</div>
                ) : (
                  logs.map((log) => (
                    <div key={log.id} className="mb-0.5">
                      <span className="text-gray-500">[{log.timestamp}]</span>{' '}
                      <span className={`
                        ${log.type === 'success' ? 'text-green-400' : ''}
                        ${log.type === 'error' ? 'text-red-400' : ''}
                        ${log.type === 'warning' ? 'text-yellow-400' : ''}
                        ${log.type === 'info' ? 'text-blue-400' : ''}
                      `}>
                        {log.message}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          <div className="col-span-5 flex flex-col gap-3 min-h-0">
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden flex-shrink-0">
              <div className="bg-gradient-to-r from-blue-500 to-cyan-600 px-4 py-2">
                <h2 className="text-sm font-semibold text-white">当前手势</h2>
              </div>
              <div className="p-3">
                <div className="flex items-center justify-between">
                  <div className="text-center flex-1">
                    <div className={`text-3xl font-bold mb-1 ${getGestureStatusStyle()}`}>
                      {gestureData?.gesture ? getGesturePreset(gestureData.gesture)?.icon : '-'}
                    </div>
                    <div className={`text-lg font-bold ${getGestureStatusStyle()}`}>
                      {gestureData?.gesture || '等待识别'}
                    </div>
                    {gestureData?.gesture_confidence != null && (
                      <div className={`text-xs font-medium ${getConfidenceColor(gestureData.gesture_confidence)}`}>
                        置信度：{(Number(gestureData.gesture_confidence) * 100).toFixed(1)}%
                      </div>
                    )}
                  </div>
                  <div className="w-px h-16 bg-gray-200" />
                  <div className="text-center flex-1">
                    <div className={`text-3xl font-bold mb-1 ${
                      gestureData?.swipe_gesture && gestureData.swipe_gesture !== '无滑动'
                        ? 'text-transparent bg-clip-text bg-gradient-to-r from-sky-500 to-orange-500'
                        : 'text-gray-400'
                    }`}>
                      {gestureData?.swipe_gesture && gestureData.swipe_gesture !== '无滑动'
                        ? (gestureData.swipe_gesture === '左翻页' ? '←' : '→')
                        : '-'}
                    </div>
                    <div className={`text-sm font-bold ${
                      gestureData?.swipe_gesture && gestureData.swipe_gesture !== '无滑动'
                        ? 'text-transparent bg-clip-text bg-gradient-to-r from-sky-500 to-orange-500'
                        : 'text-gray-400'
                    }`}>
                      {gestureData?.swipe_gesture && gestureData.swipe_gesture !== '无滑动'
                        ? gestureData.swipe_gesture
                        : '无滑动'}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden flex-shrink-0">
              <div className="bg-gradient-to-r from-purple-500 to-pink-600 px-4 py-2">
                <h2 className="text-sm font-semibold text-white flex items-center space-x-1">
                  <MousePointer2 className="w-4 h-4" />
                  <span>虚拟鼠标</span>
                </h2>
              </div>
              <div className="p-3">
                <div className="flex items-center justify-between">
                  <div className={`text-center flex-1 ${
                    gestureData?.is_mouse_active ? 'text-green-600' : 'text-gray-400'
                  }`}>
                    <div className="text-2xl font-bold">{gestureData?.is_mouse_active ? 'ON' : 'OFF'}</div>
                    <div className="text-xs font-medium">
                      {gestureData?.is_mouse_active ? '已激活' : '未激活'}
                    </div>
                  </div>
                  {gestureData?.mouse_control?.cursor_position && (
                    <>
                      <div className="w-px h-10 bg-gray-200" />
                      <div className="text-center flex-1">
                        <div className="text-xs text-gray-500 mb-1">光标位置</div>
                        <div className="font-mono text-sm font-bold text-purple-600">
                          ({gestureData.mouse_control.cursor_position.x}, {gestureData.mouse_control.cursor_position.y})
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden flex-1 min-h-0 flex flex-col">
              <div className="bg-gradient-to-r from-indigo-500 to-purple-600 px-4 py-2 flex items-center justify-between flex-shrink-0">
                <h2 className="text-sm font-semibold text-white">手势翻页</h2>
                <div className="flex items-center space-x-1">
                  <button
                    onClick={() => goToPage(Math.max(0, currentPage - 1), -1)}
                    disabled={currentPage === 0}
                    className="p-1 hover:bg-white/10 rounded transition-colors disabled:opacity-30"
                  >
                    <ChevronLeft className="w-4 h-4 text-white" />
                  </button>
                  <span className="text-xs text-white/80 font-mono">{currentPage + 1}/{PAGES.length}</span>
                  <button
                    onClick={() => goToPage(Math.min(PAGES.length - 1, currentPage + 1), 1)}
                    disabled={currentPage === PAGES.length - 1}
                    className="p-1 hover:bg-white/10 rounded transition-colors disabled:opacity-30"
                  >
                    <ChevronRight className="w-4 h-4 text-white" />
                  </button>
                </div>
              </div>
              <div className="flex-1 p-3 overflow-y-auto min-h-0">
                <div className={`transition-all duration-300 ease-out ${
                  isPageAnimating
                    ? pageDirection > 0
                      ? 'opacity-0 translate-x-4'
                      : 'opacity-0 -translate-x-4'
                    : 'opacity-100 translate-x-0'
                }`}>
                  <h3 className="text-base font-bold text-gray-800 mb-1">{PAGES[currentPage].title}</h3>
                  <p className="text-xs text-gray-600 mb-2">{PAGES[currentPage].content}</p>
                  <ul className="space-y-1">
                    {PAGES[currentPage].items.map((item, i) => (
                      <li key={i} className="flex items-start space-x-1.5 text-xs text-gray-600">
                        <span className="text-indigo-500 mt-0.5">•</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
              <div className="flex-shrink-0 px-3 pb-2">
                <div className="flex justify-center space-x-1">
                  {PAGES.map((_, i) => (
                    <button
                      key={i}
                      onClick={() => goToPage(i, i > currentPage ? 1 : -1)}
                      className={`w-2 h-2 rounded-full transition-all ${
                        i === currentPage ? 'bg-indigo-500 w-4' : 'bg-gray-300 hover:bg-gray-400'
                      }`}
                    />
                  ))}
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden flex-shrink-0">
              <div className="bg-gradient-to-r from-teal-500 to-cyan-600 px-4 py-2">
                <h2 className="text-sm font-semibold text-white">支持的手势</h2>
              </div>
              <div className="p-2">
                <div className="grid grid-cols-4 gap-1">
                  {GESTURE_PRESETS.map((preset) => (
                    <div
                      key={preset.name}
                      className={`flex flex-col items-center p-1.5 rounded-lg transition-all text-center ${
                        gestureData?.gesture === preset.name
                          ? `bg-gradient-to-r ${preset.color} text-white shadow-sm`
                          : 'bg-gray-50 hover:bg-gray-100'
                      }`}
                    >
                      <span className="text-lg font-bold leading-none">{preset.icon}</span>
                      <span className={`text-[10px] mt-0.5 leading-tight ${
                        gestureData?.gesture === preset.name ? 'text-white' : 'text-gray-600'
                      }`}>
                        {preset.name}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

      {showGuide && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-3xl w-full max-h-[80vh] overflow-y-auto">
            <div className="bg-gradient-to-r from-blue-500 to-indigo-600 px-6 py-3 flex items-center justify-between rounded-t-2xl">
              <h2 className="text-base font-semibold text-white flex items-center space-x-2">
                <Info className="w-4 h-4" />
                <span>使用指南</span>
              </h2>
              <button onClick={() => setShowGuide(false)} className="text-white/80 hover:text-white text-xl">×</button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <h3 className="text-base font-semibold text-gray-800 mb-2">快速开始</h3>
                <ol className="space-y-1.5 text-gray-600 text-sm">
                  <li className="flex items-start space-x-2">
                    <span className="flex-shrink-0 w-5 h-5 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs font-bold">1</span>
                    <span>允许浏览器访问摄像头权限</span>
                  </li>
                  <li className="flex items-start space-x-2">
                    <span className="flex-shrink-0 w-5 h-5 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs font-bold">2</span>
                    <span>点击"启动"按钮开始手势识别</span>
                  </li>
                  <li className="flex items-start space-x-2">
                    <span className="flex-shrink-0 w-5 h-5 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs font-bold">3</span>
                    <span>将手放在摄像头前，确保光线充足</span>
                  </li>
                  <li className="flex items-start space-x-2">
                    <span className="flex-shrink-0 w-5 h-5 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs font-bold">4</span>
                    <span>手掌水平滑动可控制翻页</span>
                  </li>
                </ol>
              </div>
              <div>
                <h3 className="text-base font-semibold text-gray-800 mb-2">手势说明</h3>
                <div className="grid grid-cols-3 gap-2">
                  {GESTURE_PRESETS.map((preset) => (
                    <div key={preset.name} className="flex items-center space-x-2 p-2 bg-gray-50 rounded-lg">
                      <span className="text-2xl font-bold">{preset.icon}</span>
                      <div>
                        <div className="font-medium text-gray-800 text-sm">{preset.name}</div>
                        <div className="text-xs text-gray-500">{preset.description}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="bg-yellow-50 border-l-4 border-yellow-400 p-3 rounded-r-xl">
                <div className="flex items-start space-x-2">
                  <span className="text-xl">!</span>
                  <div>
                    <div className="font-medium text-yellow-800 text-sm">注意事项</div>
                    <ul className="text-xs text-yellow-700 space-y-0.5 mt-1">
                      <li>确保周围环境光线充足均匀</li>
                      <li>手部与摄像头保持 30-50cm 距离</li>
                      <li>翻页时手掌水平滑动幅度要大</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
