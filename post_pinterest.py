import os
import json
import requests
from datetime import datetime

BUFFER_API = "https://api.buffer.com"
ANIM_HISTORY_FILE = "output/animation_history.json"
POSTED_FILE = "output/pinterest_posted_history.json"
TARGET_LINK = "https://glyfiq.link/"

# Доска Pinterest для пинов Glyfiq.
# BOARD_ID: если хотите жёстко задать доску — вставьте её boardServiceId сюда.
# BOARD_NAME: скрипт сам найдёт доску по этому имени в списке канала.
BOARD_ID = ""
BOARD_NAME = "Medical & Health Icons | Figma Framer Illustrator"

# 5 шаблонов: title (до 100 симв.) + description (до 500 симв.) + хештеги
TEMPLATES = [
    {
        "title": "{icons} — Medical & Health Icons",
        "description": (
            "Three new thin-line medical icons added to Glyfiq: {icons}.\n\n"
            "Perfect for healthcare apps, medical dashboards, and patient interfaces. "
            "Part of our growing library of 6,000+ consistent medical icons for designers.\n\n"
            "Available as a plugin for Figma, Framer & Adobe Illustrator.\n"
            "Try it free 👉 glyfiq.link"
        ),
        "tags": ["#MedicalIcons", "#HealthcareDesign", "#FigmaPlugin"],
    },
    {
        "title": "{icons} — Glyfiq Figma & Framer Plugin",
        "description": (
            "Just dropped: {icons} — now available in the Glyfiq plugin for Figma, "
            "Framer & Adobe Illustrator.\n\n"
            "A consistent thin-line style for medical and health UI design. "
            "Speed up your workflow with thousands of ready-to-use healthcare icons "
            "organized in one plugin.\n\n"
            "Free tier available 👉 glyfiq.link"
        ),
        "tags": ["#Figma", "#Framer", "#IconDesign"],
    },
    {
        "title": "{icons} — Healthcare UI Icons",
        "description": (
            "New icons for healthcare designers: {icons}.\n\n"
            "Designed for medical apps, telemedicine platforms, patient portals, "
            "and health-tech products. Thin-line style with consistent stroke weight "
            "across the entire Glyfiq library.\n\n"
            "Works in Figma, Framer & Adobe Illustrator.\n"
            "Try it free 👉 glyfiq.link"
        ),
        "tags": ["#MedicalUI", "#UXDesign", "#HealthcareDesign"],
    },
    {
        "title": "{icons} — Part of 6,000+ Medical Icons",
        "description": (
            "{icons} — three more icons from my 10-year medical illustration archive, "
            "now available in the Glyfiq plugin.\n\n"
            "Working toward 6,000+ consistent thin-line medical icons for Figma, "
            "Framer & Adobe Illustrator. One style. Three platforms. "
            "Everything a healthcare designer needs.\n\n"
            "Try it free 👉 glyfiq.link"
        ),
        "tags": ["#IconDesign", "#MedicalIcons", "#AdobeIllustrator"],
    },
    {
        "title": "{icons} — Which One Do You Need?",
        "description": (
            "Just added to Glyfiq: {icons}.\n\n"
            "Which of these medical icons would you use first in your healthcare project? "
            "They're part of our growing thin-line medical icon library for Figma, "
            "Framer & Adobe Illustrator.\n\n"
            "Free tier available — try it 👉 glyfiq.link"
        ),
        "tags": ["#FigmaPlugin", "#MedicalUI", "#UIDesign"],
    },
]

def cap_name(n, cap):
    return n if len(n) <= cap else n[:cap - 1].rstrip() + "…"

def join_icons(names, conn):
    if len(names) >= 3:
        return f"{names[0]}, {names[1]} {conn} {names[2]}"
    if len(names) == 2:
        return f"{names[0]} {conn} {names[1]}"
    return names[0] if names else "New medical icons"

def build_text(tpl_idx, names):
    """Возвращает (title, description с хештегами) с учётом лимитов Pinterest"""
    tpl = TEMPLATES[tpl_idx % len(TEMPLATES)]
    tags_line = " ".join(tpl["tags"])

    for cap in (None, 22, 16, 12):
        nm = names if cap is None else [cap_name(n, cap) for n in names]
        icons = join_icons(nm, "&")
        title = tpl["title"].replace("{icons}", icons)
        body = tpl["description"].replace("{icons}", icons)

        # Description = текст + хештеги, максимум 500 символов
        description = body + "\n\n" + tags_line
        if len(description) > 500:
            body = body[:500 - len(tags_line) - 2].rstrip() + "…"
            description = body + "\n\n" + tags_line

        # Title максимум 100 символов
        if len(title) > 100:
            title = title[:97].rstrip() + "..."

        if len(title) <= 100 and len(description) <= 500:
            return title, description

    title = tpl["title"].replace("{icons}", join_icons(names, "&"))[:97] + "..."
    description = tpl["description"].replace("{icons}", join_icons(names, "&"))
    description = description[:500 - len(tags_line) - 2].rstrip() + "…\n\n" + tags_line
    return title, description

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

def get_pinterest_channel(token):
    """Возвращает (channel_id, boards_list)"""
    data = buffer_graphql(token, "query { account { organizations { id name } } }")
    orgs = data["account"]["organizations"]
    if not orgs:
        raise Exception("В аккаунте Buffer нет организаций")
    
    # Запрашиваем канал С досками (boards внутри channel)
    query = '''query {
      channels(input: { organizationId: "%s" }) {
        id
        name
        service
        boards {
          serviceId
          name
        }
      }
    }''' % orgs[0]["id"]
    
    data = buffer_graphql(token, query)
    channels = data.get("channels", [])
    
    for ch in channels:
        if ch.get("service") == "pinterest":
            print(f"📌 Найден Pinterest-канал: {ch['name']}")
            return ch["id"], ch.get("boards", [])
    
    raise Exception("К Buffer не подключен Pinterest-канал")

def resolve_board_service_id(boards):
    """Ищем доску по имени. Возвращаем serviceId (boardServiceId)."""
    if BOARD_ID:
        print(f"📋 Используем BOARD_ID: {BOARD_ID}")
        return BOARD_ID
    
    if not BOARD_NAME:
        return None
    
    for board in boards:
        if board.get("name", "").strip().lower() == BOARD_NAME.lower():
            print(f"📋 Найдена доска: {board['name']} (serviceId: {board['serviceId']})")
            return board["serviceId"]
    
    print(f"⚠️ Доска '{BOARD_NAME}' не найдена. Доступные доски:")
    for board in boards:
        print(f"  - {board['name']} (serviceId: {board['serviceId']})")
    return None

def buffer_create_pinterest_post(token, channel_id, title, description, image_url, board_service_id):
    """Создаём пин через Buffer GraphQL API"""
    text_lit = json.dumps(description, ensure_ascii=False)
    ch_lit = json.dumps(channel_id)
    url_lit = json.dumps(image_url)
    title_lit = json.dumps(title, ensure_ascii=False)
    link_lit = json.dumps(TARGET_LINK)
    board_lit = json.dumps(board_service_id) if board_service_id else "null"
    
    # Формируем metadata.pinterest с правильными полями
    metadata_fields = [f"title: {title_lit}", f"url: {link_lit}"]
    if board_service_id:
        metadata_fields.append(f"boardServiceId: {board_lit}")
    
    metadata_block = ",\n        metadata: { pinterest: { " + ", ".join(metadata_fields) + " } }"
    
    query = f'''mutation {{
      createPost(input: {{
        text: {text_lit},
        channelId: {ch_lit},
        schedulingType: automatic,
        mode: shareNow,
        assets: [{{ image: {{ url: {url_lit} }} }}]{metadata_block}
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
            print(f"⚠️ Не удалось прочитать историю Pinterest: {e}")
    return {"posted": [], "posts_count": 0}

def save_posted(h):
    os.makedirs(os.path.dirname(POSTED_FILE), exist_ok=True)
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=2)

# ---------- Debug: посмотреть доступные доски ----------
def cmd_debug():
    token = os.environ.get("PP_STORE_BUFFER_API_KEY", "")
    if not token:
        print("⚠️ Нет PP_STORE_BUFFER_API_KEY")
        return
    try:
        channel_id, boards = get_pinterest_channel(token)
        print(f"\n📋 Доступные доски канала:")
        for board in boards:
            print(f"  - {board['name']} (serviceId: {board['serviceId']})")
    except Exception as e:
        print(f"Ошибка: {e}")

def main():
    print("📌 Постинг GIF в Pinterest через Buffer...")

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

    names = [n[0].upper() + n[1:] if n else n for n in candidate.get("icon_names", [])]

    tpl_idx = posted.get("posts_count", 0) % len(TEMPLATES)
    title, description = build_text(tpl_idx, names)

    print(f"📌 Постим: {gif_path} (GIF № {candidate.get('gif_number')})")
    print(f"🏷️  Title (вариант {tpl_idx + 1}):\n{title}\n")
    print(f"📝 Description:\n{description}\n")

    token = os.environ.get("PP_STORE_BUFFER_API_KEY", "")
    if not token:
        print("⚠️ PP_STORE_BUFFER_API_KEY не задан в секретах — пост отложен.")
        return

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    if not repo:
        print("❌ Нет GITHUB_REPOSITORY (запуск вне GitHub Actions).")
        return

    image_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{gif_path}"

    try:
        channel_id, boards = get_pinterest_channel(token)
        board_service_id = resolve_board_service_id(boards)
        
        if not board_service_id:
            print("❌ Не удалось найти доску. Pinterest требует выбора доски!")
            return
        
        ok, info = buffer_create_pinterest_post(
            token, channel_id, title, description, image_url, board_service_id
        )
    except Exception as e:
        ok, info = False, str(e)

    already_posted = "already got this one scheduled" in str(info) or "same thing twice" in str(info)

    if ok or already_posted:
        if already_posted:
            print("⚠️ Buffer сообщает, что пост уже опубликован. Помечаем как запощенный.")
        else:
            print(f"✅ Пин опубликован через Buffer, id: {info}")

        posted.setdefault("posted", []).append({
            "gif_number": candidate.get("gif_number"),
            "gif_path": gif_path,
            "icon_names": candidate.get("icon_names", []),
            "template": tpl_idx + 1,
            "title": title,
            "posted_at": datetime.now().isoformat(),
        })
        posted["posts_count"] = posted.get("posts_count", 0) + 1
        save_posted(posted)
        print("💾 История Pinterest обновлена.")
    else:
        print(f"❌ Buffer не опубликовал: {info}. Повторим в следующем запуске.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "debug":
        cmd_debug()
    else:
        main()
