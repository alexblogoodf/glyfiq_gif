import os
import sys
import json
import requests
from datetime import datetime

BUFFER_API = "https://api.buffer.com"
ANIM_HISTORY_FILE = "output/animation_history.json"
POSTED_FILE = "output/pinterest_posted_history.json"
TARGET_LINK = "https://glyfiq.link/"

# Известные ID
ORG_ID = "6abb8ca6e6e0080ae50b1028"
CHANNEL_ID = "6abb8d29ea19ca0bde20fa10"

# Доска: если автопоиск не сработает — вставьте boardServiceId сюда (инструкция в конце логов)
BOARD_ID = ""
BOARD_NAME = "Medical & Health Icons | Figma Framer Illustrator"

MANUAL_HELP = """
   РУЧНОЙ СПОСОБ ПОЛУЧИТЬ boardServiceId (2 минуты, работает всегда):
   1. Откройте https://publish.buffer.com (аккаунт PP_STORE)
   2. Начните создавать пост для Pinterest-канала
   3. Откройте DevTools (F12) → вкладка Network → фильтр "graphql"
   4. Нажмите на выпадающий список досок (Board) — Buffer отправит запрос со списком досок
   5. В ответе (Response) найдите массив "boards" и вашу доску по имени
   6. Скопируйте её "serviceId" (или "id") — длинная строка из цифр
   7. Вставьте значение в константу BOARD_ID в начале файла post_pinterest.py
"""

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

# Запасные варианты запроса досок (если introspection не поможет)
BOARD_QUERY_CANDIDATES = [
    'query { channel(input: { id: "%s" }) { boards { %s } } }',
    'query { channel(input: { id: "%s" }) { pinterest { boards { %s } } } }',
    'query { channel(input: { id: "%s" }) { pinterestMetadata { boards { %s } } } }',
    'query { channel(input: { id: "%s" }) { metadata { boards { %s } } } }',
    'query { pinterestBoards(input: { channelId: "%s" }) { %s } }',
    'query { pinterestBoards(channelId: "%s") { %s } }',
    'query { boards(input: { channelId: "%s" }) { %s } }',
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
    tpl = TEMPLATES[tpl_idx % len(TEMPLATES)]
    tags_line = " ".join(tpl["tags"])

    for cap in (None, 22, 16, 12):
        nm = names if cap is None else [cap_name(n, cap) for n in names]
        icons = join_icons(nm, "&")
        title = tpl["title"].replace("{icons}", icons)
        body = tpl["description"].replace("{icons}", icons)

        description = body + "\n\n" + tags_line
        if len(description) > 500:
            body = body[:500 - len(tags_line) - 2].rstrip() + "…"
            description = body + "\n\n" + tags_line

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


# ---------- Introspection (с защитой от null) ----------
_INTRO_CACHE = {}


def introspect_fields(token, type_name):
    if type_name in _INTRO_CACHE:
        return _INTRO_CACHE[type_name]
    q = ('{ __type(name: "%s") { fields { name type { kind name ofType { kind name ofType { kind name } } } } } }'
         % type_name)
    try:
        data = buffer_graphql(token, q)
    except Exception:
        _INTRO_CACHE[type_name] = {}
        return {}
    t = data.get("__type") or {}
    raw_fields = t.get("fields") or []   # ← ЗАЩИТА: Buffer может вернуть fields: null
    res = {}
    for f in raw_fields:
        if isinstance(f, dict) and f.get("name"):
            res[f["name"]] = f.get("type") or {}
    _INTRO_CACHE[type_name] = res
    return res


def unwrap_name(t):
    cur = t or {}
    while cur.get("kind") in ("NON_NULL", "LIST"):
        cur = cur.get("ofType") or {}
    return cur.get("name")


def pick_board_fields(token, type_name):
    fields = introspect_fields(token, type_name)
    return [w for w in ("serviceId", "id", "name") if w in fields]


def collect_boards(obj, found):
    """Рекурсивно ищем любой список boards в ответе"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "boards" and isinstance(v, list):
                for b in v:
                    if isinstance(b, dict) and b.get("name"):
                        found.append(b)
            else:
                collect_boards(v, found)
    elif isinstance(obj, list):
        for item in obj:
            collect_boards(item, found)
    return found


def find_boards_auto(token, verbose=False):
    """Путь 1: introspection — сам находим поле с досками в типе Channel"""
    ch = introspect_fields(token, "Channel")
    if not ch:
        if verbose:
            print("⚠️ Introspection типа Channel недоступна.")
        return []
    if verbose:
        print("🔎 Поля типа Channel: " + ", ".join(sorted(ch.keys())))

    paths = []
    for fname, ftype in ch.items():
        t = unwrap_name(ftype)
        if not t:
            continue
        if "board" in t.lower():
            paths.append(([fname], t))
            continue
        sub = introspect_fields(token, t)
        for sname, stype in sub.items():
            st = unwrap_name(stype)
            if st and "board" in st.lower():
                paths.append(([fname, sname], st))

    if verbose:
        print("🔎 Кандидаты-пути: " + (", ".join(".".join(p) for p, _ in paths) or "не найдены"))

    for path, btype in paths:
        fields = pick_board_fields(token, btype)
        if not fields:
            continue
        sel = " ".join(fields)
        node_sel = sel
        for part in reversed(path):
            node_sel = "%s { %s }" % (part, node_sel)
        query = 'query { channel(input: { id: "%s" }) { id %s } }' % (CHANNEL_ID, node_sel)
        try:
            data = buffer_graphql(token, query)
        except Exception as e:
            if verbose:
                print(f"   ❌ {'.'.join(path)}: {str(e)[:120]}")
            continue
        node = data.get("channel") or {}
        for part in path:
            node = node.get(part) if isinstance(node, dict) else None
        boards = [b for b in node if isinstance(b, dict) and b.get("name")] if isinstance(node, list) else []
        if boards:
            print(f"✅ Доски получены через поле: {'.'.join(path)}")
            return boards
    return []


def find_boards_legacy(token, verbose=False):
    """Путь 2: перебор заранее известных вариантов запроса"""
    for fields in ("serviceId name", "id name", "serviceId id name"):
        for tpl in BOARD_QUERY_CANDIDATES:
            query = tpl % (CHANNEL_ID, fields)
            try:
                data = buffer_graphql(token, query)
            except Exception:
                continue
            found = collect_boards(data, [])
            if found:
                print("✅ Доски получены запасным запросом.")
                return found
    return []


def resolve_board_service_id(token):
    if BOARD_ID:
        print(f"📋 Используем BOARD_ID из константы: {BOARD_ID}")
        return BOARD_ID

    boards = []
    try:
        boards = find_boards_auto(token)
        if not boards:
            boards = find_boards_legacy(token)
    except Exception as e:
        print(f"⚠️ Ошибка при поиске досок: {e}")
        boards = []

    if not boards:
        print("⚠️ Не удалось получить список досок через API.")
        print(MANUAL_HELP)
        return None

    print(f"📋 Найдено досок: {len(boards)}")
    for b in boards:
        sid = b.get("serviceId") or b.get("id")
        print(f"   - {b.get('name')} → {sid}")

    for b in boards:
        if b.get("name", "").strip().lower() == BOARD_NAME.lower():
            sid = b.get("serviceId") or b.get("id")
            print(f"✅ Выбрана доска: {b['name']} ({sid})")
            return sid

    print(f"⚠️ Доска '{BOARD_NAME}' не найдена среди доступных.")
    return None


def buffer_create_pinterest_post(token, title, description, image_url, board_service_id):
    """Правильные поля metadata.pinterest: title, url, boardServiceId"""
    text_lit = json.dumps(description, ensure_ascii=False)
    ch_lit = json.dumps(CHANNEL_ID)
    url_lit = json.dumps(image_url)
    title_lit = json.dumps(title, ensure_ascii=False)
    link_lit = json.dumps(TARGET_LINK)
    board_lit = json.dumps(board_service_id)

    query = f'''mutation {{
      createPost(input: {{
        text: {text_lit},
        channelId: {ch_lit},
        schedulingType: automatic,
        mode: shareNow,
        assets: [{{ image: {{ url: {url_lit} }} }}],
        metadata: {{
          pinterest: {{
            title: {title_lit},
            url: {link_lit},
            boardServiceId: {board_lit}
          }}
        }}
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


# ---------- Debug ----------
def cmd_debug():
    token = os.environ.get("PP_STORE_BUFFER_API_KEY", "")
    if not token:
        print("⚠️ Нет PP_STORE_BUFFER_API_KEY")
        return
    print("=" * 70)
    print(f"🎯 Org: {ORG_ID} | Channel: {CHANNEL_ID}")
    print("=" * 70)

    for tn in ("Channel", "PinterestBoard", "PinterestPostMetadataInput"):
        fields = introspect_fields(token, tn)
        print(f"\n🔍 Поля типа {tn}: " + (", ".join(sorted(fields.keys())) if fields else "(недоступно)"))

    print("\n🔍 Автопоиск досок (introspection):")
    boards = find_boards_auto(token, verbose=True)
    if not boards:
        print("\n🔍 Автопоиск досок (запасные запросы):")
        boards = find_boards_legacy(token, verbose=True)

    if boards:
        print("\n📋 Доски:")
        for b in boards:
            print(f"   - {b.get('name')} → serviceId: {b.get('serviceId') or b.get('id')}")
        print("\n💡 При желании зафиксируйте serviceId нужной доски в BOARD_ID.")
    else:
        print("\n❌ Доски не получены.")
        print(MANUAL_HELP)


# ---------- Основной запуск ----------
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

    # Доска — отдельно от публикации, чтобы ошибки не смешивались
    board_service_id = None
    try:
        board_service_id = resolve_board_service_id(token)
    except Exception as e:
        print(f"❌ Ошибка определения доски: {e}")
    if not board_service_id:
        print("❌ Не удалось определить доску. Pinterest требует выбора доски!")
        return

    try:
        ok, info = buffer_create_pinterest_post(token, title, description, image_url, board_service_id)
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
    if len(sys.argv) > 1 and sys.argv[1] == "debug":
        cmd_debug()
    else:
        main()
