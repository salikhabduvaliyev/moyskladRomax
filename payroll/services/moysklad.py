import logging
import requests
from datetime import datetime
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger(__name__)

class MoySkladService:
    """MoySklad JSON API 1.2 bilan ishlash xizmati (Romax Akfa)"""

    def __init__(self, token=None, base_url="https://api.moysklad.ru/api/remap/1.2"):
        from payroll.models import MoySkladConfig
        config = MoySkladConfig.get_solo()
        self.token = token if token is not None else config.token
        self.base_url = (base_url or config.base_url).rstrip('/')
        self.timeout = 20

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.token.strip()}" if self.token else "",
            "Accept-Encoding": "gzip",
            "Content-Type": "application/json",
        }

    def test_connection(self):
        """MoySklad tokenining to'g'riligini va ulanishni tekshirish"""
        if not self.token:
            return {"success": False, "error": "MoySklad API token kiritilmagan!"}
        
        try:
            url = f"{self.base_url}/entity/organization?limit=1"
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)
            
            if resp.status_code == 200:
                data = resp.json()
                org_name = "Kompaniya"
                if "rows" in data and len(data["rows"]) > 0:
                    org_name = data["rows"][0].get("name", "MoySklad Kompaniyasi")
                return {
                    "success": True,
                    "organization": org_name,
                    "message": f"Muvaffaqiyatli ulandi: {org_name}"
                }
            elif resp.status_code == 401:
                return {"success": False, "error": "MoySklad token noto'g'ri yoki muddati o'tgan (401 Unauthorized)"}
            elif resp.status_code == 403:
                return {"success": False, "error": "Token huquqlari yetarli emas (403 Forbidden)"}
            else:
                return {"success": False, "error": f"MoySklad xatolik qaytardi: {resp.status_code} - {resp.text[:200]}"}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"MoySklad serveriga ulanishda xatolik: {str(e)}"}

    def get_first_organization(self):
        """Birlamchi tashkilot meta ma'lumotlarini olish"""
        url = f"{self.base_url}/entity/organization?limit=1"
        resp = requests.get(url, headers=self.headers, timeout=self.timeout)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("rows"):
                return data["rows"][0]
        return None

    def get_or_create_expense_item(self, item_name="Начисление зарплаты"):
        """Xarajat moddasi (Статья расходов) mavjudligini tekshirish yoki olish"""
        url = f"{self.base_url}/entity/expenseitem?filter=name={item_name}"
        resp = requests.get(url, headers=self.headers, timeout=self.timeout)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("rows"):
                return data["rows"][0]
        fallback_url = f"{self.base_url}/entity/expenseitem?limit=1"
        fallback_resp = requests.get(fallback_url, headers=self.headers, timeout=self.timeout)
        if fallback_resp.status_code == 200:
            data = fallback_resp.json()
            if data.get("rows"):
                return data["rows"][0]
        return None

    def sync_employees(self):
        """
        MoySklad «Моя компания → Сотрудники» (/entity/employee) bo'limidan 
        barcha xodimlarni va ulardagi OKLAD (salary) qiymatini to'liq yuklash.
        """
        if not self.token:
            return {"success": False, "error": "Token kiritilmagan!"}

        from payroll.models import Employee, MoySkladConfig, PayrollItem

        try:
            url = f"{self.base_url}/entity/employee?limit=100&filter=archived=false"
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)
            
            if resp.status_code != 200:
                return {"success": False, "error": f"Xodimlarni yuklashda xatolik ({resp.status_code}): {resp.text[:200]}"}

            data = resp.json()
            rows = data.get("rows", [])
            created_count = 0
            updated_count = 0

            for i, row in enumerate(rows, 1):
                ms_id = row.get("id")
                name = row.get("name", "").strip() or row.get("fullName", "").strip()
                position = (row.get("position", "") or "").strip()
                
                # Texnik "Administrator" akkauntini ajratish
                is_staff_active = (name.lower() != "administrator")

                # OKLAD: MoySklad salary maydonidan olinadi
                raw_salary = row.get("salary")
                oklad_val = 0
                if isinstance(raw_salary, dict):
                    oklad_val = raw_salary.get("value", 0) or 0
                elif isinstance(raw_salary, (int, float)):
                    oklad_val = raw_salary

                oklad_decimal = Decimal(str(oklad_val))

                # Lavozim va ism bo'yicha guruhni aniqlash
                combined_text = f"{name} {position}".lower()
                group = "bosh"
                if "сотувчи" in combined_text or "sotuvchi" in combined_text:
                    group = "sot"
                elif "оператор" in combined_text or "operator" in combined_text:
                    group = "op"
                elif "менеджер" in combined_text or "рахбар" in combined_text or "юритувчи" in combined_text:
                    group = "men"
                elif any(k in combined_text for k in ["цех", "уста", "бригадир", "мастер", "монтаж", "монтажник"]):
                    group = "ish"

                emp, created = Employee.objects.update_or_create(
                    moysklad_id=ms_id,
                    defaults={
                        "name": name,
                        "position": position,
                        "group": group,
                        "oklad": oklad_decimal,
                        "is_active": is_staff_active,
                        "order_num": i
                    }
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

                # Agar faol oy davri bo'lsa, undagi xodim okladini ham yangilash
                PayrollItem.objects.filter(employee=emp).update(
                    oklad=oklad_decimal,
                    group=group,
                    is_active=is_staff_active
                )

            config = MoySkladConfig.get_solo()
            config.last_synced_at = timezone.now()
            config.save()

            return {
                "success": True, 
                "total": len(rows), 
                "created": created_count, 
                "updated": updated_count,
                "message": f"MoySklad «Моя компания → Сотрудники» dan {len(rows)} ta xodim va okladlar yuklandi!"
            }
        except Exception as e:
            logger.exception("Error syncing employees from MoySklad")
            return {"success": False, "error": str(e)}

    def sync_sales_facts(self, date_from, date_to):
        """
        Barcha sotuv ma'lumotlarini MoySklad'dan Token orqali yuklash:
        - Customer Orders:
          * «Шартнома суммаси» atributi (yoki sum)
          * «Сотув оператори» atributi -> operator buyurtmalar soni va summasi
          * «Сотув менеджери» atributi -> menejer sotuv summasi
          * «ПВХ», «ТЕРМО», «Чемпион», «АЛДОХ» -> ishlab chiqarish kategoriyalari fakt hajmi!
        - Demand (Отгрузка) va Retail Demand
        - CashIn va PaymentIn (Savdo tushumlari)
        """
        if not self.token:
            return {"success": False, "error": "Token kiritilmagan!"}

        from payroll.models import Employee, ProductionCategory

        try:
            d_from_str = f"{date_from} 00:00:00"
            d_to_str = f"{date_to} 23:59:59"
            
            # Xodimlar bo'yicha faktlar: {emp_ms_id: {"sales_sum": ..., "order_count": ...}}
            facts = {}

            # Ishlab chiqarish toifalari bo'yicha fakt hajmlar
            production_facts = {
                'PVX': Decimal(0),
                'Termo': Decimal(0),
                'Chempion': Decimal(0),
                'Alyuminiy': Decimal(0),
            }

            def get_or_init(emp_id):
                if emp_id not in facts:
                    facts[emp_id] = {"sales_sum": 0.0, "order_count": 0}
                return facts[emp_id]

            all_employees = list(Employee.objects.all())
            emp_by_name = {e.name.upper(): e for e in all_employees}

            # 1. CUSTOMER ORDERS (Mijoz buyurtmalari)
            try:
                orders_url = f"{self.base_url}/entity/customerorder?filter=moment>={d_from_str};moment<={d_to_str}&limit=100"
                orders_resp = requests.get(orders_url, headers=self.headers, timeout=self.timeout)
                if orders_resp.status_code == 200:
                    for order in orders_resp.json().get("rows", []):
                        order_sum = (order.get("sum", 0) or 0) / 100.0
                        attrs = order.get("attributes", []) or []

                        # Atributlardan tekshirish
                        contract_sum = 0.0
                        operator_emp_id = None
                        manager_emp_id = None

                        for a in attrs:
                            a_name = (a.get("name", "") or "").strip()
                            a_val = a.get("value")

                            # 1) Шартнома суммаси
                            if "Шартнома суммаси" in a_name and a_val:
                                try:
                                    contract_sum = float(a_val)
                                except Exception:
                                    pass

                            # 2) Сотув оператори
                            if "Сотув оператори" in a_name and isinstance(a_val, dict):
                                op_href = a_val.get("meta", {}).get("href", "")
                                operator_emp_id = op_href.split("/")[-1] if op_href else None

                            # 3) Сотув менеджери
                            if "Сотув менеджери" in a_name and isinstance(a_val, dict):
                                men_href = a_val.get("meta", {}).get("href", "")
                                manager_emp_id = men_href.split("/")[-1] if men_href else None

                            # 4) Ishlab chiqarish hajmlari
                            if a_name == "ПВХ" and a_val:
                                production_facts['PVX'] += Decimal(str(a_val))
                            elif a_name == "ТЕРМО" and a_val:
                                production_facts['Termo'] += Decimal(str(a_val))
                            elif a_name == "Чемпион" and a_val:
                                production_facts['Chempion'] += Decimal(str(a_val))
                            elif (a_name == "АЛДОХ" or "АЛЮМИНИЙ" in a_name.upper()) and a_val:
                                production_facts['Alyuminiy'] += Decimal(str(a_val))

                        # Haqiqiy summa: Shartnoma summasi yoki standart buyurtma summasi
                        effective_sum = contract_sum if contract_sum > 0 else order_sum

                        # Operatorga zakaz qo'shish
                        if operator_emp_id:
                            op_fact = get_or_init(operator_emp_id)
                            op_fact["order_count"] += 1
                            op_fact["sales_sum"] += effective_sum

                        # Menejerga sotuv summasi qo'shish
                        if manager_emp_id:
                            men_fact = get_or_init(manager_emp_id)
                            men_fact["sales_sum"] += effective_sum

                        # Owner (mas'ul xodim)
                        owner_href = order.get("owner", {}).get("meta", {}).get("href", "")
                        owner_id = owner_href.split("/")[-1] if owner_href else None
                        if owner_id and not operator_emp_id and not manager_emp_id:
                            ow_fact = get_or_init(owner_id)
                            ow_fact["order_count"] += 1
                            ow_fact["sales_sum"] += effective_sum

            except Exception as e:
                logger.warning(f"Error reading customerorder in sync_sales_facts: {e}")

            # 2. DEMAND (Yuk xatlari / Otgruzkalar)
            try:
                demand_url = f"{self.base_url}/entity/demand?filter=moment>={d_from_str};moment<={d_to_str}&limit=100"
                demand_resp = requests.get(demand_url, headers=self.headers, timeout=self.timeout)
                if demand_resp.status_code == 200:
                    for dem in demand_resp.json().get("rows", []):
                        owner_href = dem.get("owner", {}).get("meta", {}).get("href", "")
                        owner_id = owner_href.split("/")[-1] if owner_href else None
                        d_sum = (dem.get("sum", 0) or 0) / 100.0
                        if owner_id:
                            f_item = get_or_init(owner_id)
                            f_item["sales_sum"] += d_sum
            except Exception as e:
                logger.warning(f"Error reading demand: {e}")

            # 3. CASHIN va PAYMENTIN (Kassa va bank savdo tushumlari)
            try:
                for p_ep in ["cashin", "paymentin"]:
                    p_url = f"{self.base_url}/entity/{p_ep}?filter=moment>={d_from_str};moment<={d_to_str}&limit=100"
                    p_resp = requests.get(p_url, headers=self.headers, timeout=self.timeout)
                    if p_resp.status_code == 200:
                        for p_doc in p_resp.json().get("rows", []):
                            owner_href = p_doc.get("owner", {}).get("meta", {}).get("href", "")
                            owner_id = owner_href.split("/")[-1] if owner_href else None
                            p_sum = (p_doc.get("sum", 0) or 0) / 100.0
                            if owner_id and p_sum > 0:
                                f_item = get_or_init(owner_id)
                                if f_item["sales_sum"] == 0:
                                    f_item["sales_sum"] += p_sum
            except Exception as e:
                logger.warning(f"Error reading payments in: {e}")

            # 4. ProductionCategory faktlarini yangilash (agar MoySklad'da hajmlar bo'lsa)
            for cat_name, fact_vol in production_facts.items():
                if fact_vol > 0:
                    ProductionCategory.objects.filter(name__icontains=cat_name).update(fact=fact_vol)

            return {
                "success": True, 
                "facts": facts, 
                "production_facts": {k: float(v) for k, v in production_facts.items()}
            }
        except Exception as e:
            logger.exception("Error in sync_sales_facts")
            return {"success": False, "error": str(e)}

    def sync_advances(self, date_from, date_to):
        """
        Oy davomida berilgan avanslarni MoySklad kassa chiqimlari (cashout) va
        to'lov topshiriqnomalari (paymentout) dan avtomatik aniqlash.
        """
        if not self.token:
            return {"success": False, "error": "Token kiritilmagan!"}

        from payroll.models import Employee

        try:
            d_from_str = f"{date_from} 00:00:00"
            d_to_str = f"{date_to} 23:59:59"
            
            advances_by_emp = {}
            all_employees = list(Employee.objects.all())

            def add_advance(emp_id, amount):
                advances_by_emp[emp_id] = advances_by_emp.get(emp_id, 0.0) + float(amount)

            # 1. Kassa chiqimlari (cashout)
            cash_url = f"{self.base_url}/entity/cashout?filter=moment>={d_from_str};moment<={d_to_str}&limit=100"
            cash_resp = requests.get(cash_url, headers=self.headers, timeout=self.timeout)
            if cash_resp.status_code == 200:
                for row in cash_resp.json().get("rows", []):
                    summa = (row.get("sum", 0) or 0) / 100.0
                    desc = (row.get("description", "") or "").upper()
                    agent_href = row.get("agent", {}).get("meta", {}).get("href", "")
                    agent_id = agent_href.split("/")[-1] if agent_href else None

                    matched = False
                    if agent_id and any(e.moysklad_id == agent_id for e in all_employees):
                        add_advance(agent_id, summa)
                        matched = True

                    if not matched and desc:
                        for emp in all_employees:
                            first_name = emp.name.split()[0].upper()
                            if len(first_name) >= 3 and first_name in desc:
                                if emp.moysklad_id:
                                    add_advance(emp.moysklad_id, summa)
                                    matched = True
                                    break

            # 2. To'lov chiqimlari (paymentout)
            pay_url = f"{self.base_url}/entity/paymentout?filter=moment>={d_from_str};moment<={d_to_str}&limit=100"
            pay_resp = requests.get(pay_url, headers=self.headers, timeout=self.timeout)
            if pay_resp.status_code == 200:
                for row in pay_resp.json().get("rows", []):
                    summa = (row.get("sum", 0) or 0) / 100.0
                    desc = (row.get("description", "") or "").upper()
                    agent_href = row.get("agent", {}).get("meta", {}).get("href", "")
                    agent_id = agent_href.split("/")[-1] if agent_href else None

                    matched = False
                    if agent_id and any(e.moysklad_id == agent_id for e in all_employees):
                        add_advance(agent_id, summa)
                        matched = True

                    if not matched and desc:
                        for emp in all_employees:
                            first_name = emp.name.split()[0].upper()
                            if len(first_name) >= 3 and first_name in desc:
                                if emp.moysklad_id:
                                    add_advance(emp.moysklad_id, summa)
                                    matched = True
                                    break

            return {"success": True, "advances": advances_by_emp}
        except Exception as e:
            logger.exception("Error syncing advances")
            return {"success": False, "error": str(e)}

    def get_organization_account(self, org_id, search_name="Халк банк"):
        """Tashkilot hisob raqamini olish (standart bo'yicha Халк банк)"""
        try:
            url = f"{self.base_url}/entity/organization/{org_id}/accounts"
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)
            if resp.status_code == 200:
                rows = resp.json().get("rows", [])
                for r in rows:
                    acc_num = str(r.get("accountNumber") or "")
                    bank_name = str(r.get("bankName") or "")
                    name = str(r.get("name") or "")
                    if (search_name.lower() in acc_num.lower() or 
                        search_name.lower() in bank_name.lower() or 
                        search_name.lower() in name.lower()):
                        return r
                if rows:
                    return rows[0]
        except Exception as e:
            logger.warning(f"Error fetching org account: {e}")
        return None

    def close_month_in_moysklad(self, month=None, date_to=None, total_salary=0, items=None, payroll_period=None):
        """
        Oyni yakunlash va MoySklad'ga yozish:
        1. Jami oylik summasi bo'yicha Исходящий платеж (paymentout):
           - Tashkilot: РОМАКС "ROMAX AKFA" ОО
           - Hisob raqami (organizationAccount): Хр "Халк банк"
           - Statya rasxodov (expenseItem): Начисления
           - Kontragent (agent): Tashkilot (РОМАКС "ROMAX AKFA" ОО)
           - Summa: Jami hisoblangan oylik summasi
           - Sanasi va vaqti: Davr oxiri (masalan: 2026-10-31 23:59:00)
        2. Корректировка остатков на счете:
           - Davr oxiriga sana
           - Сумма корректировки ga jami oylik summasi
           - «Ойлик» polyasi tanlanib kiritiladi (value = True)
        3. Корректировка взаиморасчетов:
           - Xodimlar (kontragent) va hisoblangan jami oylik summalari (> 0)
           - 0 bo'lgan xodimlar urilmaydi
           - «Ойлик» polyasi tanlanib qo'yiladi (value = True)
           - Sanasi davr oxiriga kiritiladi
        """
        if not self.token:
            return {"success": False, "error": "MoySklad API token kiritilmagan!"}

        from payroll.models import MoySkladConfig, Employee
        config = MoySkladConfig.get_solo()

        try:
            org = self.get_first_organization()
            if not org:
                return {"success": False, "error": "MoySklad'da tashkilot topilmadi!"}

            org_id = org.get("id")
            org_account = self.get_organization_account(org_id, "Халк банк")

            # Davr oxiri sanasi va vaqti
            d_to_str = str(date_to) if date_to else (str(payroll_period.date_to) if payroll_period else "")
            if not d_to_str:
                d_to_str = timezone.now().strftime("%Y-%m-%d")
            # MoySklad API vaqtlarni MSK (UTC+3) formatida qabul qiladi.
            # Foydalanuvchi Toshkent (UTC+5, +2 soat) vaqtida ko'rishi va oyning oxirgi kuni soat 23:45 bo'lib
            # tushishi uchun MSK bo'yicha 21:45:00.000 qilib yuboriladi (21:45 + 2h = 23:45 UZT).
            moment_str = f"{d_to_str} 21:45:00.000"

            # Jami summa
            if total_salary and float(total_salary) > 0:
                tot_sal = float(total_salary)
            elif payroll_period and payroll_period.total_salary:
                tot_sal = float(payroll_period.total_salary)
            else:
                tot_sal = 0.0

            total_sum_tiyin = int(round(tot_sal * 100))
            month_label = month or (payroll_period.month if payroll_period else d_to_str[:7])

            # 1. ИСХОДЯЩИЙ ПЛАТЕЖ (paymentout)
            # Статья расходов: «Начисления» | Hisob raqami: Хр "Халк банк"
            expense_item = self.get_or_create_expense_item("Начисления")
            paymentout_payload = {
                "organization": {
                    "meta": org.get("meta")
                },
                "agent": {
                    "meta": org.get("meta")
                },
                "sum": total_sum_tiyin,
                "moment": moment_str,
                "paymentPurpose": f"{month_label} oyi uchun jami hisoblangan oylik va KPI rasxodi (Начисления). Finora tizimi orqali avtomatik yaratildi.",
                "description": f"{month_label} oyi uchun oylik to'lovi (Хр 'Халк банк')",
                "applicable": True
            }
            if org_account:
                paymentout_payload["organizationAccount"] = {
                    "meta": org_account.get("meta")
                }
            if expense_item:
                paymentout_payload["expenseItem"] = {
                    "meta": expense_item.get("meta")
                }

            create_paymentout_url = f"{self.base_url}/entity/paymentout"
            resp_paymentout = requests.post(create_paymentout_url, headers=self.headers, json=paymentout_payload, timeout=self.timeout)
            
            paymentout_id = None
            paymentout_name = ""
            if resp_paymentout.status_code in [200, 201]:
                pdoc = resp_paymentout.json()
                paymentout_id = pdoc.get("id")
                paymentout_name = pdoc.get("name", "")
            else:
                logger.error(f"Error creating paymentout: {resp_paymentout.text}")
                return {
                    "success": False,
                    "error": f"Исходящий платеж yaratishda xatolik ({resp_paymentout.status_code}): {resp_paymentout.text[:250]}"
                }

            # DIQQAT: MoySklad JSON API (Remap 1.2) da "Корректировка остатков на счете" (accountadjustment)
            # alohida REST API entitisi sifatida mavjud emas (MoySklad faqat veb-interfeys 'source: app' orqali ruxsat beradi).
            # Agar uni counterpartyadjustment orqali yuborilsa, MoySklad uni tashkilot bilan "Корректировка взаиморасчетов"
            # deb tushunib, korxona balansini buzib yuboradi. Shuning uchun ortiqcha/soxta взаиморасчет yaratilmaydi!
            account_adj_id = None

            # 3. КОРРЕКТИРОВКА ВЗАИМОРАСЧЕТОВ (Xodimlar kesimida)
            emp_adj_count = 0
            emp_adj_errors = []
            
            if items:
                emp_map = {e.id: e for e in Employee.objects.all()}
                emp_name_map = {e.name.upper(): e for e in Employee.objects.all()}

                for item in items:
                    emp_salary = float(item.get("total_salary") or 0)
                    if emp_salary <= 0:
                        continue  # 0 lar urilmaydi, faqat aniq summalar uriladi!

                    emp_sum_tiyin = int(round(emp_salary * 100))
                    emp_ms_id = item.get("emp_id") or item.get("moysklad_id")
                    
                    if not emp_ms_id:
                        eid = item.get("id")
                        if eid and eid in emp_map:
                            emp_ms_id = emp_map[eid].moysklad_id
                    
                    if not emp_ms_id:
                        ename = (item.get("name") or "").upper().replace("–", "-").replace("—", "-").strip()
                        for k, v in emp_name_map.items():
                            k_clean = k.replace("–", "-").replace("—", "-").strip()
                            if ename == k_clean or (len(ename) > 5 and (ename in k_clean or k_clean in ename)):
                                emp_ms_id = v.moysklad_id
                                break

                    if not emp_ms_id:
                        emp_adj_errors.append(f"{item.get('name')}: MoySklad ID topilmadi")
                        continue

                    emp_payload = {
                        "organization": {
                            "meta": org.get("meta")
                        },
                        "agent": {
                            "meta": {
                                "href": f"{self.base_url}/entity/employee/{emp_ms_id}",
                                "type": "employee",
                                "mediaType": "application/json"
                            }
                        },
                        "sum": emp_sum_tiyin,
                        "moment": moment_str,
                        "description": f"{month_label} oyi uchun oylik va KPI hisobi: {item.get('name')}",
                        "applicable": True,
                        "attributes": [
                            {
                                "meta": {
                                    "href": f"{self.base_url}/entity/counterpartyadjustment/metadata/attributes/af0a3c09-c0bf-11f1-0a80-07eb0037d5cd",
                                    "type": "attributemetadata",
                                    "mediaType": "application/json"
                                },
                                "value": True
                            }
                        ]
                    }

                    resp_emp = requests.post(
                        f"{self.base_url}/entity/counterpartyadjustment",
                        headers=self.headers,
                        json=emp_payload,
                        timeout=self.timeout
                    )
                    if resp_emp.status_code in [200, 201]:
                        emp_adj_count += 1
                    else:
                        emp_adj_errors.append(f"{item.get('name')}: {resp_emp.text[:100]}")

            if payroll_period:
                payroll_period.moysklad_expense_id = paymentout_id
                payroll_period.status = "closed"
                payroll_period.closed_at = timezone.now()
                payroll_period.save()

            msg_parts = [
                f"Исходящий платеж #{paymentout_name or paymentout_id} (Начисления: {tot_sal:,.0f} so'm, Хр 'Халк банк') yaratildi."
            ]
            if account_adj_id:
                msg_parts.append(f"Корректировка остатков на счете (Ойлик: ☑) yaratildi.")
            if emp_adj_count > 0:
                msg_parts.append(f"{emp_adj_count} ta xodim uchun Корректировка взаиморасчетов (Ойлик: ☑) yozildi.")

            return {
                "success": True,
                "paymentout_id": paymentout_id,
                "account_adj_id": account_adj_id,
                "emp_adj_count": emp_adj_count,
                "errors": emp_adj_errors,
                "message": " ".join(msg_parts)
            }
        except Exception as e:
            logger.exception("Error closing month in MoySklad")
            return {"success": False, "error": str(e)}
