# ⚡ Быстрый старт для деплоя на Render.com

## 🎯 Всего 4 простых шага до вашего дашборда!

---

## ✅ Шаг 1: Проверьте Git (1 минута)

Откройте терминал и выполните:

```bash
git --version
```

**Если показывает версию (например, `git version 2.43.0`)** → Git готов! ✅

**Если ошибка "command not found"** → Завершите установку Git и перезапустите терминал.

---

## ✅ Шаг 2: Загрузите код на GitHub (3 минуты)

### 2.1 Перейдите в папку приложения

```bash
# Замените на реальный путь к вашей папке
cd /путь/к/wb_price_optimizer

# Примеры:
# Windows: cd C:\Users\YourName\Desktop\wb_price_optimizer
# macOS: cd ~/Desktop/wb_price_optimizer
# Linux: cd ~/Desktop/wb_price_optimizer
```

### 2.2 Настройте Git (если делаете первый раз)

```bash
git config --global user.name "Ваше Имя"
git config --global user.email "your-email@example.com"
```

### 2.3 Выполните команды Git

**⚠️ ЗАМЕНИТЕ `YOUR_GITHUB_USERNAME` на ваш реальный логин!**

```bash
git init
git add .
git commit -m "Ready for Render deployment"
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/wb-price-optimizer.git
git push -u origin main
```

**При запросе логина/пароля:**
- **Логин:** ваш GitHub username
- **Пароль:** используйте **Personal Access Token** (получить: https://github.com/settings/tokens)

---

## ✅ Шаг 3: Деплой на Render (5 минут)

### 3.1 Зарегистрируйтесь

1. Откройте: **https://render.com/register**
2. Нажмите **"Sign up with GitHub"**
3. Разрешите доступ
4. ✅ Готово!

### 3.2 Создайте Web Service

1. В Dashboard: **"+ New"** → **"Web Service"**
2. Выберите **"Build and deploy from a Git repository"** → **"Next"**
3. Найдите **`wb-price-optimizer`** → **"Connect"**

### 3.3 Настройте сервис

Заполните форму:

| Параметр | Значение |
|----------|----------|
| **Name** | `wb-price-optimizer` |
| **Region** | `Frankfurt (EU Central)` |
| **Branch** | `main` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python main.py` |
| **Instance Type** | **Free** ✅ |

Нажмите **"Create Web Service"**

---

## ✅ Шаг 4: Добавьте API ключ (1 минута)

Пока идёт первый деплой:

1. В меню слева: **"Environment"**
2. Нажмите **"Add Environment Variable"**
3. **Key:** `WB_API_KEY`
4. **Value:** (ваш токен Wildberries)
   ```
   eyJhbGciOiJFUzI1NiIsImtpZCI6IjIwMjUwOTA0djEiLCJ0eXAiOiJKV1QifQ.eyJhY2MiOjQsImVudCI6MSwiZXhwIjoxNzgxOTAxMDA2LCJmb3IiOiJhc2lkOmUzNzEyN2I1LWNhNTgtNDU5Yi05MWVhLTRlYzA1ODU3ZDBhNCIsImlkIjoiMDE5YjM1YmEtZmZiZS03Y2U2LWI4NTAtZTMzYWE4N2MwZWQwIiwiaWlkIjoyMDMwMDI2NSwib2lkIjoyNTYwOSwicyI6NzQyMiwic2lkIjoiZTI3ODcyMzMtMzQxNy01ZjZiLTg4N2QtYjVjNTE0NmVjNmU4IiwidCI6ZmFsc2UsInVpZCI6MjAzMDAyNjV9.sXVhc06l1xxfFV0YPh7mw0P3x2splzZVtZBRB0SjZLmo_DL2ebZqTfNGrzOuVGDlk5V_ndFeynZs_244eiuB2A
   ```
5. Нажмите **"Add"** → **"Save Changes"**

---

## 🎉 Готово! Получите ваш URL

### Дождитесь завершения деплоя (2-3 минуты)

Статус деплоя в верхней части экрана:
- 🟡 **"In Progress"** → Идёт сборка
- 🟢 **"Live"** → Приложение запущено!

### Ваш постоянный URL:

```
https://wb-price-optimizer.onrender.com
```

(или с другим именем, если вы изменили Name)

---

## 🚀 Проверьте работу

### Веб-интерфейс (дашборд):
```
https://wb-price-optimizer.onrender.com
```

### API документация:
```
https://wb-price-optimizer.onrender.com/docs
```

### Health check:
```
https://wb-price-optimizer.onrender.com/health
```

---

## ⚠️ Важно знать о бесплатном плане

### "Засыпание" сервиса

После **15 минут** без активности сервис автоматически засыпает.

**Что это означает:**
- Первый запрос после сна займёт ~30 секунд (сервис "просыпается")
- Последующие запросы работают быстро
- Это нормально для бесплатного плана

**Как избежать:**
- Используйте сервис регулярно
- Или апгрейдьте до Starter ($7/мес) — не засыпает

---

## 🔄 Как обновить код

При любых изменениях просто:

```bash
cd /путь/к/wb_price_optimizer
git add .
git commit -m "Описание изменений"
git push
```

Render автоматически пересоберёт приложение! ✅

---

## 📚 Полная документация

Детальное руководство: `RENDER_DEPLOY_GUIDE.md`

---

## 🐛 Проблемы?

**Деплой Failed:**
- Откройте **"Logs"** в Render
- Проверьте ошибки в конце логов

**Сервис не запускается:**
- Проверьте `WB_API_KEY` в Environment
- Убедитесь, что Start Command = `python main.py`

**Нужна помощь?**
Напишите мне — помогу разобраться! 🚀
