"""
تطبيق التصاميم على العروض التقديمية
"""

from typing import Dict, Any, List
from modules.presentation_generator import PresentationGenerator


class DesignApplier:
    def __init__(self):
        self.generator = PresentationGenerator()

    def apply_design_to_presentation(
        self,
        presentation_path: str,
        design: Dict[str, Any],
        slides_data: List[Dict[str, Any]],
    ) -> str:
        theme_color = design.get("theme_color", "blue")
        return self.generator.create_presentation(slides_data, theme_color=theme_color)
