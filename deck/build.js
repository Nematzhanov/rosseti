// Презентация: прогноз потребления ОЭС Северо-Запада. Палитра — фирменный синий Pantone 301C (RGB 0 90 155).
// Сквозные объекты !!band / !!num / !!wave / !!shade связывают слайды переходом «Трансформация» (Morph).
const pptxgen = require('pptxgenjs');
const fs = require('fs');
const path = require('path');

const D = JSON.parse(fs.readFileSync(path.join(__dirname, 'data.json'), 'utf8'));
const IMG = path.join(__dirname, 'img') + '/';
const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE';
pres.title = 'Прогнозирование электропотребления ОЭС Северо-Запада';
pres.subject = 'Прогноз потребления на сутки вперёд с учётом погоды';

const W = 13.333, H = 7.5, WAVE_AR = 2400 / 700;
const C = {
  BLUE: '005A9B', NAVY: '06183A', CYAN: '1FA2CB', SKY: '9CC3E4', LIGHT: 'EEF4FA',
  GRAY: 'D1D3D4', GRAY2: '9AA4AD', INK: '17212B', MUTED: '5B6773', WHITE: 'FFFFFF', PALE: 'C9DDF0',
};
const FH = 'Arial Narrow', FB = 'Arial';
const f2 = v => v.toFixed(2).replace('.', ',');
const Y = D.year, S = D.seasons, ST = D.stats;
const BF = D.best_ft, BF_LORA = BF.includes('lora');  // лучший вариант дообучения Chronos-2
const BF_NAME = BF_LORA ? 'Chronos-2 после дообучения LoRA' : 'Chronos-2 после полного дообучения';
const anim = {};
let uid = 0;

const KEEP = process.env.KEEP ? process.env.KEEP.split(',').map(Number) : null;  // отладка: собрать часть слайдов
function newSlide() {
  const n = Object.keys(anim).length + 1;
  anim[n] = [];
  if (KEEP && !KEEP.includes(n)) return { _n: n, addText() {}, addShape() {}, addImage() {}, addChart() {}, addNotes() {} };
  const s = pres.addSlide();
  s._n = n;
  return s;
}
const nm = (s, base) => `s${s._n}_${base}_${++uid}`;
// Каждый вызов получает свой объект параметров: pptxgenjs меняет их на месте
function text(s, t, o, a) {
  const name = nm(s, 'txt');
  s.addText(t, { isTextBox: true, fontFace: FB, color: C.INK, margin: 0, objectName: name, ...o });
  if (a) a.push(name);
  return name;
}
function shape(s, type, o, a) {
  const name = o.objectName || nm(s, 'shp');
  s.addShape(type, { line: { type: 'none' }, ...o, objectName: name });
  if (a) a.push(name);
  return name;
}
function image(s, file, o) { s.addImage({ path: IMG + file, ...o }); }

// ---------- сквозной мотив ----------
function motif(s, mode, num) {
  if (mode === 'dark') {
    s.background = { color: C.NAVY };
    shape(s, pres.shapes.RECTANGLE, { x: 0, y: 0, w: W, h: H, fill: { color: C.BLUE }, objectName: '!!band' });
    image(s, 'overlay.png', { x: 0, y: 0, w: W, h: H, objectName: '!!shade' });
    image(s, 'wave_white.png', { x: -0.8, y: H - 3.75, w: 15, h: 15 / WAVE_AR, objectName: '!!wave' });
  } else if (mode === 'section') {
    s.background = { color: C.WHITE };
    shape(s, pres.shapes.RECTANGLE, { x: 0, y: 0, w: 4.3, h: H, fill: { color: C.BLUE }, objectName: '!!band' });
    image(s, 'overlay.png', { x: 0, y: 0, w: W, h: H, transparency: 100, objectName: '!!shade' });
    image(s, 'wave_white.png', { x: -2.4, y: H - 2.7, w: 8.4, h: 8.4 / WAVE_AR, objectName: '!!wave' });
    text(s, num, { x: 0.55, y: 2.35, w: 3.4, h: 2.1, fontFace: FH, fontSize: 150, bold: true, color: C.WHITE, objectName: '!!num' });
  } else {
    s.background = { color: C.WHITE };
    image(s, 'wave_blue.png', { x: W - 4.6, y: H - 1.0, w: 4.6, h: 4.6 / WAVE_AR, transparency: 40, objectName: '!!wave' });
    image(s, 'overlay.png', { x: 0, y: 0, w: W, h: H, transparency: 100, objectName: '!!shade' });
    shape(s, pres.shapes.RECTANGLE, { x: 0.6, y: 0.5, w: 0.62, h: 0.62, fill: { color: C.BLUE }, objectName: '!!band' });
    text(s, num, { x: 0.6, y: 0.5, w: 0.62, h: 0.62, align: 'center', valign: 'middle', fontFace: FH, fontSize: 17, bold: true, color: C.WHITE, objectName: '!!num' });
  }
}
function title(s, t, sub) {
  text(s, t.toUpperCase(), { x: 1.45, y: 0.47, w: 11.3, h: 0.68, valign: 'middle', fontFace: FH, fontSize: 30, bold: true });
  if (sub) text(s, sub, { x: 1.45, y: 1.13, w: 11.3, h: 0.38, fontSize: 14, color: C.MUTED });
}
function stat(s, x, y, w, big, label, a, color = C.BLUE, bigSize = 54, labelH = 0.75) {
  const n1 = text(s, big, { x, y, w, h: bigSize / 60, fontFace: FH, fontSize: bigSize, bold: true, color, valign: 'bottom' });
  const n2 = text(s, label, { x, y: y + bigSize / 60 + 0.08, w, h: labelH, fontSize: 13.5, color: C.MUTED, valign: 'top' });
  if (a) a.push([n1, n2]);
}
function iconCircle(s, x, y, d, kind, fill = C.BLUE) {
  const names = [shape(s, pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill } })];
  const p = d * 0.24, ix = x + p, iy = y + p, iw = d - 2 * p;
  const white = { fill: { color: C.WHITE } };
  if (kind === 'bolt') names.push(shape(s, pres.shapes.LIGHTNING_BOLT, { x: ix, y: iy, w: iw, h: iw, ...white }));
  if (kind === 'cloud') {
    names.push(shape(s, pres.shapes.SUN, { x: ix + iw * 0.3, y: iy - iw * 0.05, w: iw * 0.62, h: iw * 0.62, fill: { color: 'F2C14E' } }));
    names.push(shape(s, pres.shapes.CLOUD, { x: ix - iw * 0.05, y: iy + iw * 0.35, w: iw * 0.95, h: iw * 0.6, ...white }));
  }
  if (kind === 'grid') {
    const c = iw / 3.4;
    for (let r = 0; r < 3; r++) for (let q = 0; q < 3; q++)
      names.push(shape(s, pres.shapes.RECTANGLE, { x: ix + q * c * 1.2, y: iy + r * c * 1.2, w: c, h: c, ...white }));
  }
  if (kind === 'repeat') names.push(shape(s, pres.shapes.CIRCULAR_ARROW, { x: ix, y: iy, w: iw, h: iw, ...white }));
  if (kind === 'tree') names.push(shape(s, pres.shapes.FLOWCHART_DECISION, { x: ix, y: iy + iw * 0.12, w: iw, h: iw * 0.76, ...white }));
  if (kind === 'hex') names.push(shape(s, pres.shapes.HEXAGON, { x: ix, y: iy + iw * 0.08, w: iw, h: iw * 0.84, ...white }));
  return names;
}
const axisStyle = () => ({
  valAxisLabelColor: C.MUTED, catAxisLabelColor: C.MUTED, valAxisLabelFontSize: 11, catAxisLabelFontSize: 11,
  valAxisLabelFontFace: FB, catAxisLabelFontFace: FB, valGridLine: { color: 'E5E9ED', size: 0.75 },
  catGridLine: { style: 'none' }, valAxisLineShow: false,
});

// ---------- 1. Обложка ----------
{
  const s = newSlide(); motif(s, 'dark');
  text(s, 'ИССЛЕДОВАТЕЛЬСКИЙ ПРОЕКТ', { x: 0.8, y: 1.0, w: 8, h: 0.35, fontSize: 13, bold: true, color: C.PALE, charSpacing: 3 });
  text(s, 'ПРОГНОЗИРОВАНИЕ\nЭЛЕКТРОПОТРЕБЛЕНИЯ\nОЭС СЕВЕРО-ЗАПАДА', { x: 0.8, y: 1.45, w: 9.5, h: 2.6, fontFace: FH, fontSize: 50, bold: true, color: C.WHITE, lineSpacingMultiple: 0.92, valign: 'top' });
  text(s, 'Машинное обучение с учётом погодных факторов: почасовой прогноз на сутки вперёд', { x: 0.8, y: 4.15, w: 8.2, h: 0.75, fontSize: 19, color: 'E3EDF6' });
  shape(s, pres.shapes.RECTANGLE, { x: 0.8, y: 5.15, w: 2.3, h: 0.46, fill: { color: C.WHITE, transparency: 100 }, line: { color: C.WHITE, width: 1 } });
  text(s, 'ОКТЯБРЬ 2026', { x: 0.8, y: 5.15, w: 2.3, h: 0.46, align: 'center', valign: 'middle', fontFace: FH, fontSize: 14, bold: true, color: C.WHITE, charSpacing: 2 });
  s.addNotes('Тема: прогноз почасового потребления мощности ОЭС Северо-Запада на сутки вперёд. Сравниваем классическое машинное обучение и предобученную модель временных рядов Chronos-2, все модели используют прогноз погоды.');
}

// ---------- 2. Раздел 01 ----------
function section(num, head, sub, note) {
  const s = newSlide(); motif(s, 'section', num);
  text(s, head, { x: 5.0, y: 2.55, w: 7.6, h: 1.0, fontFace: FH, fontSize: 40, bold: true, color: C.BLUE, valign: 'bottom' });
  text(s, sub, { x: 5.0, y: 3.65, w: 7.2, h: 0.9, fontSize: 18, color: C.MUTED, valign: 'top' });
  s.addNotes(note);
}
section('01', 'ЗАДАЧА И ДАННЫЕ', 'Что прогнозируем, на каких данных и как устроена проверка', 'Первый раздел: постановка задачи и данные.');

// ---------- 3. Что прогнозируем ----------
{
  const s = newSlide(), a = anim[s._n]; motif(s, 'content', '01');
  title(s, 'Что прогнозируем');
  text(s, [
    { text: 'Почасовое потребление мощности ОЭС Северо-Запада на следующие сутки: 24 значения в МВт.', options: { breakLine: true, paraSpaceAfter: 14, fontSize: 18, color: C.INK } },
    { text: 'Прогноз выпускается накануне в 09:00 МСК, как для рынка на сутки вперёд', options: { bullet: true, breakLine: true, paraSpaceAfter: 8 } },
    { text: 'Модели видят только то, что известно к этому моменту: факт потребления до 08:00 и прогноз погоды', options: { bullet: true, breakLine: true, paraSpaceAfter: 8 } },
    { text: 'Точность оцениваем по 24 часам суток D, метрика MAPE, %', options: { bullet: true } },
  ], { x: 0.6, y: 1.75, w: 5.6, h: 3.6, fontSize: 15, color: C.MUTED, valign: 'top' }, a);

  const x0 = 6.95, tw = 5.75, ty = 2.75, seg = [9, 15, 24].map(v => v / 48 * tw);
  const g = [];
  g.push(text(s, '09:00 — выпуск прогноза', { x: x0 + seg[0] - 1.2, y: ty - 0.78, w: 2.4, h: 0.3, align: 'center', fontSize: 12, bold: true, color: C.INK }));
  g.push(shape(s, pres.shapes.ISOSCELES_TRIANGLE, { x: x0 + seg[0] - 0.12, y: ty - 0.4, w: 0.24, h: 0.2, rotate: 180, fill: { color: C.INK } }));
  g.push(shape(s, pres.shapes.RECTANGLE, { x: x0, y: ty, w: seg[0] - 0.04, h: 0.42, fill: { color: C.BLUE } }));
  g.push(shape(s, pres.shapes.RECTANGLE, { x: x0 + seg[0], y: ty, w: seg[1] - 0.04, h: 0.42, fill: { color: C.GRAY } }));
  g.push(shape(s, pres.shapes.RECTANGLE, { x: x0 + seg[0] + seg[1], y: ty, w: seg[2], h: 0.42, fill: { color: C.CYAN } }));
  const lab = (x, w, h1, h2) => {
    g.push(text(s, h1, { x, y: ty + 0.55, w, h: 0.3, fontSize: 12.5, bold: true }));
    g.push(text(s, h2, { x, y: ty + 0.85, w, h: 0.55, fontSize: 11.5, color: C.MUTED, valign: 'top' }));
  };
  lab(x0, seg[0] + 0.3, 'D−1, 00–08', 'факт известен');
  lab(x0 + seg[0] + 0.15, seg[1] - 0.2, 'D−1, 09–23', 'не оценивается');
  lab(x0 + seg[0] + seg[1] + 0.1, seg[2] - 0.1, 'Сутки D, 00–23', '24 оцениваемых часа');
  a.push(g);
  stat(s, x0, 4.75, 2.7, '7,3–15,8', 'ГВт — диапазон часовой нагрузки в 2021–2026 гг.', a, C.BLUE, 40);
  stat(s, x0 + 3.05, 4.75, 2.7, String(ST.test_days), `суток в тестовом периоде: ${ST.test_start} – ${ST.test_end}`, a, C.BLUE, 40);
  s.addNotes('Прогноз на сутки D делается в 09:00 накануне. Часы с 09 до 23 предыдущих суток модель тоже прогнозирует, но в зачёт идут только 24 часа суток D.');
}

// ---------- 4. Данные ----------
{
  const s = newSlide(), a = anim[s._n]; motif(s, 'content', '01');
  title(s, 'Данные', 'Три открытых источника, всё почасовое и во времени МСК');
  const cards = [
    ['bolt', 'СО ЕЭС', `${ST.hours_total.toLocaleString('ru-RU')} ч`, 'Потребление и генерация ОЭС Северо-Запада с января 2021 года, оперативные данные Системного оператора'],
    ['cloud', 'OPEN-METEO', '9 городов', 'Температура, ветер, облачность, радиация. Факт (реанализ ERA5) и архив прогнозов, выпущенных за сутки'],
    ['grid', 'КАЛЕНДАРЬ', '6 лет', 'Производственный календарь РФ: праздники, переносы выходных, сокращённые дни'],
  ];
  const cw = 3.85, gap = 0.3;
  cards.forEach(([icon, head, big, body], i) => {
    const x = 0.6 + i * (cw + gap), y = 1.85, g = [];
    g.push(shape(s, pres.shapes.ROUNDED_RECTANGLE, { x, y, w: cw, h: 4.3, rectRadius: 0.08, fill: { color: C.LIGHT } }));
    g.push(...iconCircle(s, x + 0.35, y + 0.35, 0.8, icon));
    g.push(text(s, head, { x: x + 0.35, y: y + 1.35, w: cw - 0.7, h: 0.35, fontFace: FH, fontSize: 16, bold: true, color: C.BLUE, charSpacing: 1 }));
    g.push(text(s, big, { x: x + 0.35, y: y + 1.75, w: cw - 0.7, h: 0.75, fontFace: FH, fontSize: 40, bold: true }));
    g.push(text(s, body, { x: x + 0.35, y: y + 2.6, w: cw - 0.7, h: 1.5, fontSize: 13.5, color: C.MUTED, valign: 'top' }));
    a.push(g);
  });
  s.addNotes('Потребление — с сайта СО ЕЭС, почасово с 2021 года. Погода — Open-Meteo по 9 городам ОЭС с весами по населению. Календарь нужен, чтобы модель знала праздники и переносы выходных.');
}

// ---------- 5. Температура ----------
{
  const s = newSlide(), a = anim[s._n]; motif(s, 'content', '01');
  title(s, 'Потребление зависит от температуры', `Среднесуточные значения, ${ST.hist_start}–${ST.hist_end}, ${ST.n_days_hist.toLocaleString('ru-RU')} суток`);
  const ch = nm(s, 'chart');
  s.addChart(pres.charts.SCATTER, [
    { name: 'Температура', values: D.scatter.x },
    { name: 'Обучающие годы', values: D.scatter.train },
    { name: 'Тестовый год', values: D.scatter.test },
  ], {
    x: 0.5, y: 1.65, w: 8.1, h: 5.25, objectName: ch, lineSize: 0, lineDataSymbol: 'circle', lineDataSymbolSize: 4,
    chartColors: [C.SKY, C.BLUE], showLegend: true, legendPos: 'b', legendFontSize: 11, legendFontFace: FB, legendColor: C.MUTED,
    showValAxisTitle: true, valAxisTitle: 'Потребление, МВт', valAxisTitleFontSize: 11, valAxisTitleColor: C.MUTED,
    showCatAxisTitle: true, catAxisTitle: 'Среднесуточная температура, °C', catAxisTitleFontSize: 11, catAxisTitleColor: C.MUTED,
    valAxisMinVal: 8000, valAxisMaxVal: 15000, valAxisMajorUnit: 1000, catAxisMinVal: -30, catAxisMaxVal: 30, catAxisMajorUnit: 10,
    valAxisLabelFormatCode: '#,##0', ...axisStyle(),
  });
  a.push(ch);
  stat(s, 9.1, 1.9, 3.6, `r = ${String(ST.corr).replace('.', ',').replace('-', '−')}`, 'корреляция среднесуточного потребления и температуры', a);
  const pct = Math.round((ST.cold_mean / ST.warm_mean - 1) * 100);
  const gw = v => (v / 1000).toFixed(1).replace('.', ',');
  stat(s, 9.1, 4.0, 3.6, `+${pct} %`, `потребление в морозы ниже −10 °C (${gw(ST.cold_mean)} ГВт) против дней теплее +15 °C (${gw(ST.warm_mean)} ГВт)`, a, C.BLUE, 54, 1.0);
  s.addNotes('Главный внешний фактор — температура: отопление и освещение. Отсюда идея добавить в модели прогноз погоды.');
}

// ---------- 6. Раздел 02 ----------
section('02', 'МОДЕЛИ И МЕТОДИКА', 'Три подхода к прогнозу и честная проверка на целом годе', 'Второй раздел: какие модели сравниваем и как проверяем.');

// ---------- 7. Три подхода ----------
{
  const s = newSlide(), a = anim[s._n]; motif(s, 'content', '02');
  title(s, 'Три подхода к прогнозу');
  const cols = [
    ['repeat', C.GRAY2, 'Базовые модели', 'Точка отсчёта', '«Как неделю назад» и линейная регрессия на погоде и календаре. Показывают, сколько даёт машинное обучение.'],
    ['tree', C.CYAN, 'LightGBM', 'Градиентный бустинг', '40 признаков: лаги потребления, прогноз погоды, тепловая инерция зданий, календарь. Переобучается каждый месяц.'],
    ['hex', C.BLUE, 'Chronos-2', 'Предобученная модель Amazon', '120 млн параметров, обучена на тысячах рядов. Погода и календарь подаются как ковариаты. Дообучение на наших данных.'],
  ];
  const cw = 3.85, gap = 0.3;
  cols.forEach(([icon, col, head, kicker, body], i) => {
    const x = 0.6 + i * (cw + gap), g = [];
    g.push(...iconCircle(s, x, 1.85, 0.95, icon, col));
    g.push(text(s, head, { x, y: 3.0, w: cw - 0.2, h: 0.55, fontFace: FH, fontSize: 28, bold: true }));
    g.push(text(s, kicker.toUpperCase(), { x, y: 3.55, w: cw - 0.2, h: 0.32, fontSize: 12, bold: true, color: col === C.GRAY2 ? C.MUTED : col, charSpacing: 1 }));
    g.push(text(s, body, { x, y: 3.98, w: cw - 0.3, h: 1.7, fontSize: 14, color: C.MUTED, valign: 'top' }));
    a.push(g);
  });
  const t = text(s, 'Ансамбль — среднее прогнозов LightGBM и Chronos-2 без дообучения.', { x: 0.6, y: 6.05, w: 8.5, h: 0.4, fontSize: 14, italic: true, color: C.INK });
  a.push(t);
  s.addNotes('Chronos-2 — модель-основа для временных рядов: её не обучают с нуля, а дообучают на наших данных. Мы сравнили дообучение LoRA и полное.');
}

// ---------- 8. Честная проверка ----------
{
  const s = newSlide(), a = anim[s._n]; motif(s, 'content', '02');
  title(s, 'Честная проверка', 'Модель на тесте видит только то, что было бы известно диспетчеру');
  const steps = [
    ['Обучение', '2021 – сентябрь 2025, фактическая погода (ERA5)'],
    ['Выпуск прогноза', 'D−1 в 09:00 по прогнозу погоды, выпущенному накануне'],
    ['Тест', `${ST.test_days} суток, ${(ST.test_days * 24).toLocaleString('ru-RU')} часов: ${ST.test_start} – ${ST.test_end}`],
    ['Переобучение', 'LightGBM — каждый месяц на всех прошлых данных; Chronos-2 — один раз'],
  ];
  const bw = 2.7, gap = 0.42;
  steps.forEach(([head, body], i) => {
    const x = 0.6 + i * (bw + gap), y = 2.0, g = [];
    g.push(shape(s, pres.shapes.ROUNDED_RECTANGLE, { x, y, w: bw, h: 2.75, rectRadius: 0.08, fill: { color: i === 2 ? C.BLUE : C.LIGHT } }));
    const fg = i === 2 ? C.WHITE : C.INK, fg2 = i === 2 ? 'DCEAF7' : C.MUTED;
    g.push(text(s, String(i + 1), { x: x + 0.3, y: y + 0.25, w: 0.8, h: 0.75, fontFace: FH, fontSize: 40, bold: true, color: i === 2 ? C.WHITE : C.BLUE }));
    g.push(text(s, head, { x: x + 0.3, y: y + 1.05, w: bw - 0.5, h: 0.4, fontFace: FH, fontSize: 20, bold: true, color: fg }));
    g.push(text(s, body, { x: x + 0.3, y: y + 1.5, w: bw - 0.5, h: 1.1, fontSize: 13, color: fg2, valign: 'top' }));
    if (i < steps.length - 1) g.push(shape(s, pres.shapes.RIGHT_ARROW, { x: x + bw + 0.09, y: y + 1.22, w: 0.24, h: 0.3, fill: { color: C.GRAY2 } }));
    a.push(g);
  });
  const n = text(s, 'Если подставить в тест фактическую погоду, точность окажется завышенной: на завтра известен только прогноз. Поэтому в тесте используется архив прогнозов погоды.', { x: 0.6, y: 5.25, w: 8.6, h: 0.8, fontSize: 14, color: C.INK });
  a.push(n);
  s.addNotes('Ключевое требование — отсутствие утечки будущего. Погода в тесте — именно прогноз, выпущенный накануне, а не факт.');
}

// ---------- 9. Раздел 03 ----------
section('03', 'РЕЗУЛЬТАТЫ', 'Точность за год, поведение в морозы и вклад погоды', 'Третий раздел: результаты бэктеста на целом годе.');

// ---------- 10. Точность за год ----------
{
  const s = newSlide(), a = anim[s._n]; motif(s, 'content', '03');
  title(s, 'Точность прогноза за год', 'MAPE, %: средняя абсолютная ошибка в процентах, 8 736 часов теста');
  const cats = ['Наивный: как неделю назад', 'LightGBM без погоды', 'LightGBM + прогноз погоды', 'Ансамбль', 'Chronos-2, дообученная'];
  const vals = [Y.naive_week['MAPE_%'], Y.lgb_noweather['MAPE_%'], Y.lgb_fcst['MAPE_%'], Y.ens_lgb_chronos['MAPE_%'], Y[BF]['MAPE_%']];
  const best = cats.map((_, i) => (i >= 2 ? vals[i] : 0));
  const ref = cats.map((_, i) => (i < 2 ? vals[i] : 0));
  const ch = nm(s, 'chart');
  s.addChart(pres.charts.BAR, [
    { name: 'Модели с погодой', labels: cats, values: best },
    { name: 'Эталоны', labels: cats, values: ref },
  ], {
    x: 0.5, y: 1.7, w: 7.6, h: 5.0, objectName: ch, barDir: 'bar', barOverlapPct: 100, barGapWidthPct: 55,
    chartColors: [C.BLUE, C.GRAY], showValue: true, dataLabelPosition: 'outEnd', dataLabelFormatCode: '0.00;;;',
    dataLabelFontSize: 13, dataLabelFontFace: FH, dataLabelFontBold: true, dataLabelColor: C.INK,
    valAxisMinVal: 0, valAxisMaxVal: 3.2, valAxisMajorUnit: 0.5, valAxisLabelFormatCode: '0.0', showLegend: false,
    catAxisLabelFontSize: 13, ...axisStyle(), catAxisLabelColor: C.INK,
  });
  a.push(ch);
  const bestM = Y[BF];
  stat(s, 8.7, 1.7, 4.0, `${f2(bestM['MAPE_%'])} %`, `средняя ошибка лучшей модели — ${BF_NAME}`, a, C.BLUE, 66, 0.55);
  stat(s, 8.7, 3.55, 4.0, `в ${(Y.naive_week['MAPE_%'] / bestM['MAPE_%']).toFixed(1).replace('.', ',')} раза`, 'точнее наивного прогноза «как неделю назад»', a, C.INK, 40, 0.5);
  stat(s, 8.7, 4.95, 4.0, `${Math.round(bestM.peak_MAE_MW)} МВт`, 'средняя ошибка в час суточного пика', a, C.INK, 40, 0.5);
  s.addNotes(`Лучшая модель — ${BF_NAME}: ${f2(bestM['MAPE_%'])} %. Второй вариант дообучения: LoRA ${f2(Y.chronos_ft_lora_cov_fcst['MAPE_%'])} %, полное ${f2(Y.chronos_ft_full_cov_fcst['MAPE_%'])} % — разница в пределах сотых. Ансамбль — ${f2(Y.ens_lgb_chronos['MAPE_%'])} %.`);
}

// ---------- 11. Холодная неделя ----------
{
  const s = newSlide(), a = anim[s._n]; motif(s, 'content', '03');
  const wk = D.week;
  title(s, 'Самая холодная неделя', `${wk.start} – ${wk.end}, почасово, МВт`);
  const ch = nm(s, 'chart');
  s.addChart(pres.charts.LINE, [
    { name: 'Факт', labels: wk.labels, values: wk.series.actual },
    { name: 'Chronos-2, дообученная', labels: wk.labels, values: wk.series[BF] },
    { name: 'LightGBM + погода', labels: wk.labels, values: wk.series.lgb_fcst },
  ], {
    x: 0.5, y: 1.65, w: 8.6, h: 5.2, objectName: ch, chartColors: [C.INK, C.BLUE, C.CYAN], lineSize: 2,
    lineDataSymbol: 'none', lineDash: ['solid', 'solid', 'dash'], showLegend: true, legendPos: 'b', legendFontSize: 12,
    legendFontFace: FB, legendColor: C.MUTED, catAxisLabelFrequency: 24, valAxisMinVal: 12000, valAxisMaxVal: 16000,
    valAxisMajorUnit: 1000, valAxisLabelFormatCode: '#,##0', catAxisLabelFontSize: 12, ...axisStyle(),
  });
  a.push(ch);
  stat(s, 9.55, 1.7, 3.3, `${String(wk.temp_mean).replace('.', ',').replace('-', '−')} °C`, 'средняя температура недели', a, C.INK, 40, 0.4);
  stat(s, 9.55, 3.0, 3.3, `${f2(wk.mape[BF])} %`, 'ошибка дообученной Chronos-2', a, C.BLUE, 48, 0.4);
  stat(s, 9.55, 4.45, 3.3, `${f2(wk.mape.lgb_fcst)} %`, 'ошибка LightGBM: деревья решений не экстраполируют и в мороз занижают пики', a, C.CYAN, 48, 0.8);
  s.addNotes('В сильный мороз потребление выходит за пределы обычных значений. LightGBM не умеет экстраполировать и занижает пики, Chronos-2 держит форму кривой.');
}

// ---------- 12. Сезоны ----------
{
  const s = newSlide(), a = anim[s._n]; motif(s, 'content', '03');
  title(s, 'Точность по сезонам', 'MAPE, %, лучшие модели');
  const seasons = Object.keys(S);
  const ch = nm(s, 'chart');
  s.addChart(pres.charts.BAR, [
    { name: 'Chronos-2, дообученная', labels: seasons, values: seasons.map(k => S[k][BF]) },
    { name: 'Ансамбль', labels: seasons, values: seasons.map(k => S[k].ens_lgb_chronos) },
    { name: 'LightGBM + погода', labels: seasons, values: seasons.map(k => S[k].lgb_fcst) },
  ], {
    x: 0.5, y: 1.65, w: 8.4, h: 5.2, objectName: ch, barDir: 'col', barGapWidthPct: 70, chartColors: [C.BLUE, C.CYAN, C.SKY],
    showValue: true, dataLabelPosition: 'outEnd', dataLabelFormatCode: '0.00', dataLabelFontSize: 12, dataLabelFontFace: FH,
    dataLabelFontBold: true, dataLabelColor: C.INK, valAxisMinVal: 0, valAxisMaxVal: 1.3, valAxisMajorUnit: 0.25,
    valAxisLabelFormatCode: '0.00', showLegend: true, legendPos: 'b', legendFontSize: 12, legendFontFace: FB, legendColor: C.MUTED,
    catAxisLabelFontSize: 14, ...axisStyle(), catAxisLabelColor: C.INK,
  });
  a.push(ch);
  stat(s, 9.4, 1.9, 3.4, `${f2(S['Зима'][BF])} %`, 'зимой лидирует Chronos-2: лучше всех держит пики в мороз', a, C.BLUE, 48);
  stat(s, 9.4, 3.75, 3.4, `${f2(S['Лето'].ens_lgb_chronos)} %`, 'летом лучший — ансамбль LightGBM и Chronos-2', a, C.CYAN, 48);
  const t = text(s, 'Сезонный выбор модели — простой способ ещё немного снизить ошибку.', { x: 9.4, y: 5.6, w: 3.4, h: 0.8, fontSize: 13.5, italic: true, color: C.INK });
  a.push(t);
  s.addNotes('Зимой и весной сильнее всех дообученная Chronos-2, летом — ансамбль. Можно переключать модель по сезону.');
}

// ---------- 13. Вклад погоды ----------
{
  const s = newSlide(), a = anim[s._n]; motif(s, 'content', '03');
  title(s, 'Что даёт прогноз погоды');
  const lw = Y.lgb_noweather['MAPE_%'], lf = Y.lgb_fcst['MAPE_%'], lo = Y.lgb_oracle['MAPE_%'];
  const cu = Y.chronos_zs_uni['MAPE_%'], cc = Y.chronos_zs_cov_fcst['MAPE_%'];
  const items = [
    ['cloud', `−${Math.round((1 - lf / lw) * 100)} %`, 'ошибки LightGBM', `${f2(lw)} % без погоды → ${f2(lf)} % с прогнозом погоды`],
    ['hex', `−${Math.round((1 - cc / cu) * 100)} %`, 'ошибки Chronos-2 без дообучения', `${f2(cu)} % → ${f2(cc)} %`],
    ['bolt', `${f2(lf - lo)} п. п.`, 'теряем из-за неточности прогноза погоды', `с фактической погодой было бы ${f2(lo)} % вместо ${f2(lf)} %`],
  ];
  const cw = 3.85, gap = 0.3;
  items.forEach(([icon, big, head, body], i) => {
    const x = 0.6 + i * (cw + gap), g = [];
    g.push(...iconCircle(s, x, 1.9, 0.8, icon));
    g.push(text(s, big, { x, y: 2.95, w: cw - 0.2, h: 1.0, fontFace: FH, fontSize: 60, bold: true, color: C.BLUE, valign: 'bottom' }));
    g.push(text(s, head, { x, y: 4.05, w: cw - 0.3, h: 0.4, fontSize: 16, bold: true }));
    g.push(text(s, body, { x, y: 4.5, w: cw - 0.3, h: 0.8, fontSize: 13.5, color: C.MUTED, valign: 'top' }));
    a.push(g);
  });
  const t = text(s, 'Ошибка прогноза температуры на сутки — около 1 °C, и на точность потребления она почти не влияет.', { x: 0.6, y: 5.75, w: 8.8, h: 0.5, fontSize: 14, italic: true, color: C.INK });
  a.push(t);
  s.addNotes('Погода — самый ценный признак после истории потребления. При этом неточность прогноза погоды почти не вредит: разница с идеальной погодой — сотые доли процента.');
}

// ---------- 14. Выводы ----------
{
  const s = newSlide(), a = anim[s._n]; motif(s, 'dark');
  text(s, 'ВЫВОДЫ', { x: 0.8, y: 0.6, w: 8, h: 0.8, fontFace: FH, fontSize: 40, bold: true, color: C.WHITE });
  const ft = Math.round((D.timing[BF_LORA ? 'chronos_ft_lora_train' : 'chronos_ft_full_train'] || 1320) / 60);
  const items = [
    [`${f2(Y[BF]['MAPE_%'])} %`, `ошибка дообученной Chronos-2 на прогнозе на сутки — лучший результат, в ${(Y.naive_week['MAPE_%'] / Y[BF]['MAPE_%']).toFixed(1).replace('.', ',')} раза точнее наивного`],
    [`−${Math.round((1 - Y.lgb_fcst['MAPE_%'] / Y.lgb_noweather['MAPE_%']) * 100)} %`, 'ошибки даёт прогноз погоды по 9 городам; его точности на сутки вперёд достаточно'],
    [`${ft} мин`, 'дообучение Chronos-2 на ноутбуке Apple M3; прогноз на целый год — около двух минут'],
    ['7 ОЭС', 'следующий шаг: те же модели для всех объединённых энергосистем и федеральных округов'],
  ];
  items.forEach(([big, body], i) => {
    const x = 0.8 + (i % 2) * 6.0, y = 1.75 + Math.floor(i / 2) * 2.1, g = [];
    g.push(text(s, big, { x, y, w: 5.4, h: 0.95, fontFace: FH, fontSize: 52, bold: true, color: C.WHITE, valign: 'bottom' }));
    g.push(text(s, body, { x, y: y + 1.0, w: 5.0, h: 0.85, fontSize: 15, color: 'DCEAF7', valign: 'top' }));
    a.push(g);
  });
  s.addNotes('Итог: предобученная модель временных рядов после дообучения даёт лучший прогноз, погода важна, всё работает на обычном ноутбуке. Дальше — масштабирование на все ОЭС.');
}

fs.writeFileSync(path.join(__dirname, 'anim.json'), JSON.stringify(anim, null, 1));
pres.writeFile({ fileName: process.env.OUT || path.join(__dirname, 'raw.pptx') }).then(f => console.log('written', f));
