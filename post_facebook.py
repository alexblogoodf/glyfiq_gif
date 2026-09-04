import os
import sys
import json
import time
import requests
from datetime import datetime

PAGE_ID = "1331329906723094"
GRAPH_URL = "https://graph-video.facebook.com/v18.0"

ANIM_HISTORY_FILE = "output/animation_history.json"
POSTED_FILE = "output/facebook_posted_history.json"
PENDING_FILE = "output/facebook_pending.json"

# 5 вариантов: с хештегами и ссылкой текстом (без https) — как для Instagram
TEMPLATES = [
    ("and",
     "✏️ {icons} — now in Glyfiq 🩺\n"
     "Find more medical & health icons for Figma, Framer & Illustrator.\n"
     "Try it free 👉 https://glyfiq.link/\n\n"
     "#MedicalIcons #IconDesign"),
    ("&",
     "Part of the Glyfiq medical icon library — available in Figma, Framer & Illustrator: {icons} 👍 "
     "More icons & growing. Try free 👉 https://glyfiq.link/\n\n"
     "#HealthcareUI #MedicalUI #Figma #IconDesign #UIDesign"),
    (",",
     "✏️ {icons} — three more icons live in Glyfiq 🎨\n"
     "Medical & health icon plugin for Figma, Framer & Illustrator.\n"
     "Free tier available 👉 https://glyfiq.link/\n\n"
     "#MedicalIcons #IconDesign"),
    ("&",
     "Now added: {icons} to Glyfiq ✏️\n"
     "More thin-line medical icons. One style. Three platforms.\n"
     "Try it free 👉 https://glyfiq.link/\n"
     "#MedicalIcons #IconDesign"),
    ("&",
     "✏️ {icons} - these icons are already available for Figma, Framer & Illustrator. "
     "You can order the icons you need for your project directly from the Glyfiq plugin. "
     "Try it free 👉 https://glyfiq.link/\n\n"
     "#MedicalIcons #IconDesign"),
]

def join_icons(names, conn):
    if len(names) >= 3:
        return f"{names[0]}, {names[1]}, {names[2]}" if conn == "," else f"{names[0]}, {names[1]} {conn} {names[2]}"
    if len(names) == 2:
        return f"{names[0]}, {names[1]}" if conn == "," else f"{names[0]} {conn} {names[1]}"
    return names[0] if names else "New icons"

def build_text(tpl_idx, names):
    conn, tpl = TEMPLATES[tpl_idx % len(TEMPLATES)]
    return tpl.replace("{icons}", join_icons(names, conn))

# ---------- История ----------
def load_posted():
    if os.path.exists(POSTED_FILE):
        try:
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Не удалось прочитать историю Facebook: {e}")
    return {"posted": [], "posts_count": 0}

def save_posted(h):
    os.makedirs(os.path.dirname(POSTED_FILE), exist_ok=True)
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=2)

def get_raw_url(path):
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"

# ---------- Facebook Graph API ----------
def publish_video_to_facebook(access_token, video_url, description):
    """
    Публикуем видео на Facebook Page через Graph API.
    Используем graph-video.facebook.com (эндпоинт специально для видео).
    """
    url = f"{GRAPH_URL}/{PAGE_ID}/videos"
    payload = {
        "access_token": access_token,
        "file_url": video_url,
        "description": description,
        "published": "true",
    }
    res = requests.post(url, data=payload, timeout=120)
    data = res.json()
    if "id" in data:
        return True, data["id"]
    return False, data.get("error", {}).get("message", str(data))

# ---------- Шаги ----------
def cmd_prepare():
    if os.path.exists(PENDING_FILE):
        print("ℹ️ Уже есть отложенный пост для Facebook. Подготовка пропущена.")
        return

    print("🎬 Подготовка поста для Facebook...")

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
        print("😴 Все GIF уже запощены в Facebook. Завершаемся.")
        return

    # Используем MP4, созданный Threads-скриптом
    gif_path = candidate.get("gif_path", "")
    mp4_path = gif_path.rsplit(".", 1)[0] + ".mp4" if gif_path else ""

    if not mp4_path or not os.path.exists(mp4_path):
        print(f"⏳ MP4 для GIF № {candidate.get('gif_number')} ещё не готов (ждём Threads-скрипт).")
        print("😴 Завершаемся, проверим снова при следующем запуске.")
        return

    names = [n[0].upper() + n[1:] if n else n for n in candidate.get("icon_names", [])]
    tpl_idx = posted.get("posts_count", 0) % len(TEMPLATES)
    text = build_text(tpl_idx, names)

    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "gif_number": candidate.get("gif_number"),
            "gif_path": gif_path,
            "mp4_path": mp4_path,
            "text": text,
            "icon_names": candidate.get("icon_names", []),
            "template": tpl_idx + 1,
        }, f, ensure_ascii=False, indent=2)

    print(f"📦 Подготовлен пост: {mp4_path} (GIF № {candidate.get('gif_number')}, вариант {tpl_idx + 1})")
    print(f"📝 Подпись:\n{text}")

def cmd_post():
    if not os.path.exists(PENDING_FILE):
        print("😴 Нет отложенного поста для Facebook.")
        return

    access_token = os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN", "")
    if not access_token:
        print("⚠️ FACEBOOK_PAGE_ACCESS_TOKEN не задан — пост отложен.")
        return

    if not os.environ.get("GITHUB_REPOSITORY"):
        print("❌ Нет GITHUB_REPOSITORY (запуск вне GitHub Actions).")
        return

    with open(PENDING_FILE, "r", encoding="utf-8") as f:
        pending = json.load(f)

    video_url = get_raw_url(pending["mp4_path"])
    print(f"🚀 Публикуем в Facebook Page {PAGE_ID}: {video_url}")

    try:
        ok, info = publish_video_to_facebook(access_token, video_url, pending["text"])
    except Exception as e:
        ok, info = False, str(e)

    if ok:
        print(f"✅ Пост опубликован в Facebook, video id: {info}")

        posted = load_posted()
        posted.setdefault("posted", []).append({
            "gif_number": pending.get("gif_number"),
            "gif_path": pending.get("gif_path"),
            "mp4_path": pending.get("mp4_path"),
            "icon_names": pending.get("icon_names", []),
            "template": pending.get("template"),
            "facebook_video_id": info,
            "posted_at": datetime.now().isoformat(),
        })
        posted["posts_count"] = posted.get("posts_count", 0) + 1
        save_posted(posted)
        os.remove(PENDING_FILE)
        print("💾 История Facebook обновлена.")
    else:
        print(f"❌ Facebook не опубликовал: {info}. Повторим в следующем запуске.")

if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "prepare"
    if command == "post":
        cmd_post()
    else:
        cmd_prepare()
