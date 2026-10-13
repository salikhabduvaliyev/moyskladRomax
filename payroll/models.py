from django.db import models
from django.utils import timezone


class MoySkladConfig(models.Model):
    """MoySklad API sozlamalari va Token"""
    token = models.CharField(max_length=255, blank=True, help_text="MoySklad API Bearer Token")
    base_url = models.CharField(max_length=255, default="https://api.moysklad.ru/api/remap/1.2")
    company_name = models.CharField(max_length=150, default="Romax Akfa")
    expense_item_name = models.CharField(
        max_length=150, 
        default="Начисление зарплаты", 
        help_text="Oylik hisoblash xarajat moddasi (Статья расходов)"
    )
    advance_expense_item_name = models.CharField(
        max_length=150, 
        default="Аванс", 
        help_text="Avans to'lovlari moddasi (Статья расходов)"
    )
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "MoySklad Sozlamasi"
        verbose_name_plural = "MoySklad Sozlamalari"

    def __str__(self):
        return f"{self.company_name} ({'Ulangan' if self.token else 'Tokensiz'})"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj


class KPIRules(models.Model):
    """Guruhlar bo'yicha KPI qoidalari"""
    # Sotuvchi qoidalari
    sot_rate = models.FloatField(default=1.0, help_text="Sotuvdan foiz (%)")
    sot_min = models.FloatField(default=100.0, help_text="Bonus uchun minimal plan foizi (%)")

    # Sotuv operatori qoidalari
    op_base = models.DecimalField(max_digits=14, decimal_places=2, default=1500000, help_text="Bonus bazasi (100%)")
    op_t1 = models.FloatField(default=50.0)
    op_k1 = models.FloatField(default=0.8)
    op_t2 = models.FloatField(default=80.0)
    op_k2 = models.FloatField(default=1.0)
    op_t3 = models.FloatField(default=100.0)
    op_k3 = models.FloatField(default=1.1)
    op_t4 = models.FloatField(default=120.0)
    op_k4 = models.FloatField(default=1.2)

    # Sotuv menejeri qoidalari
    men_t1 = models.FloatField(default=50.0, help_text="Pastki chegara (%)")
    men_t2 = models.FloatField(default=80.0, help_text="O'rta chegara (%)")
    men_r2 = models.FloatField(default=2.0, help_text="80% dan keyingi foiz (%)")
    men_t3 = models.FloatField(default=100.0, help_text="Yuqori chegara (%)")
    men_r3 = models.FloatField(default=2.0, help_text="100% dan keyingi foiz (%)")

    # Ishlab chiqarish qoidalari
    ish_min = models.FloatField(default=80.0, help_text="Ishlab chiqarish min plan bajarilishi (%)")

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "KPI Qoidalari"
        verbose_name_plural = "KPI Qoidalari"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj


class ProductionCategory(models.Model):
    """Ishlab chiqarish toifalari (PVX, Termo, Chempion, Alyuminiy)"""
    name = models.CharField(max_length=100, unique=True)
    moysklad_folder_id = models.CharField(max_length=100, blank=True, null=True, help_text="MoySklad tovarlar papkasi yoki xizmat ID")
    prev_month_volume = models.DecimalField(max_digits=14, decimal_places=2, default=0, help_text="O'tgan oy sotuv hajmi")
    growth_percent = models.FloatField(default=10.0, help_text="Rejalashtirilgan o'sish %")
    plan = models.DecimalField(max_digits=14, decimal_places=2, default=0, help_text="Oylik plan (dona/birlik)")
    fact = models.DecimalField(max_digits=14, decimal_places=2, default=0, help_text="Fakt ishlab chiqarilgan (dona/birlik)")
    tarif = models.DecimalField(max_digits=14, decimal_places=2, default=60000, help_text="Tarif (so'm/birlik)")
    order_num = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order_num', 'id']
        verbose_name = "Ishlab chiqarish kategoriyasi"
        verbose_name_plural = "Ishlab chiqarish kategoriyalari"

    def __str__(self):
        return self.name

    def calculate_plan(self):
        growth = float(self.growth_percent) / 100.0
        self.plan = round(float(self.prev_month_volume) * (1 + growth))
        return self.plan


class Employee(models.Model):
    """Xodimlar ma'lumotlari"""
    GROUP_CHOICES = [
        ('sot', 'Sotuvchi'),
        ('op', 'Sotuv operatori'),
        ('men', 'Sotuv menejeri'),
        ('ish', 'Ishlab chiqarish'),
        ('bosh', 'Boshqa (faqat oklad)'),
    ]

    moysklad_id = models.CharField(max_length=100, blank=True, null=True, unique=True, help_text="MoySklad Employee ID")
    name = models.CharField(max_length=200, verbose_name="F.I.SH")
    position = models.CharField(max_length=200, blank=True, verbose_name="Lavozim")
    group = models.CharField(max_length=20, choices=GROUP_CHOICES, default='bosh', verbose_name="Guruh")
    production_category = models.ForeignKey(
        ProductionCategory, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        related_name="employees",
        verbose_name="Ishlab chiqarish kategoriyasi"
    )
    oklad = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name="Oklad (so'm)")
    manager_custom_rate = models.FloatField(default=1.0, help_text="Menejer uchun 50-80% oralig'idagi shaxsiy stavka (%)")
    
    # Standart oylik reja va fakt (oylik kiritish uchun default qiymat)
    default_plan = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True, verbose_name="Faol xodim")
    order_num = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order_num', 'id']
        verbose_name = "Xodim"
        verbose_name_plural = "Xodimlar"

    def __str__(self):
        return f"{self.name} ({self.position or self.get_group_display()})"


class PayrollPeriod(models.Model):
    """Hisob-kitob qilinadigan oy davri"""
    STATUS_CHOICES = [
        ('draft', 'Qoralama'),
        ('calculated', 'Hisoblangan'),
        ('closed', 'Yopilgan'),
    ]

    month = models.CharField(max_length=7, unique=True, help_text="Format: YYYY-MM masalan 2026-10")
    date_from = models.DateField()
    date_to = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Umumiy moliyaviy natijalar
    total_oklad = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    total_kpi = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    total_advance = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    total_salary = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    total_rest = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    # MoySklad operatsiyalari
    moysklad_expense_id = models.CharField(max_length=150, blank=True, help_text="MoySklad Chiqim hujjati ID")
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-month']
        verbose_name = "Oylik hisob-kitob davri"
        verbose_name_plural = "Oylik hisob-kitob davrlari"

    def __str__(self):
        return f"{self.month} ({self.get_status_display()})"


class PayrollItem(models.Model):
    """Oy bo'yicha har bir xodimning hisob-kitob qatori"""
    period = models.ForeignKey(PayrollPeriod, related_name='items', on_delete=models.CASCADE)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payroll_items')
    group = models.CharField(max_length=20)
    production_category = models.ForeignKey(ProductionCategory, null=True, blank=True, on_delete=models.SET_NULL)
    
    oklad = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    plan = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    fact = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    percent = models.FloatField(default=0)
    kpi_bonus = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    advance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_salary = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    rest_to_pay = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    
    moysklad_adjustment_id = models.CharField(max_length=150, blank=True, help_text="MoySklad Korrektirovka ID")
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('period', 'employee')
        ordering = ['employee__order_num', 'id']
        verbose_name = "Oylik hisob qatori"
        verbose_name_plural = "Oylik hisob qatorlari"

    def __str__(self):
        return f"{self.employee.name} - {self.period.month}"
