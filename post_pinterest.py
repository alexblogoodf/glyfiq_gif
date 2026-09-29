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
print("🧪 ТЕСТ 1: Пост БЕЗ metadata вообще")
print("="*70)
q = '''mutation {
  createPost(input: {
    text: "Test post without board specification",
    channelId: "6abb8d29ea19ca0bde20fa10",
    schedulingType: automatic,
    mode: shareNow,
    assets: [{ image: { url: "https://via.placeholder.com/100" } }]
  }) {
    ... on PostActionSuccess { post { id text } }
    ... on MutationError { message }
  }
}'''
result = gql(token, q)
print(json.dumps(result, ensure_ascii=False, indent=2))

print("\n" + "="*70)
print("🧪 ТЕСТ 2: Пост с metadata, но БЕЗ boardServiceId")
print("="*70)
q = '''mutation {
  createPost(input: {
    text: "Test post with metadata but no board",
    channelId: "6abb8d29ea19ca0bde20fa10",
    schedulingType: automatic,
    mode: shareNow,
    assets: [{ image: { url: "https://via.placeholder.com/100" } }],
    metadata: {
      pinterest: {
        title: "Test Title",
        url: "https://glyfiq.link"
      }
    }
  }) {
    ... on PostActionSuccess { post { id text } }
    ... on MutationError { message }
  }
}'''
result = gql(token, q)
print(json.dumps(result, ensure_ascii=False, indent=2))

print("\n" + "="*70)
print("🧪 ТЕСТ 3: Пост с указанием доски по ИМЕНИ (не ID)")
print("="*70)
q = '''mutation {
  createPost(input: {
    text: "Test post with board name",
    channelId: "6abb8d29ea19ca0bde20fa10",
    schedulingType: automatic,
    mode: shareNow,
    assets: [{ image: { url: "https://via.placeholder.com/100" } }],
    metadata: {
      pinterest: {
        title: "Test Title",
        url: "https://glyfiq.link",
        board: "Medical & Health Icons | Figma Framer Illustrator"
      }
    }
  }) {
    ... on PostActionSuccess { post { id text } }
    ... on MutationError { message }
  }
}'''
result = gql(token, q)
print(json.dumps(result, ensure_ascii=False, indent=2))

print("\n" + "="*70)
print("🧪 ТЕСТ 4: Интроспекция PinterestPostMetadataInput (полная)")
print("="*70)
q = '''{
  __type(name: "PinterestPostMetadataInput") {
    name
    kind
    inputFields {
      name
      type {
        name
        kind
        ofType {
          name
          kind
        }
      }
    }
  }
}'''
result = gql(token, q)
print(json.dumps(result, ensure_ascii=False, indent=2))
