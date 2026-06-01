# -*- coding: utf-8 -*-
import asyncio
import base64
import numpy as np
import cv2
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import json
import sys
import os
import traceback
import concurrent.futures

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.detector import RobustHandDetector
from backend.mouse_control import MouseController
from backend.config import SERVER_CONFIG

# 线程池用于异步执行CPU密集的检测任务
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)


class SystemStatus(BaseModel):
    status: str
    message: Optional[str] = None


app = FastAPI(title="Gesture Recognition System", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=SERVER_CONFIG['allowed_origins'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DetectorManager:
    
    def __init__(self):
        self.detector = None
        self.mouse_controller = None
        self.is_running = False
        self.clients = set()
    
    def initialize(self):
        try:
            print("正在初始化检测器...")
            self.detector = RobustHandDetector()
            print("检测器初始化完成")
            
            print("正在初始化虚拟鼠标控制器...")
            self.mouse_controller = MouseController()
            print("虚拟鼠标控制器初始化完成")
        except Exception as e:
            print(f"初始化失败：{e}")
            traceback.print_exc()
            raise
    
    async def process_frame(self, frame: np.ndarray, mouse_control_enabled: bool = False) -> Dict[str, Any]:
        if not self.detector:
            return {'error': '检测器未初始化'}
        
        try:
            # 在线程池中执行CPU密集的检测任务，避免阻塞事件循环
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(_executor, self.detector.detect, frame)
            
            if mouse_control_enabled and self.mouse_controller and result.get('hands_detected', 0) > 0:
                mouse_result = self.mouse_controller.update(result)
                result['mouse_control'] = mouse_result
                result['mouse_control_enabled'] = True
            else:
                result['mouse_control_enabled'] = False
            
            return result
        except Exception as e:
            print(f"处理帧错误：{e}")
            traceback.print_exc()
            return {
                'hands_detected': 0,
                'landmarks': [],
                'gesture': None,
                'gesture_score': 0.0,
                'distance': 0.0,
                'fps': 0,
                'frame': None,
                'error': str(e),
                'mouse_control_enabled': False
            }
    
    def close(self):
        if self.detector:
            self.detector.close()
        if self.mouse_controller:
            if hasattr(self.mouse_controller, 'close'):
                self.mouse_controller.close()
            self.mouse_controller.disable_control()


detector_manager = DetectorManager()


@app.get("/")
async def root():
    return {
        "message": "智能手势识别系统 API",
        "version": "1.0.0",
        "endpoints": {
            "websocket": "/ws/gesture",
            "status": "/api/status"
        }
    }


@app.get("/api/status")
async def get_status():
    mouse_status = detector_manager.mouse_controller.get_status() if detector_manager.mouse_controller else {}
    return {
        "status": "running" if detector_manager.detector else "stopped",
        "detector_initialized": detector_manager.detector is not None,
        "connected_clients": len(detector_manager.clients),
        "mouse_control": mouse_status
    }


@app.websocket("/ws/gesture")
async def websocket_gesture(websocket: WebSocket):
    await websocket.accept()
    detector_manager.clients.add(websocket)
    print(f"WebSocket 连接已建立，当前客户端数：{len(detector_manager.clients)}")
    
    mouse_control_enabled = False
    
    try:
        while True:
            data = await websocket.receive_json()
            
            if 'frame' in data:
                try:
                    frame_data = base64.b64decode(data['frame'])
                    frame = cv2.imdecode(np.frombuffer(frame_data, np.uint8), cv2.IMREAD_COLOR)
                    
                    if frame is not None:
                        result = await detector_manager.process_frame(frame, mouse_control_enabled)
                        
                        response = {
                            'image': result.get('frame'),
                            'gesture': result.get('gesture'),
                            'distance': result.get('distance'),
                            'is_mouse_active': mouse_control_enabled,
                            'hands_detected': result.get('hands_detected', 0),
                            'fps': result.get('fps', 0),
                            'gesture_confidence': result.get('gesture_confidence', 0.0),
                            'swipe_gesture': result.get('swipe_gesture', '无滑动'),
                            'mouse_control': result.get('mouse_control') if mouse_control_enabled else None
                        }
                        await websocket.send_json(response)
                    else:
                        await websocket.send_json({'error': '图像解码失败'})
                
                except Exception as e:
                    print(f"处理帧错误：{e}")
                    traceback.print_exc()
                    await websocket.send_json({'error': str(e)})
            
            elif 'command' in data:
                command = data['command']
                
                if command == 'start':
                    detector_manager.is_running = True
                    await websocket.send_json({
                        'status': 'started',
                        'message': '手势识别已启动'
                    })
                
                elif command == 'stop':
                    detector_manager.is_running = False
                    await websocket.send_json({
                        'status': 'stopped',
                        'message': '手势识别已停止'
                    })
                
                elif command == 'enable_mouse':
                    if detector_manager.mouse_controller:
                        detector_manager.mouse_controller.enable_control()
                        mouse_control_enabled = True
                        await websocket.send_json({
                            'status': 'mouse_enabled',
                            'message': '虚拟鼠标控制已启用'
                        })
                
                elif command == 'disable_mouse':
                    if detector_manager.mouse_controller:
                        detector_manager.mouse_controller.disable_control()
                        mouse_control_enabled = False
                        await websocket.send_json({
                            'status': 'mouse_disabled',
                            'message': '虚拟鼠标控制已禁用'
                        })
    
    except WebSocketDisconnect:
        print(f"WebSocket 客户端断开连接")
        detector_manager.clients.discard(websocket)
        print(f"当前客户端数：{len(detector_manager.clients)}")
    
    except Exception as e:
        print(f"WebSocket 错误：{str(e)}")
        traceback.print_exc()
        detector_manager.clients.discard(websocket)
        
        try:
            await websocket.send_json({'error': str(e)})
        except:
            pass


print("手势识别与虚拟鼠标系统启动中...")
detector_manager.initialize()
print("系统已就绪: http://localhost:8000")


@app.on_event("shutdown")
async def shutdown_event():
    print("\n正在关闭系统...")
    detector_manager.close()
    print("系统已关闭")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=SERVER_CONFIG['host'],
        port=SERVER_CONFIG['port'],
        log_level="info"
    )
