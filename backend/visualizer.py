# -*- coding: utf-8 -*-
import cv2
import numpy as np
from typing import List, Any
from backend.config import VIDEO_CONFIG


class HandVisualizer:
    
    INDEX_FINGER_TIP = 8
    
    def __init__(self):
        self.connections = [
            (0, 1), (1, 2), (2, 3), (3, 4),
            (0, 5), (5, 6), (6, 7), (7, 8),
            (0, 9), (9, 10), (10, 11), (11, 12),
            (0, 13), (13, 14), (14, 15), (15, 16),
            (0, 17), (17, 18), (18, 19), (19, 20),
            (5, 9), (9, 13), (13, 17),
        ]
    
    def draw_on_frame(
        self, 
        frame: np.ndarray, 
        landmarks: List[Any], 
        w: int, 
        h: int,
        gesture_label: str, 
        gesture_score: float,
        distance: float, 
        fps: float
    ) -> np.ndarray:
        try:
            self._draw_text_info(frame, fps, gesture_label, gesture_score, distance)
            self._draw_skeleton(frame, landmarks, w, h)
            self._draw_landmarks(frame, landmarks, w, h)
            return frame
        except Exception as e:
            print(f"绘制错误：{e}")
            return frame
    
    def _draw_text_info(
        self, 
        frame: np.ndarray, 
        fps: float, 
        gesture_label: str, 
        gesture_score: float,
        distance: float
    ):
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        cv2.putText(frame, f"Gesture: {gesture_label} ({gesture_score:.2f})", (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
        
        cv2.putText(frame, f"Dist: {distance:.4f}", (10, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 1)
    
    def _draw_skeleton(self, frame: np.ndarray, landmarks: List[Any], w: int, h: int):
        try:
            for pt1_idx, pt2_idx in self.connections:
                lm1 = landmarks[pt1_idx]
                lm2 = landmarks[pt2_idx]
                
                pt1 = (int(lm1.x * w), int(lm1.y * h))
                pt2 = (int(lm2.x * w), int(lm2.y * h))
                
                if 0 <= pt1[0] < w and 0 <= pt1[1] < h and 0 <= pt2[0] < w and 0 <= pt2[1] < h:
                    cv2.line(frame, pt1, pt2, (0, 255, 0), 2)
        except Exception as e:
            print(f"骨架绘制错误：{e}")
    
    def _draw_landmarks(self, frame: np.ndarray, landmarks: List[Any], w: int, h: int):
        try:
            for idx, landmark in enumerate(landmarks):
                cx = int(landmark.x * w)
                cy = int(landmark.y * h)
                
                if 0 <= cx < w and 0 <= cy < h:
                    color = (0, 0, 255) if idx == self.INDEX_FINGER_TIP else (0, 255, 0)
                    radius = 8 if idx == self.INDEX_FINGER_TIP else 5
                    
                    cv2.circle(frame, (cx, cy), radius, color, -1)
                    cv2.circle(frame, (cx, cy), radius + 2, (255, 255, 255), 1)
        except Exception as e:
            print(f"关键点绘制错误：{e}")
    
    def encode_frame(self, frame: np.ndarray) -> str:
        import base64
        
        try:
            if frame is None or frame.size == 0:
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
            
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, VIDEO_CONFIG['jpeg_quality']])
            
            if not ret:
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                ret, buffer = cv2.imencode('.jpg', frame)
            
            jpg_as_text = base64.b64encode(buffer).decode('utf-8')
            return jpg_as_text
            
        except Exception as e:
            print(f"编码错误：{e}")
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            _, buffer = cv2.imencode('.jpg', frame)
            return base64.b64encode(buffer).decode('utf-8')
