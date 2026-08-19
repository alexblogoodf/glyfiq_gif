import os
import json
import io
from supabase import create_client, Client
from PIL import Image
import cairosvg
from datetime import datetime

# Supabase конфигурация
SUPABASE_URL = "https://ekepequivkyfkidvaaai.supabase.co"
SUPABASE_KEY = "sb_publishable_FrolWjVGFu7nnr0uOYk0JQ_k__7stet"

# Инициализация клиента
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Пути к файлам
STATE_FILE = "output/last_position.json"
HISTORY_FILE = "output/animation_history.json"
OUTPUT_GIF = "output/animation.gif"
BACKGROUND = "background.png"

# Иконки для исключения
EXCLUDED_NAMES = [
    "breast biopsy",
    "breast radiography",
    "changes in size",
    "breast mastopathy",
    "nipple changes",
    "blood from the breast",
    "breast examination",
    "mammography",
    "breast ultrasound",
    "mastopexy",
    "lump on the breast",
    "battery 90%",
    "battery 40%",
    "battery 70%",
    "battery 50%",
    "battery 20%",
    "battery 60%",
    "battery 100%",
    "battery 80%",
    "battery 30%",
    "battery 10%"
]

def load_state():
    """Загружаем последнюю позицию"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"last_id": 0, "processed_count": 0}

def save_state(last_id, processed_count):
    """Сохраняем текущую позицию"""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump({"last_id": last_id, "processed_count": processed_count}, f, indent=2)

def load_history():
    """Загружаем историю анимаций"""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    return {"animations": []}

def save_to_history(icon_ids, icon_names, gif_path):
    """Добавляем запись в историю"""
    history = load_history()
    
    animation_record = {
        "gif_number": len(history["animations"]) + 1,
        "icon_ids": icon_ids,
        "icon_names": icon_names,
        "gif_path": gif_path,
        "created_at": datetime.now().isoformat(),
        "frame_count": len(icon_ids)
    }
    
    history["animations"].append(animation_record)
    
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)
    
    return animation_record

def get_next_icons(last_id, limit=3):
    """Получаем следующие 3 иконки из Supabase, пропуская исключенные"""
    try:
        # Получаем больше иконок чем нужно, чтобы отфильтровать исключенные
        response = supabase.table('icons') \
            .select('id, name, svg_raw') \
            .gt('id', last_id) \
            .order('id', desc=False) \
            .limit(limit * 5) \  # Берем с запасом
            .execute()
        
        all_icons = response.data
        
        # Фильтруем исключенные иконки
        filtered_icons = []
        for icon in all_icons:
            if icon['name'].lower() not in [name.lower() for name in EXCLUDED_NAMES]:
                filtered_icons.append(icon)
            if len(filtered_icons) >= limit:
                break
        
        return filtered_icons[:limit]
    
    except Exception as e:
        print(f"Ошибка при получении иконок: {e}")
        return []

def recolor_svg_to_white(svg_code):
    """Перекрашиваем SVG в белый цвет"""
    svg_code = svg_code.replace('stroke="#000000"', 'stroke="#FFFFFF"')
    svg_code = svg_code.replace('stroke="#000"', 'stroke="#FFFFFF"')
    svg_code = svg_code.replace('fill="#000000"', 'fill="#FFFFFF"')
    svg_code = svg_code.replace('fill="#000"', 'fill="#FFFFFF"')
    return svg_code

def svg_to_png(svg_code, size=(256, 256)):
    """Конвертируем SVG в PNG"""
    try:
        svg_code = recolor_svg_to_white(svg_code)
        
        png_bytes = cairosvg.svg2png(
            bytestring=svg_code.encode('utf-8'),
            output_width=size[0],
            output_height=size[1]
        )
        return Image.open(io.BytesIO(png_bytes)).convert('RGBA')
    except Exception as e:
        print(f"Ошибка конвертации SVG: {e}")
        return None

def create_frame(icon_svg, background):
    """Создаем один кадр с иконкой по центру"""
    bg = Image.open(background).convert('RGBA')
    
    icon_img = svg_to_png(icon_svg)
    if icon_img is None:
        return None
    
    bg_width, bg_height = bg.size
    icon_width, icon_height = icon_img.size
    
    x = (bg_width - icon_width) // 2
    y = (bg_height - icon_height) // 2
    
    bg.paste(icon_img, (x, y), icon_img)
    
    return bg

def create_gif_from_icons(icons, background_path, output_path):
    """Создаем GIF из иконок, показывая каждую по центру по очереди"""
    frames = []
    
    for icon in icons:
        frame = create_frame(icon['svg_raw'], background_path)
        if frame:
            frames.append(frame)
    
    if not frames:
        print("Не удалось создать ни одного кадра")
        return False
    
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=1000,
        loop=0,
        optimize=True
    )
    
    return True

def main():
    print("🚀 Запуск генерации GIF...")
    
    state = load_state()
    last_id = state.get("last_id", 0)
    processed_count = state.get("processed_count", 0)
    
    print(f"📊 Последняя позиция: ID {last_id}, всего обработано GIF: {processed_count}")
    
    # Получаем следующие иконки (пропуская исключенные)
    icons = get_next_icons(last_id, limit=3)
    
    if not icons:
        print("✅ Все иконки обработаны! Начинаем сначала...")
        icons = get_next_icons(0, limit=3)
        if not icons:
            print("❌ В базе нет доступных иконок")
            return
    
    print(f"📦 Получено {len(icons)} иконок:")
    for icon in icons:
        print(f"  - {icon['name']} (ID: {icon['id']})")
    
    # Проверяем, есть ли исключенные иконки
    excluded_found = [icon for icon in icons if icon['name'].lower() in [name.lower() for name in EXCLUDED_NAMES]]
    if excluded_found:
        print(f"⚠️  Найдено исключенных иконок: {len(excluded_found)}")
        for icon in excluded_found:
            print(f"    Пропущена: {icon['name']} (ID: {icon['id']})")
    
    os.makedirs(os.path.dirname(OUTPUT_GIF), exist_ok=True)
    
    if create_gif_from_icons(icons, BACKGROUND, OUTPUT_GIF):
        # Сохраняем ID первой иконки
        first_icon_id = icons[0]['id']
        new_processed_count = processed_count + 1
        
        save_state(first_icon_id, new_processed_count)
        
        # Собираем информацию для истории
        icon_ids = [icon['id'] for icon in icons]
        icon_names = [icon['name'] for icon in icons]
        
        # Генерируем уникальное имя файла
        gif_filename = f"output/animation_{first_icon_id}.gif"
        
        # Копируем файл с уникальным именем
        import shutil
        shutil.copy(OUTPUT_GIF, gif_filename)
        
        # Добавляем запись в историю
        history_record = save_to_history(icon_ids, icon_names, gif_filename)
        
        print(f"✅ GIF успешно создан: {gif_filename}")
        print(f"📝 Состояние сохранено: ID {first_icon_id}, всего GIF: {new_processed_count}")
        print(f"📚 История обновлена: GIF #{history_record['gif_number']}")
        print(f"📋 Использованы иконки: {icon_ids}")
        
        # Сохраняем краткую информацию
        info = {
            "gif_path": gif_filename,
            "icons": [{"id": icon['id'], "name": icon['name']} for icon in icons],
            "created_at": datetime.now().isoformat(),
            "frame_count": len(icons)
        }
        
        with open("output/gif_info.json", 'w') as f:
            json.dump(info, f, indent=2)
        
    else:
        print("❌ Ошибка при создании GIF")

if __name__ == "__main__":
    main()
