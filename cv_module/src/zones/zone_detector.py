"""Zone Detection for OR Spatial Awareness"""
import cv2
import numpy as np
from typing import Tuple, Dict
import logging

from src.utils.types import Zone
from config import DEFAULT_ZONES, ZONE_RISK_LEVELS

logger = logging.getLogger(__name__)

class ZoneDetector:
    """Detects which zone a point is in based on configured polygons"""
    
    def __init__(self, frame_width: int, frame_height: int):
        self.frame_width = frame_width
        self.frame_height = frame_height
        
        # Default zones (normalized 0-1) from config
        self.zones = {
            Zone[name]: np.array(coords)
            for name, coords in DEFAULT_ZONES.items()
        }

        self.zone_risk = {
            Zone[name]: level
            for name, level in ZONE_RISK_LEVELS.items()
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
