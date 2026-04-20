"""
app.py — Джарвис v3.0
Полностью переписан: история чатов, PDF, Vision, мобильный UX.
"""
import os
import io
import base64
import uuid
import json
import datetime
from pathlib import Path
import streamlit as st
from groq import Groq
# ── Загрузка .env (локально) ──────────────────────────────────
try:
from dotenv import load_dotenv
load_dotenv()
except ImportError:
pass
# ═════════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ
# ═════════════════════════════════════════════════════════════
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
TEXT_MODEL = "llama-3.3-70b-versatile"
TEXT_FAST = "llama-3.1-8b-instant"
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
VISION_FALLBACK = "llama-3.2-11b-vision-preview"
MAX_CONTEXT = 20
MAX_TOKENS = 1500
TEMPERATURE = 0.80
APP_TITLE = "Jarvis"
APP_ICON = " "
VERSION = "3.0"
BOT_NAME = "Джарвис"
OWNER_NAME = "Сардарбека Курбаналиева"
SYSTEM_PROMPT = f"""Ты — {BOT_NAME}, передовой персональный ИИ-ассистент {OWNER_NAME}.
Твои принципы:
• Профессионализм и точность — отвечай по делу, без лишней воды.
• Экспертиза — глубокие знания в программировании, архитектуре систем, стратегии и анализе.
• Прямота — называй вещи своими именами, предлагай реальные решения.
• Обращайся к пользователю «сэр» в ключевых моментах.
Ты умеешь:
• Писать и ревьюить код на любом языке
• Анализировать изображения и документы
• Разрабатывать стратегии и планы
• Объяснять сложные концепции просто
Тон: уверенный, умный, лаконичный."""
SUGGEST_CARDS = [
(" Напиши код", "FastAPI + JWT авторизация"),
(" Объясни просто", "квантовые вычисления за 2 минуты"),
(" Стратегия", "план развития на 90 дней"),
(" Переведи текст", "на любой язык мира"),
]
CHIPS = [
(" Идея", "Предложи 3 нестандартные идеи для стартапа в 2025 году."),
(" Код", "Покажи пример чистого кода на Python с типизацией."),
(" Итоги", "Сделай структурированное резюме нашего разговора."),
(" Очистить", "__clear__"),
]
MIME_MAP = {
"jpg": "image/jpeg", "jpeg": "image/jpeg",
"png": "image/png", "webp": "image/webp", "gif": "image/gif",
}
HISTORY_FILE = Path("chat_history.json")
# ═════════════════════════════════════════════════════════════
# ИСТОРИЯ ЧАТОВ — файловое хранилище
# ═════════════════════════════════════════════════════════════
def load_history() -> dict:
"""Загружает все сессии из JSON-файла."""
if HISTORY_FILE.exists():
try:
return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
except Exception:
return {}
return {}
def save_history(history: dict) -> None:
HISTORY_FILE.write_text(
json.dumps(history, ensure_ascii=False, indent=2),
encoding="utf-8",
)
def new_chat_id() -> str:
return str(uuid.uuid4())[:8]
def chat_title(messages: list) -> str:
"""Первые слова первого сообщения пользователя."""
for m in messages:
if m["role"] == "user":
text = m["content"]
# убираем [Файл: ...] аннотации
if text.startswith("["):
text = text.split("]")[-1].strip()
return text[:38] + ("…" if len(text) > 38 else "")
return "Новый чат"
def save_current_chat():
"""Сохраняет текущую сессию в историю."""
msgs = st.session_state.get("messages", [])
if not msgs:
return
cid = st.session_state.get("chat_id")
if not cid:
return
history = load_history()
history[cid] = {
"title": chat_title(msgs),
"messages": msgs,
"ts": datetime.datetime.now().isoformat(timespec="minutes"),
}
save_history(history)
# ═════════════════════════════════════════════════════════════
# GROQ
# ═════════════════════════════════════════════════════════════
@st.cache_resource
def get_groq() -> Groq:
if not GROQ_API_KEY:
st.error(
" **GROQ_API_KEY не задан.**\n\n"
"• Replit/Render: Secrets → GROQ_API_KEY\n"
"• ПК: создай файл `.env` с GROQ_API_KEY=gsk_...\n"
"• Получить бесплатно: https://console.groq.com"
)
st.stop()
return Groq(api_key=GROQ_API_KEY)
def ask_jarvis(
messages: list,
img_b64: str = None,
img_mime: str = None,
) -> str:
client = get_groq()
context = [{"role": "system", "content": SYSTEM_PROMPT}]
context += messages[-MAX_CONTEXT:]
# ── Vision запрос ──
if img_b64:
last = context[-1]
context[-1] = {
"role": "user",
"content": [
{"type": "text",
"text": last.get("content") or "Подробно опиши что изображено на фото."},
{"type": "image_url",
"image_url": {"url": f"data:{img_mime};base64,{img_b64}"}},
],
}
for model in [VISION_MODEL, VISION_FALLBACK]:
try:
resp = client.chat.completions.create(
model=model,
messages=context,
max_tokens=MAX_TOKENS,
temperature=TEMPERATURE,
)
return resp.choices[0].message.content
except Exception:
continue
return " Vision-модели временно недоступны. Опишите изображение текстом, сэр."
# ── Текстовый запрос ──
for model in [TEXT_MODEL, TEXT_FAST]:
try:
resp = client.chat.completions.create(
model=model,
messages=context,
max_tokens=MAX_TOKENS,
temperature=TEMPERATURE,
)
return resp.choices[0].message.content
except Exception:
continue
return " Groq API временно недоступен. Повторите запрос через несколько секунд, сэр."
# ═════════════════════════════════════════════════════════════
# РАБОТА С ФАЙЛАМИ
# ═════════════════════════════════════════════════════════════
def extract_pdf_text(file_bytes: bytes) -> str:
"""Извлекает текст из PDF через pypdf."""
try:
from pypdf import PdfReader
reader = PdfReader(io.BytesIO(file_bytes))
pages = []
for i, page in enumerate(reader.pages[:30]): # макс 30 страниц
text = page.extract_text() or ""
if text.strip():
pages.append(f"[Стр. {i+1}]\n{text.strip()}")
if not pages:
return "[PDF не содержит извлекаемого текста — возможно, это сканированный total = len(reader.pages)
result = "\n\n".join(pages)
if total > 30:
result += f"\n\n… [показаны первые 30 из {total} страниц]"
return result
except Exception as e:
return f"[Ошибка чтения PDF: {e}]"
докуме
def store_image(file) -> None:
data = file.read()
ext = file.name.rsplit(".", 1)[-1].lower()
mime = MIME_MAP.get(ext, "image/jpeg")
st.session_state["pending_img"] = {
"b64": base64.b64encode(data).decode(),
"mime": mime,
"name": file.name,
}
def store_pdf(file) -> None:
data = file.read()
text = extract_pdf_text(data)
st.session_state["pending_doc"] = {
"name": file.name,
"text": text,
}
# ═════════════════════════════════════════════════════════════
# ИНИЦИАЛИЗАЦИЯ СЕССИИ
# ═════════════════════════════════════════════════════════════
def init_session():
defaults = {
"messages": [],
"pending_img": None,
"pending_doc": None,
"chat_id": new_chat_id(),
"theme": "dark",
"_inject": None,
"search_query": "",
}
for k, v in defaults.items():
if k not in st.session_state:
st.session_state[k] = v
# ═════════════════════════════════════════════════════════════
# CSS / JS
# ═════════════════════════════════════════════════════════════
def load_css() -> str:
css_path = Path(__file__).parent / "styles.css"
if css_path.exists():
css = css_path.read_text(encoding="utf-8")
else:
css = ""
return f"<style>{css}</style>"
PWA_META = """
<script>
(function() {
// Viewport — блокируем масштабирование, фиксируем под клавиатуру
function setVP() {
var v = document.querySelector('meta[name="viewport"]');
var c = 'width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no,viewport
if (v) v.content = c;
else { var m=document.createElement('meta'); m.name='viewport'; m.content=c; document.hea
}
setVP(); setTimeout(setVP,300); setTimeout(setVP,1000);
// PWA мета
[
['apple-mobile-web-app-capable','yes'],
['apple-mobile-web-app-status-bar-style','black-translucent'],
['apple-mobile-web-app-title','Jarvis'],
['theme-color','#080b12'],
['mobile-web-app-capable','yes'],
].forEach(function(p){
if(!document.querySelector('meta[name="'+p[0]+'"]')){
var m=document.createElement('meta'); m.name=p[0]; m.content=p[1]; document.head.append
}
});
// Авто-рост textarea при вводе
document.addEventListener('input', function(e) {
if (e.target && e.target.tagName === 'TEXTAREA') {
e.target.style.height = 'auto';
e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px';
}
});
// Scroll чата вниз при появлении клавиатуры (iOS)
window.visualViewport && window.visualViewport.addEventListener('resize', function() {
var chat = document.querySelector('[data-testid="stChatMessageContainer"]');
if (chat) chat.scrollTop = chat.scrollHeight;
});
})();
</script>
"""
# ═════════════════════════════════════════════════════════════
# САЙДБАР С ИСТОРИЕЙ
# ═════════════════════════════════════════════════════════════
def render_sidebar():
with st.sidebar:
# Заголовок
st.markdown(
f"<div style='font-family:var(--font-mono,monospace);font-size:.9rem;"
f"letter-spacing:.1em;padding:4px 0 8px'>"
f"<span style='color:#4F8EF7'> </span> JARVIS v{VERSION}</div>",
unsafe_allow_html=True,
)
# Новый чат
if st.button(" Новый чат", use_container_width=True):
save_current_chat()
st.session_state["messages"] = []
st.session_state["pending_img"] = None
st.session_state["pending_doc"] = None
st.session_state["chat_id"] = new_chat_id()
st.rerun()
st.divider()
# Поиск по истории
search = st.text_input(
" Поиск чатов",
value=st.session_state.get("search_query", ""),
placeholder="Введите текст…",
key="search_input",
label_visibility="collapsed",
)
st.session_state["search_query"] = search
# История чатов
history = load_history()
current_id = st.session_state.get("chat_id")
if history:
# Сортируем по времени (новые сверху)
sorted_chats = sorted(
history.items(),
key=lambda x: x[1].get("ts", ""),
reverse=True,
)
# Фильтр по поиску
if search:
sq = search.lower()
sorted_chats = [
(cid, data) for cid, data in sorted_chats
if sq in data.get("title", "").lower()
or any(sq in m.get("content", "").lower()
for m in data.get("messages", []))
]
st.caption(f"История · {len(sorted_chats)} чатов")
for cid, data in sorted_chats:
is_active = cid == current_id
col1, col2 = st.columns([5, 1])
with col1:
label = ("▶ " if is_active else "") + data.get("title", "Чат")
ts = data.get("ts", "")[:16].replace("T", " ")
if st.button(
label,
key=f"hist_{cid}",
use_container_width=True,
help=ts,
):
if cid != current_id:
save_current_chat()
st.session_state["messages"] = data["messages"]
st.session_state["pending_img"] = None
st.session_state["pending_doc"] = None
st.session_state["chat_id"] = cid
st.rerun()
with col2:
if st.button(" ", key=f"del_{cid}", help="Удалить"):
history.pop(cid, None)
save_history(history)
if cid == current_id:
st.session_state["messages"] = []
st.session_state["chat_id"] = new_chat_id()
st.rerun()
else:
st.caption("История пуста")
st.divider()
# Тема
theme_val = st.radio(
"Тема",
[" Тёмная", " Светлая"],
index=0 if st.session_state.get("theme") == "dark" else 1,
horizontal=True,
)
new_theme = "dark" if "Тёмная" in theme_val else "light"
if st.session_state.get("theme") != new_theme:
st.session_state["theme"] = new_theme
st.rerun()
st.divider()
st.caption(f"Jarvis AI · Groq × Llama\n© Sardarbek Kurbanaliev")
# ═════════════════════════════════════════════════════════════
# ГЛАВНЫЙ ЭКРАН
# ═════════════════════════════════════════════════════════════
def send_message(text: str):
st.session_state["_inject"] = text
st.rerun()
def show_attach_bar():
"""Кнопки и для прикрепления файлов."""
col_doc, col_img, col_gap = st.columns([1, 1, 8])
with col_doc:
pdf_file = st.file_uploader(
" ",
type=["pdf", "txt"],
key="upload_doc",
label_visibility="collapsed",
help="Прикрепить документ (PDF, TXT)",
)
if pdf_file:
prev = st.session_state.get("pending_doc") or {}
if prev.get("name") != pdf_file.name:
if pdf_file.name.lower().endswith(".pdf"):
store_pdf(pdf_file)
else:
text = pdf_file.read().decode("utf-8", errors="replace")
st.session_state["pending_doc"] = {"name": pdf_file.name, "text": text}
with col_img:
img_file = st.file_uploader(
" ",
type=list(MIME_MAP.keys()),
key="upload_img",
label_visibility="collapsed",
help="Прикрепить изображение",
)
if img_file:
prev = st.session_state.get("pending_img") or {}
if prev.get("name") != img_file.name:
store_image(img_file)
def show_pending_attachments():
"""Показывает превью прикреплённых файлов."""
pimg = st.session_state.get("pending_img")
pdoc = st.session_state.get("pending_doc")
if pimg:
c1, c2 = st.columns([5, 1])
with c1:
st.image(
f"data:{pimg['mime']};base64,{pimg['b64']}",
width=140,
caption=pimg["name"],
)
with c2:
if st.button("✕", key="rm_img"):
st.session_state["pending_img"] = None
st.rerun()
if pdoc:
c1, c2 = st.columns([5, 1])
with c1:
lines = len(pdoc["text"].splitlines())
st.markdown(
f'<div class="attach-preview">'
f'<span class="attach-icon"> </span>'
f'{pdoc["name"]} · {lines} строк'
f'</div>',
unsafe_allow_html=True,
)
with c2:
if st.button("✕", key="rm_doc"):
st.session_state["pending_doc"] = None
st.rerun()
def show_chat():
msgs = st.session_state.get("messages", [])
render_sidebar()
st.markdown(load_css(), unsafe_allow_html=True)
st.markdown(PWA_META, unsafe_allow_html=True)
# ── Вложения ────────────────────────────────────────────
show_attach_bar()
show_pending_attachments()
# ── Пустой экран — hero + карточки ──────────────────────
if not msgs:
st.markdown(
'<div class="jv-hero">'
'<div class="jv-badge">NEURAL AI · GROQ × LLAMA</div>'
'<div class="jv-logo">JAR<span>V</span>IS</div>'
'<p class="jv-sub">Персональный ИИ-ассистент нового поколения.<br>'
'Задайте вопрос или выберите подсказку.</p>'
'</div>',
unsafe_allow_html=True,
)
cols = st.columns(2)
for i, (title, sub) in enumerate(SUGGEST_CARDS):
with cols[i % 2]:
if st.button(
f"**{title}**\n{sub}",
key=f"card_{i}",
use_container_width=True,
):
send_message(f"{title}: {sub}")
else:
# ── История сообщений ────────────────────────────────
for msg in msgs:
with st.chat_message(msg["role"]):
# Если есть прикреплённое фото в сообщении
if msg.get("img_b64"):
st.image(
f"data:{msg['img_mime']};base64,{msg['img_b64']}",
width=160,
)
st.markdown(msg["content"])
# ── Быстрые чипы ────────────────────────────────────────
cols = st.columns(len(CHIPS))
for i, (label, cmd) in enumerate(CHIPS):
with cols[i]:
if st.button(label, key=f"chip_{i}", use_container_width=True):
if cmd == "__clear__":
save_current_chat()
st.session_state["messages"] = []
st.session_state["pending_img"] = None
st.session_state["pending_doc"] = None
st.session_state["chat_id"] = new_chat_id()
st.rerun()
else:
send_message(cmd)
# ── Поле ввода ───────────────────────────────────────────
injected = st.session_state.pop("_inject", None)
prompt = injected or st.chat_input(
"Спросите Джарвиса…",
# Enter — отправить, Shift+Enter — перенос строки (нативное поведение st.chat_input)
)
if prompt:
pi = st.session_state.get("pending_img")
pdoc = st.session_state.get("pending_doc")
# Формируем контент сообщения
user_text = prompt
if pdoc:
user_text = (
f"[Документ: {pdoc['name']}]\n\n"
f"```\n{pdoc['text'][:8000]}\n```\n\n"
f"{prompt}"
)
# Показываем сообщение пользователя
with st.chat_message("user"):
if pi:
st.markdown(prompt)
st.image(f"data:{pi['mime']};base64,{pi['b64']}", width=160)
# Сохраняем в историю сессии
user_msg: dict = {"role": "user", "content": user_text}
if pi:
user_msg["img_b64"] = pi["b64"]
user_msg["img_mime"] = pi["mime"]
st.session_state["messages"].append(user_msg)
# Сбрасываем вложения
img_b64 = pi["b64"] if pi else None
img_mime = pi["mime"] if pi else None
st.session_state["pending_img"] = None
st.session_state["pending_doc"] = None
# Ответ ассистента
with st.chat_message("assistant"):
slot = st.empty()
slot.markdown(
'<div class="jv-typing">'
'<span></span><span></span><span></span>'
'</div>',
unsafe_allow_html=True,
)
try:
reply = ask_jarvis(st.session_state["messages"], img_b64, img_mime)
except Exception as e:
reply = f" Ошибка API: `{e}`\n\nПроверьте GROQ_API_KEY и подключение slot.markdown(reply)
к инте
st.session_state["messages"].append({"role": "assistant", "content": reply})
# Автосохранение в историю
save_current_chat()
st.rerun()
# ═════════════════════════════════════════════════════════════
# ТОЧКА ВХОДА
# ═════════════════════════════════════════════════════════════
st.set_page_config(
page_title=APP_TITLE,
page_icon=APP_ICON,
layout="centered",
initial_sidebar_state="collapsed",
)
init_session()
show_chat()
