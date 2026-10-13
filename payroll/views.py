import json
from decimal import Decimal
from datetime import datetime, date
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone

from .models import MoySkladConfig, KPIRules, ProductionCategory, Employee, PayrollPeriod, PayrollItem
from .services.moysklad import MoySkladService
from .services.calculator import KPICalculator


def index(request):
    """Asosiy Oylik va KPI boshqaruv paneli"""
    config = MoySkladConfig.get_solo()
    rules = KPIRules.get_solo()
    categories = ProductionCategory.objects.all()
    
    # Joriy oy davri
    current_month = timezone.now().strftime("%Y-%m")
    period = PayrollPeriod.objects.filter(month=current_month).first()
    if not period:
        # Eng oxirgi mavjud davr
        period = PayrollPeriod.objects.first()
    
    context = {
        'config': config,
        'rules': rules,
        'categories': categories,
        'period': period,
    }
    return render(request, 'payroll/index.html', context)


@require_GET
def get_period_data(request):
    """Tanlangan oy bo'yicha to'liq ma'lumotlarni JSON formatda qaytarish"""
    month = request.GET.get('month')
    if not month:
        month = timezone.now().strftime("%Y-%m")

    # Sana hisoblash
    d_from_param = request.GET.get('date_from')
    d_to_param = request.GET.get('date_to')
    d_from = None
    d_to = None
    if d_from_param and d_to_param:
        try:
            d_from = datetime.strptime(d_from_param, '%Y-%m-%d').date()
            d_to = datetime.strptime(d_to_param, '%Y-%m-%d').date()
        except Exception:
            pass

    if not d_from or not d_to:
        try:
            y, m = map(int, month.split('-'))
            # Oyning oxirgi kuni
            if m == 12:
                next_month = date(y + 1, 1, 1)
            else:
                next_month = date(y, m + 1, 1)
            d_from = date(y, m, 1)
            d_to = date.fromordinal(next_month.toordinal() - 1)
        except Exception:
            d_from = date(2026, 10, 1)
            d_to = date(2026, 10, 31)

    # 1. Agar MoySklad token mavjud bo'lsa, to'g'ridan-to'g'ri REAL TIME rejimida hisoblab berish
    total_plans = {}
    if request.GET.get('total_plan_sot'):
        try: total_plans['sot'] = float(request.GET.get('total_plan_sot'))
        except ValueError: pass
    if request.GET.get('total_plan_op'):
        try: total_plans['op'] = float(request.GET.get('total_plan_op'))
        except ValueError: pass
    if request.GET.get('total_plan_men'):
        try: total_plans['men'] = float(request.GET.get('total_plan_men'))
        except ValueError: pass
    if request.GET.get('tarif_pvh'):
        try: total_plans['tarif_pvh'] = float(request.GET.get('tarif_pvh'))
        except ValueError: pass
    if request.GET.get('tarif_termo'):
        try: total_plans['tarif_termo'] = float(request.GET.get('tarif_termo'))
        except ValueError: pass
    if request.GET.get('tarif_montaj'):
        try: total_plans['tarif_montaj'] = float(request.GET.get('tarif_montaj'))
        except ValueError: pass
    if request.GET.get('selected_op_ids'):
        raw = request.GET.get('selected_op_ids')
        total_plans['selected_op_ids'] = [x.strip() for x in raw.split(',') if x.strip()]
    if request.GET.get('selected_men_ids'):
        raw_men = request.GET.get('selected_men_ids')
        total_plans['selected_men_ids'] = [x.strip() for x in raw_men.split(',') if x.strip()]

    config = MoySkladConfig.get_solo()
    if config.token:
        try:
            from .services.realtime import RealtimeMoySkladEngine
            engine = RealtimeMoySkladEngine(token=config.token, base_url=config.base_url)
            realtime_data = engine.get_realtime_payroll(month=month, date_from=d_from, date_to=d_to, total_plans=total_plans)
            return JsonResponse(realtime_data)
        except Exception as e:
            logger.exception("Realtime payroll calculation error, falling back to database")

    period, created = PayrollPeriod.objects.get_or_create(
        month=month,
        defaults={
            'date_from': d_from,
            'date_to': d_to,
            'status': 'draft'
        }
    )

    # Agar xodimlar uchun qatorlar bo'lmasa, faol xodimlardan yaratish
    if not period.items.exists():
        employees = Employee.objects.filter(is_active=True)
        for emp in employees:
            PayrollItem.objects.create(
                period=period,
                employee=emp,
                group=emp.group,
                production_category=emp.production_category,
                oklad=emp.oklad,
                plan=emp.default_plan,
                fact=Decimal(0),
                advance=Decimal(0),
                is_active=True
            )
        KPICalculator.calculate_period(period)

    rules = KPIRules.get_solo()
    categories = ProductionCategory.objects.all()
    config = MoySkladConfig.get_solo()

    items_data = []
    for it in period.items.select_related('employee', 'employee__production_category').all():
        emp = it.employee
        cat_name = it.employee.production_category.name if it.employee.production_category else ""
        items_data.append({
            'id': it.id,
            'emp_id': emp.id,
            'name': emp.name,
            'position': emp.position,
            'group': it.group,
            'category_id': emp.production_category_id,
            'category_name': cat_name,
            'manager_rate': emp.manager_custom_rate,
            'oklad': float(it.oklad),
            'plan': float(it.plan),
            'fact': float(it.fact),
            'percent': it.percent,
            'kpi_bonus': float(it.kpi_bonus),
            'advance': float(it.advance),
            'total_salary': float(it.total_salary),
            'rest_to_pay': float(it.rest_to_pay),
            'is_active': it.is_active,
        })

    cats_data = []
    for c in categories:
        cats_data.append({
            'id': c.id,
            'name': c.name,
            'prev_month_volume': float(c.prev_month_volume),
            'growth_percent': c.growth_percent,
            'plan': float(c.plan),
            'fact': float(c.fact),
            'tarif': float(c.tarif),
            'workers_count': Employee.objects.filter(is_active=True, group='ish', production_category=c).count()
        })

    return JsonResponse({
        'success': True,
        'period': {
            'id': period.id,
            'month': period.month,
            'date_from': period.date_from.strftime("%Y-%m-%d"),
            'date_to': period.date_to.strftime("%Y-%m-%d"),
            'status': period.status,
            'status_display': period.get_status_display(),
            'total_oklad': float(period.total_oklad),
            'total_kpi': float(period.total_kpi),
            'total_advance': float(period.total_advance),
            'total_salary': float(period.total_salary),
            'total_rest': float(period.total_rest),
            'moysklad_expense_id': period.moysklad_expense_id,
        },
        'rules': {
            'sot': {'rate': rules.sot_rate, 'min': rules.sot_min},
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
        'categories': cats_data,
        'items': items_data,
        'config': {
            'has_token': bool(config.token),
            'token_preview': f"{config.token[:6]}...{config.token[-4:]}" if config.token and len(config.token) > 10 else ("Bor" if config.token else "Kiritilmagan"),
            'company_name': config.company_name,
            'last_synced': config.last_synced_at.strftime("%Y-%m-%d %H:%M") if config.last_synced_at else None
        }
    })


@csrf_exempt
@require_POST
def save_rules_and_categories(request):
    """Qoidalar va kategoriyalar sozlamalarini saqlash"""
    try:
        data = json.loads(request.body)
        rules_data = data.get('rules', {})
        cats_data = data.get('categories', [])

        rules = KPIRules.get_solo()
        if 'sot' in rules_data:
            rules.sot_rate = float(rules_data['sot'].get('rate', rules.sot_rate))
            rules.sot_min = float(rules_data['sot'].get('min', rules.sot_min))
        if 'op' in rules_data:
            rules.op_base = Decimal(rules_data['op'].get('base', rules.op_base))
            rules.op_t1 = float(rules_data['op'].get('t1', rules.op_t1))
            rules.op_k1 = float(rules_data['op'].get('k1', rules.op_k1))
            rules.op_t2 = float(rules_data['op'].get('t2', rules.op_t2))
            rules.op_k2 = float(rules_data['op'].get('k2', rules.op_k2))
            rules.op_t3 = float(rules_data['op'].get('t3', rules.op_t3))
            rules.op_k3 = float(rules_data['op'].get('k3', rules.op_k3))
            rules.op_t4 = float(rules_data['op'].get('t4', rules.op_t4))
            rules.op_k4 = float(rules_data['op'].get('k4', rules.op_k4))
        if 'men' in rules_data:
            rules.men_t1 = float(rules_data['men'].get('t1', rules.men_t1))
            rules.men_t2 = float(rules_data['men'].get('t2', rules.men_t2))
            rules.men_r2 = float(rules_data['men'].get('r2', rules.men_r2))
            rules.men_t3 = float(rules_data['men'].get('t3', rules.men_t3))
            rules.men_r3 = float(rules_data['men'].get('r3', rules.men_r3))
        if 'ish' in rules_data:
            rules.ish_min = float(rules_data['ish'].get('min', rules.ish_min))
        rules.save()

        for cd in cats_data:
            c_id = cd.get('id')
            if c_id:
                ProductionCategory.objects.filter(id=c_id).update(
                    prev_month_volume=Decimal(cd.get('prev_month_volume', 0)),
                    growth_percent=float(cd.get('growth_percent', 10)),
                    plan=Decimal(cd.get('plan', 0)),
                    fact=Decimal(cd.get('fact', 0)),
                    tarif=Decimal(cd.get('tarif', 60000)),
                )

        return JsonResponse({'success': True, 'message': "Qoidalar va kategoriyalar muvaffaqiyatli saqlandi!"})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_POST
def update_payroll_items(request):
    """Xodimlar plani, guruhi va faktlarini yangilash"""
    try:
        data = json.loads(request.body)
        period_id = data.get('period_id')
        items = data.get('items', [])

        period = get_object_or_404(PayrollPeriod, id=period_id)

        for it in items:
            it_id = it.get('id')
            if it_id:
                item_obj = PayrollItem.objects.filter(id=it_id, period=period).first()
                if item_obj:
                    if 'group' in it:
                        item_obj.group = it['group']
                        item_obj.employee.group = it['group']
                    if 'category_id' in it:
                        item_obj.production_category_id = it['category_id']
                        item_obj.employee.production_category_id = it['category_id']
                    if 'manager_rate' in it:
                        item_obj.employee.manager_custom_rate = float(it['manager_rate'])
                    if 'plan' in it:
                        item_obj.plan = Decimal(it['plan'])
                    if 'fact' in it:
                        item_obj.fact = Decimal(it['fact'])
                    if 'advance' in it:
                        item_obj.advance = Decimal(it['advance'])
                    if 'is_active' in it:
                        item_obj.is_active = bool(it['is_active'])
                        item_obj.employee.is_active = bool(it['is_active'])

                    item_obj.employee.save()
                    item_obj.save()

        # Qayta hisoblash
        KPICalculator.calculate_period(period)

        return JsonResponse({'success': True, 'message': "Ma'lumotlar saqlandi va hisoblandi!"})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_POST
def calculate_period_view(request):
    """Hisoblash tugmasi bosilganda davrni qayta hisoblash"""
    try:
        data = json.loads(request.body)
        period_id = data.get('period_id')
        period = get_object_or_404(PayrollPeriod, id=period_id)
        
        KPICalculator.calculate_period(period)
        return JsonResponse({'success': True, 'message': "Oylik va KPI muvaffaqiyatli hisoblandi!"})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# --- MoySklad API Integratsiya Viewlari ---

@csrf_exempt
@require_POST
def moysklad_test_connection(request):
    """MoySklad API tokenini sinash"""
    try:
        data = json.loads(request.body)
        token = data.get('token', '').strip()
        service = MoySkladService(token=token if token else None)
        res = service.test_connection()
        return JsonResponse(res)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_POST
def moysklad_save_config(request):
    """MoySklad sozlamalarini saqlash"""
    try:
        data = json.loads(request.body)
        token = data.get('token', '').strip()
        company_name = data.get('company_name', '').strip()
        
        config = MoySkladConfig.get_solo()
        if token:
            config.token = token
        if company_name:
            config.company_name = company_name
        config.save()

        # Tokenni darhol tekshirish
        service = MoySkladService(token=config.token)
        test_res = service.test_connection()

        return JsonResponse({
            'success': True,
            'message': "MoySklad sozlamalari saqlandi!",
            'connection_test': test_res
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_POST
def moysklad_sync_employees(request):
    """MoySklad'dan xodimlarni yuklash"""
    try:
        service = MoySkladService()
        res = service.sync_employees()
        return JsonResponse(res)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_POST
def moysklad_sync_facts(request):
    """MoySklad'dan sotuv faktlari va avanslarni yuklash"""
    try:
        data = json.loads(request.body)
        period_id = data.get('period_id')
        period = get_object_or_404(PayrollPeriod, id=period_id)

        service = MoySkladService()
        sales_res = service.sync_sales_facts(period.date_from, period.date_to)
        adv_res = service.sync_advances(period.date_from, period.date_to)

        updated_facts = 0
        updated_advances = 0

        # Agar MoySklad'da faktlar topilsa, xodimlarga yozish
        if sales_res.get('success'):
            facts = sales_res.get('facts', {})
            for item in period.items.all():
                emp = item.employee
                if emp.moysklad_id and emp.moysklad_id in facts:
                    f_data = facts[emp.moysklad_id]
                    if item.group in ['sot', 'men']:
                        item.fact = Decimal(f_data.get('sales_sum', 0))
                        item.save()
                        updated_facts += 1
                    elif item.group == 'op':
                        item.fact = Decimal(f_data.get('order_count', 0))
                        item.save()
                        updated_facts += 1

        if adv_res.get('success'):
            advances = adv_res.get('advances', {})
            for item in period.items.all():
                emp = item.employee
                if emp.moysklad_id and emp.moysklad_id in advances:
                    item.advance = Decimal(advances[emp.moysklad_id])
                    item.save()
                    updated_advances += 1

        # Qayta hisoblash
        KPICalculator.calculate_period(period)

        return JsonResponse({
            'success': True,
            'message': f"MoySklad'dan ma'lumotlar yangilandi ({updated_facts} ta fakt, {updated_advances} ta avans).",
            'sales_sync': sales_res,
            'advance_sync': adv_res
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_POST
def moysklad_close_month(request):
    """Oyni yakunlash va MoySklad'ga Rasxod va Korrektirovka hujjatlarini yozish"""
    try:
        data = json.loads(request.body)
        period_id = data.get('period_id')
        month = data.get('month')
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        total_salary = float(data.get('total_salary', 0) or 0)
        items = data.get('items', [])

        period = None
        if period_id:
            period = PayrollPeriod.objects.filter(id=period_id).first()
        if not period and month:
            period = PayrollPeriod.objects.filter(month=month).first()

        if period:
            try:
                KPICalculator.calculate_period(period)
            except Exception as e_calc:
                logger.warning(f"Error in KPICalculator during close_month: {e_calc}")

        # MoySklad API xizmati orqali hujjat yaratish
        service = MoySkladService()
        if service.token:
            res = service.close_month_in_moysklad(
                month=month,
                date_to=date_to,
                total_salary=total_salary,
                items=items,
                payroll_period=period
            )
            if not res.get('success'):
                return JsonResponse(res, status=400)
            return JsonResponse(res)
        else:
            # Agar token bo'lmasa, lokal tizimda yopish (demo rejim)
            if period:
                period.status = 'closed'
                period.closed_at = timezone.now()
                period.moysklad_expense_id = f"DEMO-{int(datetime.now().timestamp())}"
                period.save()
            return JsonResponse({
                'success': True,
                'message': "Oy tizimda yopildi (Token kiritilmagani sababli MoySklad'ga yuborilmadi, qoralama yopildi)."
            })
    except Exception as e:
        logger.exception("Error in moysklad_close_month")
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
