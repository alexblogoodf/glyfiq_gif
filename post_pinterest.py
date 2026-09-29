import os
import sys
import json
import requests

BUFFER_API = "https://api.buffer.com"
CHANNEL_ID = "6abb8d29ea19ca0bde20fa10"
TARGET_LINK = "https://glyfiq.link/"


def buffer_graphql(token, query):
    r = requests.post(BUFFER_API,
                      headers={"Content-Type": "application/json",
                               "Authorization": f"Bearer {token}"},
                      json={"query": query}, timeout=30)
    r.raise_for_status()
    return r.json()


def try_mutation(token, board_value, label):
    """Пробуем сделать createPost с разными board значениями и смотрим ошибки"""
    print(f"\n{'='*70}")
    print(f"🔍 Попытка: {label}")
    print(f"   boardServiceId = {json.dumps(board_value) if board_value else 'НЕ УКАЗАНО'}")
    print(f"{'='*70}")
    
    text_lit = json.dumps("Test description for board discovery")
    ch_lit = json.dumps(CHANNEL_ID)
    title_lit = json.dumps("Test title")
    link_lit = json.dumps(TARGET_LINK)
    
    if board_value is None:
        meta_block = ""
    else:
        board_lit = json.dumps(board_value)
        meta_block = f''',
        metadata: {{
          pinterest: {{
            title: {title_lit},
            url: {link_lit},
            boardServiceId: {board_lit}
          }}
        }}'''
    
    query = f'''mutation {{
      createPost(input: {{
        text: {text_lit},
        channelId: {ch_lit},
        schedulingType: draft,
        assets: [{{ image: {{ url: "https://via.placeholder.com/100" }} }}]{meta_block}
      }}) {{
        ... on PostActionSuccess {{ post {{ id }} }}
        ... on MutationError {{ message }}
      }}
    }}'''
    
    result = buffer_graphql(token, query)
    print(f"\n📥 Ответ:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def try_boards_query(token, query_text, label):
    """Пробуем разные варианты получения списка досок"""
    print(f"\n{'='*70}")
    print(f"🔍 Запрос: {label}")
    print(f"{'='*70}")
    result = buffer_graphql(token, query_text)
    print(f"\n📥 Ответ:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main():
    token = os.environ.get("PP_STORE_BUFFER_API_KEY", "")
    if not token:
        print("❌ Нет PP_STORE_BUFFER_API_KEY")
        return
    
    print("=" * 70)
    print("🕵️ РАЗВЕДКА: пытаемся вытащить boardServiceId автоматически")
    print("=" * 70)
    
    # --- Этап 1: Introspection (смотрим схему API) ---
    print("\n\n" + "🔬 ЭТАП 1: Схема API (introspection)")
    for type_name in ("Channel", "PinterestBoard", "PinterestPostMetadataInput", "Query"):
        print(f"\n--- Тип: {type_name} ---")
        q = '{ __type(name: "%s") { name fields { name type { name kind ofType { name } } } } }' % type_name
        try:
            r = buffer_graphql(token, q)
            if r.get("errors"):
                print(f"  ❌ Ошибки: {r['errors']}")
            else:
                t = r.get("data", {}).get("__type")
                if t:
                    print(f"  Поля: {[f['name'] for f in (t.get('fields') or [])]}")
                else:
                    print("  Тип не найден")
        except Exception as e:
            print(f"  ❌ {e}")
    
    # --- Этап 2: Мутации с разными значениями boardServiceId ---
    print("\n\n" + "🎯 ЭТАП 2: Попытки создать пост (смотрим ошибки)")
    
    # 2.1. Без boardServiceId вообще
    try_mutation(token, None, "Без boardServiceId")
    
    # 2.2. С пустой строкой
    try_mutation(token, "", "Пустая строка")
    
    # 2.3. С заведомо неверным ID — Pinterest может вернуть список доступных
    try_mutation(token, "0000000000000000000", "Заведомо неверный ID")
    
    # 2.4. С channelId как boardServiceId (вдруг совпадает)
    try_mutation(token, CHANNEL_ID, "channelId как boardServiceId")
    
    # --- Этап 3: Разные варианты запроса списка досок ---
    print("\n\n" + "📋 ЭТАП 3: Запросы списка досок")
    
    queries = [
        ('channel { boards }', f'query {{ channel(input: {{ id: "{CHANNEL_ID}" }}) {{ id boards {{ id serviceId name }} }} }}'),
        ('channel.pinterest.boards', f'query {{ channel(input: {{ id: "{CHANNEL_ID}" }}) {{ id pinterest {{ boards {{ id serviceId name }} }} }} }}'),
        ('channel.metadata.pinterest.boards', f'query {{ channel(input: {{ id: "{CHANNEL_ID}" }}) {{ id metadata {{ pinterest {{ boards {{ id serviceId name }} }} }} }} }}'),
        ('boards(channelId)', f'query {{ boards(channelId: "{CHANNEL_ID}") {{ id serviceId name }} }}'),
        ('boards(input: {channelId})', f'query {{ boards(input: {{ channelId: "{CHANNEL_ID}" }}) {{ id serviceId name }} }}'),
        ('pinterestBoards', f'query {{ pinterestBoards(channelId: "{CHANNEL_ID}") {{ id serviceId name }} }}'),
    ]
    
    for label, q in queries:
        try:
            try_boards_query(token, q, label)
        except Exception as e:
            print(f"\n  ❌ Ошибка запроса: {e}")
    
    print("\n\n" + "=" * 70)
    print("📌 ИТОГО: смотрите ответы выше.")
    print("=" * 70)
    print("""
Что искать в ответах:
1. Если где-то есть массив "boards" с объектами {id, serviceId, name} — 
   это и есть ваша доска. Скопируйте её serviceId (или id).

2. Если в ошибке мутации написано что-то вроде:
   "boardServiceId is required, available: [xxx, yyy]"
   — скопируйте id нужной доски оттуда.

3. Если ничего не помогло:
   - Откройте publish.buffer.com → ваш Pinterest канал
   - F12 → вкладка Network
   - В ФИЛЬТРЕ сверху выберите "Fetch/XHR" (НЕ "All", НЕ "Doc")
   - В поле поиска введите "graphql"
   - Кликните на выпадающий список досок
   - Найдите запрос, в ответе которого есть массив "boards"
""")


if __name__ == "__main__":
    main()
