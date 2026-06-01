# -*- coding: utf-8 -*-
import cv2
import mediapipe as mp
import numpy as np
import time
import traceback
from typing import Dict, Any, List

from backend.config import DETECTOR_CONFIG, MODEL_PATH
from backend.gesture_matcher import GestureMatcher
from backend.visualizer import HandVisualizer


class RobustHandDetector:
    
    def __init__(self, min_detection_confidence: float = None):
        try:
            if min_detection_confidence is None:
                min_detection_confidence = DETECTOR_CONFIG['min_detection_confidence']
            
            min_tracking_confidence = DETECTOR_CONFIG.get('min_tracking_confidence', 0.2)
            num_hands = DETECTOR_CONFIG.get('num_hands', 1)
            
            base_options = mp.tasks.BaseOptions(model_asset_path=MODEL_PATH)
            
            options = mp.tasks.vision.HandLandmarkerOptions(
                base_options=base_options,
                num_hands=num_hands,
                min_hand_detection_confidence=min_detection_confidence,
                min_hand_presence_confidence=min_tracking_confidence,
                min_tracking_confidence=min_tracking_confidence,
                running_mode=mp.tasks.vision.RunningMode.IMAGE,
            )
            
            self.detector = mp.tasks.vision.HandLandmarker.create_from_options(options)
            self.frame_count = 0
            self.start_time = time.time()
            self.error_count = 0
            
            self.gesture_matcher = GestureMatcher()
            self.visualizer = HandVisualizer()
            
        except Exception as e:
            print(f"初始化失败：{e}")
            traceback.print_exc()
            raise
    
    def detect(self, frame: np.ndarray) -> Dict[str, Any]:
        try:
            self.frame_count += 1
            h, w, _ = frame.shape
            
            elapsed = time.time() - self.start_time
            fps = self.frame_count / elapsed if elapsed > 0 else 0
            
            # cv2.imdecode 返回 BGR 格式，MediaPipe 需要 RGB
            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
            
            result = self.detector.detect(mp_image)
            
            result_data = {
                'hands_detected': 0,
                'landmarks': [],
                'gesture': None,
                'gesture_score': 0.0,
                'distance': 0.0,
                'fps': fps,
                'frame': None
            }
            
            gesture_label = "无手势"
            gesture_score = 0.0
            
            if hasattr(result, 'gestures') and result.gestures:
                if len(result.gestures) > 0 and len(result.gestures[0]) > 0:
                    top_gesture = result.gestures[0][0]
                    gesture_label = top_gesture.category_name
                    gesture_score = top_gesture.score
            
            result_data['gesture'] = gesture_label if gesture_label != "无手势" else None
            result_data['gesture_score'] = gesture_score
            
            if result.hand_landmarks:
                landmarks = result.hand_landmarks[0]
                result_data['hands_detected'] = 1
                
                for idx, landmark in enumerate(landmarks):
                    result_data['landmarks'].append({
                        'x': float(landmark.x),
                        'y': float(landmark.y),
                        'z': float(landmark.z),
                        'pixel_x': int(landmark.x * w),
                        'pixel_y': int(landmark.y * h)
                    })
                
                smoothed_gesture, finger_states, smooth_confidence, swipe_gesture = self.gesture_matcher.process_gesture(landmarks)
                
                result_data['gesture'] = smoothed_gesture
                result_data['gesture_details'] = finger_states
                result_data['gesture_confidence'] = smooth_confidence
                result_data['swipe_gesture'] = swipe_gesture
                
                if len(landmarks) > 12:
                    index_tip = landmarks[8]
                    middle_tip = landmarks[12]
                    distance = np.sqrt(
                        (index_tip.x - middle_tip.x)**2 +
                        (index_tip.y - middle_tip.y)**2 +
                        (index_tip.z - middle_tip.z)**2
                    )
                    result_data['distance'] = float(distance)
                
                # 在原始BGR帧上绘制（不需要copy，因为后续只用于编码）
                debug_frame = self.visualizer.draw_on_frame(
                    frame, landmarks, w, h,
                    smoothed_gesture, smooth_confidence,
                    result_data['distance'], fps
                )
                
                result_data['frame'] = self.visualizer.encode_frame(debug_frame)
            else:
                self.gesture_matcher.gesture_history.append("无手势")
                if len(self.gesture_matcher.gesture_history) > self.gesture_matcher.max_history:
                    self.gesture_matcher.gesture_history.pop(0)
                result_data['gesture'] = "无手势"
                result_data['gesture_confidence'] = 0.0
                result_data['swipe_gesture'] = "无滑动"
                # 无手时不编码帧，减少开销
                result_data['frame'] = None
            
            return result_data
            
        except Exception as e:
            self.error_count += 1
            print(f"检测错误 [Frame {self.frame_count}]: {e}")
            traceback.print_exc()
            return {
                'hands_detected': 0,
                'landmarks': [],
                'gesture': None,
                'gesture_score': 0.0,
                'distance': 0.0,
                'fps': 0,
                'frame': None,
                'error': str(e)
            }
    
    def close(self):
        try:
            self.detector.close()
            self.gesture_matcher.reset()
            print(f"统计：帧={self.frame_count}, 错误={self.error_count}")
        except Exception as e:
            print(f"关闭错误：{e}")
