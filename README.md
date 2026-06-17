# Telegram Online Savdo Boti - Walkthrough & Setup Guide

Ushbu bot Telegram guruhlari va shaxsiy chatlar orqali online savdolarni tashkil etish, elonlar joylash, xaridlarni ro'yxatdan o'tkazish hamda cheklarni tekshirish tizimini to'liq avtomatlashtiradi.

---

## 🛠 Yaratilgan Fayllar va Tuzilishi

1. [requirements.txt](file:///home/sirojiddin/code/Munacollection/requirements.txt): Bot ishlashi uchun kerakli kutubxona (`python-telegram-bot` 20+).
2. [config.py](file:///home/sirojiddin/code/Munacollection/config.py): Bot tokeni, Admin ID-lari, guruh ID-si va karta ma'lumotlari kabi asosiy sozlamalar.
3. [database.py](file:///home/sirojiddin/code/Munacollection/database.py): SQLite ma'lumotlar bazasi orqali foydalanuvchilar, elonlar, buyurtmalar va sozlamalar bilan ishlash.
4. [bot.py](file:///home/sirojiddin/code/Munacollection/bot.py): Botning barcha interfeysi, menyulari, xabar va rasm qabul qiluvchi steyt-mashinasi hamda inline navigatsiyasi.

---

## ⚙️ Ishga Tushirish va Sozlash Bo'yicha Qo'llanma

Botni to'liq ishlatish uchun quyidagi qadamlarni bajaring:

### 1-qadam: Bot Tokenini Olish
- [@BotFather](https://t.me/BotFather) botiga o'ting.
- `/newbot` buyrug'i orqali yangi bot yarating va sizga berilgan **API Token**-ni oling.
- Olingan tokenni [config.py](file:///home/sirojiddin/code/Munacollection/config.py) faylidagi `BOT_TOKEN` o'zgaruvchisiga kiriting yoki muhit o'zgaruvchisi (Environment Variable) sifatida eksport qiling.

### 2-qadam: Admin ID va Username Sozlash
- Telegram ID-ingizni aniqlang (masalan, [@userinfobot](https://t.me/userinfobot) orqali).
- ID raqamingizni [config.py](file:///home/sirojiddin/code/Munacollection/config.py) faylidagi `ADMIN_IDS` ro'yxatiga qo'shing: `ADMIN_IDS = [ sizning_id_raqamingiz ]`.
- Admin username sozlamasini o'zgartiring (masalan, `ADMIN_USERNAME = "@MuniraCollection_Admin"`). Bu username chek yuborgan mijozlarga taqdim etiladi.

### 3-qadam: Guruh ID-sini Aniqlash (GROUP_ID)
Elonlar guruhga avtomatik yuborilishi uchun:
1. Yangi Telegram guruh yarating va **botni guruhga administrator qilib qo'shing** (xabar yozish ruxsati bilan).
2. Guruh ID-sini bilish uchun guruhga biror xabar yozing va u xabarni [@raw_data_bot](https://t.me/raw_data_bot) ga yo'naltiring, yoki bot ishga tushgach, guruhga yozilgan xabarlar orqali loglardan guruh ID-sini oling (guruh ID-lari har doim `-100` bilan boshlanadi).
3. Ushbu ID-ni [config.py](file:///home/sirojiddin/code/Munacollection/config.py)-dagi `GROUP_ID` ga yozing.

### 4-qadam: Botni Ishga Tushirish
Virtual muhitni faollashtiring va botni ishga tushiring:
```bash
source venv/bin/activate
python3 bot.py
```

---

## 📱 Botning Ishlash Logikasi

### 👤 Foydalanuvchilar (Mijozlar) Uchun:
1. **Ro'yxatdan O'tish**: Botga kirganda `Ro'yxatdan o'tish 📱` tugmasini bosib, telefon raqamini yuboradi. Telefon raqami yuborilmaguncha boshqa menyular ko'rinmaydi.
2. **Bozor 🛍**: Foydalanuvchi faol elonlarni birma-bir ko'radi, `⬅️ Oldingi` va `Keyingi ➡️` tugmalari orqali sahifalarni almashtiradi.
3. **Sotib Olish 💳**:
   - Guruhdagi elon tagidagi tugma bosilganda yoki Bozor ichida `Sotib olish 💳` tugmasi bosilganda bot karta raqami va summani chiqaradi.
   - Foydalanuvchi to'lovni qilib, chekni (rasmini) botga yuboradi.
   - Chek yuborilgach, foydalanuvchiga: *"To'lov qabul qilindi. Kuting, admin bilan bog'lanish: @admin_username"* deb ko'rsatiladi.

### 👑 Adminlar Uchun:
1. **Elon Joylashtirish ➕**: Ketma-ket rasm, kelish joyi, kelish muddati, narx va izohni yozadi. Tayyor bo'lgach, bot *Preview* (oldindan ko'rish) ko'rsatib chop etishni so'raydi. Tasdiqlansa, elon bazaga yoziladi va guruhga **"Sotib olish"** inline tugmasi bilan yuboriladi.
2. **Bozor Boshqaruvi 🛍**: Admin bozorni ko'rayotganda har bir elon ostida qo'shimcha `Tahrirlash ✏️` va `O'chirish ❌` tugmalarini ko'radi:
   - **Tahrirlash**: Istalgan maydonni (rasm, narx, izoh va b.) o'zgartirish imkonini beradi. O'zgartirish guruhga yuborilgan xabarni ham avtomatik tahrirlaydi!
   - **O'chirish**: Elonni o'chiradi va uni guruhdagi xabarini ham avtomatik o'chirib yuboradi.
3. **Buyurtmalarni Tekshirish 📝**: Mijoz chek yuborgan zahoti barcha adminlarga mijoz ma'lumotlari, telefon raqami va chek rasmi boradi. Admin tagidagi `Tasdiqlash ✅` yoki `Rad etish ❌` tugmasini bosadi:
   - Tasdiqlansa, mijozga: *"Tabriklaymiz! Buyurtmangiz tasdiqlandi!"* deb xabar boradi.
   - Rad etilsa, mijozga rad etilgani va admin username i jo'natiladi.
4. **Karta Raqami 💳**: Admin karta raqami va karta egasini to'g'ridan-to'g'ri bot orqali o'zgartira oladi.
5. **Statistika 📊**: Jami foydalanuvchilar, faol elonlar, tasdiqlangan va rad etilgan buyurtmalar sonini chiqaradi.

---

## 🔧 Oxirgi Tuzatishlar va Yangilanishlar (Yangilangan)

1. **Callback Queries va Polling Sozlamalari**:
   - Bot webhookdan polling rejimiga o'tgach, Telegram serverida saqlanib qolgan `allowed_updates = ['message']` sozlamasi sababli inline tugmalarni bosganda hech qanday update kelmayotgan edi. Bot ishga tushishida `allowed_updates=Update.ALL_TYPES` parametri qo'shildi.
   * Inline tugmalar bosilganda aylanib (spinner) qolishining oldini olish uchun har qanday xatolik yoki kutilmagan holatlarda ham `callback_query.answer()` chaqirilishini ta'minlovchi `try-except` fallback yechimi joriy etildi.

2. **Bir nechta Rasmlarni Qabul Qilish (Albomlar/Media group)**:
   * Telegram albom rasmlarini alohida-alohida va ketma-ket yuboradi. Bot navbatdagi rasmlar qayta ishlanayotganda steytni bloklab qo'ymasligi uchun asinxron fon vazifasi (`asyncio.create_task`) orqali 3 soniyalik debounce yechimi qo'shildi.
   * Bu admin 3 soniya ichida albom shaklida yuborgan barcha rasmlarni bitta e'longa to'liq yig'ib olishga xizmat qiladi.

3. **Bozorda Karusel (Carousel) Tizimi**:
   * Bozorda ko'p rasmli e'lonlar uchun bitta rasmli oyna ostida **`⬅️ Rasm`** va **`Rasm ➡️`** tugmalari qo'shildi. Bu foydalanuvchiga rasmlarni asinxron tarzda chatni to'ldirmasdan almashtirib ko'rish imkonini beradi.

4. **Guruhga Albom Shaklida Chop Etish va Tahrirlash/O'chirish**:
   * Ko'p rasmli e'lonlar guruhga Telegram albomi shaklida yuboriladi, uning ostiga esa sotib olish tugmasi joylanadi.
   * Bazada barcha rasmlar va tugmalarning xabar ID-lari saqlanadi. E'lon o'chirilganda yoki tahrirlanganda guruhdagi eski albom va tugmalar to'liq o'chirilib, yangisi boshqattan joylanadi.

5. **InputMediaPhoto Immutable Xatoligi**:
   * `python-telegram-bot` 20+ kutubxonasida `InputMediaPhoto` klassining obyekt xususiyatlari (`caption`, `parse_mode`) yaratilgandan so'ng tahrirlab bo'lmasligi sababli yuzaga kelgan xatolik bartaraf etilib, qiymatlar to'g'ridan-to'g'ri klass konstruktorining o'zida uzatildi.
