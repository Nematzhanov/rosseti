// Презентация в стиле неоморфизма: одна мягкая поверхность, выпуклые и вдавленные элементы с парой теней.
// Сквозной «шар» (!!orbL/!!orbD + !!num) связывает слайды переходом «Трансформация».
const pptxgen = require('pptxgenjs');
const fs = require('fs');
const path = require('path');

const D = JSON.parse(fs.readFileSync(path.join(__dirname, 'data.json'), 'utf8'));
const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE';
pres.title = 'Прогнозирование электропотребления ОЭС Северо-Запада';

const W = 13.333, H = 7.5;
const C = {
  BG: 'E6EBF1', INK: '2D3748', MUTED: '66768C', ACC: '2563C9', TEAL: '12A3B5', SOFT: '8FB0DE',
  GRAY: 'B4BFCD', SH_D: 'A3B1C6', SH_L: 'FFFFFF', WHITE: 'FFFFFF',
};
const F = 'Calibri';
const SH = pres.shapes;
const f2 = v => v.toFixed(2).replace('.', ',');
const Y = D.year, S = D.seasons, ST = D.stats, BF = D.best_ft, BF_LORA = BF.includes('lora');
const BF_NAME = BF_LORA ? 'Chronos-2 после дообучения LoRA' : 'Chronos-2 после полного дообучения';
const anim = {};
const SCRIPT = JSON.parse(fs.readFileSync(path.join(__dirname, 'script.json'), 'utf8'));  // сценарий выступления → заметки докладчика
let uid = 0;

const KEEP = process.env.KEEP ? process.env.KEEP.split(',').map(Number) : null;  // отладка: собрать часть слайдов
function newSlide() {
  const n = Object.keys(anim).length + 1;
  anim[n] = [];
  if (KEEP && !KEEP.includes(n)) return { _n: n, addText() {}, addShape() {}, addImage() {}, addChart() {}, addNotes() {} };
  const s = pres.addSlide();
  s._n = n;
  const addNotes = s.addNotes.bind(s);
  s.addNotes = t => addNotes(SCRIPT[n] || t);
  s.background = { color: C.BG };
  return s;
}
const nm = (s, base) => `s${s._n}_${base}_${++uid}`;
// Тени — новые объекты на каждый вызов: pptxgenjs меняет параметры на месте
const shD = (k = 1) => ({ type: 'outer', color: C.SH_D, blur: 11 * k, offset: 5 * k, angle: 45, opacity: 0.6 });
const shL = (k = 1) => ({ type: 'outer', color: C.SH_L, blur: 11 * k, offset: 5 * k, angle: 225, opacity: 0.95 });
const shIn = () => ({ type: 'inner', color: C.SH_D, blur: 7, offset: 3, angle: 45, opacity: 0.75 });

function text(s, t, o, a) {
  const name = o.objectName || nm(s, 'txt');
  s.addText(t, { isTextBox: true, fontFace: F, color: C.INK, margin: 0, ...o, objectName: name });
  if (a) a.push(name);
  return name;
}
function shape(s, type, o) {
  const name = o.objectName || nm(s, 'shp');
  s.addShape(type, { line: { type: 'none' }, ...o, objectName: name });
  return name;
}
// Выпуклый элемент: нижняя фигура со светлой тенью, верхняя — с тёмной
function raised(s, x, y, w, h, o = {}) {
  const round = o.circle ? SH.OVAL : SH.ROUNDED_RECTANGLE;
  const r = o.pill ? Math.min(w, h) / 2 : (o.r ?? 0.22);
  const k = o.k ?? 1;
  const base = () => ({ x, y, w, h, fill: { color: o.fill || C.BG }, ...(o.circle ? {} : { rectRadius: r }) });
  const n1 = shape(s, round, { ...base(), shadow: shL(k), objectName: o.names ? o.names[0] : undefined });
  const n2 = shape(s, round, { ...base(), shadow: shD(k), objectName: o.names ? o.names[1] : undefined });
  return [n1, n2];
}
// Вдавленный элемент: внутренняя тень
function inset(s, x, y, w, h, o = {}) {
  const round = o.circle ? SH.OVAL : SH.ROUNDED_RECTANGLE;
  const r = o.pill ? Math.min(w, h) / 2 : (o.r ?? 0.18);
  return shape(s, round, { x, y, w, h, fill: { color: o.fill || C.BG }, shadow: shIn(), ...(o.circle ? {} : { rectRadius: r }) });
}
function icon(s, kind, x, y, d, color = C.ACC) {
  const out = [], fill = { color };
  if (kind === 'bolt') out.push(shape(s, SH.LIGHTNING_BOLT, { x, y, w: d, h: d, fill }));
  if (kind === 'cloud') {
    out.push(shape(s, SH.SUN, { x: x + d * 0.32, y: y - d * 0.04, w: d * 0.6, h: d * 0.6, fill: { color: 'F2B84B' } }));
    out.push(shape(s, SH.CLOUD, { x: x - d * 0.04, y: y + d * 0.34, w: d * 0.95, h: d * 0.6, fill }));
  }
  if (kind === 'grid') {
    const c = d / 3.4;
    for (let r = 0; r < 3; r++) for (let q = 0; q < 3; q++)
      out.push(shape(s, SH.ROUNDED_RECTANGLE, { x: x + q * c * 1.2, y: y + r * c * 1.2, w: c, h: c, rectRadius: c * 0.25, fill }));
  }
  if (kind === 'repeat') out.push(shape(s, SH.CIRCULAR_ARROW, { x, y, w: d, h: d, fill }));
  if (kind === 'tree') out.push(shape(s, SH.FLOWCHART_DECISION, { x, y: y + d * 0.12, w: d, h: d * 0.76, fill }));
  if (kind === 'hex') out.push(shape(s, SH.HEXAGON, { x, y: y + d * 0.08, w: d, h: d * 0.84, fill }));
  return out;
}
function iconOrb(s, x, y, d, kind, color) {
  return [...raised(s, x, y, d, d, { circle: true, k: 0.7 }), ...icon(s, kind, x + d * 0.26, y + d * 0.26, d * 0.48, color)];
}

// ---------- сквозной шар ----------
function orb(s, mode, num) {
  if (mode === 'cover') {
    raised(s, 7.85, 1.3, 4.7, 4.7, { circle: true, k: 2, names: ['!!orbL', '!!orbD'] });
    shape(s, SH.OVAL, { x: 8.75, y: 2.2, w: 2.9, h: 2.9, fill: { color: C.BG }, shadow: shIn(), objectName: '!!well' });
    shape(s, SH.LIGHTNING_BOLT, { x: 9.55, y: 2.95, w: 1.3, h: 1.4, fill: { color: C.ACC }, objectName: '!!bolt' });
  } else if (mode === 'section') {
    raised(s, 1.1, 2.0, 3.5, 3.5, { circle: true, k: 1.6, names: ['!!orbL', '!!orbD'] });
    shape(s, SH.OVAL, { x: 1.6, y: 2.5, w: 2.5, h: 2.5, fill: { color: C.BG }, shadow: shIn(), objectName: '!!well' });
    text(s, num, { x: 1.6, y: 2.5, w: 2.5, h: 2.5, align: 'center', valign: 'middle', fontSize: 80, bold: true, color: C.ACC, objectName: '!!num' });
  } else if (mode === 'content') {
    raised(s, 0.55, 0.42, 0.78, 0.78, { circle: true, k: 0.6, names: ['!!orbL', '!!orbD'] });
    text(s, num, { x: 0.55, y: 0.42, w: 0.78, h: 0.78, align: 'center', valign: 'middle', fontSize: 20, bold: true, color: C.ACC, objectName: '!!num' });
  } else if (mode === 'final') {
    raised(s, 8.75, 1.55, 3.9, 3.9, { circle: true, k: 2, names: ['!!orbL', '!!orbD'] });
    shape(s, SH.OVAL, { x: 9.3, y: 2.1, w: 2.8, h: 2.8, fill: { color: C.BG }, shadow: shIn(), objectName: '!!well' });
    text(s, num, { x: 9.3, y: 2.25, w: 2.8, h: 1.7, align: 'center', valign: 'bottom', fontSize: 54, bold: true, color: C.ACC, objectName: '!!num' });
  }
}
function title(s, t, sub) {
  text(s, t, { x: 1.6, y: 0.42, w: 11.1, h: 0.78, valign: 'middle', fontSize: 32, bold: true });
  if (sub) text(s, sub, { x: 1.6, y: 1.16, w: 11.1, h: 0.36, fontSize: 15, color: C.MUTED });
}
// Карточка с крупной цифрой
function statCard(s, x, y, w, h, big, label, a, color = C.ACC, bigSize = 40) {
  const g = [...raised(s, x, y, w, h)];
  g.push(text(s, big, { x: x + 0.28, y: y + 0.2, w: w - 0.5, h: bigSize / 58, fontSize: bigSize, bold: true, color, valign: 'bottom' }));
  g.push(text(s, label, { x: x + 0.28, y: y + 0.26 + bigSize / 58, w: w - 0.5, h: h - 0.4 - bigSize / 58, fontSize: 13, color: C.MUTED, valign: 'top' }));
  a.push(g);
}
const chartBase = () => ({
  valAxisLabelColor: C.MUTED, catAxisLabelColor: C.MUTED, valAxisLabelFontSize: 11, catAxisLabelFontSize: 11,
  valAxisLabelFontFace: F, catAxisLabelFontFace: F, valGridLine: { color: 'D3DAE4', size: 0.75 },
  catGridLine: { style: 'none' }, legendFontFace: F, legendFontSize: 12, legendColor: C.MUTED,
});

// ---------- 1. Обложка ----------
{
  const s = newSlide(); orb(s, 'cover');
  const p = raised(s, 0.8, 1.05, 3.5, 0.48, { pill: true, k: 0.6 });
  text(s, 'ИССЛЕДОВАТЕЛЬСКИЙ ПРОЕКТ', { x: 0.8, y: 1.05, w: 3.5, h: 0.48, align: 'center', valign: 'middle', fontSize: 12, bold: true, color: C.ACC, charSpacing: 2 });
  text(s, 'Прогнозирование электропотребления ОЭС Северо-Запада', { x: 0.8, y: 1.85, w: 6.8, h: 2.5, fontSize: 46, bold: true, valign: 'top', lineSpacingMultiple: 0.95 });
  text(s, 'Машинное обучение с учётом погодных факторов: почасовой прогноз на сутки вперёд', { x: 0.8, y: 4.45, w: 6.4, h: 0.8, fontSize: 18, color: C.MUTED });
  inset(s, 0.8, 5.55, 2.6, 0.5, { pill: true });
  text(s, 'СО ЕЭС · 2021–2026', { x: 0.8, y: 5.55, w: 2.6, h: 0.5, align: 'center', valign: 'middle', fontSize: 13, bold: true, color: C.INK });
  inset(s, 3.6, 5.55, 2.1, 0.5, { pill: true });
  text(s, 'Октябрь 2026', { x: 3.6, y: 5.55, w: 2.1, h: 0.5, align: 'center', valign: 'middle', fontSize: 13, bold: true, color: C.INK });
  s.addNotes('Тема: прогноз почасового потребления мощности ОЭС Северо-Запада на сутки вперёд. Сравниваем классическое машинное обучение и предобученную модель временных рядов Chronos-2, все модели используют прогноз погоды.');
}

// ---------- разделы ----------
function section(num, idx, head, sub, note) {
  const s = newSlide(); orb(s, 'section', num);
  text(s, head, { x: 5.4, y: 2.35, w: 7.3, h: 1.1, fontSize: 44, bold: true, valign: 'bottom' });
  text(s, sub, { x: 5.4, y: 3.55, w: 6.9, h: 0.9, fontSize: 18, color: C.MUTED, valign: 'top' });
  for (let i = 0; i < 3; i++) {  // где мы: раздел idx из трёх
    if (i === idx) raised(s, 5.4 + i * 0.62, 4.75, 0.36, 0.36, { circle: true, k: 0.5, fill: C.ACC });
    else inset(s, 5.4 + i * 0.62, 4.75, 0.36, 0.36, { circle: true });
  }
  s.addNotes(note);
}
// ---------- История ----------
{
  const s = newSlide(), a = anim[s._n]; orb(s, 'content', '00');
  title(s, 'История: чайники после матча', 'Почему вопрос «сколько электроэнергии понадобится в этот час?» так важен');
  const g = [...raised(s, 0.6, 1.75, 4.5, 5.0, { fill: C.ACC })];
  g.push(text(s, '4 июля 1990', { x: 0.95, y: 2.05, w: 3.8, h: 0.35, fontSize: 13, bold: true, color: 'DCE7FA', charSpacing: 2 }));
  g.push(text(s, '2 800 МВт', { x: 0.95, y: 2.5, w: 3.8, h: 1.0, fontSize: 52, bold: true, color: C.WHITE, valign: 'bottom' }));
  g.push(text(s, 'скачок потребления в Великобритании за считанные минуты после серии пенальти в полуфинале чемпионата мира Англия — ФРГ', { x: 0.95, y: 3.65, w: 3.8, h: 1.5, fontSize: 14.5, color: 'E6EEFB', valign: 'top' }));
  g.push(text(s, '≈ 1,2 млн включённых чайников', { x: 0.95, y: 5.5, w: 3.8, h: 0.9, fontSize: 18, bold: true, color: C.WHITE, valign: 'top' }));
  a.push(g);
  const steps = [
    ['Что происходит', 'В перерыве и после финального свистка миллионы людей одновременно ставят чайник. Нагрузка на сеть растёт на тысячи мегаватт за минуты.'],
    ['Как справляются', 'Диспетчеры заранее изучают телепрограмму и держат наготове быстрые станции: Dinorwig выдаёт 1 320 МВт за 12 секунд. Такие пики есть и сегодня: в финале Евро-2024 — 1 300 МВт.'],
    ['Наша задача', 'Та же, только в масштабе всего региона: заранее знать, сколько электроэнергии понадобится в каждый час завтрашних суток.'],
  ];
  steps.forEach(([head, body], i) => {
    const y = 1.75 + i * 1.7, gg = [];
    gg.push(...raised(s, 5.45, y, 7.3, 1.45));
    gg.push(inset(s, 5.8, y + 0.37, 0.7, 0.7, { circle: true }));
    gg.push(text(s, String(i + 1), { x: 5.8, y: y + 0.37, w: 0.7, h: 0.7, align: 'center', valign: 'middle', fontSize: 22, bold: true, color: C.ACC }));
    gg.push(text(s, head, { x: 6.75, y: y + 0.15, w: 5.8, h: 0.4, fontSize: 18, bold: true }));
    gg.push(text(s, body, { x: 6.75, y: y + 0.55, w: 5.8, h: 0.85, fontSize: 12.5, color: C.MUTED, valign: 'top' }));
    a.push(gg);
  });
  s.addNotes('История о чайниках.');
}

section('01', 0, 'Постановка задачи', 'Проблема, актуальность, цель и задачи исследования', 'Первый раздел: зачем нужен прогноз и что мы хотим получить.');

// ---------- Проблема ----------
{
  const s = newSlide(), a = anim[s._n]; orb(s, 'content', '01');
  title(s, 'Проблема', 'Почему прогноз потребления — непростая задача');
  const corr = String(ST.corr).replace('.', ',').replace('-', '−');
  const cold = Math.round((ST.cold_mean / ST.warm_mean - 1) * 100);
  const cards = [
    ['bolt', 'Ошибка стоит денег', 'По прогнозу на завтра планируют работу электростанций и резервы. Ошибка в 1 % — это около 120 МВт мощности в ОЭС Северо-Запада.'],
    ['cloud', 'Сильная зависимость от погоды', `Корреляция потребления и температуры ${corr}: в морозы потребление на ${cold} % выше, чем в тёплые дни.`],
    ['tree', 'Простые методы не справляются', `Прогноз «как неделю назад» ошибается на ${f2(Y.naive_week['MAPE_%'])} %, а деревья решений занижают пики в сильные морозы.`],
  ];
  const cw = 3.8, gap = 0.37;
  cards.forEach(([ic, head, body], i) => {
    const x = 0.6 + i * (cw + gap), y = 1.85, g = [];
    g.push(...raised(s, x, y, cw, 4.4));
    g.push(...iconOrb(s, x + 0.35, y + 0.35, 0.95, ic));
    g.push(text(s, head, { x: x + 0.35, y: y + 1.55, w: cw - 0.7, h: 0.8, fontSize: 21, bold: true, valign: 'top' }));
    g.push(text(s, body, { x: x + 0.35, y: y + 2.4, w: cw - 0.7, h: 1.8, fontSize: 14, color: C.MUTED, valign: 'top' }));
    a.push(g);
  });
  s.addNotes('Прогноз на сутки вперёд — основа планирования энергосистемы. Сложность в сильной зависимости от погоды и в том, что простые методы ошибаются, особенно в морозы.');
}

// ---------- Актуальность ----------
{
  const s = newSlide(), a = anim[s._n]; orb(s, 'content', '01');
  title(s, 'Актуальность');
  const items = [
    ['Рынок на сутки вперёд', 'Почасовой прогноз потребления нужен каждый день, накануне — до подачи заявок на рынок на сутки вперёд.'],
    ['Новый класс моделей', 'Предобученные нейросети временных рядов, например Chronos-2 (2025), лидируют в мировых сравнениях. Их точность на данных ЕЭС России нужно проверить.'],
    ['Открытые данные', 'СО ЕЭС и Open-Meteo публикуют почасовые данные о потреблении и погоде — исследование полностью воспроизводимо.'],
  ];
  items.forEach(([head, body], i) => {
    const y = 1.75 + i * 1.65, g = [];
    g.push(...raised(s, 0.6, y, 12.15, 1.35));
    g.push(inset(s, 0.95, y + 0.3, 0.75, 0.75, { circle: true }));
    g.push(text(s, String(i + 1), { x: 0.95, y: y + 0.3, w: 0.75, h: 0.75, align: 'center', valign: 'middle', fontSize: 24, bold: true, color: C.ACC }));
    g.push(text(s, head, { x: 2.0, y: y + 0.22, w: 10.4, h: 0.45, fontSize: 20, bold: true }));
    g.push(text(s, body, { x: 2.0, y: y + 0.68, w: 10.4, h: 0.6, fontSize: 14, color: C.MUTED, valign: 'top' }));
    a.push(g);
  });
  s.addNotes('Задача востребована ежедневно; новые предобученные модели ещё не проверены на российских данных; открытые данные позволяют сделать воспроизводимое исследование.');
}

// ---------- Цель и задачи ----------
{
  const s = newSlide(), a = anim[s._n]; orb(s, 'content', '01');
  title(s, 'Цель и задачи');
  const g = [...raised(s, 0.6, 1.75, 4.6, 5.0, { fill: C.ACC })];
  g.push(text(s, 'ЦЕЛЬ', { x: 0.95, y: 2.05, w: 4.0, h: 0.35, fontSize: 13, bold: true, color: 'DCE7FA', charSpacing: 2 }));
  g.push(text(s, 'Разработать модель почасового прогноза потребления ОЭС Северо-Запада на сутки вперёд с учётом погоды и сравнить классическое машинное обучение с предобученной нейросетью Chronos-2', { x: 0.95, y: 2.5, w: 3.95, h: 4.0, fontSize: 18, bold: true, color: C.WHITE, valign: 'top' }));
  a.push(g);
  const tasks = [
    'Собрать данные СО ЕЭС, погоду и производственный календарь за 2021–2026 гг.',
    'Построить базовые модели и градиентный бустинг LightGBM',
    'Дообучить нейросеть Chronos-2 на данных энергосистемы',
    'Проверить модели на целом годе с прогнозом погоды, а не фактом',
    'Сделать интерфейс прогноза на завтра: сайт и приложение',
  ];
  tasks.forEach((t, i) => {
    const y = 1.75 + i * 1.02, gg = [];
    gg.push(inset(s, 5.55, y, 7.2, 0.8, { pill: true }));
    gg.push(...raised(s, 5.65, y + 0.1, 0.6, 0.6, { circle: true, k: 0.5 }));
    gg.push(text(s, String(i + 1), { x: 5.65, y: y + 0.1, w: 0.6, h: 0.6, align: 'center', valign: 'middle', fontSize: 17, bold: true, color: C.ACC }));
    gg.push(text(s, t, { x: 6.45, y, w: 6.15, h: 0.8, valign: 'middle', fontSize: 14.5 }));
    a.push(gg);
  });
  s.addNotes('Цель — точный прогноз на сутки вперёд с учётом погоды. Пять задач идут по порядку: данные, классические модели, нейросеть, честная проверка, интерфейс.');
}

// ---------- 3. Что прогнозируем ----------
{
  const s = newSlide(), a = anim[s._n]; orb(s, 'content', '01');
  title(s, 'Что прогнозируем');
  const g0 = [...raised(s, 0.6, 1.75, 5.7, 4.75)];
  g0.push(text(s, [
    { text: 'Почасовое потребление мощности ОЭС Северо-Запада на следующие сутки: 24 значения, МВт.', options: { breakLine: true, paraSpaceAfter: 14, fontSize: 18, color: C.INK, bold: true } },
    { text: 'Прогноз выпускается накануне в 09:00 МСК, как для рынка на сутки вперёд', options: { bullet: true, breakLine: true, paraSpaceAfter: 9 } },
    { text: 'Модели видят только то, что известно к этому моменту: факт потребления до 08:00 и прогноз погоды', options: { bullet: true, breakLine: true, paraSpaceAfter: 9 } },
    { text: 'Точность оцениваем по 24 часам суток D, метрика MAPE, %', options: { bullet: true } },
  ], { x: 0.95, y: 2.05, w: 5.0, h: 4.2, fontSize: 15, color: C.MUTED, valign: 'top' }));
  a.push(g0);

  const x0 = 6.95, tw = 5.75, ty = 2.55, seg = [9, 15, 24].map(v => v / 48 * tw), g = [];
  g.push(...raised(s, x0 - 0.25, ty - 0.85, tw + 0.5, 2.55));
  g.push(text(s, '09:00 — выпуск прогноза', { x: x0 + seg[0] - 1.2, y: ty - 0.6, w: 2.4, h: 0.3, align: 'center', fontSize: 12, bold: true }));
  g.push(inset(s, x0, ty, tw, 0.42, { pill: true }));
  g.push(shape(s, SH.ROUNDED_RECTANGLE, { x: x0, y: ty, w: seg[0], h: 0.42, rectRadius: 0.21, fill: { color: C.ACC } }));
  g.push(shape(s, SH.ROUNDED_RECTANGLE, { x: x0 + seg[0] + seg[1], y: ty, w: seg[2], h: 0.42, rectRadius: 0.21, fill: { color: C.TEAL } }));
  g.push(shape(s, SH.OVAL, { x: x0 + seg[0] - 0.13, y: ty - 0.24, w: 0.26, h: 0.26, fill: { color: C.INK } }));
  const lab = (x, w, h1, h2) => {
    g.push(text(s, h1, { x, y: ty + 0.6, w, h: 0.3, fontSize: 12.5, bold: true }));
    g.push(text(s, h2, { x, y: ty + 0.9, w, h: 0.5, fontSize: 11.5, color: C.MUTED, valign: 'top' }));
  };
  lab(x0, seg[0] + 0.3, 'D−1, 00–08', 'факт известен');
  lab(x0 + seg[0] + 0.15, seg[1] - 0.2, 'D−1, 09–23', 'не оценивается');
  lab(x0 + seg[0] + seg[1] + 0.1, seg[2] - 0.1, 'Сутки D, 00–23', '24 оцениваемых часа');
  a.push(g);
  statCard(s, 6.7, 4.25, 2.95, 1.95, '7,3–15,8 ГВт', 'диапазон часовой нагрузки в 2021–2026 гг.', a, C.ACC, 30);
  statCard(s, 9.95, 4.25, 2.8, 1.95, `${ST.test_days} суток`, `тестовый период: ${ST.test_start} – ${ST.test_end}`, a, C.ACC, 30);
  s.addNotes('Прогноз на сутки D делается в 09:00 накануне. Часы с 09 до 23 предыдущих суток модель тоже прогнозирует, но в зачёт идут только 24 часа суток D.');
}

section('02', 1, 'Данные и модели', 'Откуда данные, какие модели сравниваем и как проверяем', 'Второй раздел: данные, модели и методика проверки.');

// ---------- 4. Данные ----------
{
  const s = newSlide(), a = anim[s._n]; orb(s, 'content', '02');
  title(s, 'Данные', 'Три открытых источника, всё почасовое и во времени МСК');
  const cards = [
    ['bolt', 'СО ЕЭС', `${ST.hours_total.toLocaleString('ru-RU')} ч`, 'Потребление и генерация ОЭС Северо-Запада с января 2021 года, оперативные данные Системного оператора'],
    ['cloud', 'Open-Meteo', '9 городов', 'Температура, ветер, облачность, радиация. Факт (реанализ ERA5) и архив прогнозов, выпущенных за сутки'],
    ['grid', 'Календарь', '6 лет', 'Производственный календарь РФ: праздники, переносы выходных, сокращённые дни'],
  ];
  const cw = 3.8, gap = 0.37;
  cards.forEach(([ic, head, big, body], i) => {
    const x = 0.6 + i * (cw + gap), y = 1.85, g = [];
    g.push(...raised(s, x, y, cw, 4.55));
    g.push(...iconOrb(s, x + 0.35, y + 0.35, 0.95, ic));
    g.push(text(s, head.toUpperCase(), { x: x + 0.35, y: y + 1.55, w: cw - 0.7, h: 0.35, fontSize: 14, bold: true, color: C.ACC, charSpacing: 1 }));
    g.push(text(s, big, { x: x + 0.35, y: y + 1.92, w: cw - 0.7, h: 0.7, fontSize: 36, bold: true }));
    g.push(text(s, body, { x: x + 0.35, y: y + 2.75, w: cw - 0.7, h: 1.6, fontSize: 13.5, color: C.MUTED, valign: 'top' }));
    a.push(g);
  });
  s.addNotes('Потребление — с сайта СО ЕЭС, почасово с 2021 года. Погода — Open-Meteo по 9 городам ОЭС с весами по населению. Календарь нужен, чтобы модель знала праздники и переносы выходных.');
}

// ---------- 5. Температура ----------
{
  const s = newSlide(), a = anim[s._n]; orb(s, 'content', '02');
  title(s, 'Потребление зависит от температуры', `Среднесуточные значения, ${ST.hist_start}–${ST.hist_end}, ${ST.n_days_hist.toLocaleString('ru-RU')} суток`);
  const g = [...raised(s, 0.6, 1.75, 8.1, 5.05)];
  const ch = nm(s, 'chart');
  const pts = D.scatter.x.map((t, i) => [t, D.scatter.train[i] ?? D.scatter.test[i]]).filter(([t, c]) => t != null && c != null);
  s.addChart(pres.charts.SCATTER, [
    { name: 'Температура', values: pts.map(p => p[0]) },
    { name: 'Потребление', values: pts.map(p => p[1]) },
  ], {
    x: 0.8, y: 1.9, w: 7.7, h: 4.75, objectName: ch, lineSize: 0, lineDataSymbol: 'circle', lineDataSymbolSize: 3,
    chartColors: [C.ACC], showLegend: false,
    showValAxisTitle: true, valAxisTitle: 'Потребление, МВт', valAxisTitleFontSize: 11, valAxisTitleColor: C.MUTED,
    showCatAxisTitle: true, catAxisTitle: 'Среднесуточная температура, °C', catAxisTitleFontSize: 11, catAxisTitleColor: C.MUTED,
    valAxisMinVal: 8000, valAxisMaxVal: 15000, valAxisMajorUnit: 1000, catAxisMinVal: -30, catAxisMaxVal: 30, catAxisMajorUnit: 10,
    valAxisLabelFormatCode: '#,##0', ...chartBase(),
  });
  g.push(ch);
  a.push(g);
  const pct = Math.round((ST.cold_mean / ST.warm_mean - 1) * 100);
  const gw = v => (v / 1000).toFixed(1).replace('.', ',');
  statCard(s, 9.1, 1.75, 3.65, 2.3, `r = ${String(ST.corr).replace('.', ',').replace('-', '−')}`, 'корреляция среднесуточного потребления и температуры', a);
  statCard(s, 9.1, 4.4, 3.65, 2.4, `+${pct} %`, `потребление в морозы ниже −10 °C (${gw(ST.cold_mean)} ГВт) против дней теплее +15 °C (${gw(ST.warm_mean)} ГВт)`, a);
  s.addNotes('Главный внешний фактор — температура: отопление и освещение. Отсюда идея добавить в модели прогноз погоды.');
}


// ---------- 7. Три подхода ----------
{
  const s = newSlide(), a = anim[s._n]; orb(s, 'content', '02');
  title(s, 'Три подхода к прогнозу');
  const cols = [
    ['repeat', 'Базовые модели', 'точка отсчёта', '«Как неделю назад» и линейная регрессия на погоде и календаре. Показывают, сколько даёт машинное обучение.', false],
    ['tree', 'LightGBM', 'градиентный бустинг', '40 признаков: лаги потребления, прогноз погоды, тепловая инерция зданий, календарь. Переобучается каждый месяц.', false],
    ['hex', 'Chronos-2', 'предобученная модель Amazon', '120 млн параметров, обучена на тысячах рядов. Погода и календарь — ковариаты. Дообучена на наших данных.', true],
  ];
  const cw = 3.8, gap = 0.37;
  cols.forEach(([ic, head, kicker, body, hot], i) => {
    const x = 0.6 + i * (cw + gap), y = 1.75, g = [];
    g.push(...raised(s, x, y, cw, 4.35, { fill: hot ? C.ACC : C.BG }));
    if (hot) g.push(...icon(s, ic, x + 0.4, y + 0.4, 0.75, C.WHITE));
    else g.push(...iconOrb(s, x + 0.3, y + 0.3, 0.95, ic));
    const fg = hot ? C.WHITE : C.INK, fg2 = hot ? 'DCE7FA' : C.MUTED;
    g.push(text(s, head, { x: x + 0.35, y: y + 1.45, w: cw - 0.6, h: 0.6, fontSize: 28, bold: true, color: fg }));
    g.push(text(s, kicker.toUpperCase(), { x: x + 0.35, y: y + 2.05, w: cw - 0.6, h: 0.3, fontSize: 12, bold: true, color: hot ? 'DCE7FA' : C.ACC, charSpacing: 1 }));
    g.push(text(s, body, { x: x + 0.35, y: y + 2.45, w: cw - 0.65, h: 1.75, fontSize: 14, color: fg2, valign: 'top' }));
    a.push(g);
  });
  const t = [inset(s, 0.6, 6.35, 7.6, 0.55, { pill: true })];
  t.push(text(s, 'Ансамбль — среднее прогнозов LightGBM и Chronos-2 без дообучения', { x: 0.9, y: 6.35, w: 7.2, h: 0.55, valign: 'middle', fontSize: 14, color: C.INK }));
  a.push(t);
  s.addNotes('Chronos-2 — модель-основа для временных рядов: её не обучают с нуля, а дообучают на наших данных. Мы сравнили дообучение LoRA и полное.');
}

// ---------- 8. Честная проверка ----------
{
  const s = newSlide(), a = anim[s._n]; orb(s, 'content', '02');
  title(s, 'Честная проверка', 'Модель на тесте видит только то, что было бы известно диспетчеру');
  const steps = [
    ['Обучение', '2021 – сентябрь 2025, фактическая погода (ERA5)'],
    ['Выпуск прогноза', 'D−1 в 09:00 по прогнозу погоды, выпущенному накануне'],
    ['Тест', `${ST.test_days} суток, ${(ST.test_days * 24).toLocaleString('ru-RU')} часов: ${ST.test_start} – ${ST.test_end}`],
    ['Переобучение', 'LightGBM — каждый месяц на всех прошлых данных; Chronos-2 — один раз'],
  ];
  const bw = 2.75, gap = 0.37;
  steps.forEach(([head, body], i) => {
    const x = 0.6 + i * (bw + gap), y = 1.9, hot = i === 2, g = [];
    g.push(...raised(s, x, y, bw, 3.0, { fill: hot ? C.ACC : C.BG }));
    if (hot) g.push(shape(s, SH.OVAL, { x: x + 0.3, y: y + 0.3, w: 0.7, h: 0.7, fill: { color: '3A75D4' }, shadow: shIn() }));
    else g.push(inset(s, x + 0.3, y + 0.3, 0.7, 0.7, { circle: true }));
    g.push(text(s, String(i + 1), { x: x + 0.3, y: y + 0.3, w: 0.7, h: 0.7, align: 'center', valign: 'middle', fontSize: 24, bold: true, color: hot ? C.WHITE : C.ACC }));
    g.push(text(s, head, { x: x + 0.3, y: y + 1.2, w: bw - 0.5, h: 0.42, fontSize: 20, bold: true, color: hot ? C.WHITE : C.INK }));
    g.push(text(s, body, { x: x + 0.3, y: y + 1.68, w: bw - 0.5, h: 1.2, fontSize: 13, color: hot ? 'DCE7FA' : C.MUTED, valign: 'top' }));
    a.push(g);
  });
  const n = [inset(s, 0.6, 5.35, 12.15, 0.95, { r: 0.3 })];
  n.push(text(s, 'Если подставить в тест фактическую погоду, точность окажется завышенной: на завтра известен только прогноз. Поэтому в тесте используется архив прогнозов погоды.', { x: 0.95, y: 5.35, w: 11.5, h: 0.95, valign: 'middle', fontSize: 14 }));
  a.push(n);
  s.addNotes('Ключевое требование — отсутствие утечки будущего. Погода в тесте — именно прогноз, выпущенный накануне, а не факт.');
}

section('03', 2, 'Результаты', 'Точность за год, поведение в морозы и вклад погоды', 'Третий раздел: результаты проверки на целом годе.');

// ---------- 10. Точность за год ----------
{
  const s = newSlide(), a = anim[s._n]; orb(s, 'content', '03');
  title(s, 'Точность прогноза за год', 'MAPE, %: средняя абсолютная ошибка, 8 736 часов теста');
  const rows = [
    [BF_LORA ? 'Chronos-2, дообучение LoRA' : 'Chronos-2, полное дообучение', Y[BF]['MAPE_%'], C.ACC],
    ['Ансамбль', Y.ens_lgb_chronos['MAPE_%'], C.TEAL],
    ['LightGBM + прогноз погоды', Y.lgb_fcst['MAPE_%'], C.SOFT],
    ['LightGBM без погоды', Y.lgb_noweather['MAPE_%'], C.GRAY],
    ['Наивный: как неделю назад', Y.naive_week['MAPE_%'], C.GRAY],
  ];
  const g0 = [...raised(s, 0.6, 1.75, 8.6, 5.05)];
  a.push(g0);
  const tx = 3.65, tw = 4.55, max = 3.0;
  rows.forEach(([label, v, col], i) => {
    const y = 2.15 + i * 0.9, g = [];
    g.push(text(s, label, { x: 0.95, y, w: 2.6, h: 0.44, valign: 'middle', fontSize: 14, bold: i === 0, color: C.INK }));
    g.push(inset(s, tx, y, tw, 0.44, { pill: true }));
    g.push(shape(s, SH.ROUNDED_RECTANGLE, { x: tx, y, w: Math.max(0.44, v / max * tw), h: 0.44, rectRadius: 0.22, fill: { color: col } }));
    g.push(text(s, `${f2(v)} %`, { x: tx + tw + 0.15, y, w: 0.85, h: 0.44, valign: 'middle', fontSize: 15, bold: true, color: C.INK }));
    a.push(g);
  });
  const best = Y[BF];
  statCard(s, 9.55, 1.75, 3.2, 1.95, `${f2(best['MAPE_%'])} %`, `ошибка лучшей модели — ${BF_NAME}`, a, C.ACC, 40);
  statCard(s, 9.55, 3.95, 3.2, 1.3, `в ${(Y.naive_week['MAPE_%'] / best['MAPE_%']).toFixed(1).replace('.', ',')} раза`, 'точнее наивного прогноза', a, C.INK, 28);
  statCard(s, 9.55, 5.5, 3.2, 1.3, `${Math.round(best.peak_MAE_MW)} МВт`, 'ошибка в час суточного пика', a, C.INK, 28);
  s.addNotes(`Лучшая модель — ${BF_NAME}: ${f2(best['MAPE_%'])} %. Второй вариант дообучения: LoRA ${f2(Y.chronos_ft_lora_cov_fcst['MAPE_%'])} %, полное ${f2(Y.chronos_ft_full_cov_fcst['MAPE_%'])} % — разница в пределах сотых. Ансамбль — ${f2(Y.ens_lgb_chronos['MAPE_%'])} %.`);
}

// ---------- 11. Холодная неделя ----------
{
  const s = newSlide(), a = anim[s._n]; orb(s, 'content', '03');
  const wk = D.week;
  title(s, 'Самая холодная неделя', `${wk.start} – ${wk.end}, почасово, МВт`);
  const g = [...raised(s, 0.6, 1.75, 8.75, 5.05)];
  const cx = 0.8, cy = 1.9, cw = 8.35, chh = 4.75, L = { x: 0.1, y: 0.05, w: 0.87, h: 0.74 };
  const ch = nm(s, 'chart');
  const lab = wk.labels.map(() => '');
  s.addChart(pres.charts.LINE, [
    { name: 'Факт', labels: lab.map((_, i) => String(i)), values: wk.series.actual },
    { name: 'Chronos-2, дообученная', labels: lab.map((_, i) => String(i)), values: wk.series[BF] },
    { name: 'LightGBM + погода', labels: lab.map((_, i) => String(i)), values: wk.series.lgb_fcst },
  ], {
    x: cx, y: cy, w: cw, h: chh, objectName: ch, chartColors: [C.INK, C.ACC, C.TEAL], lineSize: 2, lineDataSymbol: 'none',
    showLegend: true, legendPos: 'b', catAxisHidden: true, layout: L,
    valAxisMinVal: 12000, valAxisMaxVal: 16000, valAxisMajorUnit: 1000, valAxisLabelFormatCode: '#,##0', ...chartBase(),
  });
  g.push(ch);
  wk.labels.forEach((t, i) => {
    if (!t) return;
    const d = i / 24, px = cx + (L.x + (d + 0.5) / 7 * L.w) * cw;
    g.push(text(s, t, { x: px - 0.6, y: cy + (L.y + L.h) * chh + 0.04, w: 1.2, h: 0.28, align: 'center', fontSize: 11, color: C.MUTED }));
  });
  a.push(g);
  statCard(s, 9.7, 1.75, 3.05, 1.5, `${String(wk.temp_mean).replace('.', ',').replace('-', '−')} °C`, 'средняя температура недели', a, C.INK, 30);
  statCard(s, 9.7, 3.5, 3.05, 1.5, `${f2(wk.mape[BF])} %`, 'ошибка дообученной Chronos-2', a, C.ACC, 30);
  statCard(s, 9.7, 5.25, 3.05, 1.55, `${f2(wk.mape.lgb_fcst)} %`, 'ошибка LightGBM: в мороз занижает пики', a, C.TEAL, 30);
  s.addNotes('В сильный мороз потребление выходит за пределы обычных значений. LightGBM не умеет экстраполировать и занижает пики, Chronos-2 держит форму кривой.');
}

// ---------- 12. Сезоны ----------
{
  const s = newSlide(), a = anim[s._n]; orb(s, 'content', '03');
  title(s, 'Точность по сезонам', 'MAPE, %, лучшие модели');
  const seasons = Object.keys(S);
  const g = [...raised(s, 0.6, 1.75, 8.75, 5.05)];
  const ch = nm(s, 'chart');
  s.addChart(pres.charts.BAR, [
    { name: 'Chronos-2, дообученная', labels: seasons, values: seasons.map(k => S[k][BF]) },
    { name: 'Ансамбль', labels: seasons, values: seasons.map(k => S[k].ens_lgb_chronos) },
    { name: 'LightGBM + погода', labels: seasons, values: seasons.map(k => S[k].lgb_fcst) },
  ], {
    x: 0.8, y: 1.9, w: 8.35, h: 4.75, objectName: ch, barDir: 'col', barGapWidthPct: 70, chartColors: [C.ACC, C.TEAL, C.SOFT],
    showValue: true, dataLabelPosition: 'outEnd', dataLabelFormatCode: '0.00', dataLabelFontSize: 11, dataLabelFontFace: F,
    dataLabelColor: C.INK, valAxisMinVal: 0, valAxisMaxVal: 1.3, valAxisMajorUnit: 0.25, valAxisLabelFormatCode: '0.00',
    showLegend: true, legendPos: 'b', catAxisLabelFontSize: 14, ...chartBase(), catAxisLabelColor: C.INK,
  });
  g.push(ch);
  a.push(g);
  statCard(s, 9.7, 1.75, 3.05, 2.2, `${f2(S['Зима'][BF])} %`, 'зимой лидирует Chronos-2: лучше всех держит пики в мороз', a, C.ACC, 36);
  statCard(s, 9.7, 4.2, 3.05, 2.6, `${f2(S['Лето'].ens_lgb_chronos)} %`, 'летом лучший — ансамбль. Выбор модели по сезону снижает ошибку ещё немного', a, C.TEAL, 36);
  s.addNotes('Зимой и весной сильнее всех дообученная Chronos-2, летом — ансамбль. Можно переключать модель по сезону.');
}

// ---------- 13. Вклад погоды ----------
{
  const s = newSlide(), a = anim[s._n]; orb(s, 'content', '03');
  title(s, 'Что даёт прогноз погоды');
  const lw = Y.lgb_noweather['MAPE_%'], lf = Y.lgb_fcst['MAPE_%'], lo = Y.lgb_oracle['MAPE_%'];
  const cu = Y.chronos_zs_uni['MAPE_%'], cc = Y.chronos_zs_cov_fcst['MAPE_%'];
  const items = [
    ['cloud', `−${Math.round((1 - lf / lw) * 100)} %`, 'ошибки LightGBM', `${f2(lw)} % без погоды → ${f2(lf)} % с прогнозом погоды`],
    ['hex', `−${Math.round((1 - cc / cu) * 100)} %`, 'ошибки Chronos-2 без дообучения', `${f2(cu)} % → ${f2(cc)} %`],
    ['bolt', `${f2(lf - lo)} п. п.`, 'теряем из-за неточности прогноза погоды', `с фактической погодой было бы ${f2(lo)} % вместо ${f2(lf)} %`],
  ];
  const cw = 3.8, gap = 0.37;
  items.forEach(([ic, big, head, body], i) => {
    const x = 0.6 + i * (cw + gap), y = 1.75, g = [];
    g.push(...raised(s, x, y, cw, 4.3));
    g.push(...iconOrb(s, x + 0.3, y + 0.3, 0.95, ic));
    g.push(text(s, big, { x: x + 0.35, y: y + 1.45, w: cw - 0.6, h: 1.0, fontSize: 56, bold: true, color: C.ACC, valign: 'bottom' }));
    g.push(text(s, head, { x: x + 0.35, y: y + 2.6, w: cw - 0.6, h: 0.4, fontSize: 16, bold: true }));
    g.push(text(s, body, { x: x + 0.35, y: y + 3.05, w: cw - 0.6, h: 1.0, fontSize: 13.5, color: C.MUTED, valign: 'top' }));
    a.push(g);
  });
  const t = [inset(s, 0.6, 6.35, 9.6, 0.55, { pill: true })];
  t.push(text(s, 'Ошибка прогноза температуры на сутки — около 1 °C, на точность потребления она почти не влияет', { x: 0.9, y: 6.35, w: 9.2, h: 0.55, valign: 'middle', fontSize: 14 }));
  a.push(t);
  s.addNotes('Погода — самый ценный признак после истории потребления. При этом неточность прогноза погоды почти не вредит: разница с идеальной погодой — сотые доли процента.');
}

// ---------- Применение ----------
{
  const s = newSlide(), a = anim[s._n]; orb(s, 'content', '03');
  title(s, 'Прогноз на завтра одной кнопкой', 'Настольное приложение на Java Swing и веб-интерфейс с той же моделью');
  const g = [...raised(s, 0.6, 1.75, 8.3, 5.05)];
  const img = nm(s, 'img');
  s.addImage({ path: path.join(__dirname, 'img', 'app.jpg'), x: 0.85, y: 2.0, w: 7.8, h: 7.8 * 656 / 992, objectName: img, rounding: false });
  g.push(img);
  a.push(g);
  statCard(s, 9.25, 1.75, 3.5, 1.5, '≈ 30 с', 'расчёт прогноза на сутки на ноутбуке', a, C.ACC, 30);
  statCard(s, 9.25, 3.5, 3.5, 1.5, '24 часа', 'почасовой прогноз с коридором 10–90 %', a, C.ACC, 30);
  statCard(s, 9.25, 5.25, 3.5, 1.55, 'Авто', 'сам докачивает данные СО ЕЭС и прогноз погоды', a, C.ACC, 30);
  s.addNotes('Результат исследования оформлен в инструмент: выбираешь сутки, нажимаешь «Сделать прогноз» и через полминуты получаешь почасовой прогноз с коридором неопределённости.');
}

// ---------- 14. Выводы ----------
{
  const s = newSlide(), a = anim[s._n]; orb(s, 'final', `${f2(Y[BF]['MAPE_%'])} %`);
  text(s, 'Выводы', { x: 0.6, y: 0.5, w: 7, h: 0.8, fontSize: 40, bold: true });
  text(s, 'ошибка лучшей модели', { x: 9.3, y: 4.0, w: 2.8, h: 0.6, align: 'center', valign: 'top', fontSize: 15, color: C.MUTED });
  const ftKey = BF_LORA ? 'chronos_ft_lora_train' : 'chronos_ft_full_train';
  const ft = Math.round((D.timing[ftKey] || 1320) / 60);
  const items = [
    ['Лучший прогноз', `Дообученная Chronos-2 точнее наивного прогноза в ${(Y.naive_week['MAPE_%'] / Y[BF]['MAPE_%']).toFixed(1).replace('.', ',')} раза и лучше всех держит морозные пики`],
    ['Погода важна', `Прогноз погоды по 9 городам снижает ошибку на ${Math.round((1 - Y.lgb_fcst['MAPE_%'] / Y.lgb_noweather['MAPE_%']) * 100)} %, его точности на сутки достаточно`],
    ['Хватает ноутбука', `Дообучение Chronos-2 заняло ${ft} мин на Apple M3, прогноз на целый год — пару минут`],
    ['Дальше', 'Те же модели для всех ОЭС — данные по 8 энергосистемам уже собраны — и ежедневный автоматический прогноз'],
  ];
  items.forEach(([head, body], i) => {
    const x = 0.6 + (i % 2) * 3.95, y = 1.6 + Math.floor(i / 2) * 2.6, g = [];
    g.push(...raised(s, x, y, 3.65, 2.3));
    g.push(text(s, head, { x: x + 0.3, y: y + 0.25, w: 3.1, h: 0.45, fontSize: 19, bold: true, color: C.ACC }));
    g.push(text(s, body, { x: x + 0.3, y: y + 0.78, w: 3.1, h: 1.35, fontSize: 14, color: C.INK, valign: 'top' }));
    a.push(g);
  });
  s.addNotes('Итог: предобученная модель временных рядов после дообучения даёт лучший прогноз, погода важна, всё работает на обычном ноутбуке. Дальше — масштабирование на все ОЭС.');
}

// ---------- Спасибо и QR ----------
{
  const s = newSlide(), a = anim[s._n]; orb(s, 'section', '?');
  text(s, 'Спасибо за внимание', { x: 5.0, y: 1.85, w: 4.4, h: 1.9, fontSize: 40, bold: true, valign: 'bottom' });
  text(s, 'Прогноз на завтра, результаты за год и код — по QR-коду', { x: 5.0, y: 3.85, w: 3.9, h: 1.1, fontSize: 16, color: C.MUTED, valign: 'top' });
  text(s, 'nematzhanov.github.io/rosseti', { x: 5.0, y: 5.05, w: 4.2, h: 0.4, fontSize: 14, bold: true, color: C.ACC });
  const g = [...raised(s, 9.35, 1.9, 3.4, 3.9, { r: 0.3 })];
  const img = nm(s, 'qr');
  s.addImage({ path: path.join(__dirname, 'img', 'qr.png'), x: 9.7, y: 2.25, w: 2.7, h: 2.7, objectName: img, altText: 'QR-код: nematzhanov.github.io/rosseti' });
  g.push(img);
  g.push(text(s, 'Наведите камеру', { x: 9.7, y: 5.05, w: 2.7, h: 0.5, align: 'center', valign: 'middle', fontSize: 13, color: C.MUTED }));
  a.push(g);
  s.addNotes('Спасибо.');
}

fs.writeFileSync(path.join(__dirname, 'anim.json'), JSON.stringify(anim, null, 1));
pres.writeFile({ fileName: process.env.OUT || path.join(__dirname, 'raw_neo.pptx') }).then(f => console.log('written', f));
