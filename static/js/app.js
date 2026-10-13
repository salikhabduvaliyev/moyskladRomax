/* Finora Systems · Oylik va KPI Moduli Real-Time Engine (Romax Akfa) */

const state = {
    currentTab: 'plan',
    period: null,
    rules: null,
    categories: [],
    production_summary: [],
    items: [],
    config: null,
    selected_op_ids: null,
    selected_men_ids: null,
    manual_production_facts: {},
    total_plans: {
        op: 2000000000,
        men: 2400000000,
        tarif_pvh: 60000,
        tarif_termo: 80000,
        tarif_montaj: 50000,
        op_count: 2,
        op_target_count: 2,
        men_count: 2,
        men_target_count: 2,
        pvh_count: 8,
        termo_count: 1,
        montaj_count: 5
    },
    calced: false,
    closed: false
};

const G_NAMES = {
    op: 'Sotuv operatori',
    men: 'Sotuv menejeri / Sotuvchi',
    ish: 'Ishlab chiqarish / Montaj',
    bosh: 'Boshqa (faqat oklad)'
};

const PD_UNITS = {
    op: 'so\'m',
    men: 'so\'m',
    ish: 'm²',
    bosh: '—'
};

// Yordamchi raqam formatlash funksiyasi (bo'shliq - probel bilan ajratish)
const f = (n, maxDecimals = 0) => {
    if (n === null || n === undefined || isNaN(n)) return '0';
    if (maxDecimals > 0 && n % 1 !== 0) {
        const fixed = Number(n).toFixed(maxDecimals).replace(/\.?0+$/, '');
        const parts = fixed.split('.');
        parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
        return parts.join('.');
    }
    return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
};

function parseFormattedNumber(val) {
    if (val === null || val === undefined) return 0;
    const clean = String(val).replace(/\s+/g, '').replace(/,/g, '.');
    const num = parseFloat(clean);
    return isNaN(num) ? 0 : num;
}

// Input maydonlarida kiritish paytida real-time 1 000 000 ko'rinishida formatlash va kursorni saqlash
function handleFormattedNumberInput(inputEl, callback, isFloat = false) {
    const origVal = inputEl.value;
    const selStart = inputEl.selectionStart !== null ? inputEl.selectionStart : origVal.length;
    
    // Kursor oldidagi raqamlarni (va nuqtani) sanab olamiz
    const charsBeforeCursor = origVal.slice(0, selStart).replace(/[^\d.]/g, '').length;
    
    // Faqat raqamlar va (agar float bo'lsa) bitta nuqtani qoldiramiz
    let clean = origVal.replace(/[^\d.,]/g, '').replace(/,/g, '.');
    if (!isFloat) {
        clean = clean.replace(/\./g, '');
    } else {
        const dotIdx = clean.indexOf('.');
        if (dotIdx !== -1) {
            clean = clean.slice(0, dotIdx + 1) + clean.slice(dotIdx + 1).replace(/\./g, '');
        }
    }
    
    if (clean === '') {
        inputEl.value = '';
        if (callback) callback(0);
        return;
    }
    
    // Butun qismini har 3 ta raqamdan keyin probel bilan ajratamiz
    const parts = clean.split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
    const formatted = parts.join('.');
    
    inputEl.value = formatted;
    
    // Kursorni kiritilgan raqamdan keyingi to'g'ri pozitsiyaga qo'yish
    let newCursorPos = 0;
    if (charsBeforeCursor === 0) {
        newCursorPos = 0;
    } else {
        let countedChars = 0;
        for (let i = 0; i < formatted.length; i++) {
            if (/[\d.]/.test(formatted[i])) {
                countedChars++;
            }
            if (countedChars >= charsBeforeCursor) {
                newCursorPos = i + 1;
                break;
            }
        }
        if (countedChars < charsBeforeCursor) newCursorPos = formatted.length;
    }
    try {
        inputEl.setSelectionRange(newCursorPos, newCursorPos);
    } catch (err) {}
    
    const num = parseFloat(clean) || 0;
    if (callback) callback(num);
}

const $ = (s) => document.querySelector(s);

// Operator tanlash va boshqaruv funksiyalari
function isOpSelected(e) {
    if (!state.selected_op_ids) return true;
    const strId = String(e.id);
    const strUid = String(e.emp_id || '');
    return state.selected_op_ids.includes(strId) || (strUid && state.selected_op_ids.includes(strUid));
}

function getTargetOpCount() {
    const allOps = state.items.filter(e => e.group === 'op' && e.is_active);
    const max = allOps.length || 1;
    let target = parseInt(state.total_plans.op_target_count, 10);
    if (isNaN(target) || target < 1) target = 1;
    if (target > max) target = max;
    return target;
}

function ensureSelectedOpIds() {
    const allOps = state.items.filter(e => e.group === 'op' && e.is_active);
    const target = getTargetOpCount();
    if (!state.selected_op_ids || !Array.isArray(state.selected_op_ids) || state.selected_op_ids.length === 0) {
        state.selected_op_ids = allOps.slice(0, target).map(e => String(e.emp_id || e.id));
    } else {
        const validIds = allOps.map(e => String(e.emp_id || e.id));
        state.selected_op_ids = state.selected_op_ids.filter(id => validIds.includes(id));
        if (state.selected_op_ids.length === 0) {
            state.selected_op_ids = allOps.slice(0, target).map(e => String(e.emp_id || e.id));
        }
    }
}

function applyOperatorPlans() {
    const allOps = state.items.filter(e => e.group === 'op');
    const selectedCount = (state.selected_op_ids && state.selected_op_ids.length) || 0;
    const indPlan = selectedCount > 0 ? Math.round(state.total_plans.op / selectedCount) : 0;

    allOps.forEach(e => {
        const isSel = isOpSelected(e);
        e.plan = isSel ? indPlan : 0;
        const inp = document.getElementById(`emp-plan-${e.id}`);
        if (inp) inp.value = f(e.plan);
    });
}

function updateOpUI() {
    const selectedCount = (state.selected_op_ids && state.selected_op_ids.length) || 0;
    const allOps = state.items.filter(e => e.group === 'op');
    const max = allOps.length || 1;
    const indPlan = selectedCount > 0 ? Math.round(state.total_plans.op / selectedCount) : 0;

    const disp = document.getElementById('indPlanOpDisplay');
    if (disp) disp.textContent = selectedCount > 0 ? `Har biriga: ${f(indPlan)} so'm` : `Rejali operator tanlanmagan (0 so'm)`;

    const badge = document.getElementById('opCountBadge');
    if (badge) badge.textContent = `${selectedCount} nafar rejali operator`;

    const selBadge = document.getElementById('opSelectedBadge');
    if (selBadge) selBadge.textContent = `${selectedCount} / ${max} tanlangan`;

    const countInp = document.getElementById('inputTargetOpCount');
    if (countInp && document.activeElement !== countInp) countInp.value = selectedCount;

    allOps.forEach(e => {
        const isSel = isOpSelected(e);
        const stSpan = document.getElementById(`op-status-${e.id}`);
        if (stSpan) {
            stSpan.style.color = isSel ? 'var(--pr)' : 'var(--tx-muted)';
            stSpan.textContent = isSel ? `✓ Reja oladi (${f(indPlan)} so'm)` : `— Rejasiz (0 so'm)`;
        }
        const chk = document.querySelector(`.op-plan-checkbox[data-emp-id="${e.id}"]`);
        if (chk) chk.checked = isSel;
        const box = chk ? chk.closest('.op-select-item') : null;
        if (box) {
            box.style.borderColor = isSel ? 'var(--pr)' : 'var(--bd)';
            box.style.background = isSel ? 'rgba(37,99,235,0.03)' : 'var(--card)';
        }
    });
}

function onOpTargetCountInput(val) {
    const allOps = state.items.filter(e => e.group === 'op' && e.is_active);
    let num = parseInt(val, 10);
    if (isNaN(num) || num < 0) num = 0;
    if (num > allOps.length) num = allOps.length;
    state.total_plans.op_target_count = num;

    ensureSelectedOpIds();
    while (state.selected_op_ids.length < num) {
        const nextOp = allOps.find(e => !isOpSelected(e));
        if (nextOp) {
            state.selected_op_ids.push(String(nextOp.emp_id || nextOp.id));
        } else {
            break;
        }
    }
    if (state.selected_op_ids.length > num) {
        state.selected_op_ids = state.selected_op_ids.slice(0, num);
    }

    applyOperatorPlans();
    updateOpUI();
}

function onOpTargetCountChange(val) {
    onOpTargetCountInput(val);
    onPlanChange('op', state.total_plans.op);
}

function onOpCheckboxChange(empId, empUid, isChecked) {
    const idToUse = String(empUid || empId);

    if (isChecked) {
        if (!state.selected_op_ids.includes(idToUse)) {
            state.selected_op_ids.push(idToUse);
        }
    } else {
        state.selected_op_ids = state.selected_op_ids.filter(id => id !== idToUse && id !== String(empId));
    }

    state.total_plans.op_target_count = state.selected_op_ids.length;
    applyOperatorPlans();
    updateOpUI();
    onPlanChange('op', state.total_plans.op);
}

// Sotuv menejerlari tanlash va boshqaruv funksiyalari
function isMenSelected(e) {
    if (!state.selected_men_ids) return true;
    const strId = String(e.id);
    const strUid = String(e.emp_id || '');
    return state.selected_men_ids.includes(strId) || (strUid && state.selected_men_ids.includes(strUid));
}

function getTargetMenCount() {
    const allMen = state.items.filter(e => e.group === 'men' && e.is_active);
    const max = allMen.length || 1;
    let target = parseInt(state.total_plans.men_target_count, 10);
    if (isNaN(target) || target < 1) target = 1;
    if (target > max) target = max;
    return target;
}

function ensureSelectedMenIds() {
    const allMen = state.items.filter(e => e.group === 'men' && e.is_active);
    const target = getTargetMenCount();
    if (!state.selected_men_ids || !Array.isArray(state.selected_men_ids) || state.selected_men_ids.length === 0) {
        state.selected_men_ids = allMen.slice(0, target).map(e => String(e.emp_id || e.id));
    } else {
        const validIds = allMen.map(e => String(e.emp_id || e.id));
        state.selected_men_ids = state.selected_men_ids.filter(id => validIds.includes(id));
        if (state.selected_men_ids.length === 0) {
            state.selected_men_ids = allMen.slice(0, target).map(e => String(e.emp_id || e.id));
        }
    }
}

function applyManagerPlans() {
    const allMen = state.items.filter(e => e.group === 'men');
    const selectedCount = (state.selected_men_ids && state.selected_men_ids.length) || 0;
    const indPlan = selectedCount > 0 ? Math.round(state.total_plans.men / selectedCount) : 0;

    allMen.forEach(e => {
        const isSel = isMenSelected(e);
        e.plan = isSel ? indPlan : 0;
        const inp = document.getElementById(`emp-plan-${e.id}`);
        if (inp) inp.value = f(e.plan);
    });
}

function updateMenUI() {
    const selectedCount = (state.selected_men_ids && state.selected_men_ids.length) || 0;
    const allMen = state.items.filter(e => e.group === 'men');
    const max = allMen.length || 1;
    const indPlan = selectedCount > 0 ? Math.round(state.total_plans.men / selectedCount) : 0;

    const disp = document.getElementById('indPlanMenDisplay');
    if (disp) disp.textContent = selectedCount > 0 ? `Har biriga: ${f(indPlan)} so'm` : `Rejali sotuvchi tanlanmagan (0 so'm)`;

    const badge = document.getElementById('menCountBadge');
    if (badge) badge.textContent = `${selectedCount} nafar rejali sotuvchi`;

    const selBadge = document.getElementById('menSelectedBadge');
    if (selBadge) selBadge.textContent = `${selectedCount} / ${max} tanlangan`;

    const countInp = document.getElementById('inputTargetMenCount');
    if (countInp && document.activeElement !== countInp) countInp.value = selectedCount;

    allMen.forEach(e => {
        const isSel = isMenSelected(e);
        const stSpan = document.getElementById(`men-status-${e.id}`);
        if (stSpan) {
            stSpan.style.color = isSel ? 'var(--pr)' : 'var(--tx-muted)';
            stSpan.textContent = isSel ? `✓ Reja oladi (${f(indPlan)} so'm)` : `— Rejasiz (0 so'm)`;
        }
        const chk = document.querySelector(`.men-plan-checkbox[data-emp-id="${e.id}"]`);
        if (chk) chk.checked = isSel;
        const box = chk ? chk.closest('.men-select-item') : null;
        if (box) {
            box.style.borderColor = isSel ? 'var(--pr)' : 'var(--bd)';
            box.style.background = isSel ? 'rgba(37,99,235,0.03)' : 'var(--card)';
        }
    });
}

function onMenTargetCountInput(val) {
    const allMen = state.items.filter(e => e.group === 'men' && e.is_active);
    let num = parseInt(val, 10);
    if (isNaN(num) || num < 0) num = 0;
    if (num > allMen.length) num = allMen.length;
    state.total_plans.men_target_count = num;

    ensureSelectedMenIds();
    while (state.selected_men_ids.length < num) {
        const nextMen = allMen.find(e => !isMenSelected(e));
        if (nextMen) {
            state.selected_men_ids.push(String(nextMen.emp_id || nextMen.id));
        } else {
            break;
        }
    }
    if (state.selected_men_ids.length > num) {
        state.selected_men_ids = state.selected_men_ids.slice(0, num);
    }

    applyManagerPlans();
    updateMenUI();
}

function onMenTargetCountChange(val) {
    onMenTargetCountInput(val);
    onPlanChange('men', state.total_plans.men);
}

function onMenCheckboxChange(empId, empUid, isChecked) {
    const idToUse = String(empUid || empId);

    if (isChecked) {
        if (!state.selected_men_ids.includes(idToUse)) {
            state.selected_men_ids.push(idToUse);
        }
    } else {
        state.selected_men_ids = state.selected_men_ids.filter(id => id !== idToUse && id !== String(empId));
    }

    state.total_plans.men_target_count = state.selected_men_ids.length;
    applyManagerPlans();
    updateMenUI();
    onPlanChange('men', state.total_plans.men);
}

// Ishlab chiqarish hajmini qo'lda kiritish va qayta hisoblash funksiyalari
function onProductionVolumeInput(empId, val) {
    const num = typeof val === 'number' ? Math.max(0, val) : Math.max(0, parseFloat(val) || 0);
    state.manual_production_facts[String(empId)] = num;

    if (state.production_summary) {
        const p = state.production_summary.find(x => String(x.id) === String(empId) || String(x.emp_id) === String(empId));
        if (p) {
            p.fact_m2 = num;
            p.is_manual = true;
            p.bonus = Math.round(num * p.tarif);
            p.total_salary = p.oklad + p.bonus;

            const bEl = document.getElementById(`prod-bonus-${p.id}`);
            if (bEl) {
                bEl.textContent = f(p.bonus);
                bEl.style.color = p.bonus > 0 ? 'var(--ok)' : 'var(--tx-muted)';
            }
            const tEl = document.getElementById(`prod-tot-${p.id}`);
            if (tEl) tEl.textContent = f(p.total_salary);

            const inEl = document.getElementById(`prod-fact-${p.id}`);
            if (inEl) {
                inEl.style.color = num > 0 ? 'var(--pr)' : 'var(--tx-muted)';
            }

            const sEl = document.getElementById(`prod-status-${p.id}`);
            if (sEl) {
                sEl.innerHTML = `<span class="chip" style="background:rgba(234,88,12,0.12); color:#ea580c; font-weight:700; font-size:11px;">Qo'lda kiritildi</span>`;
            }

            const rwEl = document.getElementById(`prod-reset-wrap-${p.id}`);
            if (rwEl) {
                rwEl.innerHTML = `<button class="b b-secondary" style="padding:2px 7px; font-size:11px; margin-left:4px; height:26px;" onclick="resetProductionVolume('${p.id}')" title="MoySklad avtomatik faktiga qaytarish (↺ Avto: ${p.auto_fact_m2 || 0} m²)">↺ Avto</button>`;
            }
        }
    }

    const it = state.items.find(x => String(x.id) === String(empId) || String(x.emp_id) === String(empId));
    if (it) {
        it.fact = num;
        const p = state.production_summary?.find(x => String(x.id) === String(empId));
        it.kpi_bonus = p ? p.bonus : 0;
        it.total_salary = it.oklad + it.kpi_bonus;
        it.rest_to_pay = it.total_salary - it.advance;
    }
}

function resetProductionVolume(empId) {
    delete state.manual_production_facts[String(empId)];
    if (state.production_summary) {
        const p = state.production_summary.find(x => String(x.id) === String(empId) || String(x.emp_id) === String(empId));
        if (p) {
            p.fact_m2 = p.auto_fact_m2 || 0;
            p.is_manual = false;
            p.bonus = Math.round(p.fact_m2 * p.tarif);
            p.total_salary = p.oklad + p.bonus;
        }
    }
    const it = state.items.find(x => String(x.id) === String(empId) || String(x.emp_id) === String(empId));
    if (it) {
        const p = state.production_summary?.find(x => String(x.id) === String(empId));
        it.fact = p ? p.fact_m2 : 0;
        it.kpi_bonus = p ? p.bonus : 0;
        it.total_salary = it.oklad + it.kpi_bonus;
        it.rest_to_pay = it.total_salary - it.advance;
    }
    const prodTableBody = document.getElementById('productionTableBody');
    if (prodTableBody) {
        prodTableBody.innerHTML = renderProductionRows();
    } else {
        draw();
    }
}

// Boshlang'ich yuklash
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initDates();
    loadPeriodData();
});

function initTheme() {
    const saved = localStorage.getItem('finora_theme') || 'light';
    document.documentElement.setAttribute('data-theme', saved);
    $('#themeIcon').textContent = saved === 'dark' ? '☀️' : '🌙';
}

function toggleTheme() {
    const curr = document.documentElement.getAttribute('data-theme') || 'light';
    const next = curr === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('finora_theme', next);
    $('#themeIcon').textContent = next === 'dark' ? '☀️' : '🌙';
}

function initDates() {
    const defaultYm = '2026-10';
    $('#mon').value = defaultYm;
    $('#d1').value = '2026-10-01';
    $('#d2').value = '2026-10-31';

    $('#mon').onchange = (e) => {
        const [y, m] = e.target.value.split('-');
        const lastDay = new Date(y, m, 0).getDate();
        $('#d1').value = `${e.target.value}-01`;
        $('#d2').value = `${e.target.value}-${String(lastDay).padStart(2, '0')}`;
        loadPeriodData();
    };

    $('#d1').onchange = () => loadPeriodData();
    $('#d2').onchange = () => loadPeriodData();
}

// Serverdan ma'lumotlarni REAL TIME yuklash
async function loadPeriodData() {
    const mon = $('#mon').value;
    const d1 = $('#d1') ? $('#d1').value : '';
    const d2 = $('#d2') ? $('#d2').value : '';
    const tp = state.total_plans;
    try {
        const pObj = {
            month: mon,
            date_from: d1,
            date_to: d2,
            total_plan_op: tp.op,
            total_plan_men: tp.men,
            tarif_pvh: tp.tarif_pvh,
            tarif_termo: tp.tarif_termo,
            tarif_montaj: tp.tarif_montaj
        };
        if (state.selected_op_ids && state.selected_op_ids.length) {
            pObj.selected_op_ids = state.selected_op_ids.join(',');
        }
        if (state.selected_men_ids && state.selected_men_ids.length) {
            pObj.selected_men_ids = state.selected_men_ids.join(',');
        }
        const params = new URLSearchParams(pObj);
        const resp = await fetch(`/api/period-data/?${params.toString()}`);
        const data = await resp.json();
        
        if (data.success) {
            state.period = data.period;
            state.rules = data.rules;
            state.categories = data.categories || [];
            state.production_summary = data.production_summary || [];
            state.items = data.items;
            state.config = data.config;
            if (data.total_plans) {
                state.total_plans = Object.assign(state.total_plans, data.total_plans);
            }
            ensureSelectedOpIds();
            applyOperatorPlans();
            ensureSelectedMenIds();
            applyManagerPlans();

            if (state.production_summary && state.manual_production_facts) {
                state.production_summary.forEach(p => {
                    p.auto_fact_m2 = p.fact_m2;
                    if (state.manual_production_facts[String(p.id)] !== undefined) {
                        p.fact_m2 = state.manual_production_facts[String(p.id)];
                        p.is_manual = true;
                        p.bonus = Math.round(p.fact_m2 * p.tarif);
                        p.total_salary = p.oklad + p.bonus;
                    }
                });
                state.items.forEach(it => {
                    if (state.manual_production_facts[String(it.id)] !== undefined) {
                        it.fact = state.manual_production_facts[String(it.id)];
                        const p = state.production_summary.find(x => String(x.id) === String(it.id));
                        it.kpi_bonus = p ? p.bonus : 0;
                        it.total_salary = it.oklad + it.kpi_bonus;
                        it.rest_to_pay = it.total_salary - it.advance;
                    }
                });
            }
            state.calced = true;
            state.closed = data.period.status === 'closed';

            updateHeaderStatus();
            draw();
        } else {
            showToast(data.error || "Ma'lumotlarni yuklab bo'lmadi", 'err');
        }
    } catch (e) {
        showToast("Server bilan bog'lanishda xatolik: " + e.message, 'err');
    }
}

function updateHeaderStatus() {
    const p = state.period;
    const cfg = state.config;
    const activeCount = state.items.filter(i => i.is_active).length;
    $('#cnt').textContent = activeCount;

    const badge = $('#statBadge');
    badge.textContent = p.status_display || 'Real-Time Jonli';
    badge.className = 'chip chip-status chip-ok';

    const msPulse = $('#msPulse');
    const msText = $('#msStatusText');

    if (cfg && cfg.has_token) {
        msPulse.className = 'status-pulse online';
        msText.textContent = `MoySklad: Jonli Ulangan (${cfg.company_name})`;
    } else {
        msPulse.className = 'status-pulse';
        msText.textContent = 'MoySklad: Tokensiz (Demo rejim)';
    }
}

function switchTab(t) {
    state.currentTab = t;
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('on', btn.dataset.t === t);
    });
    draw();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function draw() {
    const content = $('#tabContent');
    if (state.currentTab === 'plan') {
        content.innerHTML = renderPlan();
    } else if (state.currentTab === 'calc') {
        content.innerHTML = renderCalc();
    } else {
        content.innerHTML = renderFin();
    }
}

// 1-TAB: Plan va qoidalar
function renderPlan() {
    const r = state.rules;
    const C = state.categories;
    const items = state.items;
    const tp = state.total_plans;

    ensureSelectedOpIds();
    const allOps = items.filter(e => e.group === 'op' && e.is_active);
    const targetOpCount = getTargetOpCount();
    const selectedCount = (state.selected_op_ids && state.selected_op_ids.length) || 1;
    const ind_op = Math.round(tp.op / selectedCount);

    ensureSelectedMenIds();
    const allMen = items.filter(e => e.group === 'men' && e.is_active);
    const targetMenCount = getTargetMenCount();
    const selectedMenCount = (state.selected_men_ids && state.selected_men_ids.length) || 1;
    const ind_men = Math.round(tp.men / selectedMenCount);

    // Ishlab chiqarish toifalari (PVX, TERMO, Chempion, ALDOX, Montaj)
    const catRows = C.map((c, i) => {
        const nameU = c.name.toUpperCase();
        const isPvh = nameU.includes('PVX');
        const isMont = nameU.includes('MONT') || nameU.includes('МОНТ');
        let deptLabel = isPvh ? 'Ишлаб чикариш булими (ПВХ)' : isMont ? 'Монтаж бўлими (Алоҳида)' : 'Ишлаб чикариш булими (ТЕРМО)';
        let polyLabel = isPvh ? 'ПВХ' : isMont ? 'Монтаж' : (nameU.includes('CHEMP') ? 'Чемпион' : (nameU.includes('ALYUM') || nameU.includes('ALDOX') ? 'АЛДОХ' : 'ТЕРМО'));

        return `
            <tr>
                <td><b>${c.name}</b><br><span class="note" style="color:${isMont ? '#0284c7' : 'var(--pr)'}; font-weight:600;">${deptLabel}</span></td>
                <td><span class="chip" style="font-weight:600;">${polyLabel} polyasi</span></td>
                <td>${f(c.prev_month_volume)}</td>
                <td><input type="number" class="styled-input" style="width:75px" value="${c.growth_percent}" onchange="updateCatGrowth(${i}, this.value)"></td>
                <td><input type="text" inputmode="numeric" class="styled-input" style="width:95px; text-align:right;" value="${f(c.plan)}" oninput="handleFormattedNumberInput(this, v => { state.categories[${i}].plan=v; draw(); })"></td>
                <td><b style="color:var(--pr);">${f(c.fact)}</b></td>
                <td><input type="text" inputmode="numeric" class="styled-input" style="width:105px; text-align:right;" value="${f(c.tarif)}" oninput="handleFormattedNumberInput(this, v => { state.categories[${i}].tarif=v; draw(); })"></td>
                <td><span class="chip">${c.workers_count || 1} nafar</span></td>
            </tr>
        `;
    }).join('');

    const empRows = items.map((e, idx) => {
        let deptChip = '';
        if (e.dept === 'Монтаж') {
            deptChip = `<span class="chip" style="background:rgba(14,165,233,0.12); color:#0284c7; font-weight:600;">Монтаж бўлими (Алоҳида)</span>`;
        } else if (e.dept === 'PVX bo\'limi') {
            deptChip = `<span class="chip" style="background:rgba(37,99,235,0.08); color:#2563eb; font-weight:600;">PVX бўлими</span>`;
        } else if (e.dept === 'TERMO bo\'limi') {
            deptChip = `<span class="chip" style="background:rgba(234,88,12,0.08); color:#ea580c; font-weight:600;">TERMO бўлими</span>`;
        } else if (e.group === 'men') {
            const isSel = isMenSelected(e);
            deptChip = isSel 
                ? `so'm · 50–80% da <input type="number" step="0.1" class="styled-input" style="width:55px" value="${e.manager_rate || 1}" oninput="state.items[${idx}].manager_rate=+this.value;">%` 
                : `<span class="note" style="color:var(--tx-muted); font-weight:500;">— Rejasiz (Faqat oklad)</span>`;
            e.plan = isSel ? ind_men : 0;
        } else if (e.group === 'op') {
            const isSel = isOpSelected(e);
            deptChip = isSel 
                ? `<span class="chip chip-ok" style="font-weight:600;">✓ Reja oladi (${f(ind_op)} so'm)</span>` 
                : `<span class="note" style="color:var(--tx-muted); font-weight:500;">— Rejasiz (Faqat oklad)</span>`;
            e.plan = isSel ? ind_op : 0;
        } else {
            deptChip = `<span class="note">Faqat oklad</span>`;
        }

        return `
            <tr>
                <td><b>${e.name}</b></td>
                <td class="l">${e.position}</td>
                <td>
                    ${e.group === 'bosh' || e.group === 'ish' ? '—' : `
                        <input type="text" inputmode="numeric" id="emp-plan-${e.id}" class="styled-input" style="width:145px; font-weight:600; text-align:right;" value="${f(e.plan)}" oninput="handleFormattedNumberInput(this, v => { state.items[${idx}].plan = v; })">
                    `}
                </td>
                <td class="l">${deptChip}</td>
                <td>
                    <input type="checkbox" ${e.is_active ? 'checked' : ''} onchange="state.items[${idx}].is_active=this.checked; updateHeaderStatus();">
                </td>
            </tr>
        `;
    }).join('');

    return `
        <!-- Umumiy Plan Kiritish Karti (Real-Time Taqsimlash) -->
        <div class="card" style="border:1.5px solid var(--bd); background:linear-gradient(135deg, rgba(37,99,235,0.02), rgba(16,185,129,0.02));">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; flex-wrap:wrap; gap:8px;">
                <div>
                    <h3 style="font-size:16px; font-weight:700;">Umumiy Rejalar (Guruhlar bo'yicha Real-Time Taqsimlash)</h3>
                    <p class="note" style="margin-top:2px;">Umumiy plan summasi kiritilganda, tizim faol xodimlar sonini aniqlab, har bitta xodim uchun planni avtomatik taqsimlaydi.</p>
                </div>
                <span class="chip chip-status">Real-Time Avtomatik Taqsimot</span>
            </div>

            <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));">
                <!-- Sotuv operatorlari umumiy plani -->
                <div class="rule" style="background:var(--card); border:1px solid var(--bd);">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                        <b class="rule-title" style="font-size:15px; color:var(--tx-main); margin:0;">Sotuv operatorlari umumiy rejasi</b>
                        <span class="chip chip-ok" id="opSelectedBadge" style="font-weight:600; font-size:11px;">${selectedCount} / ${allOps.length || 1} tanlangan</span>
                    </div>

                    <label style="display:flex; justify-content:space-between; align-items:center; margin-top:10px; font-weight:600;">
                        <span>Jami plan (so'm)</span> 
                        <input type="text" inputmode="numeric" id="inputTotalPlanOp" class="styled-input" style="width:175px; font-weight:700; font-size:14px; text-align:right;" value="${f(tp.op)}" oninput="handleFormattedNumberInput(this, v => onPlanInput('op', v))" onchange="onPlanChange('op', parseFormattedNumber(this.value))">
                    </label>

                    <label style="display:flex; justify-content:space-between; align-items:center; margin-top:8px; font-weight:600;">
                        <span>Reja beriladigan operatorlar soni:</span>
                        <input type="number" id="inputTargetOpCount" min="1" max="${allOps.length || 10}" class="styled-input" style="width:80px; font-weight:700; font-size:14px; text-align:center;" value="${targetOpCount}" oninput="onOpTargetCountInput(this.value)" onchange="onOpTargetCountChange(this.value)">
                    </label>

                    <!-- Operatorlarni tanlash ro'yxati -->
                    <div style="margin-top:12px; padding:10px; background:var(--bg); border:1px solid var(--bd); border-radius:8px;">
                        <div style="font-size:11px; font-weight:700; color:var(--tx-muted); text-transform:uppercase; margin-bottom:8px; letter-spacing:0.5px;">
                            Reja oladigan operatorlarni tanlang (Ixtiyoriy):
                        </div>
                        <div id="opSelectionList">
                            ${allOps.map(e => {
                                const isSel = isOpSelected(e);
                                return `
                                    <div class="op-select-item" style="display:flex; justify-content:space-between; align-items:center; padding:7px 10px; margin-bottom:5px; background:${isSel ? 'rgba(37,99,235,0.03)' : 'var(--card)'}; border:1px solid ${isSel ? 'var(--pr)' : 'var(--bd)'}; border-radius:6px; transition:all 0.15s ease;">
                                        <label style="display:flex; align-items:center; gap:8px; margin:0; cursor:pointer; font-size:13px; font-weight:600; color:var(--tx-main);">
                                            <input type="checkbox" class="op-plan-checkbox" data-emp-id="${e.id}" data-emp-uid="${e.emp_id}" ${isSel ? 'checked' : ''} onchange="onOpCheckboxChange('${e.id}', '${e.emp_id}', this.checked)">
                                            <span>${e.name}</span>
                                        </label>
                                        <span id="op-status-${e.id}" style="font-size:12px; font-weight:700; color:${isSel ? 'var(--pr)' : 'var(--tx-muted)'};">
                                            ${isSel ? `✓ Reja oladi (${f(ind_op)} so'm)` : `— Rejasiz (0 so'm)`}
                                        </span>
                                    </div>
                                `;
                            }).join('')}
                        </div>
                    </div>

                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:12px; font-size:13px; padding-top:8px; border-top:1px dashed var(--bd);">
                        <span class="chip" id="opCountBadge" style="font-weight:600;">${selectedCount} nafar rejali operator</span>
                        <b style="color:var(--pr); font-size:14px;" id="indPlanOpDisplay">Har biriga: ${f(ind_op)} so'm</b>
                    </div>
                    <div class="note" style="margin-top:6px;">Faqat tanlangan operatorlarga reja beriladi va shartnoma summasidan koeffitsient hisoblanadi. Tanlanmaganlar faqat oklad oladi.</div>
                </div>

                <!-- Sotuv menejerlari umumiy plani -->
                <div class="rule" style="background:var(--card); border:1px solid var(--bd);">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                        <b class="rule-title" style="font-size:15px; color:var(--tx-main); margin:0;">Sotuv menejerlari umumiy rejasi</b>
                        <span class="chip chip-ok" id="menSelectedBadge" style="font-weight:600; font-size:11px;">${selectedMenCount} / ${allMen.length || 1} tanlangan</span>
                    </div>

                    <label style="display:flex; justify-content:space-between; align-items:center; margin-top:10px; font-weight:600;">
                        <span>Jami plan (so'm)</span> 
                        <input type="text" inputmode="numeric" id="inputTotalPlanMen" class="styled-input" style="width:175px; font-weight:700; font-size:14px; text-align:right;" value="${f(tp.men)}" oninput="handleFormattedNumberInput(this, v => onPlanInput('men', v))" onchange="onPlanChange('men', parseFormattedNumber(this.value))">
                    </label>

                    <label style="display:flex; justify-content:space-between; align-items:center; margin-top:8px; font-weight:600;">
                        <span>Reja beriladigan sotuvchilar soni:</span>
                        <input type="number" id="inputTargetMenCount" min="1" max="${allMen.length || 10}" class="styled-input" style="width:80px; font-weight:700; font-size:14px; text-align:center;" value="${targetMenCount}" oninput="onMenTargetCountInput(this.value)" onchange="onMenTargetCountChange(this.value)">
                    </label>

                    <!-- Sotuvchilarni tanlash ro'yxati -->
                    <div style="margin-top:12px; padding:10px; background:var(--bg); border:1px solid var(--bd); border-radius:8px;">
                        <div style="font-size:11px; font-weight:700; color:var(--tx-muted); text-transform:uppercase; margin-bottom:8px; letter-spacing:0.5px;">
                            Reja oladigan sotuvchilarni tanlang (Ixtiyoriy):
                        </div>
                        <div id="menSelectionList">
                            ${allMen.map(e => {
                                const isSel = isMenSelected(e);
                                return `
                                    <div class="men-select-item" style="display:flex; justify-content:space-between; align-items:center; padding:7px 10px; margin-bottom:5px; background:${isSel ? 'rgba(37,99,235,0.03)' : 'var(--card)'}; border:1px solid ${isSel ? 'var(--pr)' : 'var(--bd)'}; border-radius:6px; transition:all 0.15s ease;">
                                        <label style="display:flex; align-items:center; gap:8px; margin:0; cursor:pointer; font-size:13px; font-weight:600; color:var(--tx-main);">
                                            <input type="checkbox" class="men-plan-checkbox" data-emp-id="${e.id}" data-emp-uid="${e.emp_id}" ${isSel ? 'checked' : ''} onchange="onMenCheckboxChange('${e.id}', '${e.emp_id}', this.checked)">
                                            <span>${e.name}</span>
                                        </label>
                                        <span id="men-status-${e.id}" style="font-size:12px; font-weight:700; color:${isSel ? 'var(--pr)' : 'var(--tx-muted)'};">
                                            ${isSel ? `✓ Reja oladi (${f(ind_men)} so'm)` : `— Rejasiz (0 so'm)`}
                                        </span>
                                    </div>
                                `;
                            }).join('')}
                        </div>
                    </div>

                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:12px; font-size:13px; padding-top:8px; border-top:1px dashed var(--bd);">
                        <span class="chip" id="menCountBadge" style="font-weight:600;">${selectedMenCount} nafar rejali sotuvchi</span>
                        <b style="color:var(--pr); font-size:14px;" id="indPlanMenDisplay">Har biriga: ${f(ind_men)} so'm</b>
                    </div>
                    <div class="note" style="margin-top:6px;">Сотрудники lavozimi «СОТУВЧИ» bo'lgan xodimlar ichidan tanlanganlar o'rtasida teng taqsimlanadi.</div>
                </div>
            </div>
        </div>

        <!-- KPI Qoidalari -->
        <div class="card">
            <h3 style="margin-bottom:12px; font-size:15px; font-weight:700;">KPI Qoidalari (Guruhlar bo'yicha)</h3>
            <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));">
                <div class="rule">
                    <b class="rule-title">Sotuv operatori — Koeffitsient tizimi</b>
                    <label>Plan ≥ % <input type="number" class="styled-input" value="${r.op.t1}" oninput="state.rules.op.t1=+this.value"></label>
                    <label>→ koeffitsient <input type="number" step="0.1" class="styled-input" value="${r.op.k1}" oninput="state.rules.op.k1=+this.value"></label>
                    <label>Plan ≥ % <input type="number" class="styled-input" value="${r.op.t2}" oninput="state.rules.op.t2=+this.value"></label>
                    <label>→ koeffitsient <input type="number" step="0.1" class="styled-input" value="${r.op.k2}" oninput="state.rules.op.k2=+this.value"></label>
                    <label>Plan ≥ % <input type="number" class="styled-input" value="${r.op.t3}" oninput="state.rules.op.t3=+this.value"></label>
                    <label>→ koeffitsient <input type="number" step="0.1" class="styled-input" value="${r.op.k3}" oninput="state.rules.op.k3=+this.value"></label>
                    <label>Plan ≥ % <input type="number" class="styled-input" value="${r.op.t4}" oninput="state.rules.op.t4=+this.value"></label>
                    <label>→ koeffitsient <input type="number" step="0.1" class="styled-input" value="${r.op.k4}" oninput="state.rules.op.k4=+this.value"></label>
                    <div class="note">Operatorning o'ziga tegishli davr ichidagi buyurtmalari (shartnoma summasi)dan koeffitsient % olinadi.</div>
                </div>

                <div class="rule">
                    <b class="rule-title">Sotuv menejeri — Hajm bo'yicha %</b>
                    <label>Pastki chegara, plan ≥ % <input type="number" class="styled-input" value="${r.men.t1}" oninput="state.rules.men.t1=+this.value"></label>
                    <label>Plan ≥ % <input type="number" class="styled-input" value="${r.men.t2}" oninput="state.rules.men.t2=+this.value"></label>
                    <label>→ sotuvdan % <input type="number" step="0.1" class="styled-input" value="${r.men.r2}" oninput="state.rules.men.r2=+this.value"></label>
                    <label>Plan ≥ % <input type="number" class="styled-input" value="${r.men.t3}" oninput="state.rules.men.t3=+this.value"></label>
                    <label>→ sotuvdan % <input type="number" step="0.1" class="styled-input" value="${r.men.r3}" oninput="state.rules.men.r3=+this.value"></label>
                    <div class="note">Tepada taqsimlangan reja bo'yicha % aniqlanadi va buyurtmalar hajmidan tegishli stavka olinadi.</div>
                </div>

                <!-- Foydalanuvchi talabi: Ishlab chiqarish va Montaj har bir ishlab chiqarish va alohida montaj qilingan kv uchun summa kiritiladi -->
                <div class="rule" style="background:var(--card); border:1px solid var(--bd);">
                    <b class="rule-title" style="font-size:15px; color:var(--tx-main);">Ishlab chiqarish va Montaj tariflari</b>
                    <label style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">
                        <span>ПВХ tarifi (so'm / m²)</span>
                        <input type="text" inputmode="numeric" id="inputTarifPvh" class="styled-input" style="width:125px; font-weight:700; text-align:right;" value="${f(tp.tarif_pvh || 60000)}" oninput="handleFormattedNumberInput(this, v => onTarifInput('pvh', v))" onchange="onTarifChange('pvh', parseFormattedNumber(this.value))">
                    </label>
                    <label style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">
                        <span>ТЕРМО tarifi (so'm / m²)</span>
                        <input type="text" inputmode="numeric" id="inputTarifTermo" class="styled-input" style="width:125px; font-weight:700; text-align:right;" value="${f(tp.tarif_termo || 80000)}" oninput="handleFormattedNumberInput(this, v => onTarifInput('termo', v))" onchange="onTarifChange('termo', parseFormattedNumber(this.value))">
                    </label>
                    <label style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">
                        <span>Монтаж tarifi (so'm / m²)</span>
                        <input type="text" inputmode="numeric" id="inputTarifMontaj" class="styled-input" style="width:125px; font-weight:700; text-align:right;" value="${f(tp.tarif_montaj || 50000)}" oninput="handleFormattedNumberInput(this, v => onTarifInput('montaj', v))" onchange="onTarifChange('montaj', parseFormattedNumber(this.value))">
                    </label>
                    <div class="note" style="margin-top:8px;">Har bir ishlab chiqarish va montaj qilingan kv.m uchun shu summa bo'yicha shaxsiy bonus hisoblanadi. 0 kv bo'lsa faqat oklad to'lanadi.</div>
                </div>
            </div>
        </div>

        <!-- Foydalanuvchi talabi: Ishlab chiqarish va Montaj xodimlar kesimida jonli hajm jadvali -->
        <div class="card">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap; gap:8px;">
                <div>
                    <h3 style="font-size:15px; font-weight:700;">Ishlab chiqarish va Montaj — Xodimlar kesimida jonli hajm (m²)</h3>
                    <p class="note" style="margin-top:2px;">
                        Faqat shu davr ichida yakunlangan (отгрузка qilingan) buyurtmalardan har bir xodimga tegishli polyalar bo'yicha real-time olinadi. Ishlab chiqarmagan xodim faqat okladini oladi.
                    </p>
                </div>
                <span class="chip chip-status chip-ok">MoySklad Jonli Faktlar</span>
            </div>
            <div class="sc">
                <table>
                    <thead>
                        <tr>
                            <th>Xodim</th>
                            <th>Bo'lim</th>
                            <th>Bog'langan Polya</th>
                            <th>Ishlab chiqarilgan hajm</th>
                            <th>Tarif (so'm/m²)</th>
                            <th>KPI Bonus (so'm)</th>
                            <th>Oklad (so'm)</th>
                            <th>Kutilayotgan oylik</th>
                            <th>Holat</th>
                        </tr>
                    </thead>
                    <tbody id="productionTableBody">${renderProductionRows()}</tbody>
                </table>
            </div>
        </div>

        <!-- Xodimlar oylik plani -->
        <div class="card">
            <h3 style="margin-bottom:12px; font-size:15px; font-weight:700;">Oylik plan (Har bir xodimga taqsimlangan)</h3>
            <div class="sc">
                <table>
                    <thead>
                        <tr>
                            <th>Xodim</th>
                            <th class="l">Lavozim</th>
                            <th>Taqsimlangan Plan</th>
                            <th class="l">Bo'lim / Birlik</th>
                            <th>Aktiv</th>
                        </tr>
                    </thead>
                    <tbody>${empRows}</tbody>
                </table>
            </div>
            <div style="margin-top:16px; display:flex; gap:10px;">
                <button class="b b-primary" onclick="switchTab('calc')">
                    Nachisleniya va KPI ko'rish →
                </button>
            </div>
        </div>
    `;
}

// Ishlab chiqarish va montaj xodimlari jadvali qatorlari
function renderProductionRows() {
    const list = state.production_summary || [];
    if (!list.length) {
        return `<tr><td colspan="9" style="text-align:center; padding:16px;" class="note">Ishlab chiqarish va montaj xodimlari topilmadi</td></tr>`;
    }

    return list.map(p => {
        const isManual = p.is_manual || (state.manual_production_facts && state.manual_production_facts[String(p.id)] !== undefined);
        const hasWork = p.fact_m2 > 0;
        const autoVal = p.auto_fact_m2 !== undefined ? p.auto_fact_m2 : p.fact_m2;

        let statusBadge = '';
        if (isManual) {
            statusBadge = `<span class="chip" style="background:rgba(234,88,12,0.12); color:#ea580c; font-weight:700; font-size:11px;">Qo'lda kiritildi</span>`;
        } else if (hasWork) {
            statusBadge = `<span class="chip chip-status chip-ok" style="font-weight:600;">MoySklad Jonli</span>`;
        } else {
            statusBadge = `<span class="note" style="color:var(--tx-muted); font-weight:500;">Faqat oklad (0 m²)</span>`;
        }

        let polyChip = `<span class="chip" style="font-weight:600;">${p.linked_poly}</span>`;
        if (p.dept === 'Монтаж') {
            polyChip = `<span class="chip" style="background:rgba(14,165,233,0.12); color:#0284c7; font-weight:600;">${p.linked_poly}</span>`;
        } else if (p.dept === "PVX bo'limi") {
            polyChip = `<span class="chip" style="background:rgba(37,99,235,0.08); color:#2563eb; font-weight:600;">${p.linked_poly}</span>`;
        } else if (p.dept === "TERMO bo'limi") {
            polyChip = `<span class="chip" style="background:rgba(234,88,12,0.08); color:#ea580c; font-weight:600;">${p.linked_poly}</span>`;
        }

        return `
            <tr>
                <td><b>${p.name}</b><br><span class="note">${p.position}</span></td>
                <td><span class="chip" style="font-weight:600;">${p.dept}</span></td>
                <td>${polyChip}</td>
                <td>
                    <div style="display:inline-flex; align-items:center; gap:4px;">
                        <input type="text" 
                               inputmode="decimal"
                               id="prod-fact-${p.id}" 
                               class="styled-input" 
                               style="width:95px; font-weight:700; text-align:right; font-size:13px; color:${hasWork ? 'var(--pr)' : 'var(--tx-muted)'};" 
                               value="${p.fact_m2 ? f(p.fact_m2, 2) : '0'}" 
                               oninput="handleFormattedNumberInput(this, v => onProductionVolumeInput('${p.id}', v), true)"
                               title="MoySklad avtomatik qiymati: ${autoVal} m². O'zgartirish yoki qo'lda kiritish mumkin.">
                        <span class="note" style="font-weight:600;">m²</span>
                        <span id="prod-reset-wrap-${p.id}">
                            ${isManual ? `<button class="b b-secondary" style="padding:2px 7px; font-size:11px; margin-left:4px; height:26px;" onclick="resetProductionVolume('${p.id}')" title="MoySklad avtomatik faktiga qaytarish (↺ Avto: ${autoVal} m²)">↺ Avto</button>` : ''}
                        </span>
                    </div>
                </td>
                <td>${f(p.tarif)} <span class="note">so'm</span></td>
                <td><b id="prod-bonus-${p.id}" style="color:${hasWork ? 'var(--ok)' : 'var(--tx-muted)'}; font-size:14px;">${f(p.bonus)}</b></td>
                <td><b>${f(p.oklad)}</b></td>
                <td><b id="prod-tot-${p.id}" style="color:var(--tx-main); font-size:14px;">${f(p.total_salary)}</b></td>
                <td id="prod-status-${p.id}">${statusBadge}</td>
            </tr>
        `;
    }).join('');
}

// Boshqariladigan va kursor sakramaydigan real-time kiritish funksiyalari
function onPlanInput(grp, val) {
    const num = typeof val === 'number' ? val : (parseFloat(val) || 0);
    state.total_plans[grp] = num;

    if (grp === 'op') {
        const selectedCount = (state.selected_op_ids && state.selected_op_ids.length) || 0;
        const indPlan = selectedCount > 0 ? Math.round(num / selectedCount) : 0;
        state.items.filter(e => e.group === 'op').forEach(e => {
            const isSel = isOpSelected(e);
            e.plan = isSel ? indPlan : 0;
            const inp = document.getElementById(`emp-plan-${e.id}`);
            if (inp) inp.value = f(e.plan);
        });
        updateOpUI();
        return;
    }

    if (grp === 'men') {
        const selectedCount = (state.selected_men_ids && state.selected_men_ids.length) || 0;
        const indPlan = selectedCount > 0 ? Math.round(num / selectedCount) : 0;
        state.items.filter(e => e.group === 'men').forEach(e => {
            const isSel = isMenSelected(e);
            e.plan = isSel ? indPlan : 0;
            const inp = document.getElementById(`emp-plan-${e.id}`);
            if (inp) inp.value = f(e.plan);
        });
        updateMenUI();
        return;
    }

    const activeItems = state.items.filter(e => e.is_active && e.group === grp);
    const count = activeItems.length || 1;
    const indPlan = Math.round(num / count);

    activeItems.forEach(e => {
        e.plan = indPlan;
        const inp = document.getElementById(`emp-plan-${e.id}`);
        if (inp) inp.value = f(indPlan);
    });
}

let planDebounceTimer = null;
function onPlanChange(grp, val) {
    clearTimeout(planDebounceTimer);
    planDebounceTimer = setTimeout(() => {
        const tp = state.total_plans;
        const mon = $('#mon').value;
        const d1 = $('#d1') ? $('#d1').value : '';
        const d2 = $('#d2') ? $('#d2').value : '';
        const pObj = {
            month: mon,
            date_from: d1,
            date_to: d2,
            total_plan_op: tp.op,
            total_plan_men: tp.men,
            tarif_pvh: tp.tarif_pvh,
            tarif_termo: tp.tarif_termo,
            tarif_montaj: tp.tarif_montaj
        };
        if (state.selected_op_ids && state.selected_op_ids.length) {
            pObj.selected_op_ids = state.selected_op_ids.join(',');
        }
        if (state.selected_men_ids && state.selected_men_ids.length) {
            pObj.selected_men_ids = state.selected_men_ids.join(',');
        }
        const params = new URLSearchParams(pObj);
        fetch(`/api/period-data/?${params.toString()}`)
            .then(r => r.json())
            .then(data => {
                if (data.success && data.items) {
                    data.items.forEach(fresh => {
                        const local = state.items.find(i => i.id === fresh.id);
                        if (local) {
                            local.fact = fresh.fact;
                            local.advance = fresh.advance;
                            local.percent = fresh.percent;
                            local.kpi_bonus = fresh.kpi_bonus;
                            local.total_salary = fresh.total_salary;
                            local.rest_to_pay = fresh.rest_to_pay;
                        }
                    });
                }
            }).catch(e => console.error(e));
    }, 300);
}

// Ishlab chiqarish va Montaj tariflari jonli kiritish
function onTarifInput(cat, val) {
    const num = typeof val === 'number' ? val : (parseFloat(val) || 0);
    if (cat === 'pvh') state.total_plans.tarif_pvh = num;
    else if (cat === 'termo') state.total_plans.tarif_termo = num;
    else if (cat === 'montaj') state.total_plans.tarif_montaj = num;

    if (state.production_summary) {
        state.production_summary.forEach(p => {
            if (p.dept === "PVX bo'limi") {
                p.tarif = state.total_plans.tarif_pvh;
                p.bonus = Math.round(p.fact_m2 * p.tarif);
            } else if (p.dept === "TERMO bo'limi") {
                p.tarif = state.total_plans.tarif_termo;
                p.bonus = Math.round(p.fact_m2 * p.tarif);
            } else if (p.dept === "Монтаж") {
                p.tarif = state.total_plans.tarif_montaj;
                p.bonus = Math.round(p.fact_m2 * p.tarif);
            }
            p.total_salary = p.oklad + p.bonus;
        });
    }

    state.items.forEach(item => {
        if (item.group === 'ish') {
            if (item.dept === "PVX bo'limi") {
                item.kpi_bonus = Math.round(item.fact * state.total_plans.tarif_pvh);
            } else if (item.dept === "TERMO bo'limi") {
                item.kpi_bonus = Math.round(item.fact * state.total_plans.tarif_termo);
            } else if (item.dept === "Монтаж") {
                item.kpi_bonus = Math.round(item.fact * state.total_plans.tarif_montaj);
            }
            item.total_salary = item.oklad + item.kpi_bonus;
            item.rest_to_pay = item.total_salary - item.advance;
        }
    });

    const prodTableBody = document.getElementById('productionTableBody');
    if (prodTableBody) {
        prodTableBody.innerHTML = renderProductionRows();
    }
}

let tarifDebounceTimer = null;
function onTarifChange(cat, val) {
    clearTimeout(tarifDebounceTimer);
    tarifDebounceTimer = setTimeout(() => {
        const tp = state.total_plans;
        const mon = $('#mon').value;
        const d1 = $('#d1') ? $('#d1').value : '';
        const d2 = $('#d2') ? $('#d2').value : '';
        const pObj = {
            month: mon,
            date_from: d1,
            date_to: d2,
            total_plan_op: tp.op,
            total_plan_men: tp.men,
            tarif_pvh: tp.tarif_pvh,
            tarif_termo: tp.tarif_termo,
            tarif_montaj: tp.tarif_montaj
        };
        if (state.selected_op_ids && state.selected_op_ids.length) {
            pObj.selected_op_ids = state.selected_op_ids.join(',');
        }
        if (state.selected_men_ids && state.selected_men_ids.length) {
            pObj.selected_men_ids = state.selected_men_ids.join(',');
        }
        const params = new URLSearchParams(pObj);
        fetch(`/api/period-data/?${params.toString()}`)
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    if (data.production_summary) state.production_summary = data.production_summary;
                    if (data.items) {
                        data.items.forEach(fresh => {
                            const local = state.items.find(i => i.id === fresh.id);
                            if (local) {
                                local.fact = fresh.fact;
                                local.advance = fresh.advance;
                                local.percent = fresh.percent;
                                local.kpi_bonus = fresh.kpi_bonus;
                                local.total_salary = fresh.total_salary;
                                local.rest_to_pay = fresh.rest_to_pay;
                            }
                        });
                    }
                    const prodTableBody = document.getElementById('productionTableBody');
                    if (prodTableBody) prodTableBody.innerHTML = renderProductionRows();
                }
            }).catch(e => console.error(e));
    }, 300);
}

function updateCatGrowth(idx, val) {
    const c = state.categories[idx];
    if (c) {
        c.growth_percent = +val;
        c.plan = Math.round(c.prev_month_volume * (1 + c.growth_percent / 100));
        draw();
    }
}

function recalcCategoryPlans() {
    state.categories.forEach(c => {
        c.plan = Math.round(c.prev_month_volume * (1 + c.growth_percent / 100));
    });
    draw();
    showToast("Kategoriyalar plani qayta hisoblandi!", 'ok');
}

// 2-TAB: Nachisleniya
function renderCalc() {
    const activeItems = state.items.filter(i => i.is_active);

    let s = { ok: 0, b: 0, av: 0, t: 0, r: 0 };

    const rows = activeItems.map((e) => {
        const auto = getAutoKpi(e);
        const k = computeKpi(e);
        const tot = e.oklad + k.bonus;
        const rest = tot - e.advance;

        s.ok += e.oklad;
        s.b += k.bonus;
        s.av += e.advance;
        s.t += tot;
        s.r += rest;

        const isUnselected = (e.group === 'op' && !isOpSelected(e)) || (e.group === 'men' && !isMenSelected(e));
        const colorClass = (e.group === 'ish' ? (e.fact > 0 ? 'g' : '') : isUnselected ? '' : (k.percent >= 100 ? 'g' : k.percent >= 80 ? 'w' : 'r'));

        const factDisplay = e.group === 'bosh' ? '—' : `<b>${f(e.fact)}</b> <span class="note">${e.group === 'ish' ? 'm²' : 'so\'m'}</span>`;
        const percentDisplay = (e.group === 'bosh' || isUnselected) ? '—' : (e.group === 'ish' ? (e.fact > 0 ? `${f(e.fact)} m²` : '0 m² (faqat oklad)') : `${k.percent.toFixed(2).replace('.', ',')}%`);

        return `
            <tr>
                <td><b>${e.name}</b><br><span class="note">${e.position}</span></td>
                <td><b>${f(e.oklad)}</b></td>
                <td>${e.group === 'bosh' || e.group === 'ish' || isUnselected ? '—' : f(e.plan)}</td>
                <td>${factDisplay}</td>
                <td class="${colorClass}">${percentDisplay}</td>
                <td>
                    <input type="text" 
                           inputmode="numeric"
                           id="emp-kpi-${e.id}" 
                           class="styled-input" 
                           style="width:135px; font-weight:700; color:${k.bonus > 0 ? 'var(--ok)' : 'var(--tx-muted)'}; text-align:right;" 
                           value="${f(k.bonus)}" 
                           oninput="handleFormattedNumberInput(this, v => onKpiBonusChange(${e.id}, v))"
                           title="Avtomatik hisoblangan: ${f(auto.bonus)} so'm${isUnselected ? ' (Reja belgilanmagan)' : ''}. Ixtiyoriy o'zgartirish yoki qo'shimcha KPI kiritish mumkin.">
                </td>
                <td><span style="color:var(--wa); font-weight:600;">${f(e.advance)}</span></td>
                <td id="emp-tot-${e.id}"><b>${f(tot)}</b></td>
                <td id="emp-rest-${e.id}"><b class="${rest < 0 ? 'r' : 'g'}">${f(rest)}</b></td>
            </tr>
        `;
    }).join('');

    return `
        <!-- Qadamlar -->
        <div class="steps">
            <span class="st on">1. Xodimlar (${activeItems.length})</span>
            <span class="st on">2. MoySklad Real-Time Hisoblandi</span>
            <span class="st ${state.closed ? 'on' : ''}">3. Yakunlash</span>
        </div>

        <!-- KPI Natijalari -->
        <div class="kpis">
            <div class="k accent-pr"><small>Oklad jami</small><b>${f(s.ok)}</b></div>
            <div class="k accent-ok"><small>KPI bonus</small><b id="calc-card-bonus">${f(s.b)}</b></div>
            <div class="k accent-wa"><small>Avanslar (${$('#d1').value} – ${$('#d2').value})</small><b>${f(s.av)}</b></div>
            <div class="k accent-pr"><small>Jami oylik</small><b id="calc-card-total">${f(s.t)}</b></div>
            <div class="k ${s.r < 0 ? 'accent-er' : 'accent-ok'}" id="calc-card-rest-wrap"><small>To'lashga qoldiq</small><b id="calc-card-rest">${f(s.r)}</b></div>
        </div>

        <!-- Jadval -->
        <div class="card">
            <div class="sc">
                <table>
                    <thead>
                        <tr>
                            <th>Xodim</th>
                            <th>Oklad</th>
                            <th>Plan</th>
                            <th>Jonli Fakt (MoySklad)</th>
                            <th>Bajarilish</th>
                            <th>KPI bonus</th>
                            <th>Avans</th>
                            <th>Jami oylik</th>
                            <th>Qoldiq</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                    <tfoot>
                        <tr>
                            <td>Jami</td>
                            <td>${f(s.ok)}</td>
                            <td></td>
                            <td></td>
                            <td></td>
                            <td id="calc-foot-bonus">${f(s.b)}</td>
                            <td>${f(s.av)}</td>
                            <td id="calc-foot-total">${f(s.t)}</td>
                            <td id="calc-foot-rest">${f(s.r)}</td>
                        </tr>
                    </tfoot>
                </table>
            </div>

            <div class="note" style="margin-top:12px;">
                💡 <b>KPI bonus maydoni</b>: Tizim avtomatik hisoblagan bonusni chiqaradi. Uni xohlagancha o'zgartirishingiz yoki qo'shimcha KPI kiritishingiz mumkin. Barcha o'zgarishlar jami oylik va qoldiqqa real-time ta'sir qiladi.
            </div>

            <div style="margin-top:16px; display:flex; gap:10px; flex-wrap:wrap;">
                <button class="b b-secondary" onclick="loadPeriodData()">
                    MoySklad'dan qayta yangilash
                </button>
                <button class="b b-primary" onclick="switchTab('fin')">
                    Yakunlashga o'tish →
                </button>
            </div>
        </div>
    `;
}

// Avtomatik KPI hisoblash
function getAutoKpi(e) {
    const r = state.rules;
    let pct = 0;
    let bonus = 0;

    if (e.group === 'sot') {
        pct = e.plan ? (e.fact / e.plan * 100) : 0;
        bonus = pct >= r.sot.min ? (e.fact * r.sot.rate / 100) : 0;
    } else if (e.group === 'op') {
        if (!isOpSelected(e) || !e.plan || e.plan <= 0) {
            pct = 0;
            bonus = 0;
        } else {
            pct = (e.fact / e.plan * 100);
            const o = r.op;
            bonus = e.fact * (pct >= o.t4 ? o.k4 : pct >= o.t3 ? o.k3 : pct >= o.t2 ? o.k2 : pct >= o.t1 ? o.k1 : 0) / 100;
        }
    } else if (e.group === 'men') {
        if (!isMenSelected(e) || !e.plan || e.plan <= 0) {
            pct = 0;
            bonus = 0;
        } else {
            pct = (e.fact / e.plan * 100);
            const m = r.men;
            const customRate = e.manager_rate || 1.0;
            bonus = e.fact * (pct >= m.t3 ? m.r3 : pct >= m.t2 ? m.r2 : pct >= m.t1 ? customRate : 0) / 100;
        }
    } else if (e.group === 'ish') {
        pct = e.percent || (e.plan ? (e.fact / e.plan * 100) : 0);
        bonus = e.kpi_bonus || 0;
    }

    return { percent: pct, bonus: Math.round(bonus) };
}

// Xodim KPI bonusi (foydalanuvchi qo'lda o'zgartirgan bo'lsa yoki avtomatik)
function computeKpi(e) {
    const auto = getAutoKpi(e);
    if (e.custom_kpi !== undefined && e.custom_kpi !== null && !isNaN(e.custom_kpi)) {
        return { percent: auto.percent, bonus: Math.round(e.custom_kpi) };
    }
    return auto;
}

// KPI bonusini joyida kiritish va real-time hisoblash
function onKpiBonusChange(empId, val) {
    const num = typeof val === 'number' ? val : (parseFloat(val) || 0);
    const item = state.items.find(i => i.id === empId);
    if (!item) return;

    item.custom_kpi = num;
    item.kpi_bonus = num;
    const tot = item.oklad + num;
    const rest = tot - item.advance;
    item.total_salary = tot;
    item.rest_to_pay = rest;

    // Satrdagi qiymatlarni darhol yangilash (fokus yo'qolmasligi uchun DOM update)
    const totEl = document.getElementById(`emp-tot-${empId}`);
    if (totEl) totEl.innerHTML = `<b>${f(tot)}</b>`;

    const restEl = document.getElementById(`emp-rest-${empId}`);
    if (restEl) {
        restEl.className = rest < 0 ? 'r' : 'g';
        restEl.innerHTML = `<b>${f(rest)}</b>`;
    }

    const inp = document.getElementById(`emp-kpi-${empId}`);
    if (inp) {
        inp.style.color = num > 0 ? 'var(--ok)' : 'var(--tx-muted)';
    }

    // Tepaning umumiy ko'rsatkichlari va jadval footerini yangilash
    const activeItems = state.items.filter(i => i.is_active);
    let s = { ok: 0, b: 0, av: 0, t: 0, r: 0 };
    activeItems.forEach(e => {
        const k = computeKpi(e);
        const t = e.oklad + k.bonus;
        const r = t - e.advance;
        s.ok += e.oklad;
        s.b += k.bonus;
        s.av += e.advance;
        s.t += t;
        s.r += r;
    });

    const cardB = document.getElementById('calc-card-bonus');
    if (cardB) cardB.textContent = f(s.b);

    const cardT = document.getElementById('calc-card-total');
    if (cardT) cardT.textContent = f(s.t);

    const cardR = document.getElementById('calc-card-rest');
    if (cardR) cardR.textContent = f(s.r);

    const cardWrap = document.getElementById('calc-card-rest-wrap');
    if (cardWrap) {
        cardWrap.className = `k ${s.r < 0 ? 'accent-er' : 'accent-ok'}`;
    }

    const footB = document.getElementById('calc-foot-bonus');
    if (footB) footB.textContent = f(s.b);

    const footT = document.getElementById('calc-foot-total');
    if (footT) footT.textContent = f(s.t);

    const footR = document.getElementById('calc-foot-rest');
    if (footR) footR.textContent = f(s.r);
}

// 3-TAB: Yakunlash va MoySklad
function renderFin() {
    const activeItems = state.items.filter(i => i.is_active);
    const end = $('#d2').value;

    let totalSalary = 0;
    let nonZeroCount = 0;
    const empRows = activeItems.map(e => {
        const k = computeKpi(e);
        const tot = Math.round(e.oklad + k.bonus);
        totalSalary += tot;
        if (tot > 0) nonZeroCount++;
        return `
            <tr>
                <td><b>${e.name}</b></td>
                <td>${e.category_name || G_NAMES[e.group]}</td>
                <td><b>${f(tot)}</b></td>
                <td class="l">${end} 23:45</td>
            </tr>
        `;
    }).join('');

    return `
        <div class="card">
            <h3 style="font-size:16px; font-weight:700; margin-bottom:12px;">Oy yakuni — MoySklad'ga yoziladigan avtomatik hujjatlar</h3>
            
            <div class="kpis" style="margin-top:14px; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));">
                <div class="k accent-pr">
                    <small>1) Исходящий платеж (Халк банк)</small>
                    <b>${f(totalSalary)}</b> so'm
                    <small style="margin-top:6px; color:var(--tx-muted);">Ҳ/р: «Халк банк» · Статья: «Начисления» · Sana: ${end} 23:45</small>
                </div>
                <div class="k accent-ok">
                    <small>2) Корректировка взаиморасчетов (Xodimlar)</small>
                    <b>${nonZeroCount} ta xodim (> 0)</b>
                    <small style="margin-top:6px; color:var(--tx-muted);">Ойлик: ☑ · Xodimlar shaxsiy hisobiga · Sana: ${end} 23:45</small>
                </div>
            </div>
            <div style="margin-top:10px; font-size:12px; color:var(--tx-muted); background:var(--bg-subtle, rgba(0,0,0,0.03)); padding:8px 12px; border-radius:6px;">
                ℹ️ <b>Eslatma:</b> Korxona o'zaro hisob-kitob balansi (взаиморасчеты) buzilmasligi uchun tashkilot nomiga soxta взаиморасчет yozilmaydi. MoySklad API cheklovi sababli <i>«Корректировка остатков на счете»</i> MoySklad veb-interfeysida (Деньги → Корректировки → Остаток на счете) orqali kiritiladi.
            </div>

            <div class="sc" style="margin-top:16px;">
                <table>
                    <thead>
                        <tr>
                            <th>Xodim</th>
                            <th>Bo'lim / Guruh</th>
                            <th>Hisoblangan jami oylik</th>
                            <th class="l">Sana</th>
                        </tr>
                    </thead>
                    <tbody>${empRows}</tbody>
                </table>
            </div>

            <div style="margin-top:20px;" id="closeMonthActionWrap">
                <button id="btnCloseMonth" class="b b-primary" ${state.closed ? 'disabled' : ''} onclick="closeMonthAndSendToMoySklad()">
                    ${state.closed ? '✓ Oy MoySklad\'da yakunlangan' : 'Oyni yakunlash va MoySklad\'ga yozish'}
                </button>
                <div id="closeMonthStatusBox" style="margin-top:14px; padding:12px 16px; border-radius:8px; border:1px solid transparent; display:none;"></div>
            </div>
        </div>
    `;
}

async function closeMonthAndSendToMoySklad() {
    const btn = document.getElementById('btnCloseMonth');
    const statusBox = document.getElementById('closeMonthStatusBox');
    const end = $('#d2')?.value || '2026-10-31';
    const start = $('#d1')?.value || '2026-10-01';
    const mon = $('#mon')?.value || '2026-10';

    const activeItems = state.items.filter(i => i.is_active);
    let totalSalary = 0;
    const empPayload = [];
    for (const e of activeItems) {
        const k = computeKpi(e);
        const tot = Math.round(e.oklad + k.bonus);
        totalSalary += tot;
        empPayload.push({
            id: e.id,
            emp_id: e.emp_id || e.moysklad_id,
            moysklad_id: e.emp_id || e.moysklad_id,
            name: e.name,
            oklad: e.oklad,
            bonus: k.bonus,
            total_salary: tot,
            group: e.group,
            category_name: e.category_name
        });
    }

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="status-pulse" style="display:inline-block; margin-right:8px;"></span> MoySklad\'ga yozilmoqda, kuting...';
    }
    if (statusBox) {
        statusBox.style.display = 'block';
        statusBox.style.background = 'rgba(37,99,235,0.06)';
        statusBox.style.borderColor = 'var(--pr)';
        statusBox.style.color = 'var(--pr)';
        statusBox.innerHTML = `<strong>MoySklad'ga yozilmoqda...</strong> Исходящий платеж (Ҳ/р: «Халк банк»), Корректировка остатков на счете (Ойлик: ☑) va xodimlar oyliklari jo'natilmoqda...`;
    }

    try {
        const resp = await fetch('/api/moysklad/close-month/', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                period_id: state.period_id || 1,
                month: mon,
                date_from: start,
                date_to: end,
                total_salary: totalSalary,
                items: empPayload
            })
        });
        const res = await resp.json();
        
        if (res.success) {
            state.closed = true;
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '✓ Oy MoySklad\'da muvaffaqiyatli yakunlandi';
            }
            if (statusBox) {
                statusBox.style.display = 'block';
                statusBox.style.background = 'rgba(16,185,129,0.1)';
                statusBox.style.borderColor = 'var(--ok)';
                statusBox.style.color = 'var(--ok)';
                statusBox.innerHTML = `
                    <div style="font-size:15px; font-weight:700; margin-bottom:6px;">✓ Buyruqlar muvaffaqiyatli bajarildi!</div>
                    <div>${res.message || "Barcha buyruqlar MoySklad tizimida muvaffaqiyatli ro'yxatdan o'tkazildi."}</div>
                `;
            }
            showToast("✓ Buyruqlar muvaffaqiyatli bajarildi!", 'ok');
            await loadPeriodData();
            draw();
        } else {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = 'Oyni yakunlash va MoySklad\'ga yozish';
            }
            const errMsg = res.error || "MoySklad'ga yozishda xatolik yuz berdi!";
            if (statusBox) {
                statusBox.style.display = 'block';
                statusBox.style.background = 'rgba(239,68,68,0.1)';
                statusBox.style.borderColor = 'var(--er)';
                statusBox.style.color = 'var(--er)';
                statusBox.innerHTML = `
                    <div style="font-size:15px; font-weight:700; margin-bottom:6px;">✗ Buyruqlar bajarilmadi!</div>
                    <div>${errMsg}</div>
                `;
            }
            showToast("✗ Buyruqlar bajarilmadi: " + errMsg, 'err');
        }
    } catch (e) {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = 'Oyni yakunlash va MoySklad\'ga yozish';
        }
        if (statusBox) {
            statusBox.style.display = 'block';
            statusBox.style.background = 'rgba(239,68,68,0.1)';
            statusBox.style.borderColor = 'var(--er)';
            statusBox.style.color = 'var(--er)';
            statusBox.innerHTML = `
                <div style="font-size:15px; font-weight:700; margin-bottom:6px;">✗ Buyruqlar bajarilmadi!</div>
                <div>Tarmoq yoki tizim xatoligi: ${e.message}</div>
            `;
        }
        showToast("✗ Buyruqlar bajarilmadi: " + e.message, 'err');
    }
}

// MoySklad Modal & API Funksiyalari
function openModal(id) {
    const m = $(`#${id}`);
    if (m) m.classList.add('active');
}

function closeModal(id) {
    const m = $(`#${id}`);
    if (m) m.classList.remove('active');
}

document.addEventListener('click', (e) => {
    if (e.target && e.target.classList.contains('modal-overlay')) {
        e.target.classList.remove('active');
    }
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.active').forEach(m => m.classList.remove('active'));
    }
});

function toggleTokenVisibility() {
    const inp = $('#modalMsToken');
    inp.type = inp.type === 'password' ? 'text' : 'password';
}

async function testModalToken() {
    const token = $('#modalMsToken').value.trim();
    const resBox = $('#tokenTestResult');
    resBox.style.display = 'block';
    resBox.className = 'test-result-box';
    resBox.textContent = 'MoySklad serveriga so\'rov yuborilmoqda...';

    try {
        const resp = await fetch('/api/moysklad/test-token/', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ token })
        });
        const res = await resp.json();
        if (res.success) {
            resBox.className = 'test-result-box ok';
            resBox.textContent = '✓ ' + (res.message || 'MoySklad API ga muvaffaqiyatli ulandi!');
        } else {
            resBox.className = 'test-result-box err';
            resBox.textContent = '✗ ' + (res.error || 'Ulanib bo\'lmadi');
        }
    } catch (e) {
        resBox.className = 'test-result-box err';
        resBox.textContent = '✗ Server xatosi: ' + e.message;
    }
}

async function saveModalToken() {
    const token = $('#modalMsToken').value.trim();
    const company = $('#modalCompanyName').value.trim();

    try {
        const resp = await fetch('/api/moysklad/save-config/', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ token, company_name: company })
        });
        const res = await resp.json();
        if (res.success) {
            showToast(res.message || "MoySklad sozlamalari saqlandi!", 'ok');
            closeModal('msModal');
            await loadPeriodData();
        } else {
            showToast(res.error || "Saqlashda xatolik", 'err');
        }
    } catch (e) {
        showToast("Xatolik: " + e.message, 'err');
    }
}

async function syncFromMoySklad() {
    showToast("MoySklad'dan jonli yangilanmoqda...", 'ok');
    await loadPeriodData();
    showToast("MoySklad'dan barcha ma'lumotlar jonli yangilandi!", 'ok');
}

// Toast xabarlari
function showToast(msg, type = 'ok') {
    const box = $('#toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = msg;
    box.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}
