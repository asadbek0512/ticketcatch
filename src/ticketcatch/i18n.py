"""Interface text in Uzbek, Russian and English.

One flat dict per language so a missing key is obvious in a diff and a test can assert the three
stay in step. Uzbek is the reference: it is complete by definition, and any key absent from another
language falls back to it rather than showing a raw key to a user.
"""

from datetime import date

DEFAULT = "uz"

LANG_NAMES = {"uz": "🇺🇿 O'zbekcha", "ru": "🇷🇺 Русский", "en": "🇬🇧 English"}

MONTHS = {
    "uz": ("yan", "fev", "mar", "apr", "may", "iyn", "iyl", "avg", "sen", "okt", "noy", "dek"),
    "ru": ("янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"),
    "en": ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
}
WEEKDAYS = {
    "uz": ("Du", "Se", "Ch", "Pa", "Ju", "Sha", "Yak"),
    "ru": ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"),
    "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
}

UZ: dict[str, str] = {
    # --- onboarding ---
    "start": (
        "✈️ <b>TicketCatch</b> — 4 ta saytdagi eng arzon aviabiletni bitta ro'yxatda ko'rsataman.\n\n"
        "<b>Qayerga uchasiz?</b> Tanlang — narxni hozir topaman 👇"
    ),
    "start_deeplink": "✈️ <b>{route}</b> · {date}\n\nNarxni qidiryapman…",
    "help": (
        "<b>Qanday ishlataman?</b>\n\n"
        "1️⃣ <b>/qidir</b> — panel ochiladi. Qayerdan, qayerga va qaysi kun — tanlang.\n"
        "2️⃣ <b>🔍 Hozir qidirish</b> — 4 ta saytdan narx keladi (~1 daqiqa).\n"
        "3️⃣ <b>🔔 Kuzatuvga qo'shish</b> — kuniga 2 marta o'zim tekshirib, narx tushsa yozaman.\n\n"
        "<b>Buyruqlar:</b>\n"
        "/qidir — qidiruv paneli\n"
        "/list — kuzatuvlarim\n"
        "/remove 3 — kuzatuvni o'chirish\n"
        "/sozlama — til, valyuta, davlat\n"
        "/help — shu yordam\n\n"
        "🔁 Borish-qaytish uchun panelda <b>🔁 Qaytish qo'shish</b> tugmasini bosing — "
        "ikki yo'nalish birga narxlanadi, alohida ikki chipta emas.\n\n"
        "<b>Kuzatuvni ochsangiz</b> (/list → yo'nalish ustiga bosing):\n"
        "📉 <b>Narx tarixi</b> — narx ko'tarilyaptimi yoki tushyaptimi, grafik bilan. "
        "Hozir olish kerakmi yoki kutish arziydimi — aytib beraman.\n"
        "🔥 <b>Narx signali</b> — siz aytgan narxdan pastga tushsa alohida ogohlantiraman.\n"
        "⏸ <b>Pauza</b> — vaqtincha to'xtatish. Tarix saqlanadi, o'chirmang.\n\n"
        "Tez yo'l: <code>/add ICN TAS 2026-08-15 2026-08-29</code>\n\n"
        "<i>Narxlar saytlardan real vaqtda olinadi, lekin bilet sotib olingunicha "
        "o'zgarishi mumkin — bu kafolat emas, taqqoslash.</i>"
    ),
    # --- panel ---
    "panel_title": "🎫 <b>Qidiruv paneli</b>",
    "panel_route": "{origin} → {destination}",
    "panel_date": "📅 {date}",
    "panel_money": "💱 {market} · {currency}",
    "panel_hint": "Tugmalardan o'zgartiring, keyin 🔍 bosing.",
    "panel_return": "🔁 Qaytish: {date}",
    "panel_oneway": "➡️ Faqat borish",
    "btn_oneway": "➡️ Faqat borish",
    "btn_roundtrip": "🔁 Qaytish qo'shish",
    "btn_clear_return": "✖️ Qaytishni olib tashlash",
    "pick_return": "Qaysi kuni qaytasiz?",
    "err_return_before": "Qaytish sanasi borish sanasidan keyin bo'lsin.",
    "results_return": "qaytish {date}",
    "btn_from": "📍 Qayerdan",
    "btn_to": "🎯 Qayerga",
    "btn_date": "📅 Sana",
    "btn_swap": "🔄 Almashtirish",
    "btn_search": "🔍 Hozir qidirish",
    "btn_watch": "🔔 Kuzatuvga qo'shish",
    "btn_watches": "📋 Kuzatuvlarim",
    "btn_settings": "⚙️ Sozlamalar",
    "btn_help": "❓ Yordam",
    "btn_back": "⬅️ Orqaga",
    "btn_panel": "🎫 Panelga",
    "btn_type": "✏️ O'zim yozaman",
    "btn_other_date": "✏️ Boshqa sana",
    "btn_refresh": "🔄 Yangilash",
    "btn_more": "🌍 Boshqa davlatlar",
    "btn_popular": "⭐️ Ommabop",
    "btn_cheapest_days": "📆 Arzon kunlar",
    # --- pickers ---
    "ask_from": "📍 Qayerdan uchasiz?",
    "ask_to": "🎯 Qayerga uchasiz?",
    "ask_date": "📅 Qaysi kun?",
    "ask_region": "🌍 Qaysi mintaqa?",
    "type_airport": "✏️ Shahar nomini yoki IATA kodini yozing:\n<code>Dubay</code> · <code>DXB</code>",
    "type_date": "✏️ Sanani yozing:\n<code>2026-08-15</code>",
    "found_airports": "🔎 <b>{query}</b> bo'yicha topildi:",
    "no_airports": "🤷 <b>{query}</b> topilmadi. Shahar nomini boshqacha yozing yoki 3 harfli IATA kodini kiriting (masalan <code>DXB</code>).",
    "bad_date": "Sana noto'g'ri. Format: <code>2026-08-15</code>",
    "past_date": "Bu kun o'tib ketgan — kelajakdagi sanani tanlang.",
    "too_far": "Juda uzoq sana — aviakompaniyalar odatda 11 oygacha sotadi.",
    "same_city": "Uchish va qo'nish shahri bir xil bo'lmasin.",
    "saved": "✅ Saqlandi",
    # --- search ---
    "searching": "⏳ <b>{route}</b> · {date}\n4 ta saytdan qidiryapman, ~1 daqiqa…",
    "search_failed": "⚠️ Qidiruvda xatolik. Birozdan keyin qayta urinib ko'ring.",
    "search_empty": "😕 <b>{route}</b> · {date} — bu kun uchun reys topilmadi.\nBoshqa sanani tanlab ko'ring.",
    "results_head": "🎫 <b>{route}</b> · {date}",
    "results_foot": "<i>Narx bosilganda saytga o'tasiz. Narx sotib olishgacha o'zgarishi mumkin.</i>",
    "cooldown": "⏳ Biroz kuting — {seconds} soniyadan keyin yana qidira olasiz.",
    # --- watches ---
    "watch_added": "🔔 <b>{route}</b> · {date} kuzatuvga qo'shildi.\nKuniga 2 marta tekshirib turaman.",
    "watch_exists": "Bu yo'nalish allaqachon kuzatuvda",
    "watch_removed": "🗑 Kuzatuv o'chirildi",
    "watch_none": "Sizda kuzatuv yo'q.\n<b>/qidir</b> orqali yo'nalish tanlab, 🔔 tugmasini bosing.",
    "watch_list": "📋 <b>Kuzatuvlaringiz:</b>",
    "watch_limit": "Kuzatuvlar chegarasi — {limit} ta. Avval eskisini o'chiring: /list",
    "watch_unknown": "Bunday kuzatuv topilmadi",
    "watch_open": "Kuzatuvni ko'rish uchun ustiga bosing.",
    "watch_detail": "🔔 <b>{route}</b>\n{date}\n\n💱 {market} · {currency}\n{status}{threshold}",
    "status_active": "✅ Kuzatilmoqda — kuniga 2 marta",
    "status_paused": "⏸ Pauzada — xabar yubormayman",
    "watch_paused": "⏸ Pauza qilindi. Tarix saqlanadi.",
    "watch_resumed": "▶️ Yana kuzatilmoqda",
    "thr_line": "\n🔥 Signal: {price} dan past bo'lsa",
    "thr_ask": (
        "🔥 <b>Narx signali</b>\n\nNarx qaysi darajadan pastga tushsa, alohida ogohlantiraman?\n"
        "Tugmani bosing yoki raqam yozing (masalan <code>750000</code>)."
    ),
    "thr_set": "🔥 Signal o'rnatildi: {price} dan past",
    "thr_cleared": "Signal o'chirildi",
    "thr_bad": "Faqat raqam yozing, masalan <code>750000</code>",
    "btn_thr_off": "✖️ Signalni o'chirish",
    "btn_history": "📉 Narx tarixi",
    "btn_share": "📤 Ulashish",
    "btn_other_route": "🌍 Boshqa yo'nalish",
    "btn_threshold": "🔥 Narx signali",
    "btn_pause": "⏸ Pauza",
    "btn_resume": "▶️ Davom etish",
    "btn_delete": "🗑 O'chirish",
    "hist_title": "📉 <b>Narx tarixi</b>",
    "hist_thin": (
        "Hali tarix yetarli emas — kamida ikki marta tekshirilishi kerak.\n"
        "Kuniga 2 marta tekshiraman, ertaga grafik paydo bo'ladi."
    ),
    "hist_now": "Hozir: <b>{price}</b>",
    "hist_range": "Eng arzon: {low} · eng qimmat: {high}",
    "hist_flat": "➖ Narx deyarli o'zgarmayapti — kutishning ma'nosi yo'q.",
    "hist_low": "🟢 Hozir eng arzon davri — olish payti.",
    "hist_high": "🔴 Eng arzonidan {percent}% qimmat — kutib turish arziydi.",
    "hist_mid": "🟡 Eng arzonidan {percent}% qimmat — o'rta daraja.",
    # --- last known board (instant, from the database) ---
    "ago_now": "hozir",
    "ago_min": "{n} daqiqa oldin",
    "ago_hour": "{n} soat oldin",
    "ago_day": "{n} kun oldin",
    "checked_at": "🕒 {ago} tekshirilgan:",
    "refreshing": "🔄 Hozirgi narxlar tekshirilmoqda…",
    "no_prices_yet": (
        "Hali narx yig'ilmagan — birinchi tekshiruvdan keyin shu yerda darhol ko'rinadi.\n"
        "Kutmasangiz, 🔍 bilan hozir qidiring."
    ),
    "btn_search_live": "🔍 Hozir qayta qidirish",
    "list_price": "     💰 {price} · {ago}",
    "list_no_price": "     💰 hali tekshirilmagan",
    "remove_format": "Format: <code>/remove 3</code> — raqamni /list dan oling",
    "add_format": "Format: <code>/add ICN TAS 2026-08-15 [qaytish] [narx]</code>",
    "add_ok": "✅ Kuzatuv qo'shildi: <b>{route}</b> · {date}{extra}",
    # --- settings ---
    "settings_title": "⚙️ <b>Sozlamalar</b>\n\n🌐 Til: {lang}\n💱 Valyuta: {currency}\n🏳️ Davlat: {market}\n⏰ Xabar: {times} ({tz})\n\n<i>Davlat — biletni qaysi mamlakatdan sotib olayotganingiz. Narx shunga qarab o'zgaradi.</i>",
    "btn_lang": "🌐 Til",
    "btn_currency": "💱 Valyuta",
    "btn_market": "🏳️ Davlat",
    "ask_lang": "🌐 Tilni tanlang:",
    "ask_currency": "💱 Valyutani tanlang:",
    "ask_market": "🏳️ Biletni qaysi davlatdan sotib olasiz?",
    "market_note": "🏳️ {market} tanlandi, valyuta {currency} ga o'tkazildi.",
    "btn_notify": "⏰ Xabar vaqti",
    "ask_notify": "⏰ Xabar kuniga 2 marta keladi.\n\nErtalabki soatni tanlang — kechqurungisi 12 soatdan keyin.\n\nHozir: <b>{times}</b> ({tz})",
    "notify_saved": "⏰ Endi xabar {times} da keladi.",
    "btn_tz": "🌍 Vaqt zonasi",
    "ask_tz": "🌍 Qaysi mamlakatda yashaysiz? Xabar shu yerdagi soat bo'yicha keladi.\n\nHozir: <b>{tz}</b>",
    "tz_saved": "🌍 Vaqt zonasi: {tz} — xabar {times} da keladi.",
    # --- digest ---
    "digest_head": "🎫 <b>{route}</b> · {date}",
    "nonstop": "✈️ to'g'ridan-to'g'ri",
    "transfers": "🔁 {count} transfer",
    "stops_unknown": "❔ transfer noma'lum",
    "cheaper": "↓ <b>{amount} arzonlashdi</b>",
    "pricier": "↑ {amount} qimmatlashdi",
    "alert": "🔥 <b>ALERT</b> — narx {threshold} dan past!",
    "alert_now": "🎯 <b>Kutgan narxingiz keldi!</b>\n{route} · {date}\nSiz kutgan: {threshold} · Hozir: <b>{price}</b>",
    "deal_post": "🔥 <b>{route}</b> · {date}\n<b>{price}</b> — odatdagidan {percent}% arzon (odatda ~{typical})",
    "deal_foot": "\n<i>Shu yo'nalishni kuzatish uchun</i> 👉 @ticketcatch_bot",
    "inline_ask": "✈️ Yo'nalish yozing",
    "inline_ask_desc": "Masalan: ICN TAS  yoki  ICN TAS 2026-09-25",
    "inline_open": "🔍 Narxni botda ko'rish",
    "inline_open_desc": "{route} — hozir tayyor narx yo'q, bot to'liq qidiradi",
    "inline_open_text": "✈️ <b>{route}</b> · {date}\n\nBu yo'nalish narxini ko'rish 👉 @ticketcatch_bot",
    "inline_footer": '👉 <a href="{url}">Botda bugungi narxni ko\'ring</a>',
    "inline_title": "{route} · {price} dan",
    "inline_desc": "{date} · {airline}",
    "bags": "🧳 {count} ta",
    "bags_none": "🧳 yo'q",
    # --- misc ---
    "stats": "📊 <b>TicketCatch</b>\n\n👤 Foydalanuvchi: {users}\n🔔 Faol kuzatuv: {watches}\n🔍 Qidiruv: {searches}\n💾 Narx yozuvi: {quotes}",
    "region_kr": "🇰🇷 Koreya",
    "region_uz": "🇺🇿 O'zbekiston",
    "region_cis": "🌏 MDH",
    "region_asia": "🌏 Osiyo",
    "region_gulf": "🕌 Yaqin Sharq",
    "region_eu": "🇪🇺 Yevropa",
    "region_am": "🌎 Amerika",
    "region_af": "🌍 Afrika · Okeaniya",
}

RU: dict[str, str] = {
    "start": (
        "✈️ <b>TicketCatch</b> — собираю цены с 4 сайтов в один список, от самой дешёвой.\n\n"
        "<b>Куда летим?</b> Выберите — найду цену прямо сейчас 👇"
    ),
    "start_deeplink": "✈️ <b>{route}</b> · {date}\n\nИщу цену…",
    "help": (
        "<b>Как пользоваться?</b>\n\n"
        "1️⃣ <b>/qidir</b> — откроется панель. Выберите откуда, куда и когда.\n"
        "2️⃣ <b>🔍 Искать сейчас</b> — цены с 4 сайтов (~1 минута).\n"
        "3️⃣ <b>🔔 Следить</b> — проверяю 2 раза в день и пишу, когда подешевеет.\n\n"
        "<b>Команды:</b>\n"
        "/qidir — панель поиска\n"
        "/list — мои маршруты\n"
        "/remove 3 — удалить маршрут\n"
        "/sozlama — язык, валюта, страна\n"
        "/help — эта справка\n\n"
        "🔁 Для «туда-обратно» нажмите <b>🔁 Добавить обратно</b> в панели — оба плеча "
        "считаются вместе, а не как два отдельных билета.\n\n"
        "<b>Откройте маршрут</b> (/list → нажмите на него):\n"
        "📉 <b>История цены</b> — график: дорожает или дешевеет. Скажу, брать сейчас "
        "или подождать.\n"
        "🔥 <b>Сигнал по цене</b> — предупрежу отдельно, когда упадёт ниже вашей суммы.\n"
        "⏸ <b>Пауза</b> — временно остановить. История сохраняется, не удаляйте.\n\n"
        "Быстро: <code>/add ICN TAS 2026-08-15 2026-08-29</code>\n\n"
        "<i>Цены берутся с сайтов в реальном времени, но могут измениться до покупки — "
        "это сравнение, а не гарантия.</i>"
    ),
    "panel_title": "🎫 <b>Панель поиска</b>",
    "panel_route": "{origin} → {destination}",
    "panel_date": "📅 {date}",
    "panel_money": "💱 {market} · {currency}",
    "panel_hint": "Измените кнопками, затем нажмите 🔍.",
    "panel_return": "🔁 Обратно: {date}",
    "panel_oneway": "➡️ Только туда",
    "btn_oneway": "➡️ Только туда",
    "btn_roundtrip": "🔁 Добавить обратно",
    "btn_clear_return": "✖️ Убрать обратный",
    "pick_return": "Когда обратно?",
    "err_return_before": "Обратная дата должна быть позже даты вылета.",
    "results_return": "обратно {date}",
    "btn_from": "📍 Откуда",
    "btn_to": "🎯 Куда",
    "btn_date": "📅 Дата",
    "btn_swap": "🔄 Поменять",
    "btn_search": "🔍 Искать сейчас",
    "btn_watch": "🔔 Следить",
    "btn_watches": "📋 Мои маршруты",
    "btn_settings": "⚙️ Настройки",
    "btn_help": "❓ Помощь",
    "btn_back": "⬅️ Назад",
    "btn_panel": "🎫 К панели",
    "btn_type": "✏️ Ввести вручную",
    "btn_other_date": "✏️ Другая дата",
    "btn_refresh": "🔄 Обновить",
    "btn_more": "🌍 Другие страны",
    "btn_popular": "⭐️ Популярные",
    "btn_cheapest_days": "📆 Дешёвые дни",
    "ask_from": "📍 Откуда летите?",
    "ask_to": "🎯 Куда летите?",
    "ask_date": "📅 Какой день?",
    "ask_region": "🌍 Какой регион?",
    "type_airport": "✏️ Напишите город или код IATA:\n<code>Дубай</code> · <code>DXB</code>",
    "type_date": "✏️ Напишите дату:\n<code>2026-08-15</code>",
    "found_airports": "🔎 Найдено по запросу <b>{query}</b>:",
    "no_airports": "🤷 По запросу <b>{query}</b> ничего нет. Напишите город иначе или введите 3-буквенный код IATA (например <code>DXB</code>).",
    "bad_date": "Неверная дата. Формат: <code>2026-08-15</code>",
    "past_date": "Этот день уже прошёл — выберите будущую дату.",
    "too_far": "Слишком далёкая дата — авиакомпании обычно продают на 11 месяцев вперёд.",
    "same_city": "Город вылета и прилёта не могут совпадать.",
    "saved": "✅ Сохранено",
    "searching": "⏳ <b>{route}</b> · {date}\nИщу на 4 сайтах, ~1 минута…",
    "search_failed": "⚠️ Ошибка поиска. Попробуйте чуть позже.",
    "search_empty": "😕 <b>{route}</b> · {date} — рейсов на этот день нет.\nПопробуйте другую дату.",
    "results_head": "🎫 <b>{route}</b> · {date}",
    "results_foot": "<i>Нажмите на цену, чтобы перейти на сайт. Цена может измениться до покупки.</i>",
    "cooldown": "⏳ Подождите — следующий поиск через {seconds} сек.",
    "watch_added": "🔔 <b>{route}</b> · {date} — слежу.\nПроверяю 2 раза в день.",
    "watch_exists": "Этот маршрут уже отслеживается",
    "watch_removed": "🗑 Маршрут удалён",
    "watch_none": "У вас нет маршрутов.\nОткройте <b>/qidir</b> и нажмите 🔔.",
    "watch_list": "📋 <b>Ваши маршруты:</b>",
    "watch_limit": "Лимит маршрутов — {limit}. Сначала удалите старый: /list",
    "watch_unknown": "Такой маршрут не найден",
    "watch_open": "Нажмите на маршрут, чтобы открыть его.",
    "watch_detail": "🔔 <b>{route}</b>\n{date}\n\n💱 {market} · {currency}\n{status}{threshold}",
    "status_active": "✅ Отслеживается — 2 раза в день",
    "status_paused": "⏸ На паузе — сообщений не будет",
    "watch_paused": "⏸ Поставлено на паузу. История сохранится.",
    "watch_resumed": "▶️ Снова отслеживается",
    "thr_line": "\n🔥 Сигнал: ниже {price}",
    "thr_ask": (
        "🔥 <b>Сигнал по цене</b>\n\nНиже какой цены предупредить отдельно?\n"
        "Нажмите кнопку или введите число (например <code>750000</code>)."
    ),
    "thr_set": "🔥 Сигнал установлен: ниже {price}",
    "thr_cleared": "Сигнал отключён",
    "thr_bad": "Введите только число, например <code>750000</code>",
    "btn_thr_off": "✖️ Отключить сигнал",
    "btn_history": "📉 История цены",
    "btn_share": "📤 Поделиться",
    "btn_other_route": "🌍 Другой маршрут",
    "btn_threshold": "🔥 Сигнал по цене",
    "btn_pause": "⏸ Пауза",
    "btn_resume": "▶️ Продолжить",
    "btn_delete": "🗑 Удалить",
    "hist_title": "📉 <b>История цены</b>",
    "hist_thin": (
        "Истории пока мало — нужно хотя бы две проверки.\n"
        "Проверяю 2 раза в день, завтра появится график."
    ),
    "hist_now": "Сейчас: <b>{price}</b>",
    "hist_range": "Минимум: {low} · максимум: {high}",
    "hist_flat": "➖ Цена почти не меняется — ждать нет смысла.",
    "hist_low": "🟢 Сейчас самая низкая цена — можно брать.",
    "hist_high": "🔴 На {percent}% дороже минимума — стоит подождать.",
    "hist_mid": "🟡 На {percent}% дороже минимума — средний уровень.",
    # --- last known board (instant, from the database) ---
    "ago_now": "только что",
    "ago_min": "{n} мин назад",
    "ago_hour": "{n} ч назад",
    "ago_day": "{n} дн назад",
    "checked_at": "🕒 Проверено {ago}:",
    "refreshing": "🔄 Проверяем актуальные цены…",
    "no_prices_yet": (
        "Цены ещё не собраны — после первой проверки появятся здесь сразу.\n"
        "Не хотите ждать — нажмите 🔍."
    ),
    "btn_search_live": "🔍 Проверить сейчас",
    "list_price": "     💰 {price} · {ago}",
    "list_no_price": "     💰 ещё не проверено",
    "remove_format": "Формат: <code>/remove 3</code> — номер возьмите из /list",
    "add_format": "Формат: <code>/add ICN TAS 2026-08-15 [обратно] [цена]</code>",
    "add_ok": "✅ Маршрут добавлен: <b>{route}</b> · {date}{extra}",
    "settings_title": "⚙️ <b>Настройки</b>\n\n🌐 Язык: {lang}\n💱 Валюта: {currency}\n🏳️ Страна: {market}\n⏰ Сообщения: {times} ({tz})\n\n<i>Страна — откуда вы покупаете билет. От неё зависит цена.</i>",
    "btn_lang": "🌐 Язык",
    "btn_currency": "💱 Валюта",
    "btn_market": "🏳️ Страна",
    "ask_lang": "🌐 Выберите язык:",
    "ask_currency": "💱 Выберите валюту:",
    "ask_market": "🏳️ Из какой страны покупаете билет?",
    "market_note": "🏳️ Выбрано: {market}, валюта переключена на {currency}.",
    "btn_notify": "⏰ Время сообщений",
    "ask_notify": "⏰ Сообщения приходят 2 раза в день.\n\nВыберите утренний час — вечерний будет через 12 часов.\n\nСейчас: <b>{times}</b> ({tz})",
    "notify_saved": "⏰ Теперь сообщения приходят в {times}.",
    "btn_tz": "🌍 Часовой пояс",
    "ask_tz": "🌍 В какой стране вы живёте? Время считается по ней.\n\nСейчас: <b>{tz}</b>",
    "tz_saved": "🌍 Часовой пояс: {tz} — сообщения в {times}.",
    "digest_head": "🎫 <b>{route}</b> · {date}",
    "nonstop": "✈️ без пересадок",
    "transfers": "🔁 {count} пересадка",
    "stops_unknown": "❔ пересадки неизвестны",
    "cheaper": "↓ <b>дешевле на {amount}</b>",
    "pricier": "↑ дороже на {amount}",
    "alert": "🔥 <b>ALERT</b> — цена ниже {threshold}!",
    "alert_now": "🎯 <b>Ваша цена наступила!</b>\n{route} · {date}\nВы ждали: {threshold} · Сейчас: <b>{price}</b>",
    "deal_post": "🔥 <b>{route}</b> · {date}\n<b>{price}</b> — на {percent}% дешевле обычного (обычно ~{typical})",
    "deal_foot": "\n<i>Следить за этим направлением</i> 👉 @ticketcatch_bot",
    "inline_ask": "✈️ Введите направление",
    "inline_ask_desc": "Например: ICN TAS  или  ICN TAS 2026-09-25",
    "inline_open": "🔍 Посмотреть цену в боте",
    "inline_open_desc": "{route} — готовой цены нет, бот выполнит полный поиск",
    "inline_open_text": "✈️ <b>{route}</b> · {date}\n\nПосмотреть цену 👉 @ticketcatch_bot",
    "inline_footer": '👉 <a href="{url}">Посмотреть сегодняшнюю цену в боте</a>',
    "inline_title": "{route} · от {price}",
    "inline_desc": "{date} · {airline}",
    "bags": "🧳 {count} шт",
    "bags_none": "🧳 нет",
    "stats": "📊 <b>TicketCatch</b>\n\n👤 Пользователей: {users}\n🔔 Маршрутов: {watches}\n🔍 Поисков: {searches}\n💾 Записей цен: {quotes}",
    "region_kr": "🇰🇷 Корея",
    "region_uz": "🇺🇿 Узбекистан",
    "region_cis": "🌏 СНГ",
    "region_asia": "🌏 Азия",
    "region_gulf": "🕌 Ближний Восток",
    "region_eu": "🇪🇺 Европа",
    "region_am": "🌎 Америка",
    "region_af": "🌍 Африка · Океания",
}

EN: dict[str, str] = {
    "start": (
        "✈️ <b>TicketCatch</b> — prices from 4 sites in one list, cheapest first.\n\n"
        "<b>Where to?</b> Pick a route and I'll price it now 👇"
    ),
    "start_deeplink": "✈️ <b>{route}</b> · {date}\n\nSearching…",
    "help": (
        "<b>How to use it</b>\n\n"
        "1️⃣ <b>/qidir</b> — opens the panel. Pick from, to and the day.\n"
        "2️⃣ <b>🔍 Search now</b> — prices from 4 sites (~1 minute).\n"
        "3️⃣ <b>🔔 Watch</b> — I check twice a day and write when it gets cheaper.\n\n"
        "<b>Commands:</b>\n"
        "/qidir — search panel\n"
        "/list — my watches\n"
        "/remove 3 — delete a watch\n"
        "/sozlama — language, currency, country\n"
        "/help — this help\n\n"
        "🔁 For a round trip press <b>🔁 Add return</b> in the panel — both legs are priced "
        "together, which is not the same as two separate tickets.\n\n"
        "<b>Open a watch</b> (/list → tap the route):\n"
        "📉 <b>Price history</b> — a graph of where the fare has been. I say whether to book "
        "now or wait.\n"
        "🔥 <b>Price alert</b> — a separate warning when it drops below your number.\n"
        "⏸ <b>Pause</b> — stop it for a while. The history is kept, so don't delete it.\n\n"
        "Shortcut: <code>/add ICN TAS 2026-08-15 2026-08-29</code>\n\n"
        "<i>Prices are read from the sites live, but can change before you buy — "
        "this is a comparison, not a guarantee.</i>"
    ),
    "panel_title": "🎫 <b>Search panel</b>",
    "panel_route": "{origin} → {destination}",
    "panel_date": "📅 {date}",
    "panel_money": "💱 {market} · {currency}",
    "panel_hint": "Change it with the buttons, then press 🔍.",
    "panel_return": "🔁 Return: {date}",
    "panel_oneway": "➡️ One way",
    "btn_oneway": "➡️ One way",
    "btn_roundtrip": "🔁 Add return",
    "btn_clear_return": "✖️ Remove return",
    "pick_return": "When are you coming back?",
    "err_return_before": "The return date must be after the departure date.",
    "results_return": "return {date}",
    "btn_from": "📍 From",
    "btn_to": "🎯 To",
    "btn_date": "📅 Date",
    "btn_swap": "🔄 Swap",
    "btn_search": "🔍 Search now",
    "btn_watch": "🔔 Watch this",
    "btn_watches": "📋 My watches",
    "btn_settings": "⚙️ Settings",
    "btn_help": "❓ Help",
    "btn_back": "⬅️ Back",
    "btn_panel": "🎫 Panel",
    "btn_type": "✏️ Type it",
    "btn_other_date": "✏️ Another date",
    "btn_refresh": "🔄 Refresh",
    "btn_more": "🌍 More countries",
    "btn_popular": "⭐️ Popular",
    "btn_cheapest_days": "📆 Cheapest days",
    "ask_from": "📍 Flying from?",
    "ask_to": "🎯 Flying to?",
    "ask_date": "📅 Which day?",
    "ask_region": "🌍 Which region?",
    "type_airport": "✏️ Type a city or IATA code:\n<code>Dubai</code> · <code>DXB</code>",
    "type_date": "✏️ Type the date:\n<code>2026-08-15</code>",
    "found_airports": "🔎 Found for <b>{query}</b>:",
    "no_airports": "🤷 Nothing found for <b>{query}</b>. Try another spelling, or type the 3-letter IATA code (e.g. <code>DXB</code>).",
    "bad_date": "Bad date. Format: <code>2026-08-15</code>",
    "past_date": "That day has passed — pick a future date.",
    "too_far": "Too far ahead — airlines usually sell 11 months out.",
    "same_city": "Origin and destination can't be the same.",
    "saved": "✅ Saved",
    "searching": "⏳ <b>{route}</b> · {date}\nSearching 4 sites, ~1 minute…",
    "search_failed": "⚠️ Search failed. Please try again shortly.",
    "search_empty": "😕 <b>{route}</b> · {date} — no flights found for that day.\nTry another date.",
    "results_head": "🎫 <b>{route}</b> · {date}",
    "results_foot": "<i>Tap a price to open the site. Prices can change before purchase.</i>",
    "cooldown": "⏳ Please wait — you can search again in {seconds}s.",
    "watch_added": "🔔 Watching <b>{route}</b> · {date}.\nI'll check it twice a day.",
    "watch_exists": "You're already watching this route",
    "watch_removed": "🗑 Watch removed",
    "watch_none": "You have no watches.\nOpen <b>/qidir</b> and press 🔔.",
    "watch_list": "📋 <b>Your watches:</b>",
    "watch_limit": "Watch limit is {limit}. Remove an old one first: /list",
    "watch_unknown": "No such watch",
    "watch_open": "Tap a route to open it.",
    "watch_detail": "🔔 <b>{route}</b>\n{date}\n\n💱 {market} · {currency}\n{status}{threshold}",
    "status_active": "✅ Watching — twice a day",
    "status_paused": "⏸ Paused — no messages",
    "watch_paused": "⏸ Paused. The history is kept.",
    "watch_resumed": "▶️ Watching again",
    "thr_line": "\n🔥 Alert: below {price}",
    "thr_ask": (
        "🔥 <b>Price alert</b>\n\nBelow which price should I warn you separately?\n"
        "Tap a button or type a number (for example <code>750000</code>)."
    ),
    "thr_set": "🔥 Alert set: below {price}",
    "thr_cleared": "Alert switched off",
    "thr_bad": "Type just a number, for example <code>750000</code>",
    "btn_thr_off": "✖️ Switch the alert off",
    "btn_history": "📉 Price history",
    "btn_share": "📤 Share",
    "btn_other_route": "🌍 Another route",
    "btn_threshold": "🔥 Price alert",
    "btn_pause": "⏸ Pause",
    "btn_resume": "▶️ Resume",
    "btn_delete": "🗑 Delete",
    "hist_title": "📉 <b>Price history</b>",
    "hist_thin": (
        "Not enough history yet — it takes at least two checks.\n"
        "I check twice a day, so the graph shows up tomorrow."
    ),
    "hist_now": "Now: <b>{price}</b>",
    "hist_range": "Lowest: {low} · highest: {high}",
    "hist_flat": "➖ The price barely moves — waiting gains nothing.",
    "hist_low": "🟢 This is the cheapest it has been — a good time to book.",
    "hist_high": "🔴 {percent}% above the lowest seen — worth waiting.",
    "hist_mid": "🟡 {percent}% above the lowest seen — middle of the range.",
    # --- last known board (instant, from the database) ---
    "ago_now": "just now",
    "ago_min": "{n} min ago",
    "ago_hour": "{n}h ago",
    "ago_day": "{n}d ago",
    "checked_at": "🕒 Checked {ago}:",
    "refreshing": "🔄 Checking today's prices…",
    "no_prices_yet": (
        "No prices collected yet — after the first check they show up here instantly.\n"
        "If you don't want to wait, press 🔍."
    ),
    "btn_search_live": "🔍 Search again now",
    "list_price": "     💰 {price} · {ago}",
    "list_no_price": "     💰 not checked yet",
    "remove_format": "Format: <code>/remove 3</code> — take the number from /list",
    "add_format": "Format: <code>/add ICN TAS 2026-08-15 [return] [price]</code>",
    "add_ok": "✅ Watch added: <b>{route}</b> · {date}{extra}",
    "settings_title": "⚙️ <b>Settings</b>\n\n🌐 Language: {lang}\n💱 Currency: {currency}\n🏳️ Country: {market}\n⏰ Digest: {times} ({tz})\n\n<i>Country is where you buy the ticket. The fare itself depends on it.</i>",
    "btn_lang": "🌐 Language",
    "btn_currency": "💱 Currency",
    "btn_market": "🏳️ Country",
    "ask_lang": "🌐 Choose a language:",
    "ask_currency": "💱 Choose a currency:",
    "ask_market": "🏳️ Which country do you buy from?",
    "market_note": "🏳️ {market} selected, currency switched to {currency}.",
    "btn_notify": "⏰ Delivery time",
    "ask_notify": "⏰ Your digest arrives twice a day.\n\nPick the morning hour — the evening one follows 12 hours later.\n\nNow: <b>{times}</b> ({tz})",
    "notify_saved": "⏰ Your digest now arrives at {times}.",
    "btn_tz": "🌍 Time zone",
    "ask_tz": "🌍 Which country do you live in? The delivery hour follows its clock.\n\nNow: <b>{tz}</b>",
    "tz_saved": "🌍 Time zone: {tz} — digest at {times}.",
    "digest_head": "🎫 <b>{route}</b> · {date}",
    "nonstop": "✈️ nonstop",
    "transfers": "🔁 {count} stop",
    "stops_unknown": "❔ stops unknown",
    "cheaper": "↓ <b>{amount} cheaper</b>",
    "pricier": "↑ {amount} more expensive",
    "alert": "🔥 <b>ALERT</b> — price is below {threshold}!",
    "alert_now": "🎯 <b>Your price is here!</b>\n{route} · {date}\nYou wanted: {threshold} · Now: <b>{price}</b>",
    "deal_post": "🔥 <b>{route}</b> · {date}\n<b>{price}</b> — {percent}% below the usual (normally ~{typical})",
    "deal_foot": "\n<i>Track this route</i> 👉 @ticketcatch_bot",
    "inline_ask": "✈️ Type a route",
    "inline_ask_desc": "For example: ICN TAS  or  ICN TAS 2026-09-25",
    "inline_open": "🔍 See the price in the bot",
    "inline_open_desc": "{route} — no price ready, the bot will run a full search",
    "inline_open_text": "✈️ <b>{route}</b> · {date}\n\nSee this route 👉 @ticketcatch_bot",
    "inline_footer": '👉 <a href="{url}">See today\'s price in the bot</a>',
    "inline_title": "{route} · from {price}",
    "inline_desc": "{date} · {airline}",
    "bags": "🧳 {count}",
    "bags_none": "🧳 none",
    "stats": "📊 <b>TicketCatch</b>\n\n👤 Users: {users}\n🔔 Active watches: {watches}\n🔍 Searches: {searches}\n💾 Price rows: {quotes}",
    "region_kr": "🇰🇷 Korea",
    "region_uz": "🇺🇿 Uzbekistan",
    "region_cis": "🌏 CIS",
    "region_asia": "🌏 Asia",
    "region_gulf": "🕌 Middle East",
    "region_eu": "🇪🇺 Europe",
    "region_am": "🌎 Americas",
    "region_af": "🌍 Africa · Oceania",
}

LANGS: dict[str, dict[str, str]] = {"uz": UZ, "ru": RU, "en": EN}

# Country names for the point-of-sale picker. Kept out of the tables above because they are data
# for money.MARKETS, not interface copy, and the placeholder test would have nothing to check.
COUNTRIES: dict[str, dict[str, str]] = {
    "uz": {
        "kr": "Koreya",
        "uz": "O'zbekiston",
        "us": "AQSH",
        "ru": "Rossiya",
        "kz": "Qozog'iston",
        "tr": "Turkiya",
        "ae": "BAA",
        "de": "Germaniya",
        "gb": "Buyuk Britaniya",
        "jp": "Yaponiya",
    },
    "ru": {
        "kr": "Корея",
        "uz": "Узбекистан",
        "us": "США",
        "ru": "Россия",
        "kz": "Казахстан",
        "tr": "Турция",
        "ae": "ОАЭ",
        "de": "Германия",
        "gb": "Великобритания",
        "jp": "Япония",
    },
    "en": {
        "kr": "Korea",
        "uz": "Uzbekistan",
        "us": "USA",
        "ru": "Russia",
        "kz": "Kazakhstan",
        "tr": "Turkey",
        "ae": "UAE",
        "de": "Germany",
        "gb": "United Kingdom",
        "jp": "Japan",
    },
}


def country(code: str, lang: str) -> str:
    return COUNTRIES.get(normalize(lang), COUNTRIES["uz"]).get(code.lower(), code.upper())


def normalize(lang: str | None) -> str:
    """Telegram sends things like 'ru-RU' or 'uz'; anything we don't speak becomes the default."""
    if not lang:
        return DEFAULT
    code = lang.split("-")[0].lower()
    return code if code in LANGS else DEFAULT


def t(lang: str, key: str, /, **kwargs) -> str:
    """Translate. Falls back to Uzbek, then to the key itself — never crashes a handler.

    lang and key are positional-only on purpose: a translation is free to contain a {lang} or
    {key} placeholder, and without the `/` that kwarg collides with this function's own parameter
    and raises TypeError. That is exactly how the settings screen died — the one screen whose text
    naturally says "Language: {lang}"."""
    table = LANGS.get(normalize(lang), UZ)
    text = table.get(key) or UZ.get(key) or key
    if not kwargs:
        return text
    try:
        return text.format(**kwargs)
    except (KeyError, IndexError):  # a translation with a stale placeholder must not break a reply
        return text


def day_label(day: date, lang: str) -> str:
    """'15 avg (Sha)' — short enough for a two-column keyboard."""
    code = normalize(lang)
    return f"{day.day} {MONTHS[code][day.month - 1]} ({WEEKDAYS[code][day.weekday()]})"


MINUTE = 60
HOUR = 3600
DAY = 86400
JUST_NOW = 120  # under two minutes, "1 minute ago" is noise — it may as well be now


def ago_label(seconds: float, lang: str) -> str:
    """'3 soat oldin'. How stale a stored price is, in the unit the user thinks in.

    Shown next to every price we did not fetch just now, because a price without its age is a claim
    rather than an observation."""
    seconds = max(seconds, 0)
    if seconds < JUST_NOW:
        return t(lang, "ago_now")
    if seconds < HOUR:
        return t(lang, "ago_min", n=int(seconds // MINUTE))
    if seconds < DAY:
        return t(lang, "ago_hour", n=int(seconds // HOUR))
    return t(lang, "ago_day", n=int(seconds // DAY))
