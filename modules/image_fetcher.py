"""
جالب الصور الذكي — يستخدم Groq لاستخراج كلمات مفتاحية إنجليزية
ثم يجلب صورة مناسبة من loremflickr (مجاني، بدون مفتاح API)
"""

import os
import hashlib
import requests
from pathlib import Path
from typing import Optional

CACHE_DIR = Path("outputs/img_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

TIMEOUT = 8   # ثواني

# ── خريطة الكلمات العربية → إنجليزية ───────────────────────────────────────
_ARABIC_TO_EN = {
    # تعليم
    "تعليم": "education",        "مدرسة": "school",
    "جامعة": "university",       "طالب": "students",
    "تدريب": "training",         "تعلم": "learning",
    "مناهج": "curriculum",       "اختبار": "exam",
    # تقنية
    "تقنية": "technology",       "ذكاء اصطناعي": "artificial intelligence",
    "برمجة": "coding",           "حاسوب": "computer",
    "شبكة": "network",           "أمن": "cybersecurity",
    "بيانات": "data analytics",  "سحابة": "cloud computing",
    "هاتف": "smartphone",        "تطبيق": "mobile app",
    "ابتكار": "innovation",      "ذكاء": "artificial intelligence",
    # أعمال
    "أعمال": "business",         "شركة": "corporate office",
    "تجارة": "commerce",         "سوق": "market",
    "مبيعات": "sales",           "تسويق": "marketing",
    "إدارة": "management",       "قيادة": "leadership",
    "فريق": "team",              "اجتماع": "meeting",
    "عمل": "workplace",          "موظف": "employees",
    "استراتيجية": "strategy",    "خطة": "planning",
    "ميزانية": "finance",        "مالية": "finance",
    "استثمار": "investment",     "اقتصاد": "economy",
    "نمو": "growth chart",       "أرباح": "profit",
    # صحة
    "صحة": "healthcare",         "طب": "medicine",
    "مستشفى": "hospital",        "دواء": "pharmacy",
    "لياقة": "fitness",          "رياضة": "sports",
    # بيئة وطبيعة
    "بيئة": "environment",       "طبيعة": "nature landscape",
    "طاقة": "renewable energy",  "خضراء": "green energy",
    "ماء": "water",              "غابة": "forest",
    # مجتمع
    "مجتمع": "community",        "أسرة": "family",
    "شباب": "youth",             "ثقافة": "culture",
    "سياحة": "tourism",          "سفر": "travel",
    # مشاريع وبناء
    "بناء": "architecture",      "مشروع": "construction project",
    "تصميم": "design",           "هندسة": "engineering",
    "مدينة": "smart city",       "بنية": "infrastructure",
    # خلاصة وأهداف
    "خلاصة": "success achievement", "نتائج": "results achievement",
    "توصية": "presentation",    "هدف": "goal target",
    "مستقبل": "future vision",   "رؤية": "vision future",
    "إنجاز": "achievement",      "نجاح": "success",
}

_SLIDE_TYPE_DEFAULTS = {
    "title":      "professional presentation",
    "conclusion": "success achievement team",
    "table":      "data analytics chart",
    "chart":      "business graph analytics",
    "bullets":    "professional business",
}


def get_slide_image(
    slide_title: str,
    slide_bullets: list,
    slide_type: str = "bullets",
    groq_client=None,
) -> Optional[str]:
    """
    يجلب صورة مناسبة للشريحة.
    يعيد مسار الصورة المحلية أو None إذا فشل الجلب.
    """
    keywords = _extract_keywords(slide_title, slide_bullets, slide_type, groq_client)
    if not keywords:
        return None
    return _download_image(keywords)


def _extract_keywords(
    title: str, bullets: list, slide_type: str, groq_client
) -> str:
    """استخرج كلمات مفتاحية إنجليزية من المحتوى العربي"""

    # أولاً: جرب عبر Groq AI لدقة أعلى
    if groq_client:
        try:
            content = title + "\n" + "\n".join(bullets[:3])
            resp = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{
                    "role": "user",
                    "content": (
                        "You are a keyword extractor. "
                        "Extract 2-3 English keywords suitable for image search "
                        "from the following Arabic text. "
                        "Return ONLY the keywords separated by commas. "
                        "Focus on the main topic. No explanation.\n\n"
                        f"Arabic text:\n{content}"
                    )
                }],
                max_tokens=25,
                temperature=0.2,
            )
            kw = resp.choices[0].message.content.strip()
            kw = kw.replace("\n", ",").replace(" ", ",")
            kw = ",".join([k.strip() for k in kw.split(",") if k.strip()])
            if kw and len(kw) > 2:
                return kw
        except Exception:
            pass

    # ثانياً: خريطة الكلمات العربية
    full_text = title + " " + " ".join(bullets[:3])
    for arabic, english in _ARABIC_TO_EN.items():
        if arabic in full_text:
            return english.replace(" ", ",")

    # ثالثاً: قيمة افتراضية حسب نوع الشريحة
    return _SLIDE_TYPE_DEFAULTS.get(slide_type, "professional business")


def _download_image(keywords: str) -> Optional[str]:
    """تحميل الصورة مع تخزين مؤقت محلي"""
    safe_kw   = keywords.strip()[:80]
    cache_key = hashlib.md5(safe_kw.encode()).hexdigest()[:10]
    cache_path = CACHE_DIR / f"{cache_key}.jpg"

    if cache_path.exists() and cache_path.stat().st_size > 4000:
        return str(cache_path)

    try:
        url  = f"https://loremflickr.com/900/550/{safe_kw}"
        resp = requests.get(url, timeout=TIMEOUT, allow_redirects=True)
        if resp.status_code == 200 and len(resp.content) > 4000:
            cache_path.write_bytes(resp.content)
            return str(cache_path)
    except Exception:
        pass

    return None
