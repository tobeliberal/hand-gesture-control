# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.gesture_matcher import GestureMatcher


class MockLandmark:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z


def _make_fist_landmarks():
    landmarks = []
    landmarks.append(MockLandmark(0.5, 0.6, 0.0))
    landmarks.append(MockLandmark(0.44, 0.56, 0.02))
    landmarks.append(MockLandmark(0.42, 0.52, 0.04))
    landmarks.append(MockLandmark(0.40, 0.50, 0.05))
    landmarks.append(MockLandmark(0.39, 0.48, 0.06))
    landmarks.append(MockLandmark(0.54, 0.48, 0.02))
    landmarks.append(MockLandmark(0.57, 0.46, 0.03))
    landmarks.append(MockLandmark(0.60, 0.47, 0.04))
    landmarks.append(MockLandmark(0.55, 0.50, 0.05))
    landmarks.append(MockLandmark(0.56, 0.50, 0.02))
    landmarks.append(MockLandmark(0.59, 0.48, 0.03))
    landmarks.append(MockLandmark(0.62, 0.49, 0.04))
    landmarks.append(MockLandmark(0.57, 0.52, 0.05))
    landmarks.append(MockLandmark(0.57, 0.52, 0.02))
    landmarks.append(MockLandmark(0.60, 0.51, 0.03))
    landmarks.append(MockLandmark(0.63, 0.52, 0.04))
    landmarks.append(MockLandmark(0.58, 0.54, 0.05))
    landmarks.append(MockLandmark(0.58, 0.54, 0.02))
    landmarks.append(MockLandmark(0.61, 0.53, 0.03))
    landmarks.append(MockLandmark(0.64, 0.54, 0.04))
    landmarks.append(MockLandmark(0.59, 0.56, 0.05))
    return landmarks


def _make_index_only_landmarks():
    landmarks = []
    landmarks.append(MockLandmark(0.5, 0.6, 0.0))
    landmarks.append(MockLandmark(0.45, 0.55, 0.02))
    landmarks.append(MockLandmark(0.42, 0.50, 0.04))
    landmarks.append(MockLandmark(0.40, 0.46, 0.05))
    landmarks.append(MockLandmark(0.38, 0.42, 0.06))
    landmarks.append(MockLandmark(0.55, 0.48, 0.02))
    landmarks.append(MockLandmark(0.58, 0.40, 0.03))
    landmarks.append(MockLandmark(0.60, 0.35, 0.04))
    landmarks.append(MockLandmark(0.62, 0.25, 0.05))
    landmarks.append(MockLandmark(0.57, 0.50, 0.02))
    landmarks.append(MockLandmark(0.60, 0.45, 0.03))
    landmarks.append(MockLandmark(0.62, 0.43, 0.04))
    landmarks.append(MockLandmark(0.63, 0.41, 0.05))
    landmarks.append(MockLandmark(0.58, 0.52, 0.02))
    landmarks.append(MockLandmark(0.60, 0.50, 0.03))
    landmarks.append(MockLandmark(0.62, 0.49, 0.04))
    landmarks.append(MockLandmark(0.63, 0.48, 0.05))
    landmarks.append(MockLandmark(0.59, 0.54, 0.02))
    landmarks.append(MockLandmark(0.61, 0.53, 0.03))
    landmarks.append(MockLandmark(0.62, 0.52, 0.04))
    landmarks.append(MockLandmark(0.63, 0.51, 0.05))
    return landmarks


def _make_palm_landmarks():
    landmarks = []
    landmarks.append(MockLandmark(0.5, 0.6, 0.0))
    landmarks.append(MockLandmark(0.42, 0.52, 0.02))
    landmarks.append(MockLandmark(0.38, 0.44, 0.04))
    landmarks.append(MockLandmark(0.35, 0.36, 0.05))
    landmarks.append(MockLandmark(0.32, 0.28, 0.06))
    landmarks.append(MockLandmark(0.55, 0.45, 0.02))
    landmarks.append(MockLandmark(0.58, 0.35, 0.03))
    landmarks.append(MockLandmark(0.60, 0.25, 0.04))
    landmarks.append(MockLandmark(0.62, 0.15, 0.05))
    landmarks.append(MockLandmark(0.57, 0.46, 0.02))
    landmarks.append(MockLandmark(0.60, 0.35, 0.03))
    landmarks.append(MockLandmark(0.63, 0.25, 0.04))
    landmarks.append(MockLandmark(0.65, 0.15, 0.05))
    landmarks.append(MockLandmark(0.58, 0.48, 0.02))
    landmarks.append(MockLandmark(0.61, 0.38, 0.03))
    landmarks.append(MockLandmark(0.63, 0.28, 0.04))
    landmarks.append(MockLandmark(0.65, 0.18, 0.05))
    landmarks.append(MockLandmark(0.59, 0.50, 0.02))
    landmarks.append(MockLandmark(0.62, 0.42, 0.03))
    landmarks.append(MockLandmark(0.64, 0.32, 0.04))
    landmarks.append(MockLandmark(0.66, 0.22, 0.05))
    return landmarks


def test_distance_calculation():
    matcher = GestureMatcher()
    lm1 = MockLandmark(0.5, 0.5, 0.0)
    lm2 = MockLandmark(0.6, 0.6, 0.0)
    distance = matcher._dist(lm1, lm2)
    assert distance > 0


def test_angle_calculation():
    matcher = GestureMatcher()
    a = MockLandmark(0.4, 0.5, 0.0)
    b = MockLandmark(0.5, 0.5, 0.0)
    c = MockLandmark(0.6, 0.5, 0.0)
    angle = matcher._angle_between(a, b, c)
    assert 170.0 < angle <= 180.0


def test_fist_recognition():
    matcher = GestureMatcher()
    landmarks = _make_fist_landmarks()
    gesture, states, confidence = matcher.recognize_gesture(landmarks)
    assert gesture == "拳头", f"Expected 拳头 but got {gesture}, states={states}"


def test_smoothing():
    matcher = GestureMatcher()
    matcher.gesture_history = ["拳头", "拳头", "拳头", "拳头", "拳头"]
    matcher.current_gesture = "拳头"
    smoothed_gesture, confidence = matcher._smooth_gesture("拳头")
    assert confidence == 1.0 or confidence >= 0.5


def test_reset():
    matcher = GestureMatcher()
    matcher.gesture_history.append("拳头")
    matcher.current_gesture = "拳头"
    matcher.reset()
    assert len(matcher.gesture_history) == 0
    assert matcher.current_gesture == "无手势"


def test_no_landmarks():
    matcher = GestureMatcher()
    gesture, states, confidence = matcher.recognize_gesture([])
    assert gesture == "无手势"


def test_swipe_detection():
    matcher = GestureMatcher()
    landmarks = _make_fist_landmarks()
    result = matcher.detect_swipe(landmarks)
    assert result == "无滑动"


def test_smoothed_gesture_output():
    matcher = GestureMatcher()
    landmarks = _make_fist_landmarks()
    gesture, finger_states, confidence, swipe = matcher.process_gesture(landmarks)
    assert isinstance(gesture, str)
    assert isinstance(finger_states, dict)
    assert isinstance(confidence, float)
    assert isinstance(swipe, str)