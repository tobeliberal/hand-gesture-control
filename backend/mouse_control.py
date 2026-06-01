# -*- coding: utf-8 -*-
import queue
import threading
import pyautogui
import numpy as np
from typing import Dict, Any, List
import time


class MouseController:
    
    INDEX_FINGER_TIP = 8
    MIDDLE_FINGER_TIP = 12
    
    def __init__(self, click_threshold: float = 0.05):
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0
        
        self.screen_width, self.screen_height = pyautogui.size()
        
        self.alpha = 0.4
        self.move_threshold = 3
        self.scale = 1.5
        
        self.click_threshold = click_threshold
        self.click_threshold_frames = 2
        self.click_cooldown = 0.5
        
        self.is_control_enabled = False
        self.last_x, self.last_y = -1, -1
        self.smoothed_x = self.screen_width // 2
        self.smoothed_y = self.screen_height // 2
        
        self.last_click_time = 0
        self.click_frames = 0
        
        self.cmd_queue = queue.Queue(maxsize=1)
        self.worker = threading.Thread(target=self._mouse_worker, daemon=True)
        self.worker.start()
        
        print(f"鼠标控制线程启动：{self.screen_width}x{self.screen_height}")
    
    def _mouse_worker(self):
        while True:
            try:
                task = self.cmd_queue.get()
                if task is None:
                    break
                if 'type' in task:
                    if task['type'] == 'move':
                        pyautogui.moveTo(task['x'], task['y'], duration=0.0, _pause=False)
                    elif task['type'] == 'click':
                        pyautogui.click(_pause=False)
                else:
                    pyautogui.moveTo(task['x'], task['y'], duration=0.0, _pause=False)
                self.cmd_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"鼠标工作线程错误：{e}")
    
    def update(self, result: Dict[str, Any]) -> Dict[str, Any]:
        response = {
            'mouse_controlled': False,
            'cursor_position': None,
            'clicked': False,
            'gesture': None,
            'is_active': self.is_control_enabled
        }
        
        if not self.is_control_enabled:
            return response
        
        landmarks = result.get('landmarks', [])
        if not landmarks or len(landmarks) < self.MIDDLE_FINGER_TIP + 1:
            return response
        
        try:
            index_tip = landmarks[self.INDEX_FINGER_TIP]
            middle_tip = landmarks[self.MIDDLE_FINGER_TIP]
            
            raw_x = index_tip['x']
            raw_y = index_tip['y']
            
            target_x = int(raw_x * self.screen_width)
            target_y = int(raw_y * self.screen_height)
            
            target_x = max(0, min(target_x, self.screen_width - 1))
            target_y = max(0, min(target_y, self.screen_height - 1))
            
            if self.last_x == -1:
                self.last_x, self.last_y = target_x, target_y
                self.smoothed_x, self.smoothed_y = target_x, target_y
            
            self.smoothed_x = int(self.alpha * target_x + (1 - self.alpha) * self.smoothed_x)
            self.smoothed_y = int(self.alpha * target_y + (1 - self.alpha) * self.smoothed_y)
            
            dist = np.sqrt((self.smoothed_x - self.last_x)**2 + (self.smoothed_y - self.last_y)**2)
            if dist > self.move_threshold:
                try:
                    if self.cmd_queue.full():
                        try:
                            self.cmd_queue.get_nowait()
                        except queue.Empty:
                            pass
                    self.cmd_queue.put_nowait({'type': 'move', 'x': self.smoothed_x, 'y': self.smoothed_y})
                    self.last_x, self.last_y = self.smoothed_x, self.smoothed_y
                except queue.Full:
                    pass
                except Exception as e:
                    print(f"放入移动任务失败：{e}")
            
            response['mouse_controlled'] = True
            response['cursor_position'] = {'x': self.smoothed_x, 'y': self.smoothed_y}
            
            distance = np.sqrt(
                (index_tip['x'] - middle_tip['x'])**2 +
                (index_tip['y'] - middle_tip['y'])**2
            )
            
            current_time = time.time()
            if distance < self.click_threshold:
                self.click_frames += 1
                
                if self.click_frames >= self.click_threshold_frames:
                    if current_time - self.last_click_time >= self.click_cooldown:
                        try:
                            if self.cmd_queue.full():
                                try:
                                    self.cmd_queue.get_nowait()
                                except queue.Empty:
                                    pass
                            self.cmd_queue.put_nowait({'type': 'click'})
                            response['clicked'] = True
                            self.last_click_time = current_time
                        except queue.Full:
                            pass
                        except Exception as e:
                            print(f"放入点击任务失败：{e}")
                        self.click_frames = 0
            else:
                self.click_frames = 0
                response['gesture'] = 'moving'
            
            return response
            
        except Exception as e:
            print(f"更新光标位置错误：{e}")
            import traceback
            traceback.print_exc()
            return response
    
    def enable_control(self):
        self.is_control_enabled = True
        self.last_x, self.last_y = -1, -1
        self.smoothed_x = self.screen_width // 2
        self.smoothed_y = self.screen_height // 2
        self.click_frames = 0
        self.last_click_time = 0
        while not self.cmd_queue.empty():
            try:
                self.cmd_queue.get_nowait()
            except queue.Empty:
                break
        print("鼠标控制 [已启用]")
    
    def disable_control(self):
        self.is_control_enabled = False
        self.click_frames = 0
        while not self.cmd_queue.empty():
            try:
                self.cmd_queue.get_nowait()
            except queue.Empty:
                break
        print("鼠标控制 [已禁用]")
    
    def get_status(self) -> Dict[str, Any]:
        return {
            'is_control_enabled': self.is_control_enabled,
            'screen_resolution': f"{self.screen_width}x{self.screen_height}",
            'alpha': self.alpha,
            'move_threshold': self.move_threshold,
            'scale': self.scale,
            'click_threshold': self.click_threshold,
            'queue_size': self.cmd_queue.qsize()
        }
    
    def reset(self):
        self.last_x, self.last_y = -1, -1
        self.click_frames = 0
        self.last_click_time = 0
        while not self.cmd_queue.empty():
            try:
                self.cmd_queue.get_nowait()
            except queue.Empty:
                break
        print("鼠标控制器已重置")
    
    def close(self):
        try:
            self.cmd_queue.put_nowait(None)
            self.worker.join(timeout=1.0)
        except Exception as e:
            print(f"关闭鼠标控制器时出错：{e}")
        while not self.cmd_queue.empty():
            try:
                self.cmd_queue.get_nowait()
            except queue.Empty:
                break
        print("鼠标控制器已关闭")
