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
OUTPUT_GIF = "output/animation.gif"
BACKGROUND = "background.png"

def load_state():
    """Загружаем последнюю позицию"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"last_id": 0, "processed_count": 0}

def save_state(last_id, processed_count):
    """Сохраняем текущую позицию - ID ПЕРВОЙ иконки из тройки"""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump({"last_id": last_id, "processed_count": processed_count}, f, indent=2)

def get_next_icons(last_id, limit=3):
    """Получаем следующие 3 иконки из Supabase"""
    try:
        response = supabase.table('icons') \
            .select('id, name, svg_raw') \
            .gt('id', last_id) \
            .order('id', desc=False) \
            .limit(limit) \
            .execute()
        
        return response.data
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
    print(" Запуск генерации GIF...")
    
    state = load_state()
    last_id = state.get("last_id", 0)
    processed_count = state.get("processed_count", 0)
    
    print(f"📊 Последняя позиция: ID {last_id}, всего обработано: {processed_count}")
    
    icons = get_next_icons(last_id, limit=3)
    
    if not icons:
        print("✅ Все иконки обработаны! Начинаем сначала...")
        icons = get_next_icons(0, limit=3)
        if not icons:
            print("❌ В базе нет иконок")
            return
    
    print(f"📦 Получено {len(icons)} иконок:")
    for icon in icons:
        print(f"  - {icon['name']} (ID: {icon['id']})")
    
    os.makedirs(os.path.dirname(OUTPUT_GIF), exist_ok=True)
    
    if create_gif_from_icons(icons, BACKGROUND, OUTPUT_GIF):
        # 🔥 ВАЖНО: Сохраняем ID ПЕРВОЙ иконки, а не последней!
        first_icon_id = icons[0]['id']
        new_processed_count = processed_count + 1  # Увеличиваем на 1, а не на 3
        
        save_state(first_icon_id, new_processed_count)
        
        print(f"✅ GIF успешно создан: {OUTPUT_GIF}")
        print(f"📝 Состояние сохранено: ID {first_icon_id} (первая из тройки), всего обработано: {new_processed_count}")
        
        # Генерируем уникальное имя файла на основе ID первой иконки
        gif_filename = f"output/animation_{first_icon_id}.gif"
        
        # Сохраняем копию с уникальным именем
        import shutil
        shutil.copy(OUTPUT_GIF, gif_filename)
        
        info = {
            "gif_path": gif_filename,
            "icons": [{"id": icon['id'], "name": icon['name']} for icon in icons],
            "created_at": str(datetime.now()),
            "frame_count": len(icons),
            "start_id": first_icon_id
        }
        
        with open("output/gif_info.json", 'w') as f:
            json.dump(info, f, indent=2)
        
        print(f"ℹ️  GIF сохранён как: {gif_filename}")
        print(f"📋 Информация о GIF сохранена в output/gif_info.json")
    else:
        print("❌ Ошибка при создании GIF")

if __name__ == "__main__":
    main()
