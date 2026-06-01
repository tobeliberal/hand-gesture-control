# -*- coding: utf-8 -*-
from typing import Dict, Tuple, List, Any
from collections import Counter, deque
import time
import math
from backend.config import GESTURE_CONFIG


class GestureMatcher:
    
    WRIST = 0
    THUMB_CMC = 1
    THUMB_MCP = 2
    THUMB_IP = 3
    THUMB_TIP = 4
    INDEX_MCP = 5
    INDEX_PIP = 6
    INDEX_DIP = 7
    INDEX_TIP = 8
    MIDDLE_MCP = 9
    MIDDLE_PIP = 10
    MIDDLE_DIP = 11
    MIDDLE_TIP = 12
    RING_MCP = 13
    RING_PIP = 14
    RING_DIP = 15
    RING_TIP = 16
    PINKY_MCP = 17
    PINKY_PIP = 18
    PINKY_DIP = 19
    PINKY_TIP = 20
    
    # 手势匹配规则配置：标准匹配 + 宽松匹配统一管理
    # standard: 标准手指状态匹配规则
    # relaxed: 宽松匹配规则（拇指状态可能误判时），None 表示无需宽松匹配
    # relaxed_condition: 宽松匹配的额外条件函数，None 表示无条件通过
    GESTURE_RULES: List[Dict[str, Any]] = [
        {
            'name': '手掌',
            'standard': {'thumb': True, 'index': True, 'middle': True, 'ring': True, 'pinky': True},
            'relaxed': None,
        },
        {
            'name': '摇滚',
            'standard': {'thumb': False, 'index': True, 'middle': False, 'ring': False, 'pinky': True},
            'relaxed': {'thumb': True, 'index': True, 'middle': False, 'ring': False, 'pinky': True},
        },
        {
            'name': '数字 4',
            'standard': {'thumb': False, 'index': True, 'middle': True, 'ring': True, 'pinky': True},
            'relaxed': None,
        },
        {
            'name': '数字 3',
            'standard': {'thumb': False, 'index': True, 'middle': True, 'ring': True, 'pinky': False},
            'relaxed': {'thumb': True, 'index': True, 'middle': True, 'ring': True, 'pinky': False},
        },
        {
            'name': '数字 2',
            'standard': {'thumb': False, 'index': True, 'middle': True, 'ring': False, 'pinky': False},
            'relaxed': {'thumb': True, 'index': True, 'middle': True, 'ring': False, 'pinky': False},
        },
        {
            'name': '数字 1',
            'standard': {'thumb': False, 'index': True, 'middle': False, 'ring': False, 'pinky': False},
            'relaxed': {'thumb': True, 'index': True, 'middle': False, 'ring': False, 'pinky': False},
            'relaxed_condition': '_is_not_thumb_up',
        },
    ]
    
    def __init__(self):
        self.gesture_history: List[str] = []
        self.max_history = GESTURE_CONFIG['smoothing_history_length']
        self.current_gesture = "无手势"
        self.gesture_confidence = 0.0
        
        self.swipe_positions: deque = deque(maxlen=GESTURE_CONFIG.get('swipe_track_frames', 15))
        self.swipe_cooldown = 0
        self.swipe_cooldown_max = GESTURE_CONFIG.get('swipe_cooldown_frames', 15)
        self.last_swipe = None
        
        # 缓存上一次的手指状态，用于稳定性判断
        self._last_finger_states = None
        self._stable_count = 0
    
    def _dist(self, lm1: Any, lm2: Any) -> float:
        """快速距离计算，避免 numpy 开销"""
        dx = lm1.x - lm2.x
        dy = lm1.y - lm2.y
        dz = lm1.z - lm2.z
        return math.sqrt(dx*dx + dy*dy + dz*dz)
    
    def _dist2d(self, lm1: Any, lm2: Any) -> float:
        """2D距离计算（仅xy平面）"""
        dx = lm1.x - lm2.x
        dy = lm1.y - lm2.y
        return math.sqrt(dx*dx + dy*dy)
    
    def _angle_between(self, a: Any, b: Any, c: Any) -> float:
        """计算向量 ba 和 bc 之间的角度（度）"""
        bax = a.x - b.x
        bay = a.y - b.y
        baz = a.z - b.z
        bcx = c.x - b.x
        bcy = c.y - b.y
        bcz = c.z - b.z
        
        dot = bax*bcx + bay*bcy + baz*bcz
        norm_ba = math.sqrt(bax*bax + bay*bay + baz*baz)
        norm_bc = math.sqrt(bcx*bcx + bcy*bcy + bcz*bcz)
        
        norm_product = norm_ba * norm_bc
        if norm_product < 1e-8:
            return 0.0
        
        cos_angle = max(-1.0, min(1.0, dot / norm_product))
        return math.degrees(math.acos(cos_angle))
    
    def _is_finger_extended(self, landmarks: List[Any], tip_idx: int, pip_idx: int, mcp_idx: int) -> bool:
        """
        判断四指是否伸直。
        核心判定：tip到mcp距离 / pip到mcp距离 > 阈值 → 伸直
        辅助判定：tip到wrist距离必须 > mcp到wrist距离（蜷缩时tip更靠近手腕）
        """
        tip = landmarks[tip_idx]
        pip = landmarks[pip_idx]
        mcp = landmarks[mcp_idx]
        wrist = landmarks[self.WRIST]
        
        d_tip_mcp = self._dist(tip, mcp)
        d_pip_mcp = self._dist(pip, mcp)
        
        if d_pip_mcp < 1e-6:
            return False
        
        ratio = d_tip_mcp / d_pip_mcp
        
        # 明确伸直：比率大
        if ratio > 1.2:
            # 二次验证：tip必须比MCP更远离手腕（排除蜷缩手指因z坐标导致的误判）
            d_tip_wrist = self._dist(tip, wrist)
            d_mcp_wrist = self._dist(mcp, wrist)
            if d_mcp_wrist > 1e-6 and d_tip_wrist < d_mcp_wrist * 0.95:
                # tip比MCP更靠近手腕 → 手指实际是蜷缩的
                return False
            return True
        
        return False
    
    def _is_thumb_extended(self, landmarks: List[Any]) -> bool:
        """
        判断拇指是否伸直（横向伸展）。
        核心判定：拇指尖到食指MCP的距离 vs 拇指IP到食指MCP的距离。
        伸展时 tip 远离手掌，IP 靠近手掌，所以 tip距离/IP距离 > 阈值。
        """
        thumb_tip = landmarks[self.THUMB_TIP]
        thumb_ip = landmarks[self.THUMB_IP]
        thumb_mcp = landmarks[self.THUMB_MCP]
        index_mcp = landmarks[self.INDEX_MCP]
        
        # 主判定：tip到index_mcp距离 / ip到index_mcp距离
        d_tip_to_index = self._dist(thumb_tip, index_mcp)
        d_ip_to_index = self._dist(thumb_ip, index_mcp)
        
        if d_ip_to_index > 1e-6:
            ratio = d_tip_to_index / d_ip_to_index
            # 伸展时 tip 比 ip 更远离食指根部
            if ratio > 1.15:
                return True
        
        # 辅助：拇指IP关节角度
        angle = self._angle_between(thumb_mcp, thumb_ip, thumb_tip)
        if angle > 160.0:
            # 角度接近180度说明拇指接近伸直
            d_tip_mcp = self._dist(thumb_tip, thumb_mcp)
            d_ip_mcp = self._dist(thumb_ip, thumb_mcp)
            if d_ip_mcp > 1e-6 and d_tip_mcp / d_ip_mcp > 1.1:
                return True
        
        return False
    
    def _is_thumb_up(self, landmarks: List[Any]) -> bool:
        """点赞手势：拇指向上竖起，其余四指弯曲"""
        thumb_tip = landmarks[self.THUMB_TIP]
        thumb_ip = landmarks[self.THUMB_IP]
        thumb_mcp = landmarks[self.THUMB_MCP]
        index_mcp = landmarks[self.INDEX_MCP]
        wrist = landmarks[self.WRIST]
        
        # 拇指尖必须明显高于 IP 关节（y更小=更高）
        if thumb_tip.y >= thumb_ip.y - 0.02:
            return False
        
        # 拇指尖必须明显高于 MCP
        if thumb_tip.y >= thumb_mcp.y - 0.01:
            return False
        
        # 拇指必须伸展（距离比判定）
        d_tip_index = self._dist(thumb_tip, index_mcp)
        d_ip_index = self._dist(thumb_ip, index_mcp)
        if d_ip_index > 1e-6:
            if d_tip_index / d_ip_index < 1.05:
                return False
        
        return True
    
    def _is_ok_gesture(self, landmarks: List[Any], finger_states: Dict[str, bool]) -> bool:
        """OK手势：拇指尖和食指尖形成圆圈，其余三指伸直或自然弯曲"""
        thumb_tip = landmarks[self.THUMB_TIP]
        index_tip = landmarks[self.INDEX_TIP]
        index_pip = landmarks[self.INDEX_PIP]
        
        # 拇指和食指尖距离
        dist = self._dist(thumb_tip, index_tip)
        
        # OK阈值：拇指食指尖距离要小于食指PIP到食指尖距离的一定比例
        finger_len = self._dist(index_pip, index_tip)
        if finger_len < 1e-6:
            return False
        
        # 拇指食指尖距离 < 食指长度 * 0.6
        ok_threshold = finger_len * 0.6
        if dist > ok_threshold:
            return False
        
        # 至少拇指和食指需要判定为"非完全伸展"状态（形成圆圈）
        # 如果食指完全伸直且拇指完全伸直，不太可能是OK
        if finger_states.get('index', False) and finger_states.get('thumb', False):
            # 两者都伸直但距离很近 → 可能是OK
            if dist < finger_len * 0.4:
                return True
            return False
        
        return True
    
    def recognize_gesture(self, landmarks: List[Any]) -> Tuple[str, Dict[str, bool], float]:
        if not landmarks or len(landmarks) < 21:
            return "无手势", {}, 0.0
        
        finger_states = {
            'thumb': self._is_thumb_extended(landmarks),
            'index': self._is_finger_extended(landmarks, self.INDEX_TIP, self.INDEX_PIP, self.INDEX_MCP),
            'middle': self._is_finger_extended(landmarks, self.MIDDLE_TIP, self.MIDDLE_PIP, self.MIDDLE_MCP),
            'ring': self._is_finger_extended(landmarks, self.RING_TIP, self.RING_PIP, self.RING_MCP),
            'pinky': self._is_finger_extended(landmarks, self.PINKY_TIP, self.PINKY_PIP, self.PINKY_MCP),
        }
        
        gesture = self._match_gesture(finger_states, landmarks)
        return gesture, finger_states, 1.0
    
    def _matches_rule(self, finger_states: Dict[str, bool], rule: Dict[str, bool]) -> bool:
        """检查手指状态是否匹配规则"""
        for finger, expected in rule.items():
            if finger_states.get(finger, False) != expected:
                return False
        return True
    
    def _match_by_rules(self, finger_states: Dict[str, bool], landmarks: List[Any]) -> str:
        """基于配置规则进行手势匹配（标准匹配 + 宽松匹配）"""
        for rule in self.GESTURE_RULES:
            # 首先尝试标准匹配
            if self._matches_rule(finger_states, rule['standard']):
                return rule['name']
            
            # 如果存在宽松匹配规则，尝试宽松匹配
            if rule['relaxed'] is not None and self._matches_rule(finger_states, rule['relaxed']):
                # 检查是否有额外的宽松匹配条件
                condition_name = rule.get('relaxed_condition')
                if condition_name is None:
                    return rule['name']
                # 通过方法名字符串调用条件函数，避免 lambda 引用实例方法的问题
                condition_fn = getattr(self, condition_name)
                if condition_fn(landmarks):
                    return rule['name']
        
        return "无手势"
    
    def _is_not_thumb_up(self, landmarks: List[Any]) -> bool:
        """宽松匹配辅助：拇指非向上竖起（排除点赞误判）"""
        return not self._is_thumb_up(landmarks)
    
    def _match_gesture(self, finger_states: Dict[str, bool], landmarks: List[Any]) -> str:
        # === 特殊手势优先检测 ===
        
        # OK手势：拇指和食指形成圆圈
        if self._is_ok_gesture(landmarks, finger_states):
            return "OK"
        
        # 点赞/拳头：四指全部弯曲
        if not any([finger_states['index'], finger_states['middle'],
                    finger_states['ring'], finger_states['pinky']]):
            if finger_states['thumb'] and self._is_thumb_up(landmarks):
                return "点赞"
            return "拳头"
        
        # === 基于规则的通用匹配 ===
        return self._match_by_rules(finger_states, landmarks)
    
    def _smooth_gesture(self, gesture: str) -> Tuple[str, float]:
        """平滑过滤：众数决策 + 粘滞机制"""
        self.gesture_history.append(gesture)
        
        if len(self.gesture_history) > self.max_history:
            self.gesture_history.pop(0)
        
        min_history = GESTURE_CONFIG.get('min_history_for_smoothing', 3)
        if len(self.gesture_history) < min_history:
            return gesture, 0.5
        
        counter = Counter(self.gesture_history)
        most_common, most_common_count = counter.most_common(1)[0]
        majority_ratio = most_common_count / len(self.gesture_history)
        
        # 粘滞机制：当前手势高置信度时，新手势需要更强证据
        if self.gesture_confidence >= 0.6 and most_common != self.current_gesture:
            if majority_ratio < 0.7:
                return self.current_gesture, self.gesture_confidence
        
        self.current_gesture = most_common
        return most_common, majority_ratio
    
    def detect_swipe(self, landmarks: List[Any], finger_states: Dict[str, bool] = None) -> str:
        """检测左右滑动手势"""
        if not landmarks or len(landmarks) < 21:
            return "无滑动"
        
        wrist = landmarks[self.WRIST]
        middle_mcp = landmarks[self.MIDDLE_MCP]
        palm_center_x = (wrist.x + middle_mcp.x) / 2
        current_time = time.time()
        self.swipe_positions.append((palm_center_x, current_time))
        
        if self.swipe_cooldown > 0:
            self.swipe_cooldown -= 1
            return "无滑动"
        
        if len(self.swipe_positions) < 4:
            return "无滑动"
        
        positions = list(self.swipe_positions)
        total_displacement = positions[-1][0] - positions[0][0]
        
        threshold = GESTURE_CONFIG.get('swipe_threshold', 0.08)
        
        if abs(total_displacement) > threshold:
            self.swipe_cooldown = self.swipe_cooldown_max
            self.swipe_positions.clear()
            if total_displacement > 0:
                self.last_swipe = "右翻页"
                return "右翻页"
            else:
                self.last_swipe = "左翻页"
                return "左翻页"
        
        return "无滑动"
    
    def process_gesture(self, landmarks: List[Any]) -> Tuple[str, Dict[str, bool], float, str]:
        gesture, finger_states, raw_confidence = self.recognize_gesture(landmarks)
        smoothed_gesture, smooth_confidence = self._smooth_gesture(gesture)
        self.gesture_confidence = smooth_confidence
        swipe_gesture = self.detect_swipe(landmarks, finger_states)
        return smoothed_gesture, finger_states, smooth_confidence, swipe_gesture
    
    def reset(self):
        self.gesture_history.clear()
        self.current_gesture = "无手势"
        self.gesture_confidence = 0.0
        self.swipe_positions.clear()
        self.swipe_cooldown = 0
        self.last_swipe = None
