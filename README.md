# Finora Systems — Oylik va KPI Moduli (Romax Akfa · MoySklad API)

Python Django asosida ishlab chiqilgan to'liq fullstack tizim. MoySklad JSON API 1.2 orqali xodimlarning maoshi, savdo ko'rsatkichlari, ishlab chiqarish hajmi va oylik KPI bonuslarini avtomatlashtirishga mo'ljallangan.

---

## 🌟 Asosiy Imkoniyatlar

1. **MoySklad API Integratsiyasi (Bearer Token)**:
   - Brauzer interfeysidan xavfsiz MoySklad tokenni kiritish va ulanishni tekshirish (`/entity/organization`).
   - Xodimlarni bir bosishda MoySklad'dan import qilish (`/entity/employee`).
   - Sotuvchilar va menejerlarning oylik sotuv faktlarini avtomatik tortish (`/report/profit/byemployee`).
   - Sotuv operatorlarining zakazlar sonini yuklash (`/entity/customerorder`).
   - Kassa va bank chiqimlaridan oylik avanslarni avtomatik hisobga olish (`/entity/cashout`, `/entity/paymentout`).
   - Oy yakunida MoySklad tizimida avtomatik «Начисление зарплаты» xarajat orderi yaratish.

2. **Guruhlar bo'yicha KPI Qoidalari**:
   - **Sotuvchilar**: Plan bajarilishi $\ge 100\%$ bo'lganda, sotuv summasidan 1% bonus.
   - **Sotuv operatorlari**: Plan bajarilishiga ko'ra pog'onali koeffitsient (50% $\to$ 0.8, 80% $\to$ 1.0, 100% $\to$ 1.1, 120% $\to$ 1.2; Baza: 1 500 000 so'm).
   - **Sotuv menejerlari / Rahbarlar**: Sotuv hajmidan pog'onali foiz (50-80% oralig'ida shaxsiy stavka, 80% dan keyin 2%, 100% dan keyin 2%).
   - **Ishlab chiqarish (PVX, Termo, Chempion, Alyuminiy)**: Kategoriya bo'yicha plan, fakt va tarif. Agar plan $\ge 80\%$ bajarilsa: $\text{Bonus} = \frac{\text{Fakt} \times \text{Tarif}}{\text{Kategoriyadagi ishchilar soni}}$.
   - **Boshqa xodimlar**: Qat'iy belgilangan oklad (KPI yo'q).

3. **3 Bosqichli Jarayon**:
   - `1. Plan va qoidalar`: Oylik planlar va tariflarni belgilash, o'sish % bo'yicha kategoriyalar planini hisoblash.
   - `2. Nachisleniya`: Oklad, fakt, bajarilish %, KPI bonus, avanslar va to'lashga qoldiqni hisoblash.
   - `3. Yakunlash`: Oy yakuni hisoboti va MoySklad'ga to'g'ridan-to'g'ri yozish.

---

## 🚀 Ishga Tushirish

### 1. Virtual muhit va bog'liqliklar:
```bash
# Virtual muhitni faollashtirish
.\venv\Scripts\activate

# Paketlarni o'rnatish (kerak bo'lsa)
pip install django requests python-dotenv
```

### 2. Ma'lumotlar bazasini tayyorlash:
```bash
python manage.py migrate
python manage.py seed_data
```

### 3. Serverni ishga tushirish:
```bash
python manage.py runserver 127.0.0.1:8000
```
Brauzerda oching: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

---

## 🔑 MoySklad Tokenni Kiritish
1. Dastur sahifasining yuqori qismidagi **«MoySklad Token»** tugmasini bosing.
2. MoySklad tizimidan olingan API tokenni kiriting (*Настройки → Пользователи → Токены для доступа*).
3. **«Ulanishni tekshirish»** tugmasi orqali token to'g'riligini tasdiqlang.
4. **«Saqlash va Bog'lash»** tugmasini bosing.
5. Endi **«MoySklad'dan yangilash»** tugmasi orqali barcha xodimlar va ko'rsatkichlar MoySklad bazasidan avtomatik yangilanadi!
