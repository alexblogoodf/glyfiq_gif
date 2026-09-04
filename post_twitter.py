import os
import json
import requests
from datetime import datetime

BUFFER_API = "https://api.buffer.com"
ANIM_HISTORY_FILE = "output/animation_history.json"
POSTED_FILE = "output/posted_history.json"
LINK = "glyfiq.link"

# 5 вариантов сообщений (чередуются по кругу)
TEMPLATES = [
    ("and",
     "🩺 {icons} — now in Glyfiq *️⃣\n"
     "Find more medical & health icons for Figma, Framer & Illustrator.\n"
     "Try it free 👉 glyfiq.link\n\n"
     "#Figma #Framer"),
    ("&",
     "Part of the Glyfiq medical icon library — available in Figma, Framer & Illustrator: {icons} 👍 "
     "More icons & growing. Try free 👉 glyfiq.link\n\n"
     "#HealthcareUI #IconDesign"),
    (",",
     "🩺 {icons} — three more icons live in Glyfiq *️⃣\n"
     "Medical & health icon plugin for Figma, Framer & Illustrator.\n"
     "Free tier available 👉 glyfiq.link\n\n"
     "#Figma #Framer"),
    ("&",
     "Now added: {icons} to Glyfiq 🩺\n"
     "More thin-line medical icons. One style. Three platforms.\n"
     "Try it free 👉 glyfiq.link\n"
     "#IconDesign #Figma"),
    ("&",
     "🩺 {icons} - these icons are already available for Figma, Framer & Illustrator. "
     "You can order the icons you need directly from the Glyfiq plugin. "
     "👉 glyfiq.link\n\n"
     "#Figma #Framer"),
]

def tweet_len(text):
    n = 0
    for ch in text:
        o = ord(ch)
        if o >= 0x1000 or 0x2600 <= o <= 0x27BF or 0x2B00 <= o <= 0x2BFF or 0xFE00 <= o <= 0xFE0F:
            n += 2
        else:
            n += 1
    return n

def eff_len(text):
    """Twitter считает любую ссылку как 23 символа"""
    return tweet_len(text) + 12 * text.count(LINK)

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
    lines = tpl.split("\n")
    body = [l for l in lines if not l.startswith("#")]
    tags = [l for l in lines if l.startswith("#")]

    text = tpl.replace("{icons}", join_icons(names, conn))
    for with_tags in (True, False):
        base = "\n".join(body + tags) if with_tags else "\n".join(body)
        for cap in (None, 22, 16, 12):
            nm = names if cap is None else [cap_name(n, cap) for n in names]
            text = base.replace("{icons}", join_icons(nm, conn))
            if eff_len(text) <= 280:
                return text
    return text

# ---------- Buffer API (как в main-9.py) ----------
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

def get_buffer_channel_id(token):
    data = buffer_graphql(token, "query { account { organizations { id name } } }")
    orgs = data["account"]["organizations"]
    if not orgs:
        raise Exception("В аккаунте Buffer нет организаций")
    data = buffer_graphql(token,
                          'query { channels(input: { organizationId: "%s" }) { id name service } }' % orgs[0]["id"])
    channels = data.get("channels", [])
    for ch in channels:
        if ch.get("service") in ("twitter", "x"):
            return ch["id"]
    if channels:
        print(f"⚠️ X-канал не найден, беру первый: {channels[0]['name']}")
        return channels[0]["id"]
    raise Exception("В Buffer не подключено ни одного канала")

def buffer_create_post(token, channel_id, text, image_url):
    text_lit = json.dumps(text, ensure_ascii=False)
    ch_lit = json.dumps(channel_id)
    url_lit = json.dumps(image_url)
    query = f'''mutation {{
      createPost(input: {{
        text: {text_lit},
        channelId: {ch_lit},
        schedulingType: automatic,
        mode: shareNow,
        assets: [{{ image: {{ url: {url_lit} }} }}]
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

# ---------- История постов ----------
def load_posted():
    if os.path.exists(POSTED_FILE):
        try:
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Не удалось прочитать историю постов: {e}")
    return {"posted": [], "posts_count": 0}

def save_posted(h):
    os.makedirs(os.path.dirname(POSTED_FILE), exist_ok=True)
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=2)

def main():
    print("🚀 Постинг GIF в X (Twitter) через Buffer...")

    if not os.path.exists(ANIM_HISTORY_FILE):
        print("❌ Файл истории анимаций не найден — постить нечего.")
        return

    with open(ANIM_HISTORY_FILE, "r", encoding="utf-8") as f:
        anim = json.load(f)

    animations = sorted(anim.get("animations", []), key=lambda a: a.get("gif_number", 0))

    posted = load_posted()
    posted_numbers = {p.get("gif_number") for p in posted.get("posted", [])}

    candidate = None
    for a in animations:
        if a.get("gif_number") not in posted_numbers:
            candidate = a
            break

    if candidate is None:
        print("😴 Все доступные GIF уже запощены. Завершаемся.")
        return

    gif_path = candidate.get("gif_path", "")
    if not gif_path or not os.path.exists(gif_path):
        print(f"❌ Файл {gif_path} не найден в папке. Доступных GIF нет — завершаемся.")
        return

    # Имена иконок с заглавной буквы
    names = [n[0].upper() + n[1:] if n else n for n in candidate.get("icon_names", [])]

    tpl_idx = posted.get("posts_count", 0) % len(TEMPLATES)
    text = build_text(tpl_idx, names)

    print(f"📄 Постим: {gif_path} (GIF № {candidate.get('gif_number')})")
    print(f"📝 Текст (вариант {tpl_idx + 1}):\n{text}\n")

    token = os.environ.get("BUFFER_API_KEY", "")
    if not token:
        print("⚠️ BUFFER_API_KEY не задан в секретах — пост отложен.")
        return

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    if not repo:
        print("❌ Нет GITHUB_REPOSITORY (запуск вне GitHub Actions).")
        return

    image_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{gif_path}"

    try:
        channel_id = get_buffer_channel_id(token)
        ok, info = buffer_create_post(token, channel_id, text, image_url)
    except Exception as e:
        ok, info = False, str(e)

    already_posted = "already got this one scheduled" in str(info) or "same thing twice" in str(info)

    if ok or already_posted:
        if already_posted:
            print("⚠️ Buffer сообщает, что пост уже опубликован. Помечаем как запощенный.")
        else:
            print(f"✅ Пост опубликован через Buffer, id: {info}")

        posted.setdefault("posted", []).append({
            "gif_number": candidate.get("gif_number"),
            "gif_path": gif_path,
            "icon_names": candidate.get("icon_names", []),
            "template": tpl_idx + 1,
            "posted_at": datetime.now().isoformat(),
        })
        posted["posts_count"] = posted.get("posts_count", 0) + 1
        save_posted(posted)
        print("💾 История постов обновлена.")
    else:
        print(f"❌ Buffer не опубликовал: {info}. Повторим в следующем запуске.")

if __name__ == "__main__":
    main()
