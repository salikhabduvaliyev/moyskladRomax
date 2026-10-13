from decimal import Decimal
from payroll.models import KPIRules, ProductionCategory, Employee, PayrollPeriod, PayrollItem

class KPICalculator:
    """Oylik va KPI hisoblash dvigateli"""

    @classmethod
    def calculate_employee_kpi(cls, emp, plan, fact, rules, categories, active_counts_by_cat):
        plan = float(plan)
        fact = float(fact)
        pct = (fact / plan * 100.0) if plan > 0 else 0.0
        bonus = 0.0

        group = emp.group

        if group == 'sot':
            # Sotuvchi: Sotuvdan % agar plan >= min
            if pct >= rules.sot_min:
                bonus = fact * (rules.sot_rate / 100.0)
            else:
                bonus = 0.0

        elif group == 'op':
            # Sotuv operatori: Shartnoma summasidan koeffitsient % bo'yicha
            if pct >= rules.op_t4:
                bonus = fact * (rules.op_k4 / 100.0)
            elif pct >= rules.op_t3:
                bonus = fact * (rules.op_k3 / 100.0)
            elif pct >= rules.op_t2:
                bonus = fact * (rules.op_k2 / 100.0)
            elif pct >= rules.op_t1:
                bonus = fact * (rules.op_k1 / 100.0)
            else:
                bonus = 0.0

        elif group == 'men':
            # Sotuv menejeri: Pog'onali sotuvdan %
            if pct >= rules.men_t3:
                bonus = fact * (rules.men_r3 / 100.0)
            elif pct >= rules.men_t2:
                bonus = fact * (rules.men_r2 / 100.0)
            elif pct >= rules.men_t1:
                custom_rate = float(emp.manager_custom_rate or 1.0)
                bonus = fact * (custom_rate / 100.0)
            else:
                bonus = 0.0

        elif group == 'ish':
            # Ishlab chiqarish: kategoriya bo'yicha teng taqsimlanadi
            cat = emp.production_category
            if cat:
                c_plan = float(cat.plan)
                c_fact = float(cat.fact)
                c_tarif = float(cat.tarif)
                pct = (c_fact / c_plan * 100.0) if c_plan > 0 else 0.0
                
                workers_count = active_counts_by_cat.get(cat.id, 1) or 1
                if pct >= rules.ish_min:
                    bonus = (c_fact * c_tarif) / workers_count
                else:
                    bonus = 0.0

        elif group == 'bosh':
            pct = 0.0
            bonus = 0.0

        return {
            "percent": round(pct, 1),
            "bonus": round(bonus)
        }

    @classmethod
    def calculate_period(cls, period):
        """Davr (oy) bo'yicha barcha hisob-kitoblarni amalga oshirish va saqlash"""
        rules = KPIRules.get_solo()
        categories = {c.id: c for c in ProductionCategory.objects.all()}
        
        # Kategoriyalar bo'yicha faol xodimlar sonini hisoblash
        active_counts_by_cat = {}
        for c_id in categories.keys():
            count = Employee.objects.filter(is_active=True, group='ish', production_category_id=c_id).count()
            active_counts_by_cat[c_id] = max(count, 1)

        items = period.items.select_related('employee', 'employee__production_category').all()

        total_oklad = Decimal(0)
        total_kpi = Decimal(0)
        total_advance = Decimal(0)
        total_salary = Decimal(0)
        total_rest = Decimal(0)

        for item in items:
            emp = item.employee
            if not item.is_active:
                continue

            # Ishlab chiqarish uchun plan va fakt kategoriyadan olinishi mumkin
            if item.group == 'ish' and item.employee.production_category:
                cat = item.employee.production_category
                calc_plan = cat.plan
                calc_fact = cat.fact
            else:
                calc_plan = item.plan
                calc_fact = item.fact

            res = cls.calculate_employee_kpi(
                emp=emp,
                plan=calc_plan,
                fact=calc_fact,
                rules=rules,
                categories=categories,
                active_counts_by_cat=active_counts_by_cat
            )

            item.percent = res["percent"]
            item.kpi_bonus = Decimal(res["bonus"])
            item.total_salary = item.oklad + item.kpi_bonus
            item.rest_to_pay = item.total_salary - item.advance
            item.save()

            total_oklad += item.oklad
            total_kpi += item.kpi_bonus
            total_advance += item.advance
            total_salary += item.total_salary
            total_rest += item.rest_to_pay

        period.total_oklad = total_oklad
        period.total_kpi = total_kpi
        period.total_advance = total_advance
        period.total_salary = total_salary
        period.total_rest = total_rest
        if period.status != 'closed':
            period.status = 'calculated'
        period.save()

        return period
