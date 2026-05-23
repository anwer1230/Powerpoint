"""
معالج الذكاء الاصطناعي — يعمل على Groq (سريع + مجاني)
يستخدم مكتبة groq الرسمية مع نموذج Llama 3.3 70B
"""

import os
import json
import re
from typing import List, Dict, Any

GROQ_MODEL = "llama-3.3-70b-versatile"


class AIProcessor:
    def __init__(self):
        self.groq_available = False
        self.client = None
        self._init_groq()

    def _init_groq(self):
        try:
            from groq import Groq
            api_key = os.environ.get("GROQ_API_KEY", "").strip()
            if api_key:
                self.client = Groq(api_key=api_key)
                self.groq_available = True
        except Exception as e:
            print(f"[Groq init error] {e}")

    @property
    def is_ai_available(self) -> bool:
        return self.groq_available

    # ── الدالة الرئيسية ──────────────────────────────────────────────────────
    def text_to_presentation_structure(
        self,
        text: str,
        num_slides: int = 6,
        presentation_type: str = "general",
        title_override: str = "",
        include_tables: bool = False,
        include_charts: bool = False,
        extracted_tables: List = None,
    ) -> List[Dict[str, Any]]:

        if self.groq_available:
            slides = self._process_with_groq(
                text, num_slides, presentation_type,
                include_tables, include_charts
            )
        else:
            slides = self._process_locally(
                text, num_slides, presentation_type, extracted_tables or []
            )

        if title_override and slides:
            slides[0]["title"] = title_override

        return slides

    # ── المعالجة عبر Groq ────────────────────────────────────────────────────
    def _process_with_groq(
        self, text: str, num_slides: int, ptype: str,
        include_tables: bool, include_charts: bool
    ) -> List[Dict[str, Any]]:

        type_labels = {
            "general": "عام", "business": "تجاري",
            "educational": "تعليمي", "sales": "تسويقي",
        }
        label = type_labels.get(ptype, "عام")

        extras = ""
        if include_tables:
            extras += (
                '\n- أضف شريحة جدول واحدة على الأقل بنوع "table" '
                'مع مفتاح "table_data" (مصفوفة من مصفوفات نصية)'
            )
        if include_charts:
            extras += (
                '\n- أضف شريحة رسم بياني بنوع "chart" مع مفاتيح '
                '"chart_type" (bar/pie/line) و"chart_labels" و"chart_values" (أرقام)'
            )

        system_prompt = (
            "أنت خبير محترف في إنشاء العروض التقديمية باللغة العربية. "
            "تُنتج دائماً JSON صحيحاً وكاملاً بدون أي نص إضافي."
        )

        user_prompt = f"""حلّل النص التالي وأنشئ هيكل عرض تقديمي {label} من {num_slides} شرائح.{extras}

النص:
{text[:4000]}

القواعد:
- الشريحة الأولى: نوع "title" مع عنوان رئيسي وعنوان فرعي
- الشريحة الأخيرة: نوع "conclusion" مع 3 نقاط خلاصة
- الشرائح الوسطى: نوع "bullets" مع 3-5 نقاط لكل شريحة
- كل المحتوى باللغة العربية
- أرجع JSON فقط بهذا الشكل:

[
  {{
    "title": "عنوان الشريحة",
    "subtitle": "عنوان فرعي",
    "bullets": ["نقطة 1", "نقطة 2", "نقطة 3"],
    "slide_type": "title|bullets|table|chart|conclusion",
    "table_data": [["العمود1","العمود2"],["قيمة1","قيمة2"]],
    "chart_type": "bar",
    "chart_labels": ["تسمية1","تسمية2"],
    "chart_values": [10, 20],
    "chart_title": "عنوان الرسم"
  }}
]"""

        try:
            response = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                max_tokens=3000,
                temperature=0.65,
            )
            content = response.choices[0].message.content.strip()
            match = re.search(r'\[.*\]', content, re.DOTALL)
            if match:
                slides = json.loads(match.group())
                if isinstance(slides, list) and slides:
                    return slides
        except Exception as e:
            print(f"[Groq request error] {e}")

        return self._process_locally(text, num_slides, ptype, [])

    # ── المعالجة المحلية الاحتياطية ──────────────────────────────────────────
    def _process_locally(
        self, text: str, num_slides: int, ptype: str,
        extracted_tables: List
    ) -> List[Dict[str, Any]]:

        lines = [l.strip() for l in text.split('\n') if l.strip()]
        sentences = []
        for line in lines:
            parts = re.split(r'[.،,;؛]', line)
            sentences.extend([p.strip() for p in parts if len(p.strip()) > 5])

        title = sentences[0][:70] if sentences else "العرض التقديمي"
        slides: List[Dict[str, Any]] = []

        slides.append({
            "title": title,
            "subtitle": _subtitle(ptype),
            "bullets": [],
            "slide_type": "title",
        })

        remaining = sentences[1:] if len(sentences) > 1 else ["محتوى العرض"]
        content_count = max(1, num_slides - 2)
        chunk_size = max(1, len(remaining) // max(1, content_count))
        sec_titles = _section_titles(ptype)
        tables_used = 0

        for i in range(content_count):
            chunk = remaining[i * chunk_size: (i + 1) * chunk_size]
            bullets = [b[:120] for b in chunk if b][:5]
            if not bullets:
                bullets = [f"النقطة الرئيسية {i+1}", "التفاصيل والمعلومات", "الخلاصة الجزئية"]

            slide: Dict[str, Any] = {
                "title": sec_titles[i % len(sec_titles)],
                "subtitle": "",
                "bullets": bullets,
                "slide_type": "bullets",
            }

            if (extracted_tables and tables_used < len(extracted_tables)
                    and i == content_count // 2):
                slide["slide_type"] = "table"
                slide["table_data"] = extracted_tables[tables_used]
                tables_used += 1

            slides.append(slide)

        slides.append({
            "title": "الخلاصة والتوصيات",
            "subtitle": "",
            "bullets": [
                "✅ " + (sentences[-1][:90] if sentences else "تم عرض أهم النقاط"),
                "📌 نرحب بأسئلتكم واستفساراتكم",
                "🙏 شكراً لاهتمامكم",
            ],
            "slide_type": "conclusion",
        })

        return slides[:num_slides]


def _subtitle(ptype: str) -> str:
    return {
        "business": "عرض تجاري احترافي",
        "educational": "مواد تعليمية متميزة",
        "sales": "عرض تسويقي متكامل",
        "general": "عرض تقديمي شامل",
    }.get(ptype, "عرض تقديمي")


def _section_titles(ptype: str) -> List[str]:
    return {
        "business":    ["نظرة عامة", "الأهداف الاستراتيجية", "الخطة التنفيذية", "الميزانية والموارد", "مؤشرات النجاح"],
        "educational": ["المقدمة", "المفاهيم الأساسية", "التطبيقات العملية", "الأمثلة والتدريبات", "التقييم"],
        "sales":       ["المشكلة", "الحل المقترح", "المميزات والفوائد", "الأسعار والعروض", "لماذا نحن؟"],
        "general":     ["المقدمة", "المحتوى الرئيسي", "التفاصيل", "النتائج", "التوصيات"],
    }.get(ptype, ["المقدمة", "المحتوى", "التفاصيل", "النتائج", "الخلاصة"])
