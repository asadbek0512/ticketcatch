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
        "✈️ <b>TicketCatch</b> — aviabilet narxlarini kuzatuvchi bot.\n\n"
        "Men bir vaqtda <b>4 ta saytdan</b> narxlarni olaman — Kiwi, Trip.com, Google Flights, "
        "Aviasales — va bitta ro'yxatga jamlab, eng arzonidan boshlab ko'rsataman.\n\n"
        "<b>Nima qila olaman:</b>\n"
        "🔍 Istalgan yo'nalish bo'yicha hozir narx topish\n"
        "🔔 Yo'nalishni kuzatuvga qo'yish — kuniga 3 marta tekshiraman\n"
        "📉 Narx tushsa, o'zim xabar beraman\n"
        "🌍 Dunyoning istalgan aeroporti, o'z valyutangizda\n\n"
        "Boshlash uchun 👇"
    ),
    "help": (
        "<b>Qanday ishlataman?</b>\n\n"
        "1️⃣ <b>/qidir</b> — panel ochiladi. Qayerdan, qayerga va qaysi kun — tanlang.\n"
        "2️⃣ <b>🔍 Hozir qidirish</b> — 4 ta saytdan narx keladi (~1 daqiqa).\n"
        "3️⃣ <b>🔔 Kuzatuvga qo'shish</b> — kuniga 3 marta o'zim tekshirib, narx tushsa yozaman.\n\n"
        "<b>Buyruqlar:</b>\n"
        "/qidir — qidiruv paneli\n"
        "/list — kuzatuvlarim\n"
        "/remove 3 — kuzatuvni o'chirish\n"
        "/sozlama — til, valyuta, davlat\n"
        "/help — shu yordam\n\n"
        "Tez yo'l: <code>/add ICN TAS 2026-08-15</code>\n\n"
        "<i>Narxlar saytlardan real vaqtda olinadi, lekin bilet sotib olingunicha "
        "o'zgarishi mumkin — bu kafolat emas, taqqoslash.</i>"
    ),
    # --- panel ---
    "panel_title": "🎫 <b>Qidiruv paneli</b>",
    "panel_route": "{origin} → {destination}",
    "panel_date": "📅 {date}",
    "panel_money": "💱 {market} · {currency}",
    "panel_hint": "Tugmalardan o'zgartiring, keyin 🔍 bosing.",
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
    "watch_added": "🔔 <b>{route}</b> · {date} kuzatuvga qo'shildi.\nKuniga 3 marta tekshirib turaman.",
    "watch_exists": "Bu yo'nalish allaqachon kuzatuvda",
    "watch_removed": "🗑 Kuzatuv o'chirildi",
    "watch_none": "Sizda kuzatuv yo'q.\n<b>/qidir</b> orqali yo'nalish tanlab, 🔔 tugmasini bosing.",
    "watch_list": "📋 <b>Kuzatuvlaringiz:</b>",
    "watch_limit": "Kuzatuvlar chegarasi — {limit} ta. Avval eskisini o'chiring: /list",
    "watch_unknown": "Bunday kuzatuv topilmadi",
    "remove_format": "Format: <code>/remove 3</code> — raqamni /list dan oling",
    "add_format": "Format: <code>/add ICN TAS 2026-08-15 [narx]</code>",
    "add_ok": "✅ Kuzatuv qo'shildi: <b>{route}</b> · {date}{extra}",
    # --- settings ---
    "settings_title": "⚙️ <b>Sozlamalar</b>\n\n🌐 Til: {lang}\n💱 Valyuta: {currency}\n🏳️ Davlat: {market}\n\n<i>Davlat — biletni qaysi mamlakatdan sotib olayotganingiz. Narx shunga qarab o'zgaradi.</i>",
    "btn_lang": "🌐 Til",
    "btn_currency": "💱 Valyuta",
    "btn_market": "🏳️ Davlat",
    "ask_lang": "🌐 Tilni tanlang:",
    "ask_currency": "💱 Valyutani tanlang:",
    "ask_market": "🏳️ Biletni qaysi davlatdan sotib olasiz?",
    "market_note": "🏳️ {market} tanlandi, valyuta {currency} ga o'tkazildi.",
    # --- digest ---
    "digest_head": "🎫 <b>{route}</b> · {date}",
    "nonstop": "✈️ to'g'ridan-to'g'ri",
    "transfers": "🔁 {count} transfer",
    "stops_unknown": "❔ transfer noma'lum",
    "cheaper": "↓ <b>{amount} arzonlashdi</b>",
    "pricier": "↑ {amount} qimmatlashdi",
    "alert": "🔥 <b>ALERT</b> — narx {threshold} dan past!",
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
        "✈️ <b>TicketCatch</b> — бот, который следит за ценами на авиабилеты.\n\n"
        "Я собираю цены сразу с <b>4 сайтов</b> — Kiwi, Trip.com, Google Flights, Aviasales — "
        "и показываю одним списком, начиная с самого дешёвого.\n\n"
        "<b>Что я умею:</b>\n"
        "🔍 Найти цену по любому маршруту прямо сейчас\n"
        "🔔 Взять маршрут на контроль — проверяю 3 раза в день\n"
        "📉 Сам напишу, когда цена упадёт\n"
        "🌍 Любой аэропорт мира, в вашей валюте\n\n"
        "Начнём 👇"
    ),
    "help": (
        "<b>Как пользоваться?</b>\n\n"
        "1️⃣ <b>/qidir</b> — откроется панель. Выберите откуда, куда и когда.\n"
        "2️⃣ <b>🔍 Искать сейчас</b> — цены с 4 сайтов (~1 минута).\n"
        "3️⃣ <b>🔔 Следить</b> — проверяю 3 раза в день и пишу, когда подешевеет.\n\n"
        "<b>Команды:</b>\n"
        "/qidir — панель поиска\n"
        "/list — мои маршруты\n"
        "/remove 3 — удалить маршрут\n"
        "/sozlama — язык, валюта, страна\n"
        "/help — эта справка\n\n"
        "Быстро: <code>/add ICN TAS 2026-08-15</code>\n\n"
        "<i>Цены берутся с сайтов в реальном времени, но могут измениться до покупки — "
        "это сравнение, а не гарантия.</i>"
    ),
    "panel_title": "🎫 <b>Панель поиска</b>",
    "panel_route": "{origin} → {destination}",
    "panel_date": "📅 {date}",
    "panel_money": "💱 {market} · {currency}",
    "panel_hint": "Измените кнопками, затем нажмите 🔍.",
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
    "watch_added": "🔔 <b>{route}</b> · {date} — слежу.\nПроверяю 3 раза в день.",
    "watch_exists": "Этот маршрут уже отслеживается",
    "watch_removed": "🗑 Маршрут удалён",
    "watch_none": "У вас нет маршрутов.\nОткройте <b>/qidir</b> и нажмите 🔔.",
    "watch_list": "📋 <b>Ваши маршруты:</b>",
    "watch_limit": "Лимит маршрутов — {limit}. Сначала удалите старый: /list",
    "watch_unknown": "Такой маршрут не найден",
    "remove_format": "Формат: <code>/remove 3</code> — номер возьмите из /list",
    "add_format": "Формат: <code>/add ICN TAS 2026-08-15 [цена]</code>",
    "add_ok": "✅ Маршрут добавлен: <b>{route}</b> · {date}{extra}",
    "settings_title": "⚙️ <b>Настройки</b>\n\n🌐 Язык: {lang}\n💱 Валюта: {currency}\n🏳️ Страна: {market}\n\n<i>Страна — откуда вы покупаете билет. От неё зависит цена.</i>",
    "btn_lang": "🌐 Язык",
    "btn_currency": "💱 Валюта",
    "btn_market": "🏳️ Страна",
    "ask_lang": "🌐 Выберите язык:",
    "ask_currency": "💱 Выберите валюту:",
    "ask_market": "🏳️ Из какой страны покупаете билет?",
    "market_note": "🏳️ Выбрано: {market}, валюта переключена на {currency}.",
    "digest_head": "🎫 <b>{route}</b> · {date}",
    "nonstop": "✈️ без пересадок",
    "transfers": "🔁 {count} пересадка",
    "stops_unknown": "❔ пересадки неизвестны",
    "cheaper": "↓ <b>дешевле на {amount}</b>",
    "pricier": "↑ дороже на {amount}",
    "alert": "🔥 <b>ALERT</b> — цена ниже {threshold}!",
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
        "✈️ <b>TicketCatch</b> — a bot that watches flight prices for you.\n\n"
        "I pull prices from <b>4 sites at once</b> — Kiwi, Trip.com, Google Flights, Aviasales — "
        "and show them as one list, cheapest first.\n\n"
        "<b>What I can do:</b>\n"
        "🔍 Find the price for any route right now\n"
        "🔔 Watch a route — I check it 3 times a day\n"
        "📉 Message you when the price drops\n"
        "🌍 Any airport in the world, in your currency\n\n"
        "Let's start 👇"
    ),
    "help": (
        "<b>How to use it</b>\n\n"
        "1️⃣ <b>/qidir</b> — opens the panel. Pick from, to and the day.\n"
        "2️⃣ <b>🔍 Search now</b> — prices from 4 sites (~1 minute).\n"
        "3️⃣ <b>🔔 Watch</b> — I check 3 times a day and write when it gets cheaper.\n\n"
        "<b>Commands:</b>\n"
        "/qidir — search panel\n"
        "/list — my watches\n"
        "/remove 3 — delete a watch\n"
        "/sozlama — language, currency, country\n"
        "/help — this help\n\n"
        "Shortcut: <code>/add ICN TAS 2026-08-15</code>\n\n"
        "<i>Prices are read from the sites live, but can change before you buy — "
        "this is a comparison, not a guarantee.</i>"
    ),
    "panel_title": "🎫 <b>Search panel</b>",
    "panel_route": "{origin} → {destination}",
    "panel_date": "📅 {date}",
    "panel_money": "💱 {market} · {currency}",
    "panel_hint": "Change it with the buttons, then press 🔍.",
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
    "watch_added": "🔔 Watching <b>{route}</b> · {date}.\nI'll check it 3 times a day.",
    "watch_exists": "You're already watching this route",
    "watch_removed": "🗑 Watch removed",
    "watch_none": "You have no watches.\nOpen <b>/qidir</b> and press 🔔.",
    "watch_list": "📋 <b>Your watches:</b>",
    "watch_limit": "Watch limit is {limit}. Remove an old one first: /list",
    "watch_unknown": "No such watch",
    "remove_format": "Format: <code>/remove 3</code> — take the number from /list",
    "add_format": "Format: <code>/add ICN TAS 2026-08-15 [price]</code>",
    "add_ok": "✅ Watch added: <b>{route}</b> · {date}{extra}",
    "settings_title": "⚙️ <b>Settings</b>\n\n🌐 Language: {lang}\n💱 Currency: {currency}\n🏳️ Country: {market}\n\n<i>Country is where you buy the ticket. The fare itself depends on it.</i>",
    "btn_lang": "🌐 Language",
    "btn_currency": "💱 Currency",
    "btn_market": "🏳️ Country",
    "ask_lang": "🌐 Choose a language:",
    "ask_currency": "💱 Choose a currency:",
    "ask_market": "🏳️ Which country do you buy from?",
    "market_note": "🏳️ {market} selected, currency switched to {currency}.",
    "digest_head": "🎫 <b>{route}</b> · {date}",
    "nonstop": "✈️ nonstop",
    "transfers": "🔁 {count} stop",
    "stops_unknown": "❔ stops unknown",
    "cheaper": "↓ <b>{amount} cheaper</b>",
    "pricier": "↑ {amount} more expensive",
    "alert": "🔥 <b>ALERT</b> — price is below {threshold}!",
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


def t(lang: str, key: str, **kwargs) -> str:
    """Translate. Falls back to Uzbek, then to the key itself — never crashes a handler."""
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
