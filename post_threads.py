import os
import sys
import json
import time
import shutil
import subprocess
import requests
from datetime import datetime

THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN")
USER_ID = os.environ.get("THREADS_USER_ID")
REPO_NAME = os.environ.get("GITHUB_REPOSITORY")
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")
GRAPH_URL = "https://graph.threads.net/v1.0"

ANIM_HISTORY_FILE = "output/animation_history.json"
POSTED_FILE = "output/threads_posted_history.json"
PENDING_FILE = "output/threads_pending.json"

# 5 вариантов сообщений (БЕЗ хэштегов и БЕЗ ссылки)
TEMPLATES = [
    ("and",
     "✏️ {icons} — now in Glyfiq 🩺\n"
     "Find more medical & health icons for Figma, Framer & Illustrator."),
    ("&",
     "Part of the Glyfiq medical icon library — available in Figma, Framer & Illustrator: {icons} 👍 "
     "More icons & growing."),
    (",",
     "✏️ {icons} — three more icons live in Glyfiq 🎨\n"
     "Medical & health icon plugin for Figma, Framer & Illustrator."),
    ("&",
     "Now added: {icons} to Glyfiq ✏️\n"
     "More thin-line medical icons. One style. Three platforms."),
    ("&",
     "✏️ {icons} - these icons are already available for Figma, Framer & Illustrator. "
     "You can order the icons you need for your project directly from the Glyfiq plugin."),
]

REPLY_TEXT = "Try it free 👉 https://glyfiq.link/"
TOPIC = "Design Threads"

def tweet_len(text):
    n = 0
    for ch in text:
        o = ord(ch)
        if o >= 0x1000 or 0x2600 <= o <= 0x27BF or 0x2B00 <= o <= 0x2BFF or 0xFE00 <= o <= 0xFE0F:
            n += 2
        else:
            n += 1
    return n

def cap_name(n, cap):
    return n if len(n) <= cap else n[:cap - 1].rstrip() + "…"

def join_icons(names, conn):
    if len(names) >= 3:
        return f"{names[0]}, {names[1]}, {names[2]}" if conn == "," else f"{names[0]}, {names[1]} {conn} {names[2]}"
    if len(names) == 2:
        return f"{names[0]}, {names[1]}" if conn == "," else f"{names[0]} {conn} {names[1]}"
    return names[0] if names else "New icons"

def build_text(tpl_idx, names):
    conn, tpl = TEMPLATES[tpl_idx % len(TEMPLATES)]
    for cap in (None, 22, 16, 12):
        nm = names if cap is None else [cap_name(n, cap) for n in names]
        text = tpl.replace("{icons}", join_icons(nm, conn))
        if tweet_len(text) <= 500:
            return text
    return tpl.replace("{icons}", join_icons(names, conn))

# ---------- История постов Threads ----------
def load_posted():
    if os.path.exists(POSTED_FILE):
        try:
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Не удалось прочитать историю Threads: {e}")
    return {"posted": [], "posts_count": 0}

def save_posted(h):
    os.makedirs(os.path.dirname(POSTED_FILE), exist_ok=True)
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=2)

def get_raw_url(path):
    return f"https://raw.githubusercontent.com/{REPO_NAME}/{BRANCH}/{path}"

# ---------- ffmpeg: системный или из imageio-ffmpeg ----------
def get_ffmpeg_exe():
    """Быстрый путь: системный ffmpeg, а если нет — бинарник из imageio-ffmpeg"""
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        print(f"⚠️ imageio-ffmpeg недоступен: {e}")
        return "ffmpeg"

def gif_to_mp4(gif_path):
    mp4_path = gif_path.rsplit(".", 1)[0] + ".mp4"
    if os.path.exists(mp4_path):
        print(f"ℹ️ MP4 уже существует: {mp4_path}")
        return mp4_path
    ffmpeg_exe = get_ffmpeg_exe()
    print(f"🎞 Использую ffmpeg: {ffmpeg_exe}")
    cmd = [ffmpeg_exe, "-y", "-stream_loop", "2", "-i", gif_path,
           "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4_path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not os.path.exists(mp4_path):
        print(f"❌ Ошибка ffmpeg: {res.stderr[-800:]}")
        return None
    print(f"🎞 GIF сконвертирован в {mp4_path}")
    return mp4_path

# ---------- Threads API ----------
def create_video_container(text, video_url, topic_tag=None):
    url = f"{GRAPH_URL}/{USER_ID}/threads"
    payload = {
        "access_token": THREADS_ACCESS_TOKEN,
        "text": text,
        "media_type": "VIDEO",
        "video_url": video_url,
    }
    if topic_tag:
        payload["topic_tag"] = topic_tag
    res = requests.post(url, data=payload).json()
    if "id" not in res:
        raise Exception(f"Ошибка создания медиа-контейнера: {res}")
    return res["id"]

def check_container_status(container_id):
    url = f"{GRAPH_URL}/{container_id}"
    payload = {"access_token": THREADS_ACCESS_TOKEN, "fields": "status,error_message"}
    time.sleep(45)
    for _ in range(4):
        res = requests.get(url, params=payload).json()
        status = res.get("status")
        if status == "FINISHED":
            return True
        if status == "ERROR":
            raise Exception(f"Ошибка обработки видео Meta: {res.get('error_message')}")
        time.sleep(30)
    raise Exception("Таймаут: Meta не успела обработать видео.")

def publish_container(creation_id):
    url = f"{GRAPH_URL}/{USER_ID}/threads_publish"
    payload = {"access_token": THREADS_ACCESS_TOKEN, "creation_id": creation_id}
    res = requests.post(url, data=payload).json()
    if "id" not in res:
        raise Exception(f"Ошибка публикации: {res}")
    return res["id"]

def create_reply_container(text, reply_to_id, topic_tag=None):
    url = f"{GRAPH_URL}/{USER_ID}/threads"
    payload = {
        "access_token": THREADS_ACCESS_TOKEN,
        "text": text,
        "reply_to_id": reply_to_id,
    }
    if topic_tag:
        payload["topic_tag"] = topic_tag
    res = requests.post(url, data=payload).json()
    if "id" not in res:
        raise Exception(f"Ошибка создания reply: {res}")
    return res["id"]

# ---------- Шаги ----------
def cmd_prepare():
    print("🎬 Подготовка поста для Threads...")

    if not os.path.exists(ANIM_HISTORY_FILE):
        print("❌ История анимаций не найдена — постить нечего.")
        return

    with open(ANIM_HISTORY_FILE, "r", encoding="utf-8") as f:
        anim = json.load(f)

    animations = sorted(anim.get("animations", []), key=lambda a: a.get("gif_number", 0))
    posted = load_posted()
    posted_numbers = {p.get("gif_number") for p in posted.get("posted", [])}

    candidate = next((a for a in animations if a.get("gif_number") not in posted_numbers), None)

    if candidate is None:
        print("😴 Все GIF уже запощены в Threads. Завершаемся.")
        return

    gif_path = candidate.get("gif_path", "")
    if not gif_path or not os.path.exists(gif_path):
        print(f"❌ Файл {gif_path} не найден. Доступных GIF нет — завершаемся.")
        return

    names = [n[0].upper() + n[1:] if n else n for n in candidate.get("icon_names", [])]
    tpl_idx = posted.get("posts_count", 0) % len(TEMPLATES)
    text = build_text(tpl_idx, names)

    mp4_path = gif_to_mp4(gif_path)
    if not mp4_path:
        print("❌ Не удалось сконвертировать GIF в MP4. Повторим в следующем запуске.")
        return

    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "gif_number": candidate.get("gif_number"),
            "gif_path": gif_path,
            "mp4_path": mp4_path,
            "text": text,
            "reply_text": REPLY_TEXT,
            "topic": TOPIC,
            "icon_names": candidate.get("icon_names", []),
            "template": tpl_idx + 1,
        }, f, ensure_ascii=False, indent=2)

    print(f"📦 Подготовлен пост: {mp4_path} (GIF № {candidate.get('gif_number')}, вариант {tpl_idx + 1})")
    print(f"📝 Текст:\n{text}")
    print(f"💬 Reply: {REPLY_TEXT}")

def cmd_post():
    if not os.path.exists(PENDING_FILE):
        print("😴 Нет отложенного поста для Threads.")
        return

    if not THREADS_ACCESS_TOKEN or not USER_ID:
        print("⚠️ THREADS_ACCESS_TOKEN / THREADS_USER_ID не заданы — пост отложен.")
        return

    if not REPO_NAME:
        print("❌ Нет GITHUB_REPOSITORY (запуск вне GitHub Actions).")
        return

    with open(PENDING_FILE, "r", encoding="utf-8") as f:
        pending = json.load(f)

    video_url = get_raw_url(pending["mp4_path"])
    text = pending.get("text", "")
    reply_text = pending.get("reply_text", REPLY_TEXT)
    topic = pending.get("topic", TOPIC)

    print(f"🚀 Публикуем в Threads: {video_url}")

    try:
        container_id = create_video_container(text, video_url, topic_tag=topic)
        check_container_status(container_id)
        published_id = publish_container(container_id)
        print(f"✅ Основной пост опубликован, id: {published_id}")

        time.sleep(2)
        print(f"💬 Публикуем reply: {reply_text}")
        reply_container_id = create_reply_container(reply_text, published_id, topic_tag=topic)
        published_reply_id = publish_container(reply_container_id)
        print(f"✅ Reply опубликован, id: {published_reply_id}")

    except Exception as e:
        print(f"❌ Threads не опубликовал: {e}. Повторим в следующем запуске.")
        return

    posted = load_posted()
    posted.setdefault("posted", []).append({
        "gif_number": pending.get("gif_number"),
        "gif_path": pending.get("gif_path"),
        "mp4_path": pending.get("mp4_path"),
        "icon_names": pending.get("icon_names", []),
        "template": pending.get("template"),
        "threads_post_id": published_id,
        "threads_reply_id": published_reply_id,
        "posted_at": datetime.now().isoformat(),
    })
    posted["posts_count"] = posted.get("posts_count", 0) + 1
    save_posted(posted)
    os.remove(PENDING_FILE)

    print("💾 История постов Threads обновлена.")

if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "prepare"
    if command == "post":
        cmd_post()
    else:
        cmd_prepare()
