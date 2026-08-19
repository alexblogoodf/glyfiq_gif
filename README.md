# Auto GIF Generator from Supabase Icons

Автоматическая генерация GIF анимаций из иконок в Supabase.

## Настройка

### 1. Добавьте секреты в GitHub Repository:

Зайдите в Settings → Secrets and variables → Actions и добавьте:

- `SUPABASE_URL`: https://ekepequivkyfkidvaaai.supabase.co
- `SUPABASE_KEY`: sb_publishable_FrolWjVGFu7nnr0uOYk0JQ_k__7stet

### 2. Убедитесь, что в репозитории есть:

- `background.png` - фоновое изображение
- Папка `output/` для сохранения результатов

### 3. Запуск

**Автоматически:** 
- Запускается каждые 6 часов (настройте в `.github/workflows/generate-gif.yml`)

**Вручную:**
1. Зайдите в Actions → Generate GIF from Supabase Icons
2. Нажмите "Run workflow"
3. Опционально: отметьте "Reset position" для начала сначала

## Структура output/
