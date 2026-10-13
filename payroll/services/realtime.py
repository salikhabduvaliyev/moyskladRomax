import logging
import requests
from decimal import Decimal
from datetime import datetime, date

logger = logging.getLogger(__name__)

class RealtimeMoySkladEngine:
    """
    MoySklad API orqali ma'lumotlarni hech qanday modellarga yozmasdan,
    to'g'ridan-to'g'ri REAL TIME rejimida hisoblab beruvchi dvigatel (Romax Akfa).
    """

    def __init__(self, token=None, base_url="https://api.moysklad.ru/api/remap/1.2"):
        from payroll.models import MoySkladConfig
        config = MoySkladConfig.get_solo()
        self.token = token if token is not None else config.token
        self.base_url = (base_url or config.base_url).rstrip('/')
        self.timeout = 25

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.token.strip()}" if self.token else "",
            "Accept-Encoding": "gzip",
            "Content-Type": "application/json",
        }

    def get_realtime_payroll(self, month, date_from=None, date_to=None, total_plans=None):
        from payroll.models import KPIRules, ProductionCategory

        total_plans = total_plans or {}

        # 1. Sana oralig'i
        if not date_from or not date_to:
            try:
                y, m = map(int, month.split('-'))
                if m == 12:
                    next_m = date(y + 1, 1, 1)
                else:
                    next_m = date(y, m + 1, 1)
                d_from = date(y, m, 1)
                d_to = date.fromordinal(next_m.toordinal() - 1)
            except Exception:
                d_from = date(2026, 10, 1)
                d_to = date(2026, 10, 31)
        else:
            d_from = date_from
            d_to = date_to

        if isinstance(d_from, str):
            try:
                d_from = datetime.strptime(d_from[:10], '%Y-%m-%d').date()
            except Exception:
                d_from = date(2026, 10, 1)
        if isinstance(d_to, str):
            try:
                d_to = datetime.strptime(d_to[:10], '%Y-%m-%d').date()
            except Exception:
                d_to = date(2026, 10, 31)

        d_from_str = f"{d_from} 00:00:00"
        d_to_str = f"{d_to} 23:59:59"

        rules = KPIRules.get_solo()
        categories = list(ProductionCategory.objects.all())

        # 2. XODIMLAR: MoySklad «Моя компания → Сотрудники» dan real-time
        employees = []
        if self.token:
            try:
                url_emp = f"{self.base_url}/entity/employee?limit=100&filter=archived=false"
                resp_emp = requests.get(url_emp, headers=self.headers, timeout=self.timeout)
                if resp_emp.status_code == 200:
                    rows = resp_emp.json().get('rows', [])
                    for i, r in enumerate(rows, 1):
                        name = (r.get('name') or r.get('fullName') or '').strip()
                        if name.lower() == 'administrator':
                            continue
                        pos = (r.get('position') or '').strip()

                        # OKLAD: xodim kartochkasidagi salary maydoni
                        salary_obj = r.get('salary', {})
                        oklad_val = 0.0
                        if isinstance(salary_obj, dict):
                            oklad_val = float(salary_obj.get('value', 0) or 0)
                        elif isinstance(salary_obj, (int, float)):
                            oklad_val = float(salary_obj)

                        # Guruh va bo'limlarni aniqlash:
                        # 1) Sotuv operatorlari (оператор)
                        # 2) Sotuv menejerlari va sotuvchilar (менеджер, рахбар, юритувчи, сотувчи)
                        # 3) Монтажчилар (монтаж) -> ALOHIDA BO'LIM! PVX yoki Termoga bog'liq emas!
                        # 4) PVX bo'limi (бригадир пвх, цех, уста, мастер)
                        # 5) TERMO bo'limi (бригадир термо, термо)
                        # 6) Boshqa (faqat oklad)
                        combined = f"{name} {pos}".lower()
                        pos_lower = pos.lower()
                        group = "bosh"
                        dept = pos or "Boshqa"

                        # 1) Sotuv operatorlari
                        if "оператор" in combined:
                            group = "op"
                            dept = "Sotuv operatori"
                        # 2) Sotuvchilar — Foydalanuvchi talabi: Сотрудники lavozimi «сотувчи» bo'lsa olinadi
                        elif "сотувчи" in pos_lower or "sotuvchi" in pos_lower:
                            group = "men"
                            dept = "Сотувчи"
                        # 3) Монтажчилар — ALOHIDA BO'LIM! PVX yoki Termoga bog'liq emas!
                        elif "монтаж" in combined:
                            group = "ish"
                            dept = "Монтаж"
                        # 4) TERMO bo'limi
                        elif any(k in combined for k in ["термо", "бригадир терм"]):
                            group = "ish"
                            dept = "TERMO bo'limi"
                        # 5) PVX bo'limi
                        elif any(k in combined for k in ["цех", "уста", "бригадир пвх", "мастер"]):
                            group = "ish"
                            dept = "PVX bo'limi"
                        # 6) Boshqa (faqat oklad: рахбар, иш юритувчи, ошпаз, омборчи, чизмачи, шофёр va b.)
                        else:
                            group = "bosh"
                            dept = pos or "Boshqa (oklad)"

                        employees.append({
                            'id': r.get('id'),
                            'ms_id': r.get('id'),
                            'name': name,
                            'position': pos or dept,
                            'group': group,
                            'dept': dept,
                            'oklad': oklad_val,
                            'manager_rate': 1.0,
                            'order_num': i,
                            'is_active': True
                        })
            except Exception as e:
                logger.exception(f"Error fetching realtime employees: {e}")

        # Faol xodimlar sonini guruhlar bo'yicha aniqlash
        op_count = sum(1 for e in employees if e['is_active'] and e['group'] == 'op') or 1
        men_count = sum(1 for e in employees if e['is_active'] and e['group'] == 'men') or 1
        pvh_count = sum(1 for e in employees if e['is_active'] and e['dept'] == 'PVX bo\'limi') or 1
        termo_count = sum(1 for e in employees if e['is_active'] and e['dept'] == 'TERMO bo\'limi') or 1
        montaj_count = sum(1 for e in employees if e['is_active'] and e['dept'] == 'Монтаж') or 1

        # 3. ZAKAZLAR: MoySklad «Продажи → Заказы покупателей» dan real-time
        orders_by_emp = {}  # {emp_id: {"order_count": int, "contract_sum": float}}
        emp_prod_pvh = {}   # {emp_id: float (m2)} - Faqat ПВХ polyasi
        emp_prod_termo = {} # {emp_id: float (m2)} - ТЕРМО, Чемпион, АЛДОХ polyalari
        emp_mont_sqm = {}   # {emp_id: float (m2)} - АЛДОХ, Чемпион, ТЕРМО, ПВХ qismlari
        emp_prod_order_cnt = {} # {emp_id: int}
        
        production_live_facts = {
            'PVX': 0.0,
            'Termo': 0.0,
            'Chempion': 0.0,
            'Alyuminiy': 0.0,
            'Montaj': 0.0
        }

        def get_emp_order_slot(emp_id):
            if emp_id not in orders_by_emp:
                orders_by_emp[emp_id] = {"order_count": 0, "contract_sum": 0.0}
            return orders_by_emp[emp_id]

        if self.token:
            try:
                # 0. Barcha otgruzkalarni (demand) olib, zakazlarga bog'lash
                demands_by_order_id = {}
                try:
                    dem_url = f"{self.base_url}/entity/demand?expand=customerOrder&limit=100"
                    resp_dem = requests.get(dem_url, headers=self.headers, timeout=self.timeout)
                    if resp_dem.status_code == 200:
                        for dm_row in resp_dem.json().get('rows', []):
                            dm_moment = (dm_row.get('moment', '') or '')[:10]
                            cord = dm_row.get('customerOrder', {})
                            cord_href = cord.get('meta', {}).get('href', '') if cord else ''
                            cord_id = cord_href.split('/')[-1] if cord_href else None
                            if cord_id and dm_moment:
                                try:
                                    dm_date = datetime.strptime(dm_moment, '%Y-%m-%d').date()
                                    demands_by_order_id.setdefault(cord_id, []).append(dm_date)
                                except Exception:
                                    pass
                except Exception as e_dem:
                    logger.warning(f"Error fetching demands map: {e_dem}")

                orders_url = f"{self.base_url}/entity/customerorder?expand=demands,state,owner&limit=100&order=moment,desc"
                resp_ord = requests.get(orders_url, headers=self.headers, timeout=self.timeout)
                if resp_ord.status_code == 200:
                    orders_data = resp_ord.json().get('rows', [])
                    for order in orders_data:
                        state_name = order.get('state', {}).get('name', '')
                        demands = order.get('demands', [])
                        shipped_sum = order.get('shippedSum', 0) or 0
                        order_sum = (order.get('sum', 0) or 0) / 100.0
                        desc = (order.get('description', '') or '').upper()

                        order_moment_str = (order.get('moment', '') or '')[:10]
                        try:
                            order_date = datetime.strptime(order_moment_str, '%Y-%m-%d').date() if order_moment_str else None
                        except Exception:
                            order_date = None

                        is_order_in_period = bool(order_date and (d_from <= order_date <= d_to))

                        attrs = {a.get('name'): a.get('value') for a in order.get('attributes', [])}
                        contract_sum = float(attrs.get('Шартнома суммаси') or order_sum or 0)

                        # A) Sotuv operatori (faqat tanlangan davrdagi zakazlar)
                        if is_order_in_period:
                            op_attr = attrs.get('Сотув оператори')
                            if isinstance(op_attr, dict):
                                op_href = op_attr.get('meta', {}).get('href', '')
                                op_id = op_href.split('/')[-1] if op_href else None
                                op_name = (op_attr.get('name', '') or '').upper()
                                for emp in employees:
                                    if emp['group'] == 'op' and (emp['ms_id'] == op_id or (op_name and op_name in emp['name'].upper())):
                                        slot = get_emp_order_slot(emp['id'])
                                        slot['order_count'] += 1
                                        slot['contract_sum'] += contract_sum
                                        break

                            # B) Sotuvchilar (Menejerlar)
                            men_attr = attrs.get('Сотув менеджери')
                            matched_men = False
                            if isinstance(men_attr, dict):
                                men_href = men_attr.get('meta', {}).get('href', '')
                                men_id = men_href.split('/')[-1] if men_href else None
                                men_name = (men_attr.get('name', '') or '').upper()
                                for emp in employees:
                                    if emp['group'] == 'men' and (emp['ms_id'] == men_id or (men_name and men_name in emp['name'].upper())):
                                        slot = get_emp_order_slot(emp['id'])
                                        slot['order_count'] += 1
                                        slot['contract_sum'] += contract_sum
                                        matched_men = True
                                        break

                            # C) Owner yoki tavsif bo'yicha sotuvchini aniqlash
                            if not matched_men:
                                owner_href = order.get('owner', {}).get('meta', {}).get('href', '')
                                owner_id = owner_href.split('/')[-1] if owner_href else None
                                for emp in employees:
                                    if emp['group'] == 'men':
                                        emp_first = emp['name'].split()[0].upper()
                                        if emp['ms_id'] == owner_id or (len(emp_first) >= 4 and emp_first in desc):
                                            slot = get_emp_order_slot(emp['id'])
                                            slot['order_count'] += 1
                                            slot['contract_sum'] += contract_sum
                                            matched_men = True
                                            break

                        # D) ISHLAB CHIQARISH VA MONTAJ:
                        # Foydalanuvchi talabi:
                        # qachonki Заказ покупателя otgruzga bolsa otgruzka sanasi boyicha Заказ покупателя dagi malumotlar hisobga kirishi kerak
                        # agar otgruzga bolmasa ulanmagan bolsa bunda kirmaydi hisoblanmaydi Заказ покупателя
                        order_id = order.get('id')
                        all_demand_dates = list(demands_by_order_id.get(order_id, []))
                        for d in demands:
                            dm = (d.get('moment', '') or '')[:10]
                            if dm:
                                try:
                                    dd = datetime.strptime(dm, '%Y-%m-%d').date()
                                    if dd not in all_demand_dates:
                                        all_demand_dates.append(dd)
                                except Exception:
                                    pass

                        has_demands = len(all_demand_dates) > 0
                        is_production_in_period = False
                        if has_demands:
                            # Faqat OTGRUZKA SANASI tanlangan davr oralig'ida bo'lsa hisobga olinadi
                            is_production_in_period = any(d_from <= dd <= d_to for dd in all_demand_dates)
                        else:
                            # Otgruzga ulanmagan bo'lsa, hisobga kirmaydi / hisoblanmaydi
                            is_production_in_period = False

                        if is_production_in_period:
                            pvh_val = float(attrs.get('ПВХ') or 0)
                            termo_val = float(attrs.get('ТЕРМО') or 0)
                            chemp_val = float(attrs.get('Чемпион') or 0)
                            aldox_val = float(attrs.get('АЛДОХ') or 0)
                            mont_val = pvh_val + termo_val + chemp_val + aldox_val

                            # 1) ПВХ polyasi -> Faqat «Ишлаб чикариш булими (ПВХ)» xodimiga
                            if pvh_val > 0:
                                production_live_facts['PVX'] += pvh_val
                                pvh_emp_attr = attrs.get('Ишлаб чикариш булими (ПВХ)')
                                if isinstance(pvh_emp_attr, dict):
                                    pvh_eid = pvh_emp_attr.get('meta', {}).get('href', '').split('/')[-1]
                                    pvh_name = (pvh_emp_attr.get('name', '') or '').upper()
                                    for emp in employees:
                                        if emp['ms_id'] == pvh_eid or (pvh_name and pvh_name in emp['name'].upper()):
                                            emp_prod_pvh[emp['id']] = emp_prod_pvh.get(emp['id'], 0.0) + pvh_val
                                            emp_prod_order_cnt[emp['id']] = emp_prod_order_cnt.get(emp['id'], 0) + 1
                                            break

                            # 2) ТЕРМО, Чемпион, АЛДОХ polyalari -> Faqat «Ишлаб чикариш булими (ТЕРМО)» xodimiga
                            t_sum = termo_val + chemp_val + aldox_val
                            if t_sum > 0:
                                production_live_facts['Termo'] += termo_val
                                production_live_facts['Chempion'] += chemp_val
                                production_live_facts['Alyuminiy'] += aldox_val
                                termo_emp_attr = attrs.get('Ишлаб чикариш булими (ТЕРМО)')
                                if isinstance(termo_emp_attr, dict):
                                    termo_eid = termo_emp_attr.get('meta', {}).get('href', '').split('/')[-1]
                                    termo_name = (termo_emp_attr.get('name', '') or '').upper()
                                    for emp in employees:
                                        if emp['ms_id'] == termo_eid or (termo_name and termo_name in emp['name'].upper()):
                                            emp_prod_termo[emp['id']] = emp_prod_termo.get(emp['id'], 0.0) + t_sum
                                            emp_prod_order_cnt[emp['id']] = emp_prod_order_cnt.get(emp['id'], 0) + 1
                                            break

                            # 3) Монтаж: АЛДОХ, Чемпион, ТЕРМО, ПВХ qismini oladi
                            if mont_val > 0:
                                production_live_facts['Montaj'] += mont_val
                                mont_emp_attr = attrs.get('Монтаж командаси')
                                if isinstance(mont_emp_attr, dict):
                                    mont_eid = mont_emp_attr.get('meta', {}).get('href', '').split('/')[-1]
                                    mont_name = (mont_emp_attr.get('name', '') or '').upper()
                                    for emp in employees:
                                        if emp['ms_id'] == mont_eid or (mont_name and mont_name in emp['name'].upper()):
                                            emp_mont_sqm[emp['id']] = emp_mont_sqm.get(emp['id'], 0.0) + mont_val
                                            emp_prod_order_cnt[emp['id']] = emp_prod_order_cnt.get(emp['id'], 0) + 1
                                            break

            except Exception as e:
                logger.exception(f"Error fetching realtime orders: {e}")

        # 4. AVANSLAR: MoySklad kassa chiqimlaridan (FAQAT «ОЙЛИК ИШ ХАКИ» moddasi va «Дата начисления» bo'yicha real-time)
        advances_by_emp = {}
        if self.token:
            try:
                for ep in ['cashout', 'paymentout']:
                    c_url = f"{self.base_url}/entity/{ep}?expand=agent,expenseItem&limit=100"
                    c_resp = requests.get(c_url, headers=self.headers, timeout=self.timeout)
                    if c_resp.status_code == 200:
                        for row in c_resp.json().get('rows', []):
                            summa = (row.get('sum', 0) or 0) / 100.0
                            desc = (row.get('description', '') or '').upper()
                            moment_str = (row.get('moment', '') or '')[:10]

                            exp_obj = row.get('expenseItem', {}) or {}
                            exp_name = (exp_obj.get('name', '') or '').upper()
                            exp_href = exp_obj.get('meta', {}).get('href', '')

                            # Foydalanuvchi talabi: FAQAT «ОЙЛИК ИШ ХАКИ» moddasi bo'yicha xodimning o'ziga berilgan avanslar olinadi!
                            is_salary_expense = (
                                ('ОЙЛИК' in exp_name and 'ИШ ХАКИ' in exp_name) or 
                                '144eaa73-bfe5-11f1-0a80-112e001725cd' in exp_href or 
                                exp_name == 'ОЙЛИК ИШ ХАКИ'
                            )
                            if not is_salary_expense:
                                continue

                            agent_obj = row.get('agent', {}) or {}
                            agent_meta = agent_obj.get('meta', {}) or {}
                            agent_type = agent_meta.get('type', '')

                            # Faqat xodimga (employee) to'langan bo'lsa olinadi (boshqa tashkilot/kontragent xarajatlari kirmaydi)
                            if agent_type and agent_type != 'employee':
                                continue

                            # Foydalanuvchi talabi: MoySklad'dagi «Дата начисления» (hujjat moment sanasi) bo'yicha tanlangan davr ichida
                            try:
                                moment_date = datetime.strptime(moment_str[:10], '%Y-%m-%d').date()
                            except Exception:
                                moment_date = None

                            if not moment_date or not (d_from <= moment_date <= d_to):
                                continue

                            agent_href = agent_meta.get('href', '')
                            agent_id = agent_href.split('/')[-1] if agent_href else None
                            agent_name = (agent_obj.get('name', '') or '').strip().upper()

                            matched = False
                            if agent_id:
                                for emp in employees:
                                    if emp['ms_id'] == agent_id:
                                        advances_by_emp[emp['id']] = advances_by_emp.get(emp['id'], 0.0) + summa
                                        matched = True
                                        break

                            if not matched and agent_name:
                                for emp in employees:
                                    emp_name_u = emp['name'].upper()
                                    if emp_name_u in agent_name or agent_name in emp_name_u:
                                        advances_by_emp[emp['id']] = advances_by_emp.get(emp['id'], 0.0) + summa
                                        matched = True
                                        break
            except Exception as e:
                logger.exception(f"Error fetching realtime advances: {e}")

        # 5. ISHLAB CHIQARISH KATEGORIYALARI
        cats_result = []
        for c in categories:
            c_name_u = c.name.upper()
            if 'PVX' in c_name_u:
                live_fact = production_live_facts['PVX']
                w_count = pvh_count
                dept_label = "Ишлаб чикариш булими (ПВХ)"
                poly_label = "ПВХ"
            elif 'TERMO' in c_name_u:
                live_fact = production_live_facts['Termo']
                w_count = termo_count
                dept_label = "Ишлаб чикариш булими (ТЕРМО)"
                poly_label = "ТЕРМО"
            elif 'CHEMP' in c_name_u:
                live_fact = production_live_facts['Chempion']
                w_count = termo_count
                dept_label = "Ишлаб чикариш булими (ТЕРМО)"
                poly_label = "Чемпион"
            elif 'ALYUM' in c_name_u or 'ALDOX' in c_name_u:
                live_fact = production_live_facts['Alyuminiy']
                w_count = termo_count
                dept_label = "Ишлаб чикариш булими (ТЕРМО)"
                poly_label = "АЛДОХ"
            elif 'MONT' in c_name_u or 'МОНТ' in c_name_u:
                live_fact = production_live_facts['Montaj']
                w_count = montaj_count
                dept_label = "Монтаж бўлими (Алоҳида)"
                poly_label = "Монтаж"
            else:
                live_fact = float(c.fact)
                w_count = 1
                dept_label = "Boshqa"
                poly_label = c.name

            fact_to_use = live_fact if live_fact > 0 else float(c.fact)

            cats_result.append({
                'id': c.id,
                'name': c.name,
                'dept_label': dept_label,
                'poly_label': poly_label,
                'prev_month_volume': float(c.prev_month_volume),
                'growth_percent': c.growth_percent,
                'plan': float(c.plan),
                'fact': round(fact_to_use, 2),
                'tarif': float(c.tarif),
                'workers_count': w_count
            })

        # 6. PLANLAR VA TARIFLARNI REAL TIME TAQSIMLASH:
        tot_plan_op = float(total_plans.get('op') or 2000000000.0)    # masalan 2 mlrd so'm
        tot_plan_men = float(total_plans.get('men') or 2400000000.0) # masalan 2.4 mlrd so'm
        tarif_pvh = float(total_plans.get('tarif_pvh') or 60000.0)    # so'm/m2
        tarif_termo = float(total_plans.get('tarif_termo') or 80000.0) # so'm/m2
        tarif_montaj = float(total_plans.get('tarif_montaj') or 50000.0) # so'm/m2

        selected_op_ids = total_plans.get('selected_op_ids')
        if selected_op_ids:
            matched_selected = sum(
                1 for idx, e in enumerate(employees) 
                if e['is_active'] and e['group'] == 'op' and (
                    str(e['id']) in selected_op_ids or 
                    str(e.get('ms_id', '')) in selected_op_ids or 
                    str(idx) in selected_op_ids
                )
            )
            op_target_count = matched_selected if matched_selected > 0 else len(selected_op_ids)
        else:
            op_target_count = op_count

        selected_men_ids = total_plans.get('selected_men_ids')
        if selected_men_ids:
            matched_selected_men = sum(
                1 for idx, e in enumerate(employees) 
                if e['is_active'] and e['group'] == 'men' and (
                    str(e['id']) in selected_men_ids or 
                    str(e.get('ms_id', '')) in selected_men_ids or 
                    str(idx) in selected_men_ids
                )
            )
            men_target_count = matched_selected_men if matched_selected_men > 0 else len(selected_men_ids)
        else:
            men_target_count = men_count

        ind_plan_op = round(tot_plan_op / op_target_count) if op_target_count > 0 else 0
        ind_plan_men = round(tot_plan_men / men_target_count) if men_target_count > 0 else 0

        # 7. ISHLAB CHIQARISH VA MONTAJ - XODIMLAR KESIMIDA REAL-TIME TAHLIL
        # Foydalanuvchi talabi:
        # 1) Davr ichida qaysi xodim qancha kv ishlab chiqardi degan ma'lumot ko'rsatiladi
        # 2) Ишлаб чикариш булими (ПВХ) = ПВХ polyasini oladi
        # 3) Ишлаб чикариш булими (ТЕРМО) = ТЕРМО, Чемпион, АЛДОХ polyalarini oladi
        # 4) Монтаж командаси = АЛДОХ, Чемпион, ТЕРМО, ПВХ qismini oladi
        # 5) Заказ покупателя otgruzga qilingan bo'lsagina hisoblanadi
        # 6) Agar ishlab chiqarmagan bo'lsa faqat okladini oladi
        # 7) Har bir ishlab chiqarish va alohida montaj qilingan kv uchun summa (tarif) kiritiladi
        production_summary = []
        for emp in employees:
            if emp['group'] == 'ish' or emp['dept'] in ["PVX bo'limi", "TERMO bo'limi", "Монтаж"]:
                eid = emp['id']
                p_m2 = round(emp_prod_pvh.get(eid, 0.0), 2)
                t_m2 = round(emp_prod_termo.get(eid, 0.0), 2)
                m_m2 = round(emp_mont_sqm.get(eid, 0.0), 2)
                dept = emp['dept']

                if dept == "PVX bo'limi":
                    linked_poly = "ПВХ"
                    fact_m2 = p_m2
                    used_tarif = tarif_pvh
                    bonus = round(fact_m2 * tarif_pvh)
                elif dept == "TERMO bo'limi":
                    linked_poly = "ТЕРМО, Чемпион, АЛДОХ"
                    fact_m2 = t_m2
                    used_tarif = tarif_termo
                    bonus = round(fact_m2 * tarif_termo)
                elif dept == "Монтаж":
                    linked_poly = "АЛДОХ, Чемпион, ТЕРМО, ПВХ"
                    fact_m2 = m_m2
                    used_tarif = tarif_montaj
                    bonus = round(fact_m2 * tarif_montaj)
                else:
                    linked_poly = "Aralash"
                    fact_m2 = round(p_m2 + t_m2 + m_m2, 2)
                    used_tarif = tarif_pvh
                    bonus = round(p_m2 * tarif_pvh + t_m2 * tarif_termo + m_m2 * tarif_montaj)

                emp_oklad = emp['oklad']
                emp_total = emp_oklad + bonus
                ord_cnt = emp_prod_order_cnt.get(eid, 0)

                production_summary.append({
                    'emp_id': eid,
                    'name': emp['name'],
                    'position': emp['position'],
                    'dept': dept,
                    'linked_poly': linked_poly,
                    'pvh_m2': p_m2,
                    'termo_m2': t_m2,
                    'montaj_m2': m_m2,
                    'fact_m2': fact_m2,
                    'tarif': used_tarif,
                    'bonus': bonus,
                    'oklad': emp_oklad,
                    'total_salary': emp_total,
                    'order_count': ord_cnt,
                    'status_label': 'Xizmat bonusi bilan' if fact_m2 > 0 else 'Faqat oklad (0 m²)'
                })

        # 8. HAR BIR XODIMNING REAL-TIME OYLIK VA KPI HISOBI
        items_result = []
        s_ok = 0.0
        s_bonus = 0.0
        s_advance = 0.0
        s_total = 0.0
        s_rest = 0.0

        for i, emp in enumerate(employees):
            emp_id = emp['id']
            group = emp['group']
            dept = emp['dept']
            oklad = emp['oklad']
            advance = advances_by_emp.get(emp_id, 0.0)
            order_info = orders_by_emp.get(emp_id, {'order_count': 0, 'contract_sum': 0.0})

            plan_val = 0.0
            fact_val = 0.0
            pct = 0.0
            bonus = 0.0

            # 1) SOTUV OPERATORLARI (Shartnoma summasi bo'yicha koeffitsient %)
            # Foydalanuvchi talabi: Okladdan emas, o'ziga tegishli davr ichidagi shartnoma summasidan hisoblanadi
            # Tanlangan operatorlarga reja beriladi, tanlanmagan operatorlarga 0 plan (faqat oklad)
            if group == 'op':
                is_selected = True
                if selected_op_ids:
                    is_selected = (
                        str(emp_id) in selected_op_ids or
                        str(emp.get('id', '')) in selected_op_ids or
                        str(i) in selected_op_ids or
                        str(emp.get('ms_id', '')) in selected_op_ids
                    )

                fact_val = order_info['contract_sum']
                if is_selected:
                    plan_val = ind_plan_op
                    pct = (fact_val / plan_val * 100.0) if plan_val > 0 else 0.0
                    if pct >= rules.op_t4:
                        bonus = fact_val * (rules.op_k4 / 100.0)
                    elif pct >= rules.op_t3:
                        bonus = fact_val * (rules.op_k3 / 100.0)
                    elif pct >= rules.op_t2:
                        bonus = fact_val * (rules.op_k2 / 100.0)
                    elif pct >= rules.op_t1:
                        bonus = fact_val * (rules.op_k1 / 100.0)
                    else:
                        bonus = 0.0
                else:
                    plan_val = 0.0
                    pct = 0.0
                    bonus = 0.0

            # 2) SOTUV MENEJERLARI VA SOTUVCHILAR (Hajm bo'yicha %)
            elif group == 'men':
                is_selected = True
                if selected_men_ids:
                    is_selected = (
                        str(emp_id) in selected_men_ids or
                        str(emp.get('id', '')) in selected_men_ids or
                        str(i) in selected_men_ids or
                        str(emp.get('ms_id', '')) in selected_men_ids
                    )

                fact_val = order_info['contract_sum']
                if is_selected:
                    plan_val = ind_plan_men
                    pct = (fact_val / plan_val * 100.0) if plan_val > 0 else 0.0
                    if pct >= rules.men_t3:
                        bonus = fact_val * (rules.men_r3 / 100.0)
                    elif pct >= rules.men_t2:
                        bonus = fact_val * (rules.men_r2 / 100.0)
                    elif pct >= rules.men_t1:
                        bonus = fact_val * (float(emp.get('manager_rate', 1.0)) / 100.0)
                    else:
                        bonus = 0.0
                else:
                    plan_val = 0.0
                    pct = 0.0
                    bonus = 0.0

            # 3) ISHLAB CHIQARISH VA MONTAJ (Faqat otgruzka bo'lgan zakazlardan xodim bajargan kv.m boyicha)
            elif group == 'ish':
                if dept == "PVX bo'limi":
                    fact_val = round(emp_prod_pvh.get(emp_id, 0.0), 2)
                    bonus = round(fact_val * tarif_pvh)
                elif dept == "TERMO bo'limi":
                    fact_val = round(emp_prod_termo.get(emp_id, 0.0), 2)
                    bonus = round(fact_val * tarif_termo)
                elif dept == "Монтаж":
                    fact_val = round(emp_mont_sqm.get(emp_id, 0.0), 2)
                    bonus = round(fact_val * tarif_montaj)
                else:
                    p_val = emp_prod_pvh.get(emp_id, 0.0)
                    t_val = emp_prod_termo.get(emp_id, 0.0)
                    m_val = emp_mont_sqm.get(emp_id, 0.0)
                    fact_val = round(p_val + t_val + m_val, 2)
                    bonus = round(p_val * tarif_pvh + t_val * tarif_termo + m_val * tarif_montaj)
                
                # Agar ishlab chiqarmagan bo'lsa (0 kv.m) faqat okladini oladi (bonus = 0)
                plan_val = 0.0
                pct = 100.0 if fact_val > 0 else 0.0

            # 4) BOSHQALAR (Faqat oklad)
            elif group == 'bosh':
                plan_val = 0.0
                fact_val = 0.0
                pct = 0.0
                bonus = 0.0

            total_salary = oklad + bonus
            rest_to_pay = total_salary - advance

            s_ok += oklad
            s_bonus += bonus
            s_advance += advance
            s_total += total_salary
            s_rest += rest_to_pay

            items_result.append({
                'id': i,
                'emp_id': emp_id,
                'name': emp['name'],
                'position': emp['position'],
                'group': group,
                'dept': dept,
                'oklad': oklad,
                'plan': plan_val,
                'fact': fact_val,
                'percent': round(pct, 2),
                'kpi_bonus': round(bonus),
                'advance': round(advance),
                'total_salary': round(total_salary),
                'rest_to_pay': round(rest_to_pay),
                'is_active': emp['is_active']
            })

        return {
            'success': True,
            'is_realtime': True,
            'period': {
                'id': 1,
                'month': month,
                'date_from': str(d_from),
                'date_to': str(d_to),
                'status': 'calculated',
                'status_display': 'Real-Time (MoySklad Jonli)',
                'total_oklad': s_ok,
                'total_kpi': s_bonus,
                'total_advance': s_advance,
                'total_salary': s_total,
                'total_rest': s_rest,
                'moysklad_expense_id': '',
            },
            'rules': {
                'op': {
                    'base': float(rules.op_base),
                    't1': rules.op_t1, 'k1': rules.op_k1,
                    't2': rules.op_t2, 'k2': rules.op_k2,
                    't3': rules.op_t3, 'k3': rules.op_k3,
                    't4': rules.op_t4, 'k4': rules.op_k4,
                },
                'men': {
                    't1': rules.men_t1,
                    't2': rules.men_t2, 'r2': rules.men_r2,
                    't3': rules.men_t3, 'r3': rules.men_r3,
                },
                'ish': {'min': rules.ish_min}
            },
            'total_plans': {
                'op': tot_plan_op,
                'men': tot_plan_men,
                'tarif_pvh': tarif_pvh,
                'tarif_termo': tarif_termo,
                'tarif_montaj': tarif_montaj,
                'op_count': op_count,
                'op_target_count': op_target_count,
                'selected_op_ids': selected_op_ids or [],
                'men_count': men_count,
                'men_target_count': men_target_count,
                'selected_men_ids': selected_men_ids or [],
                'pvh_count': pvh_count,
                'termo_count': termo_count,
                'montaj_count': montaj_count,
            },
            'categories': cats_result,
            'production_summary': production_summary,
            'items': items_result,
            'config': {
                'has_token': bool(self.token),
                'token_preview': f"{self.token[:6]}...{self.token[-4:]}" if self.token and len(self.token) > 10 else "Bor",
                'company_name': "Romax Akfa",
                'last_synced': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        }
