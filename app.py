"""
منشئ العروض التقديمية الذكي — الإصدار 4.0
يدعم: Word/PDF، HTML→PPTX، صفحة الغلاف، الجداول، الرسوم البيانية، الصور، مواقع التصاميم
"""

import streamlit as st
import os, sys
from pathlib import Path
from datetime import datetime

sys.path.append(os.path.dirname(__file__))

from modules.ai_processor       import AIProcessor
from modules.presentation_generator import PresentationGenerator
from modules.design_importer    import DesignImporter
from modules.design_applier     import DesignApplier
from modules.file_extractor     import extract_content
from modules.html_to_pptx       import html_to_pptx, parse_html_to_slides

st.set_page_config(
    page_title="منشئ العروض التقديمية الذكي",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ═══════════════════════════════════════════════════════════
#  CSS + PWA install script
# ═══════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap');
*               { font-family: 'Cairo', sans-serif !important; }
html,body,[class*="css"] { direction: rtl; }

/* ── رأس ── */
.main-header {
    background: linear-gradient(135deg,#667eea 0%,#764ba2 100%);
    padding: 1.6rem 2rem 1.3rem;
    border-radius: 16px; color: white; text-align: center;
    margin-bottom: 1.2rem;
    box-shadow: 0 8px 32px rgba(102,126,234,.4);
    position: relative;
}
.main-header h1 { font-size: 2rem; font-weight: 900; margin-bottom: .2rem; }
.main-header p  { font-size: .95rem; opacity: .9; }

/* زر التثبيت PWA */
.pwa-btn {
    background: rgba(255,255,255,.18);
    color: white !important;
    border: 1.5px solid rgba(255,255,255,.6) !important;
    border-radius: 25px !important;
    padding: .42rem 1.1rem !important;
    font-size: .82rem !important;
    font-weight: 700 !important;
    cursor: pointer;
    transition: all .25s;
    text-decoration: none;
    display: inline-block;
    margin: .3rem .2rem 0;
    backdrop-filter: blur(4px);
}
.pwa-btn:hover { background: rgba(255,255,255,.30); transform: translateY(-1px); }
.pwa-btn:active { transform: scale(.97); }
.pwa-header-actions {
    display: flex; justify-content: center; align-items: center;
    flex-wrap: wrap; gap: .4rem; margin-top: .7rem;
}
/* مودال تثبيت */
#pwa-modal {
    display:none; position:fixed; inset:0; z-index:9999;
    background:rgba(0,0,0,.55); backdrop-filter:blur(4px);
    justify-content:center; align-items:center;
}
#pwa-modal.show { display:flex; }
.pwa-modal-box {
    background:#fff; border-radius:20px; padding:1.8rem 1.5rem;
    max-width:360px; width:90%; text-align:center; direction:rtl;
    box-shadow:0 20px 60px rgba(0,0,0,.3);
}
.pwa-modal-box h3 { color:#667eea; font-size:1.2rem; margin-bottom:.5rem; }
.pwa-modal-box p  { color:#555; font-size:.9rem; line-height:1.7; margin:.4rem 0; }
.pwa-step { background:#f0f4ff; border-radius:10px; padding:.6rem .9rem; margin:.4rem 0; font-size:.88rem; color:#333; }
.pwa-close-btn { margin-top:1rem; background:linear-gradient(135deg,#667eea,#764ba2); color:#fff; border:none; border-radius:20px; padding:.5rem 1.5rem; cursor:pointer; font-size:.9rem; font-weight:700; }

/* ── بطاقات أقسام ── */
.section-card {
    background: white; border-radius: 14px;
    padding: 1.3rem; box-shadow: 0 4px 18px rgba(0,0,0,.07);
    margin-bottom: .9rem; border: 1px solid #eef0ff;
}
.section-title {
    font-size: 1rem; font-weight: 700; color: #667eea;
    border-bottom: 2px solid #667eea;
    padding-bottom: .35rem; margin-bottom: .8rem;
}

/* ── أزرار عامة ── */
.stButton > button {
    background: linear-gradient(135deg,#667eea 0%,#764ba2 100%) !important;
    color: white !important; font-weight: 700 !important;
    border-radius: 30px !important; border: none !important;
    padding: .55rem 1.8rem !important; font-size: .95rem !important;
    box-shadow: 0 4px 15px rgba(102,126,234,.35) !important;
    transition: all .3s !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(102,126,234,.5) !important;
}

/* ── HTML قسم ── */
.html-zone {
    background: linear-gradient(135deg,#0f0c29,#302b63,#24243e);
    border-radius: 14px; padding: 1.3rem;
    border: 1.5px solid #444; margin-bottom: .9rem;
}
.html-zone .section-title { color: #a0f0a0; border-color: #a0f0a0; }

/* ── مواقع التصاميم ── */
.site-card {
    background: white; border-radius: 14px;
    padding: 1.1rem; text-align: center;
    box-shadow: 0 4px 15px rgba(0,0,0,.08);
    border: 2px solid transparent;
    transition: all .3s; margin-bottom: .8rem;
}
.site-card:hover { border-color: #667eea; transform: translateY(-3px); }
.site-icon { font-size: 2.4rem; margin-bottom: .4rem; }
.site-name { font-weight: 700; font-size: .95rem; color: #333; }
.site-desc { font-size: .78rem; color: #888; margin-bottom: .6rem; }
.open-site-btn {
    display: inline-block;
    background: linear-gradient(135deg,#667eea,#764ba2);
    color: white !important; text-decoration: none !important;
    padding: .4rem 1.2rem; border-radius: 20px;
    font-size: .82rem; font-weight: 700;
    transition: all .25s;
}
.open-site-btn:hover { opacity: .85; }

/* ── شريحة معاينة ── */
.slide-preview {
    background: white; border-radius: 10px;
    padding: .85rem 1rem; margin-bottom: .55rem;
    border-right: 4px solid #667eea;
    box-shadow: 0 2px 8px rgba(0,0,0,.05);
}
.slide-num {
    background: #667eea; color: white; border-radius: 50%;
    width: 25px; height: 25px;
    display: inline-flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: .8rem; margin-left: .45rem;
}
.badge-tag {
    background: #eef0ff; color: #667eea;
    border-radius: 20px; padding: 1px 9px;
    font-size: .75rem; font-weight: 600; margin-right: 5px;
}
.selected-badge {
    background: linear-gradient(135deg,#667eea,#764ba2);
    color: white; padding: .3rem .9rem;
    border-radius: 20px; font-size: .85rem; display: inline-block;
}
.tip-box {
    background: linear-gradient(135deg,#f0f4ff,#e8f0fe);
    border-right: 4px solid #667eea;
    border-radius: 12px; padding: 1rem;
    font-size: .88rem; line-height: 1.85;
}
.cover-form {
    background: linear-gradient(135deg,#f0f4ff,#ede8ff);
    border-radius: 14px; padding: 1.3rem;
    border: 1.5px solid #c9d4ff; margin-bottom: .9rem;
}

[data-testid="stSidebar"] { display: none; }
@media (max-width:768px) {
    .main-header h1 { font-size: 1.45rem; }
    .pwa-btn { font-size: .7rem; padding: .3rem .7rem !important; }
    .stButton > button { width: 100%; }
}
</style>

<!-- PWA: تثبيت ومانيفست -->
<link rel="manifest" href="/static/manifest.json">
<meta name="theme-color" content="#667eea">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="عروض ذكية">
<link rel="apple-touch-icon" href="/static/icon-192.png">

<script>
// ── Service Worker ──
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/sw.js')
            .then(r => console.log('SW registered'))
            .catch(e => console.log('SW error', e));
    });
}

// ── منطق التثبيت ──
let _deferredPrompt = null;
const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
const isInApp = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone;

window.addEventListener('beforeinstallprompt', e => {
    e.preventDefault();
    _deferredPrompt = e;
});

function pwaInstall() {
    if (isInApp) {
        showModal('installed');
        return;
    }
    if (_deferredPrompt) {
        // Android / Chrome — تثبيت مباشر
        _deferredPrompt.prompt();
        _deferredPrompt.userChoice.then(choice => {
            if (choice.outcome === 'accepted') showModal('done');
            _deferredPrompt = null;
        });
    } else if (isIOS) {
        showModal('ios');
    } else {
        showModal('guide');
    }
}

function showModal(type) {
    const modal = document.getElementById('pwa-modal');
    const body  = document.getElementById('pwa-modal-body');
    const msgs = {
        ios: `<h3>📱 تثبيت على iPhone / iPad</h3>
              <div class="pwa-step">1️⃣ افتح الموقع في <strong>Safari</strong></div>
              <div class="pwa-step">2️⃣ اضغط أيقونة <strong>المشاركة</strong> 🔗 في الأسفل</div>
              <div class="pwa-step">3️⃣ اختر <strong>"إضافة إلى الشاشة الرئيسية"</strong> 📲</div>
              <div class="pwa-step">4️⃣ اضغط <strong>إضافة</strong> — التطبيق جاهز!</div>
              <p style="color:#888;font-size:.8rem;margin-top:.6rem">التطبيق سيظهر كأيقونة منفصلة بدون شريط المتصفح</p>`,
        guide: `<h3>📲 تثبيت التطبيق</h3>
                <div class="pwa-step">افتح الموقع في <strong>Chrome أو Edge</strong> على جهازك</div>
                <div class="pwa-step">ابحث عن أيقونة <strong>التثبيت ⊕</strong> في شريط العنوان</div>
                <div class="pwa-step">أو اضغط ⋮ القائمة ← <strong>"تثبيت التطبيق"</strong></div>`,
        done: `<h3>✅ تم التثبيت!</h3><p>التطبيق أُضيف إلى جهازك بنجاح 🎉</p>`,
        installed: `<h3>✅ التطبيق مثبّت بالفعل</h3><p>تجد "عروض ذكية" في شاشتك الرئيسية 📱</p>`,
    };
    body.innerHTML = msgs[type] || msgs.guide;
    modal.classList.add('show');
}

function closePwaModal() {
    document.getElementById('pwa-modal').classList.remove('show');
}

window.addEventListener('appinstalled', () => {
    console.log('PWA installed successfully');
});
</script>

<!-- مودال التثبيت -->
<div id="pwa-modal" onclick="if(event.target===this)closePwaModal()">
  <div class="pwa-modal-box">
    <div id="pwa-modal-body"></div>
    <button class="pwa-close-btn" onclick="closePwaModal()">حسناً ✓</button>
  </div>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
#  Session State
# ═══════════════════════════════════════════════════════════
for k, v in {
    "presentation_generated": False,
    "file_path": None,
    "selected_design": None,
    "slides_preview": [],
    "extracted_content": None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ═══════════════════════════════════════════════════════════
#  مواقع التصاميم
# ═══════════════════════════════════════════════════════════
DESIGN_SITES = [
    {
        "name": "Slidesgo",
        "url": "https://slidesgo.com/",
        "icon": "🎨",
        "desc": "آلاف القوالب المجانية بتصاميم احترافية",
        "color": "#00bcd4",
        "category": "شامل",
    },
    {
        "name": "SlidesCarnival",
        "url": "https://www.slidescarnival.com/",
        "icon": "🎪",
        "desc": "قوالب مجانية ملونة وإبداعية",
        "color": "#ff5722",
        "category": "إبداعي",
    },
    {
        "name": "Canva Presentations",
        "url": "https://www.canva.com/presentations/",
        "icon": "✏️",
        "desc": "تصميم عروض باستخدام Canva وتصديرها PPTX",
        "color": "#00c4cc",
        "category": "تصميم",
    },
    {
        "name": "Beautiful.ai",
        "url": "https://www.beautiful.ai/",
        "icon": "✨",
        "desc": "ذكاء اصطناعي لإنشاء عروض جميلة",
        "color": "#7c4dff",
        "category": "ذكاء اصطناعي",
    },
    {
        "name": "SlideModel",
        "url": "https://slidemodel.com/",
        "icon": "📐",
        "desc": "قوالب احترافية للأعمال والتعليم",
        "color": "#1976d2",
        "category": "أعمال",
    },
    {
        "name": "FPPT",
        "url": "https://www.free-power-point-templates.com/",
        "icon": "📂",
        "desc": "قوالب PowerPoint مجانية بالكامل",
        "color": "#388e3c",
        "category": "مجاني",
    },
    {
        "name": "SlideTeam",
        "url": "https://www.slideteam.net/",
        "icon": "🏢",
        "desc": "قوالب تجارية واحترافية عالية الجودة",
        "color": "#e65100",
        "category": "تجاري",
    },
    {
        "name": "HiSlide",
        "url": "https://hislide.io/",
        "icon": "🚀",
        "desc": "قوالب عصرية وأنيقة بأسلوب حديث",
        "color": "#6a1b9a",
        "category": "عصري",
    },
    {
        "name": "Google Slides",
        "url": "https://docs.google.com/presentation/",
        "icon": "📊",
        "desc": "إنشاء وتصدير العروض من Google Slides",
        "color": "#fbbc04",
        "category": "مجاني",
    },
]


# ═══════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════
def main():
    ai_processor = AIProcessor()
    generator    = PresentationGenerator()
    design_imp   = DesignImporter()
    design_app   = DesignApplier()

    # ── رأس الصفحة مع زر التثبيت ──
    groq_badge = (
        '<span style="background:rgba(50,220,120,.25);color:#afffcf;'
        'border:1px solid rgba(50,220,120,.5);border-radius:20px;'
        'padding:.25rem .85rem;font-size:.82rem;font-weight:700;margin-right:.5rem">'
        '🟢 Groq AI • Llama 3.3 مفعّل</span>'
        if ai_processor.is_ai_available else
        '<span style="background:rgba(255,180,0,.2);color:#ffe08a;'
        'border:1px solid rgba(255,180,0,.4);border-radius:20px;'
        'padding:.25rem .85rem;font-size:.82rem;font-weight:700;margin-right:.5rem">'
        '🟡 وضع محلي — بدون AI</span>'
    )
    st.markdown(f"""
    <div class="main-header">
        <h1>📊 منشئ العروض التقديمية الذكي</h1>
        <p>نص حر • Word / PDF • كود HTML — كلها تتحول إلى PowerPoint احترافي</p>
        <div class="pwa-header-actions">
            {groq_badge}
            <button class="pwa-btn" onclick="pwaInstall()">
                📲 تثبيت كتطبيق جوال
            </button>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs([
        "✏️ إنشاء عرض",
        "💻 HTML → PPTX",
        "🎨 مواقع التصاميم",
        "ℹ️ عن التطبيق",
    ])

    # ══════════════════════════════════════════════════════
    #  تبويب 1: إنشاء عرض (نص / ملف)
    # ══════════════════════════════════════════════════════
    with tab1:
        col_main, col_side = st.columns([2, 1], gap="large")

        with col_main:
            # مصدر المحتوى
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">📁 مصدر المحتوى</div>', unsafe_allow_html=True)

            method = st.radio("اختر طريقة الإدخال",
                              ["✍️ نص حر", "📄 رفع ملف (Word / PDF)"],
                              horizontal=True, key="input_method")

            text_content, extracted_tables, extracted_images = "", [], []

            if method == "✍️ نص حر":
                text_content = st.text_area("أدخل محتوى العرض", height=195,
                    placeholder="اكتب أو الصق المحتوى هنا...", key="text_input")
            else:
                uf = st.file_uploader("ارفع ملف Word (.docx) أو PDF (.pdf)",
                                      type=["docx","doc","pdf","txt","md"], key="file_upload")
                if uf:
                    with st.spinner("📖 جاري قراءة الملف..."):
                        try:
                            fb = uf.read()
                            ex = extract_content(fb, uf.name)
                            st.session_state.extracted_content = ex
                            text_content      = ex["full_text"]
                            extracted_tables  = ex.get("tables", [])
                            extracted_images  = ex.get("images", [])
                            c1,c2,c3 = st.columns(3)
                            c1.metric("الكلمات", f"{len(text_content.split()):,}")
                            c2.metric("الجداول", len(extracted_tables))
                            c3.metric("الصور",   len(extracted_images))
                            if extracted_tables:
                                with st.expander(f"👁️ الجداول المستخرجة ({len(extracted_tables)})"):
                                    for i,t in enumerate(extracted_tables[:3],1):
                                        st.markdown(f"**جدول {i}:**")
                                        st.table(t[:5])
                        except Exception as e:
                            st.error(f"خطأ في قراءة الملف: {e}")
            st.markdown('</div>', unsafe_allow_html=True)

            # عنوان العرض
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">🏷️ عنوان العرض</div>', unsafe_allow_html=True)
            title_override = st.text_input("عنوان العرض (اختياري)",
                placeholder="مثال: خطة التطوير الاستراتيجي 2025", key="title_override")
            st.markdown('</div>', unsafe_allow_html=True)

            # صفحة الغلاف
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">🖼️ صفحة الغلاف</div>', unsafe_allow_html=True)
            add_cover = st.checkbox("إضافة صفحة غلاف مخصصة", key="add_cover")
            cover_data = None
            if add_cover:
                st.markdown('<div class="cover-form">', unsafe_allow_html=True)
                cc1,cc2 = st.columns(2)
                with cc1:
                    ct  = st.text_input("العنوان الرئيسي *", key="ct",
                                        placeholder="تقرير الأداء السنوي")
                    cs  = st.text_input("العنوان الفرعي",    key="cs",
                                        placeholder="للربع الأول 2025")
                    co  = st.text_input("اسم المؤسسة",       key="co",
                                        placeholder="شركة التقنية المتقدمة")
                with cc2:
                    cp  = st.text_input("اسم المقدِّم",      key="cp",
                                        placeholder="أحمد محمد")
                    cd  = st.text_input("التاريخ",           key="cd",
                                        value=datetime.now().strftime("%d / %m / %Y"))
                    cl  = st.text_input("أيقونة (إيموجي)",   key="cl", value="📊")
                cn = st.text_area("ملاحظة إضافية", key="cn", height=60)
                st.markdown('</div>', unsafe_allow_html=True)
                cover_data = {
                    "title": ct or title_override or "العرض التقديمي",
                    "subtitle": cs, "organization": co,
                    "presenter": cp, "date": cd,
                    "logo": cl or "📊", "note": cn,
                }
            st.markdown('</div>', unsafe_allow_html=True)

            # ── إعدادات العرض ──
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">⚙️ إعدادات العرض</div>', unsafe_allow_html=True)
            s1, s2, s3 = st.columns(3)
            with s1:
                num_slides  = st.slider("عدد الشرائح", 3, 15, 6)
                theme_color = st.selectbox("اللون",
                    ["blue","green","red","purple"],
                    format_func=lambda x:{
                        "blue":"🔵 أزرق","green":"🟢 أخضر",
                        "red":"🔴 أحمر","purple":"🟣 بنفسجي"}[x])
            with s2:
                ptype = st.selectbox("نوع العرض",
                    ["general","business","educational","sales"],
                    format_func=lambda x:{
                        "general":"📄 عام","business":"💼 تجاري",
                        "educational":"📚 تعليمي","sales":"💰 تسويقي"}[x])
                inc_tables = st.checkbox("تضمين الجداول", value=bool(extracted_tables), key="inc_t")
            with s3:
                inc_charts = st.checkbox("رسوم بيانية", key="inc_c")
                inc_images = st.checkbox("الصور المستخرجة",
                    value=bool(extracted_images), key="inc_i",
                    disabled=not extracted_images)
            st.markdown('</div>', unsafe_allow_html=True)

            # ── إعدادات الخط والصور ──
            with st.expander("🔤 إعدادات الخط والصور الذكية", expanded=False):
                f1, f2 = st.columns(2)
                with f1:
                    font_name = st.selectbox(
                        "نوع الخط",
                        [
                            # خطوط عربية رسمية
                            "Traditional Arabic",
                            "Simplified Arabic",
                            "Arabic Typesetting",
                            "Sakkal Majalla",
                            "Dubai",
                            "Aldhabi",
                            "Amiri",
                            # خطوط عالمية شائعة
                            "Times New Roman",
                            "Arial",
                            "Tahoma",
                            "Calibri",
                            "Georgia",
                            "Verdana",
                            "Trebuchet MS",
                            "Century Gothic",
                            "Garamond",
                            "Palatino Linotype",
                            "Book Antiqua",
                            "Cambria",
                            "Constantia",
                            "Corbel",
                            "Candara",
                            "Segoe UI",
                            "Microsoft Sans Serif",
                            "Courier New",
                        ],
                        index=0,
                        help="الخط المستخدم في نصوص الشرائح"
                    )
                with f2:
                    body_font_size = st.slider(
                        "حجم خط النص", min_value=14, max_value=34,
                        value=22, step=1,
                        help="حجم نص النقاط والمحتوى (العناوين تُضبط تلقائياً)"
                    )
                    use_ai_images = st.checkbox(
                        "🖼️ صور ذكية مناسبة للمحتوى",
                        value=True,
                        help="يستخدم الذكاء الاصطناعي لاختيار صور تناسب موضوع كل شريحة"
                    )

            if st.session_state.selected_design:
                st.markdown(
                    f'🎨 التصميم: <span class="selected-badge">'
                    f'{st.session_state.selected_design["name"]}</span>',
                    unsafe_allow_html=True)
                st.markdown("")

            _,bc,_ = st.columns([1,2,1])
            with bc:
                gen_btn = st.button("🚀 إنشاء العرض الآن", use_container_width=True)

        with col_side:
            st.markdown('<div class="tip-box">', unsafe_allow_html=True)
            st.markdown("""
**💡 نصائح الاستخدام**

**رفع الملفات:**
• Word — يستخرج النص، الجداول، الصور
• PDF — يستخرج النص، الجداول، الصور

**صفحة الغلاف:**
• فعّل الخيار وأدخل البيانات
• تُضاف تلقائياً أول الشرائح

**الجداول والرسوم:**
• تُكتشف تلقائياً من الملف
• يمكن توليد رسم بياني منها

**للنتائج الأفضل:**
✔ أضف عنواناً واضحاً
✔ 6-8 شرائح هو المثالي
✔ اختر النوع المناسب للعرض
""")
            st.markdown('</div>', unsafe_allow_html=True)
            if ai_processor.is_ai_available:
                st.success("🤖 Groq AI مفعّل — تحليل ذكي بنموذج Llama 3.3")
            else:
                st.warning("⚠️ Groq غير متاح — يعمل بمعالجة محلية")

        # ── معالجة الإنشاء ──
        if gen_btn:
            if not text_content.strip():
                st.warning("⚠️ الرجاء إدخال محتوى أو رفع ملف أولاً")
            else:
                _run_generation(
                    ai_processor, generator, design_app,
                    text_content, num_slides, ptype,
                    title_override, inc_tables, inc_charts, inc_images,
                    extracted_tables, extracted_images,
                    theme_color, cover_data,
                    font_name, body_font_size, use_ai_images,
                )

    # ══════════════════════════════════════════════════════
    #  تبويب 2: HTML → PPTX
    # ══════════════════════════════════════════════════════
    with tab2:
        st.markdown("""
        <div class="html-zone">
            <div class="section-title">💻 تحويل كود HTML إلى PowerPoint</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        الصق كود HTML يحتوي على عرض تقديمي (سواء مصمم يدوياً أو مولَّد بأداة مثل
        **Reveal.js** أو **Impress.js** أو **HTML5 Slides** أو أي قالب HTML)،
        وسيقوم النظام باستخراج كل الشرائح والجداول والتنسيقات وتحويلها لملف PPTX ثابت وكامل.
        """)

        html_col, hint_col = st.columns([3, 1], gap="large")

        with html_col:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">📋 كود HTML</div>', unsafe_allow_html=True)

            html_code = st.text_area(
                "الصق كود HTML هنا",
                height=380,
                placeholder="""<!-- مثال بسيط -->
<!DOCTYPE html>
<html>
<body>
  <section style="background:#667eea;color:white">
    <h1>عنوان العرض الرئيسي</h1>
    <h2>العنوان الفرعي</h2>
  </section>

  <section>
    <h2>النقاط الرئيسية</h2>
    <ul>
      <li>النقطة الأولى المهمة</li>
      <li>النقطة الثانية</li>
      <li>النقطة الثالثة</li>
    </ul>
  </section>

  <section>
    <h2>جدول البيانات</h2>
    <table>
      <tr><th>العنصر</th><th>القيمة</th></tr>
      <tr><td>المبيعات</td><td>500,000</td></tr>
      <tr><td>الأرباح</td><td>120,000</td></tr>
    </table>
  </section>
</body>
</html>""",
                key="html_input",
            )

            html_title = st.text_input(
                "عنوان اختياري يُضاف لأول شريحة",
                placeholder="مثال: عرض المشروع الاستراتيجي",
                key="html_title",
            )
            st.markdown('</div>', unsafe_allow_html=True)

            hc1, hc2, hc3 = st.columns([1, 2, 1])
            with hc2:
                html_btn = st.button("⚡ تحويل HTML إلى PowerPoint", use_container_width=True)

        with hint_col:
            st.markdown('<div class="tip-box">', unsafe_allow_html=True)
            st.markdown("""
**🧩 ما يُستخرج تلقائياً:**

📌 **الشرائح:**
`<section>` أو `<div class="slide">`
أو `<article>` أو تقسيم عبر `<h2>`

🎨 **التنسيقات:**
• ألوان الخلفية من `style="background:..."`
• ألوان النص من `style="color:..."`
• متغيرات CSS من `:root { --color: ... }`

📋 **المحتوى:**
• عناوين `h1` → `h4`
• قوائم نقطية `<ul><li>`
• فقرات `<p>`
• جداول `<table>`

⚡ **قوالب HTML مدعومة:**
• Reveal.js
• Impress.js
• HTML5 Slides
• أي HTML مخصص
""")
            st.markdown('</div>', unsafe_allow_html=True)

        # معاينة الشرائح قبل التحويل
        if html_code.strip():
            try:
                preview_slides = parse_html_to_slides(html_code)
                st.info(f"✅ تم اكتشاف **{len(preview_slides)} شريحة** في الكود")
            except Exception:
                pass

        if html_btn:
            if not html_code.strip():
                st.warning("⚠️ الرجاء لصق كود HTML أولاً")
            else:
                with st.spinner("⚡ جاري تحليل HTML وبناء العرض..."):
                    try:
                        out_file = html_to_pptx(html_code, override_title=html_title)
                        st.success("🎉 تم التحويل بنجاح!")

                        slides_info = parse_html_to_slides(html_code)
                        c1,c2,c3 = st.columns(3)
                        c1.metric("عدد الشرائح", len(slides_info))
                        tables_n = sum(1 for s in slides_info if s.get("table_data"))
                        c2.metric("الجداول", tables_n)
                        colored = sum(1 for s in slides_info if s.get("bg_color"))
                        c3.metric("شرائح ملوّنة", colored)

                        with open(out_file, "rb") as f:
                            fname = f"html_presentation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx"
                            st.download_button(
                                "📥 تنزيل العرض (PowerPoint .pptx)",
                                data=f, file_name=fname,
                                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                use_container_width=True,
                            )

                        st.markdown("### 📋 الشرائح المُستخرجة")
                        type_icons = {"title":"🏠","bullets":"📌","table":"📊","chart":"📈","conclusion":"🏁"}
                        for i, sl in enumerate(slides_info, 1):
                            stype = sl.get("slide_type","bullets")
                            icon  = type_icons.get(stype,"📌")
                            bg_badge = ""
                            if sl.get("bg_color"):
                                h = "#{:02x}{:02x}{:02x}".format(*sl["bg_color"])
                                bg_badge = f'<span style="background:{h};color:white;border-radius:20px;padding:1px 8px;font-size:.73rem;margin-right:4px">{h}</span>'
                            bullets_html = "".join(
                                f'<div style="color:#666;font-size:.86rem;padding:1px 0">◆ {b}</div>'
                                for b in sl.get("bullets",[])[:2]
                            )
                            st.markdown(
                                f'<div class="slide-preview">'
                                f'<span class="slide-num">{i}</span>'
                                f'<strong>{icon} {sl.get("title") or f"شريحة {i}"}</strong>'
                                f'<span class="badge-tag">{stype}</span>{bg_badge}'
                                f'{bullets_html}'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                    except Exception as e:
                        st.error(f"❌ خطأ في التحويل: {e}")
                        import traceback
                        st.code(traceback.format_exc(), language="python")

    # ══════════════════════════════════════════════════════
    #  تبويب 3: مواقع التصاميم
    # ══════════════════════════════════════════════════════
    with tab3:
        st.markdown("### 🌐 تصفح مواقع التصاميم")

        st.markdown("""
        <div style="background:linear-gradient(135deg,#e8f4ff,#f0e8ff);
                    border-radius:14px;padding:1.1rem;margin-bottom:1.2rem;
                    border:1.5px solid #c9d4ff">
        <strong>📌 كيف تستخدم هذه المواقع؟</strong><br>
        1️⃣ اضغط <strong>"فتح الموقع"</strong> ليُفتح في نافذة جديدة<br>
        2️⃣ تصفح القوالب واختر ما يعجبك<br>
        3️⃣ حمّل القالب كملف <strong>.pptx</strong><br>
        4️⃣ ارجع هنا وارفعه في <strong>"رفع تصميم خاص"</strong> في الأسفل ✅
        </div>
        """, unsafe_allow_html=True)

        # فلترة
        filter_col, _ = st.columns([1, 2])
        with filter_col:
            categories = ["الكل"] + list({s["category"] for s in DESIGN_SITES})
            cat_filter = st.selectbox("تصفية حسب النوع", categories, key="cat_filter")

        sites = DESIGN_SITES if cat_filter == "الكل" else [
            s for s in DESIGN_SITES if s["category"] == cat_filter]

        # عرض المواقع
        cols = st.columns(3)
        for idx, site in enumerate(sites):
            with cols[idx % 3]:
                st.markdown(
                    f"""<div class="site-card">
                    <div class="site-icon">{site['icon']}</div>
                    <div class="site-name">{site['name']}</div>
                    <div class="site-desc">{site['desc']}</div>
                    <span class="badge-tag">{site['category']}</span>
                    </div>""",
                    unsafe_allow_html=True,
                )
                st.link_button(
                    f"🌐 فتح {site['name']}",
                    site["url"],
                    use_container_width=True,
                )

        st.markdown("---")

        # رفع قالب محمّل
        st.markdown("### 📤 رفع قالب محمّل من أحد المواقع")
        st.markdown("بعد تحميل القالب من أي موقع، ارفعه هنا وسيُطبَّق على العروض القادمة:")

        up_col, info_col = st.columns([2, 1])
        with up_col:
            uploaded_ppt = st.file_uploader(
                "ارفع ملف PowerPoint (.pptx)",
                type=["pptx"], key="ppt_upload",
            )
            if uploaded_ppt:
                design = design_imp.upload_custom_design(uploaded_ppt)
                if design:
                    st.session_state.selected_design = design
                    st.success(f"✅ تم رفع القالب: **{design['name']}** — سيُستخدم في العروض القادمة")

        with info_col:
            if st.session_state.selected_design:
                st.markdown(
                    f'<div style="padding:1rem;background:#f0f4ff;border-radius:12px;text-align:center">'
                    f'<div style="font-size:2rem">✅</div>'
                    f'<div style="font-weight:700">القالب المختار:</div>'
                    f'<span class="selected-badge">{st.session_state.selected_design["name"]}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if st.button("❌ إلغاء القالب"):
                    st.session_state.selected_design = None
                    st.rerun()

        # قوالب مدمجة مباشرة
        st.markdown("---")
        st.markdown("### 🎨 أو اختر من القوالب المدمجة")
        builtin_designs = design_imp.get_all_designs()
        bc3 = st.columns(3)
        for idx, d in enumerate(builtin_designs):
            with bc3[idx % 3]:
                st.markdown(
                    f'<div class="site-card">'
                    f'<div class="site-icon">🎨</div>'
                    f'<div class="site-name">{d["name"]}</div>'
                    f'<div class="site-desc">{d["category"]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if st.button("اختر", key=f"bd_{d['id']}", use_container_width=True):
                    st.session_state.selected_design = d
                    st.success(f"✅ تم اختيار: {d['name']}")
                    st.rerun()

    # ══════════════════════════════════════════════════════
    #  تبويب 4: عن التطبيق
    # ══════════════════════════════════════════════════════
    with tab4:
        st.markdown("### ℹ️ عن التطبيق")
        fc = st.columns(4)
        for col, icon, lbl in [
            (fc[0],"📄","Word & PDF"),
            (fc[1],"💻","HTML → PPTX"),
            (fc[2],"🖼️","صفحة الغلاف"),
            (fc[3],"📊","جداول ورسوم"),
        ]:
            with col:
                st.markdown(
                    f'<div style="background:white;border-radius:12px;padding:1.1rem;'
                    f'text-align:center;box-shadow:0 4px 15px rgba(0,0,0,.06)">'
                    f'<div style="font-size:2rem">{icon}</div>'
                    f'<div style="font-weight:700;font-size:.88rem;margin-top:.3rem">{lbl}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        st.markdown("""
---
**منشئ العروض التقديمية الذكي** — الإصدار 4.0

**الميزات الكاملة:**
- 📄 رفع Word/PDF واستخراج النص والجداول والصور تلقائياً
- 💻 تحويل كود HTML كامل (مع تنسيقات وألوان CSS) إلى PPTX
- 🖼️ صفحة غلاف احترافية قابلة للتخصيص الكامل
- 📊 شرائح جداول منسقة مع تلوين الرأس والتدرج
- 📈 رسوم بيانية (أعمدة، دائري، خطي) من البيانات
- 🌐 تصفح 9 مواقع تصاميم احترافية مباشرة
- 📲 قابل للتثبيت على الجوال كـ PWA

**التقنيات المستخدمة:**
- Python + Streamlit + python-pptx
- BeautifulSoup + lxml (تحليل HTML)
- python-docx + pdfplumber (قراءة الملفات)
- matplotlib (الرسوم البيانية)
- OpenAI API (اختياري)
""")


# ══════════════════════════════════════════════════════
#  دالة مساعدة: تشغيل إنشاء العرض
# ══════════════════════════════════════════════════════
def _run_generation(
    ai_processor, generator, design_app,
    text_content, num_slides, ptype,
    title_override, inc_tables, inc_charts, inc_images,
    extracted_tables, extracted_images,
    theme_color, cover_data,
    font_name="Traditional Arabic", body_font_size=22,
    use_ai_images=False,
):
    try:
        prog = st.progress(0)
        status = st.empty()

        status.markdown("📝 **جاري تحليل المحتوى...**")
        slides = ai_processor.text_to_presentation_structure(
            text=text_content, num_slides=num_slides,
            presentation_type=ptype, title_override=title_override,
            include_tables=inc_tables, include_charts=inc_charts,
            extracted_tables=extracted_tables if inc_tables else [],
        )
        prog.progress(30)

        # إدراج جداول مستخرجة
        if inc_tables and extracted_tables:
            has_tbl = any(s.get("slide_type") == "table" for s in slides)
            if not has_tbl:
                for i, tbl in enumerate(extracted_tables[:2]):
                    slides.insert(
                        min(2 + i, len(slides) - 1),
                        {"title": f"جدول البيانات {i+1}", "slide_type": "table",
                         "table_data": tbl, "bullets": []},
                    )

        # إدراج رسم بياني
        if inc_charts and extracted_tables:
            from modules.chart_generator import parse_table_for_chart
            has_ch = any(s.get("slide_type") == "chart" for s in slides)
            if not has_ch:
                for tbl in extracted_tables:
                    info = parse_table_for_chart(tbl)
                    if info:
                        slides.insert(
                            min(3, len(slides) - 1),
                            {"title": "تحليل البيانات", "slide_type": "chart",
                             "chart_type": "bar",
                             "chart_labels": info["labels"],
                             "chart_values": info["values"],
                             "chart_title": info.get("title",""), "bullets": []},
                        )
                        break

        prog.progress(55)
        if use_ai_images:
            status.markdown("🖼️ **جاري جلب الصور الذكية المناسبة...**")
        else:
            status.markdown("🎨 **جاري تصميم الشرائح...**")

        imgs = extracted_images if inc_images else []
        groq_client = ai_processor.client if ai_processor.is_ai_available else None
        out  = generator.create_presentation(
            slides_data=slides, theme_color=theme_color,
            cover_data=cover_data, extracted_images=imgs,
            font_name=font_name, body_font_size=body_font_size,
            ai_images=use_ai_images, groq_client=groq_client,
        )
        prog.progress(80)

        if st.session_state.selected_design:
            status.markdown("✨ **تطبيق التصميم المختار...**")
            out = design_app.apply_design_to_presentation(
                out, st.session_state.selected_design, slides)

        prog.progress(100)
        status.markdown("✅ **تم الإنشاء بنجاح!**")
        st.session_state.presentation_generated = True
        st.session_state.file_path = out
        st.session_state.slides_preview = slides

        st.success("🎉 عرضك جاهز!")
        with open(out, "rb") as f:
            fname = f"عرض_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx"
            st.download_button(
                "📥 تنزيل العرض (PowerPoint .pptx)",
                data=f, file_name=fname,
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                use_container_width=True,
            )

        # معاينة الشرائح
        st.markdown("---")
        st.markdown("### 📋 معاينة الشرائح")
        if cover_data:
            st.markdown(
                f'<div class="slide-preview">'
                f'<span class="slide-num">🖼</span>'
                f'<strong>صفحة الغلاف</strong> — {cover_data.get("title","")}'
                f'<span class="badge-tag">غلاف</span></div>',
                unsafe_allow_html=True,
            )
        type_icons  = {"title":"🏠","bullets":"📌","table":"📊","chart":"📈","conclusion":"🏁"}
        type_labels = {"title":"عنوان","bullets":"محتوى","table":"جدول","chart":"رسم","conclusion":"خلاصة"}
        for i, sl in enumerate(slides, 1):
            stype = sl.get("slide_type","bullets")
            icon  = type_icons.get(stype,"📌")
            lbl   = type_labels.get(stype,"محتوى")
            bhtml = "".join(
                f'<div style="color:#666;font-size:.86rem">◆ {b}</div>'
                for b in sl.get("bullets",[])[:2]
            )
            extra = ""
            if stype == "table":
                extra = f'<div style="color:#667eea;font-size:.83rem">📊 {len(sl.get("table_data",[]))} صفوف</div>'
            elif stype == "chart":
                extra = f'<div style="color:#667eea;font-size:.83rem">📈 رسم {sl.get("chart_type","bar")}</div>'
            st.markdown(
                f'<div class="slide-preview">'
                f'<span class="slide-num">{i}</span>'
                f'<strong>{icon} {sl.get("title","")}</strong>'
                f'<span class="badge-tag">{lbl}</span>'
                f'{bhtml}{extra}</div>',
                unsafe_allow_html=True,
            )
    except Exception as e:
        st.error(f"❌ خطأ: {e}")
        import traceback
        st.code(traceback.format_exc(), language="python")


if __name__ == "__main__":
    main()
