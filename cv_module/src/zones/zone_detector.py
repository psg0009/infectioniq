"""Zone Detection for OR Spatial Awareness"""
import cv2
import numpy as np
from typing import Tuple, Dict
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class Zone(Enum):
    DOOR = "DOOR"
    SANITIZER = "SANITIZER"
    NON_STERILE = "NON_STERILE"
    STERILE = "STERILE"
    CRITICAL = "CRITICAL"

class ZoneDetector:
    """Detects which zone a point is in based on configured polygons"""
    
    def __init__(self, frame_width: int, frame_height: int):
        self.frame_width = frame_width
        self.frame_height = frame_height
        
        # Default zones (normalized 0-1)
        self.zones = {
            Zone.DOOR: np.array([[0.4, 0.85], [0.6, 0.85], [0.6, 1.0], [0.4, 1.0]]),
            Zone.SANITIZER: np.array([[0.7, 0.8], [0.9, 0.8], [0.9, 1.0], [0.7, 1.0]]),
            Zone.NON_STERILE: np.array([[0.0, 0.6], [1.0, 0.6], [1.0, 1.0], [0.0, 1.0]]),
            Zone.STERILE: np.array([[0.1, 0.15], [0.9, 0.15], [0.9, 0.6], [0.1, 0.6]]),
            Zone.CRITICAL: np.array([[0.25, 0.2], [0.75, 0.2], [0.75, 0.5], [0.25, 0.5]])
        }
        
        self.zone_risk = {
            Zone.DOOR: 1, Zone.SANITIZER: 0, Zone.NON_STERILE: 3,
            Zone.STERILE: 7, Zone.CRITICAL: 10
        }
    
    def _point_in_polygon(self, point: Tuple[float, float], polygon: np.ndarray) -> bool:
        x, y = point
        n = len(polygon)
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = polygon[i]
            xj, yj = polygon[j]
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside
    
    def get_zone(self, point: Tuple[float, float]) -> Zone:
        """Get zone for normalized point (0-1)"""
        for zone in [Zone.CRITICAL, Zone.STERILE, Zone.SANITIZER, Zone.DOOR, Zone.NON_STERILE]:
            if self._point_in_polygon(point, self.zones[zone]):
                return zone
        return Zone.NON_STERILE
    
    def get_zone_from_pixel(self, pixel: Tuple[int, int]) -> Zone:
        normalized = (pixel[0] / self.frame_width, pixel[1] / self.frame_height)
        return self.get_zone(normalized)
    
    def draw_zones(self, frame: np.ndarray) -> np.ndarray:
        overlay = frame.copy()
        colors = {
            Zone.CRITICAL: (0, 0, 255), Zone.STERILE: (0, 255, 255),
            Zone.NON_STERILE: (0, 255, 0), Zone.SANITIZER: (255, 0, 255),
            Zone.DOOR: (255, 255, 0)
        }
        for zone, polygon in self.zones.items():
            pts = (polygon * np.array([self.frame_width, self.frame_height])).astype(np.int32)
            cv2.polylines(overlay, [pts], True, colors[zone], 2)
            cv2.fillPoly(overlay, [pts], colors[zone])
        return cv2.addWeighted(frame, 0.7, overlay, 0.3, 0)
