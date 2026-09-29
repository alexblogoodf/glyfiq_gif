import os
import json
import requests

BUFFER_API = "https://api.buffer.com"
CHANNEL_ID = "6abb8d29ea19ca0bde20fa10"

def gql(token, query):
    r = requests.post(BUFFER_API,
                      headers={"Content-Type": "application/json",
                               "Authorization": f"Bearer {token}"},
                      json={"query": query}, timeout=30)
    return r.json()

token = os.environ.get("PP_STORE_BUFFER_API_KEY", "")

print("="*70)
print("🔍 ТЕСТ 5: Запрашиваем channel.metadata (полностью)")
print("="*70)
q = f'''query {{
  channel(input: {{ id: "{CHANNEL_ID}" }}) {{
    id
    name
    service
    metadata
  }}
}}'''
print(json.dumps(gql(token, q), ensure_ascii=False, indent=2))

print("\n" + "="*70)
print("🔍 ТЕСТ 6: Запрашиваем последние посты канала (ищем boardServiceId)")
print("="*70)
q = f'''query {{
  posts(filter: {{ channelIds: ["{CHANNEL_ID}"], statuses: [sent, draft] }}, first: 10) {{
    edges {{
      node {{
        id
        text
        status
        metadata
      }}
    }}
  }}
}}'''
print(json.dumps(gql(token, q), ensure_ascii=False, indent=2))

print("\n" + "="*70)
print("🔍 ТЕСТ 7: Introspection ChannelMetadata")
print("="*70)
q = '''{
  __type(name: "ChannelMetadata") {
    name
    kind
    fields {
      name
      type { name kind ofType { name } }
    }
  }
}'''
print(json.dumps(gql(token, q), ensure_ascii=False, indent=2))
