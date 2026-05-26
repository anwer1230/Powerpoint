"""
توليد الرسوم البيانية من البيانات
"""

import io
import re
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any


def create_chart_from_data(
    chart_type: str,
    labels: List[str],
    values: List[float],
    title: str = "",
    color: str = "#667eea",
) -> Optional[str]:
    """إنشاء رسم بياني وحفظه كصورة PNG"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.font_manager as fm

        plt.rcParams["font.family"] = "DejaVu Sans"
        fig, ax = plt.subplots(figsize=(8, 5))
        fig.patch.set_facecolor("#f8f9ff")
        ax.set_facecolor("#f8f9ff")

        colors_list = [
            "#667eea", "#764ba2", "#11aa55", "#e53935",
            "#ff6b35", "#00bcd4", "#ffc107", "#9c27b0",
        ]

        if chart_type == "bar":
            bars = ax.bar(labels, values, color=colors_list[: len(labels)])
            for bar, val in zip(bars, values):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + max(values) * 0.01,
                    f"{val:,.0f}",
                    ha="center",
                    va="bottom",
                    fontsize=9,
                    fontweight="bold",
                )
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)

        elif chart_type == "pie":
            wedges, texts, autotexts = ax.pie(
                values,
                labels=labels,
                autopct="%1.1f%%",
                colors=colors_list[: len(labels)],
                startangle=90,
                pctdistance=0.85,
            )
            for t in autotexts:
                t.set_fontsize(9)
                t.set_fontweight("bold")

        elif chart_type == "line":
            ax.plot(labels, values, color=color, linewidth=2.5, marker="o", markersize=7)
            ax.fill_between(range(len(labels)), values, alpha=0.15, color=color)
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)

        elif chart_type == "horizontal_bar":
            ax.barh(labels, values, color=colors_list[: len(labels)])
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)

        if title:
            ax.set_title(title, fontsize=13, fontweight="bold", pad=12)

        plt.tight_layout()

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        plt.savefig(tmp.name, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        return tmp.name

    except Exception as e:
        print(f"Chart error: {e}")
        return None


def detect_chart_request(text: str) -> Optional[Dict[str, Any]]:
    """كشف طلب رسم بياني من النص"""
    chart_keywords = {
        "bar": ["عمودي", "أعمدة", "bar chart", "مقارنة"],
        "pie": ["دائري", "pie chart", "نسب", "توزيع"],
        "line": ["خطي", "line chart", "اتجاه", "تطور"],
        "horizontal_bar": ["أفقي", "horizontal"],
    }
    text_lower = text.lower()
    for ctype, keywords in chart_keywords.items():
        for kw in keywords:
            if kw in text_lower:
                return {"type": ctype, "detected": True}
    return None


def parse_table_for_chart(table_rows: List[List[str]]) -> Optional[Dict[str, Any]]:
    """تحليل جدول لاستخراج بيانات رسم بياني"""
    if len(table_rows) < 2:
        return None
    try:
        labels = []
        values = []
        for row in table_rows[1:]:
            if len(row) >= 2:
                label = row[0].strip()
                val_str = re.sub(r"[^\d.]", "", row[1])
                if val_str:
                    labels.append(label)
                    values.append(float(val_str))
        if labels and values:
            header = table_rows[0][1] if len(table_rows[0]) > 1 else ""
            return {"labels": labels, "values": values, "title": header}
    except Exception:
        pass
    return None
