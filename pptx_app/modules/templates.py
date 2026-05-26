"""
قوالب التصميم للعروض التقديمية
"""

from typing import Dict, Tuple


THEMES: Dict[str, Dict] = {
    "blue": {
        "name": "أزرق احترافي",
        "primary": (0x66, 0x7E, 0xEA),
        "secondary": (0x76, 0x4B, 0xA2),
        "accent": (0xFF, 0xFF, 0xFF),
        "text_dark": (0x1A, 0x1A, 0x2E),
        "text_light": (0xFF, 0xFF, 0xFF),
        "bg": (0xF5, 0xF7, 0xFF),
    },
    "green": {
        "name": "أخضر طبيعي",
        "primary": (0x11, 0x99, 0x55),
        "secondary": (0x00, 0x7A, 0x3D),
        "accent": (0xFF, 0xFF, 0xFF),
        "text_dark": (0x1A, 0x2E, 0x1A),
        "text_light": (0xFF, 0xFF, 0xFF),
        "bg": (0xF0, 0xFB, 0xF4),
    },
    "red": {
        "name": "أحمر حيوي",
        "primary": (0xE5, 0x39, 0x35),
        "secondary": (0xB7, 0x1C, 0x1C),
        "accent": (0xFF, 0xCC, 0x02),
        "text_dark": (0x2E, 0x1A, 0x1A),
        "text_light": (0xFF, 0xFF, 0xFF),
        "bg": (0xFD, 0xF2, 0xF2),
    },
    "purple": {
        "name": "بنفسجي ملكي",
        "primary": (0x6A, 0x1B, 0x9A),
        "secondary": (0x4A, 0x14, 0x8C),
        "accent": (0xFF, 0xD7, 0x00),
        "text_dark": (0x1A, 0x1A, 0x2E),
        "text_light": (0xFF, 0xFF, 0xFF),
        "bg": (0xF8, 0xF0, 0xFF),
    },
}


class ProfessionalTemplates:
    def get_theme(self, color: str) -> Dict:
        return THEMES.get(color, THEMES["blue"])

    def list_themes(self):
        return [{"key": k, "name": v["name"]} for k, v in THEMES.items()]
