# -*- coding: utf-8 -*-
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, 'hand_landmarker.task')

DETECTOR_CONFIG = {
    'min_detection_confidence': 0.3,
    'min_tracking_confidence': 0.2,
    'num_hands': 1,
}

GESTURE_CONFIG = {
    'ok_gesture_distance': 0.06,
    'smoothing_history_length': 8,
    'min_history_for_smoothing': 3,
    'stability_frames': 3,
    'min_confidence': 0.0,
    'max_confidence': 1.0,
    'swipe_threshold': 0.08,
    'swipe_track_frames': 15,
    'swipe_cooldown_frames': 15,
    'thumb_extended_ratio': 1.25,
    'finger_extended_ratio': 1.2,
    'finger_extended_ratio_marginal': 1.05,
    'finger_extended_angle_threshold': 140.0,
}

MOUSE_CONFIG = {
    'click_threshold': 0.05,
    'smoothing_factor': 0.3,
    'click_frames_required': 2,
    'camera_width': 640,
    'camera_height': 480,
}

VIDEO_CONFIG = {
    'width': 640,
    'height': 480,
    'fps': 30,
    'jpeg_quality': 70,
}

SERVER_CONFIG = {
    'host': '0.0.0.0',
    'port': 8000,
    'allowed_origins': ['http://localhost:3000'],
}
