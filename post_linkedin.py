import os
import sys
import json
import requests
from datetime import datetime

BUFFER_API = "https://api.buffer.com"
ANIM_HISTORY_FILE = "output/animation_history.json"
POSTED_FILE = "output/linkedin_posted_history.json"
PENDING_FILE = "output/linkedin_pending.json"

# 5 вариантов: с хештегами и ссылкой текстом (как для Instagram)
TEMPLATES = [
    ("and",
     "✏️ {icons} — now in Glyfiq 🩺\n"
     "Find more medical & health icons for Figma, Framer & Illustrator.\n"
     "Try it free 👉 glyfiq.link\n\n"
     "#MedicalIcons #Figma #Framer #HealthcareDesign #IconDesign"),
    ("&",
     "Part of the Glyfiq medical icon library — available in Figma, Framer & Illustrator: {icons} 👍 "
     "More icons & growing. Try free 👉 glyfiq.link\n\n"
     "#HealthcareUI #MedicalUI #Figma #IconDesign #UIDesign"),
    (",",
     "✏️ {icons} — three more icons live in Glyfiq 🎨\n"
     "Medical & health icon plugin for Figma, Framer & Illustrator.\n"
     "Free tier available 👉 glyfiq.link\n\n"
     "#Figma #Framer #AdobeIllustrator #MedicalIcons #HealthcareDesign"),
    ("&",
     "Now added: {icons} to Glyfiq ✏️\n"
     "More thin-line medical icons. One style. Three platforms.\n"
     "Try it free 👉 glyfiq.link\n"
     "#IconDesign #MedicalUI #Figma #Framer #HealthcareDesign"),
    ("&",
     "✏️ {icons} - these icons are already available for Figma, Framer & Illustrator. "
     "You can order the icons you need for your project directly from the Glyfiq plugin. "
     "Try it free 👉 glyfiq.link\n\n"
     "#Figma #Framer #AdobeIllustrator #MedicalIcons #HealthcareDesign"),
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
            print(f"⚠️ Не удалось прочитать историю LinkedIn: {e}")
    return {"posted": [], "posts_count": 0}

def save_posted(h):
    os.makedirs(os.path.dirname(POSTED_FILE), exist_ok=True)
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=2)

def get_raw_url(path):
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"

# ---------- Buffer API ----------
def buffer_graphql(token, query):
    r = requests.post(BUFFER_API,
                      headers={"Content-Type": "application/json",
                               "Authorization": f"Bearer {token}"},
                      json={"query": query}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("errors"):
        raise Exception(f"GraphQL error: {data['errors']}")
    return data["data"]

def get_linkedin_channel_id(token):
    data = buffer_graphql(token, "query { account { organizations { id name } } }")
    orgs = data["account"]["organizations"]
    if not orgs:
        raise Exception("В аккаунте Buffer нет организаций")
    data = buffer_graphql(token,
                          'query { channels(input: { organizationId: "%s" }) { id name service } }' % orgs[0]["id"])
    channels = [ch for ch in data.get("channels", []) if ch.get("service") == "linkedin"]
    if not channels:
        raise Exception("К Buffer не подключен LinkedIn-канал")
    # Если подключено несколько LinkedIn-каналов — предпочитаем Glyfiq
    for ch in channels:
        if "glyfiq" in ch.get("name", "").lower():
            print(f"💼 Найден LinkedIn-канал Glyfiq: {ch['name']}")
            return ch["id"]
    print(f"💼 Найден LinkedIn-канал: {channels[0]['name']}")
    return channels[0]["id"]

def buffer_create_video_post(token, channel_id, text, video_url):
    text_lit = json.dumps(text, ensure_ascii=False)
    ch_lit = json.dumps(channel_id)
    url_lit = json.dumps(video_url)
    query = f'''mutation {{
      createPost(input: {{
        text: {text_lit},
        channelId: {ch_lit},
        schedulingType: automatic,
        mode: shareNow,
        assets: [{{ video: {{ url: {url_lit} }} }}]
      }}) {{
        ... on PostActionSuccess {{ post {{ id text }} }}
        ... on MutationError {{ message }}
      }}
    }}'''
    data = buffer_graphql(token, query)
    res = data.get("createPost", {})
    if res.get("post"):
        return True, res["post"].get("id")
    return False, res.get("message", "неизвестная ошибка Buffer")

# ---------- Шаги ----------
def cmd_prepare():
    if os.path.exists(PENDING_FILE):
        print("ℹ️ Уже есть отложенный пост для LinkedIn. Подготовка пропущена.")
        return

    print("🎬 Подготовка поста для LinkedIn...")

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
        print("😴 Все GIF уже запощены в LinkedIn. Завершаемся.")
        return

    # Используем готовый MP4 от Threads-скрипта
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
        print("😴 Нет отложенного поста для LinkedIn.")
        return

    token = os.environ.get("BUFFER_API_KEY", "")
    if not token:
        print("⚠️ BUFFER_API_KEY не задан — пост отложен.")
        return

    if not os.environ.get("GITHUB_REPOSITORY"):
        print("❌ Нет GITHUB_REPOSITORY (запуск вне GitHub Actions).")
        return

    with open(PENDING_FILE, "r", encoding="utf-8") as f:
        pending = json.load(f)

    video_url = get_raw_url(pending["mp4_path"])
    print(f"🚀 Публикуем в LinkedIn: {video_url}")

    try:
        channel_id = get_linkedin_channel_id(token)
        ok, info = buffer_create_video_post(token, channel_id, pending["text"], video_url)
    except Exception as e:
        ok, info = False, str(e)

    already_posted = "already got this one scheduled" in str(info) or "same thing twice" in str(info)

    if ok or already_posted:
        if already_posted:
            print("⚠️ Buffer сообщает, что пост уже запланирован. Помечаем как запощенный.")
        else:
            print(f"✅ Пост опубликован через Buffer, id: {info}")

        posted = load_posted()
        posted.setdefault("posted", []).append({
            "gif_number": pending.get("gif_number"),
            "gif_path": pending.get("gif_path"),
            "mp4_path": pending.get("mp4_path"),
            "icon_names": pending.get("icon_names", []),
            "template": pending.get("template"),
            "posted_at": datetime.now().isoformat(),
        })
        posted["posts_count"] = posted.get("posts_count", 0) + 1
        save_posted(posted)
        os.remove(PENDING_FILE)
        print("💾 История LinkedIn обновлена.")
    else:
        print(f"❌ Buffer не опубликовал: {info}. Повторим в следующем запуске.")

if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "prepare"
    if command == "post":
        cmd_post()
    else:
        cmd_prepare()
