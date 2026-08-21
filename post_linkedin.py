import os
import sys
import json
import requests
from datetime import datetime

BUFFER_API = "https://api.buffer.com"
ANIM_HISTORY_FILE = "output/animation_history.json"
POSTED_FILE = "output/linkedin_posted_history.json"
PENDING_FILE = "output/linkedin_pending.json"

# 5 вариантов в стиле LinkedIn: длинные, личные, с историями + привязка к конкретным иконкам
TEMPLATES = [
    # Вариант 1:
    ("🚀 Now available in Glyfiq!\n\n"
     "Just added three new medical icons to the collection:\n\n"
     "• {icon1}\n"
     "• {icon2}\n"
     "• {icon3}\n\n"
     "Speed up your design workflow and elevate your healthcare projects today.\n"
     "Glyfiq — Medical & Health Icon Plugin for Figma, Adobe Illustrator & Framer.\n\n"
     "Try it free 👉 https://glyfiq.link/\n\n"
     "#Figma #Framer #FigmaPlugin #HealthcareDesign #MedicalUI #UIDesign "
     "#UXDesign #IconDesign #ProductDesign #DesignTools #AdobeIllustrator #Illustrator"),

    # Вариант 2:
    ("I drew medical icons for stock platforms for 10 years. Now I turned that archive "
     "into a Figma, Adobe Illustrator & Framer plugin. Vibe coded the whole thing. "
     "Zero dev experience. Lots of praying. It got approved. 🙏\n\n"
     "Today's fresh additions:\n\n"
     "• {icon1}\n"
     "• {icon2}\n"
     "• {icon3}\n\n"
     "If you design healthcare apps — try it free 👇\n"
     "https://glyfiq.link/\n\n"
     "#Figma #Framer #FigmaPlugin #HealthcareDesign #MedicalUI #UIDesign "
     "#UXDesign #IconDesign #ProductDesign #AdobeIllustrator #BuildInPublic"),

    # Вариант 3:
    ("I've been drawing medical and health icons for stock platforms for 10 years. "
     "Shutterstock, Adobe Stock, iStock — thousands of icons sold over the years.\n\n"
     "Now I'm putting that entire archive into a Figma, Adobe Illustrator & Framer "
     "plugin called Glyfiq. Working toward 6,000+ icons from my existing archive over "
     "the next couple of years.\n\n"
     "Three more added today:\n\n"
     "• {icon1}\n"
     "• {icon2}\n"
     "• {icon3}\n\n"
     "Would love to hear what you think. Try it 👉 https://glyfiq.link/\n\n"
     "#Figma #Framer #FigmaPlugin #HealthcareDesign #MedicalUI #UIDesign "
     "#UXDesign #IconDesign #ProductDesign #DesignTools #AdobeIllustrator #Illustrator"),

    # Вариант 4:
    ("Which one would you use first in your healthcare project? 👇\n\n"
     "• {icon1}\n"
     "• {icon2}\n"
     "• {icon3}\n\n"
     "These three just landed in Glyfiq — the medical icon plugin I'm building for "
     "Figma, Adobe Illustrator & Framer.\n\n"
     "Every week I'm adding new icons from my 10-year archive. The goal is 6,000+ "
     "consistent thin-line medical icons in one place.\n\n"
     "Try it free 👉 https://glyfiq.link/\n\n"
     "Drop a comment — which one do you need most in your current project?\n\n"
     "#Figma #Framer #FigmaPlugin #HealthcareDesign #MedicalUI #UIDesign "
     "#UXDesign #IconDesign #ProductDesign #AdobeIllustrator"),

    # Вариант 5:
    ("10 years of drawing medical icons. Thousands sold on Shutterstock, Adobe Stock, "
     "iStock. Now that entire archive is becoming a single plugin.\n\n"
     "Today's drop:\n\n"
     "• {icon1}\n"
     "• {icon2}\n"
     "• {icon3}\n\n"
     "Each one took me hours to draw back in the day. Now they're a click away in "
     "Figma, Adobe Illustrator & Framer.\n\n"
     "I built Glyfiq with zero dev experience — just Claude, vibes, and a lot of "
     "Googling. Still can't believe it got approved. 🤯\n\n"
     "If you design anything in healthcare, give it a try 👉 https://glyfiq.link/\n\n"
     "#Figma #Framer #FigmaPlugin #HealthcareDesign #MedicalUI #UIDesign "
     "#UXDesign #IconDesign #ProductDesign #AdobeIllustrator #BuildInPublic #NoCode"),
]

def cap_name(n, cap=None):
    if cap and len(n) > cap:
        return n[:cap - 1].rstrip() + "…"
    return n

def build_text(tpl_idx, names):
    tpl = TEMPLATES[tpl_idx % len(TEMPLATES)]
    # Берём первые 3 иконки (или меньше, если их меньше)
    icon1 = names[0].capitalize() if len(names) > 0 else "Medical icon"
    icon2 = names[1].capitalize() if len(names) > 1 else "Medical icon"
    icon3 = names[2].capitalize() if len(names) > 2 else "Medical icon"
    return (tpl
            .replace("{icon1}", icon1)
            .replace("{icon2}", icon2)
            .replace("{icon3}", icon3))

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
