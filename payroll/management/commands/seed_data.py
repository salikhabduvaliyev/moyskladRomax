from decimal import Decimal
from datetime import date
from django.core.management.base import BaseCommand
from payroll.models import MoySkladConfig, KPIRules, ProductionCategory, Employee, PayrollPeriod, PayrollItem
from payroll.services.calculator import KPICalculator

class Command(BaseCommand):
    help = "Dastlabki ma'lumotlarni (Romax Akfa xodimlari, kategoriyalar, qoidalar) yuklash"

    def handle(self, *args, **options):
        self.stdout.write("Dastlabki ma'lumotlar yuklanmoqda...")

        # 1. MoySklad Config
        config = MoySkladConfig.get_solo()
        config.company_name = "Romax Akfa"
        config.save()

        # 2. KPI Rules
        rules = KPIRules.get_solo()
        rules.sot_rate = 1.0
        rules.sot_min = 100.0
        rules.op_base = Decimal("1500000")
        rules.op_t1 = 50.0
        rules.op_k1 = 0.8
        rules.op_t2 = 80.0
        rules.op_k2 = 1.0
        rules.op_t3 = 100.0
        rules.op_k3 = 1.1
        rules.op_t4 = 120.0
        rules.op_k4 = 1.2
        rules.men_t1 = 50.0
        rules.men_t2 = 80.0
        rules.men_r2 = 2.0
        rules.men_t3 = 100.0
        rules.men_r3 = 2.0
        rules.ish_min = 80.0
        rules.save()

        # 3. Production Categories
        cats_data = [
            {'name': 'PVX', 'prev': Decimal(420), 'g': 10.0, 'plan': Decimal(462), 'fact': Decimal(380), 'tarif': Decimal(60000), 'order': 1},
            {'name': 'Termo', 'prev': Decimal(260), 'g': 10.0, 'plan': Decimal(286), 'fact': Decimal(300), 'tarif': Decimal(80000), 'order': 2},
            {'name': 'Chempion', 'prev': Decimal(180), 'g': 10.0, 'plan': Decimal(198), 'fact': Decimal(150), 'tarif': Decimal(70000), 'order': 3},
            {'name': 'Alyuminiy', 'prev': Decimal(140), 'g': 10.0, 'plan': Decimal(154), 'fact': Decimal(160), 'tarif': Decimal(65000), 'order': 4},
        ]
        cat_objects = []
        for cd in cats_data:
            cat, _ = ProductionCategory.objects.update_or_create(
                name=cd['name'],
                defaults={
                    'prev_month_volume': cd['prev'],
                    'growth_percent': cd['g'],
                    'plan': cd['plan'],
                    'fact': cd['fact'],
                    'tarif': cd['tarif'],
                    'order_num': cd['order']
                }
            )
            cat_objects.append(cat)

        # 4. Employees
        raw_employees = [
            ('Бахромжон', 'Сотувчи шоурум', 'sot', Decimal(4000000)),
            ('Обиджон', 'Сотувчи шоурум', 'sot', Decimal(4000000)),
            ('Зарифа', 'Оператор шоурум', 'op', Decimal(3000000)),
            ('Мухлиса', 'Оператор шоурум', 'op', Decimal(3000000)),
            ('Элмирза Йулдошев', 'Рахбар', 'men', Decimal(6000000)),
            ('Хусниёр Азамов', 'Иш юритувчи', 'men', Decimal(5000000)),
            ('Равшанбек Кузиев', 'Цех ишчиси', 'ish', Decimal(3500000)),
            ('Рузматжон Шарипов', 'Цех ишчиси', 'ish', Decimal(3500000)),
            ('Афзалбек Эркинов', 'Цех ишчиси', 'ish', Decimal(3500000)),
            ('Чаросхон Раззокова', 'Цех ишчиси', 'ish', Decimal(3000000)),
            ('Улугбек Абдуфаттоев', 'Цех устаси', 'ish', Decimal(4500000)),
            ('Хамиджон Воисов', 'Цех бошлиги', 'ish', Decimal(5000000)),
            ('Халимжон Йулдошев', 'Бригадир ПВХ', 'ish', Decimal(4000000)),
            ('Бахтиёр Сайдкулов', 'Бригадир терм.', 'ish', Decimal(4000000)),
            ('Малика Муйдинова', 'Мастер', 'ish', Decimal(4000000)),
            ('Достон Абдувахобов', 'Монтажчи', 'ish', Decimal(3500000)),
            ('Рухниддин Хасанов', 'Монтажчи', 'ish', Decimal(3500000)),
            ('Мехриддин Йигиталиев', 'Монтаж', 'ish', Decimal(3500000)),
            ('Улугбек Туйчиев', 'Монтаж бошлиги', 'ish', Decimal(4500000)),
            ('Азамжон Гофуров', 'Омборчи', 'bosh', Decimal(3000000)),
            ('Аслиддин Йигиталиев', 'Ойнакчи', 'bosh', Decimal(3000000)),
            ('Санатжон Жураев', 'Ойнакчи', 'bosh', Decimal(3000000)),
            ('Темурмалик Облбердиев', 'Шофёр', 'bosh', Decimal(3500000)),
            ('Ёкутхон Хусанова', 'HR булими', 'bosh', Decimal(3500000)),
            ('Дилафруз Тошпулатова', 'Ошпаз', 'bosh', Decimal(2000000)),
        ]

        plans_by_group = {
            'sot': Decimal(600000000),
            'op': Decimal(80),
            'men': Decimal(1200000000),
            'ish': Decimal(120),
            'bosh': Decimal(0),
        }

        created_employees = []
        for i, (name, pos, grp, oklad) in enumerate(raw_employees):
            # Ishlab chiqarish kategoriyasini taqsimlash
            cat_rel = None
            if grp == 'ish':
                cat_rel = cat_objects[i % len(cat_objects)]

            base_plan = plans_by_group.get(grp, Decimal(0))
            if grp in ['sot', 'op', 'men']:
                plan_val = round(base_plan * Decimal(1 + (i % 3) * 0.1))
            else:
                plan_val = base_plan

            emp, _ = Employee.objects.update_or_create(
                name=name,
                defaults={
                    'position': pos,
                    'group': grp,
                    'oklad': oklad,
                    'production_category': cat_rel,
                    'manager_custom_rate': 1.0,
                    'default_plan': plan_val,
                    'order_num': i + 1,
                    'is_active': True
                }
            )
            created_employees.append(emp)

        # 5. Joriy oy davri (2026-10)
        curr_month = "2026-10"
        period, _ = PayrollPeriod.objects.get_or_create(
            month=curr_month,
            defaults={
                'date_from': date(2026, 10, 1),
                'date_to': date(2026, 10, 31),
                'status': 'draft'
            }
        )

        for i, emp in enumerate(created_employees):
            # Avans va fakt qiymatlari (prototip formulasi)
            avans_val = Decimal(round((float(emp.oklad) * (0.3 + (i % 4) * 0.1)) / 100000) * 100000)
            
            p_val = emp.default_plan
            if p_val > 0:
                f_val = Decimal(round(float(p_val) * (0.62 + ((i * 37) % 55) / 100.0)))
            else:
                f_val = Decimal(0)

            PayrollItem.objects.update_or_create(
                period=period,
                employee=emp,
                defaults={
                    'group': emp.group,
                    'production_category': emp.production_category,
                    'oklad': emp.oklad,
                    'plan': p_val,
                    'fact': f_val,
                    'advance': avans_val,
                    'is_active': emp.is_active,
                }
            )

        # Dastlabki hisob-kitobni o'tkazish
        KPICalculator.calculate_period(period)

        self.stdout.write(self.style.SUCCESS(f"Tayyor! {len(created_employees)} ta xodim va 2026-10 oylik ma'lumotlari yuklandi."))
