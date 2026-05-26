"""
استيراد التصاميم من مصادر مختلفة
"""

import os
import tempfile
from typing import List, Dict, Any, Optional


BUILTIN_DESIGNS: List[Dict[str, Any]] = [
    {
        "id": "modern_blue",
        "name": "الأزرق العصري",
        "category": "أعمال",
        "source": "مدمج",
        "thumbnail": "https://via.placeholder.com/300x200/667eea/ffffff?text=Modern+Blue",
        "theme_color": "blue",
        "colors": {"primary": "#667eea", "secondary": "#764ba2"},
    },
    {
        "id": "nature_green",
        "name": "الأخضر الطبيعي",
        "category": "تعليمي",
        "source": "مدمج",
        "thumbnail": "https://via.placeholder.com/300x200/119955/ffffff?text=Nature+Green",
        "theme_color": "green",
        "colors": {"primary": "#119955", "secondary": "#007a3d"},
    },
    {
        "id": "bold_red",
        "name": "الأحمر الجريء",
        "category": "تسويق",
        "source": "مدمج",
        "thumbnail": "https://via.placeholder.com/300x200/e53935/ffffff?text=Bold+Red",
        "theme_color": "red",
        "colors": {"primary": "#e53935", "secondary": "#b71c1c"},
    },
    {
        "id": "royal_purple",
        "name": "البنفسجي الملكي",
        "category": "فاخر",
        "source": "مدمج",
        "thumbnail": "https://via.placeholder.com/300x200/6a1b9a/ffffff?text=Royal+Purple",
        "theme_color": "purple",
        "colors": {"primary": "#6a1b9a", "secondary": "#4a148c"},
    },
    {
        "id": "midnight",
        "name": "منتصف الليل",
        "category": "أعمال",
        "source": "مدمج",
        "thumbnail": "https://via.placeholder.com/300x200/1a1a2e/ffffff?text=Midnight",
        "theme_color": "blue",
        "colors": {"primary": "#1a1a2e", "secondary": "#16213e"},
    },
    {
        "id": "sunrise",
        "name": "الشروق",
        "category": "إبداعي",
        "source": "مدمج",
        "thumbnail": "https://via.placeholder.com/300x200/ff6b35/ffffff?text=Sunrise",
        "theme_color": "red",
        "colors": {"primary": "#ff6b35", "secondary": "#f7c59f"},
    },
]


class DesignImporter:
    def search_designs(self, keyword: str, category: str = "all") -> List[Dict[str, Any]]:
        keyword = keyword.lower()
        results = []
        for d in BUILTIN_DESIGNS:
            if (keyword in d["name"].lower() or
                    keyword in d["category"].lower() or
                    keyword in d["source"].lower()):
                if category == "all" or d["category"] == category:
                    results.append(d)
        if not results:
            results = BUILTIN_DESIGNS[:4]
        return results

    def get_all_designs(self) -> List[Dict[str, Any]]:
        return BUILTIN_DESIGNS

    def upload_custom_design(self, uploaded_file) -> Optional[Dict[str, Any]]:
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pptx")
            tmp.write(uploaded_file.read())
            tmp.close()
            return {
                "id": "custom_upload",
                "name": uploaded_file.name,
                "category": "مخصص",
                "source": "رفع مستخدم",
                "thumbnail": "https://via.placeholder.com/300x200/888888/ffffff?text=Custom",
                "theme_color": "blue",
                "file_path": tmp.name,
                "colors": {"primary": "#667eea", "secondary": "#764ba2"},
            }
        except Exception:
            return None
