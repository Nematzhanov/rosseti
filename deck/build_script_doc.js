// Сценарий выступления -> Word. Тексты берутся из script.json (те же, что в заметках докладчика презентации).
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  AlignmentType, HeadingLevel, Footer, PageNumber, TabStopType,
} = require('docx');

const S = JSON.parse(fs.readFileSync(path.join(__dirname, 'script.json'), 'utf8'));
const titles = ['Обложка', 'История: чайники после матча', 'Раздел 01 · Постановка задачи', 'Проблема', 'Актуальность',
  'Цель и задачи', 'Что прогнозируем', 'Раздел 02 · Данные и модели', 'Данные', 'Потребление и температура',
  'Три подхода к прогнозу', 'Честная проверка', 'Раздел 03 · Результаты', 'Точность прогноза за год', 'Самая холодная неделя',
  'Точность по сезонам', 'Что даёт прогноз погоды', 'Прогноз на завтра одной кнопкой', 'Выводы', 'Спасибо · QR-код сайта'];
const N = Object.keys(S).length;
if (titles.length !== N) throw new Error(`слайдов ${N}, названий ${titles.length}`);

const WPM = 130; // слов в минуту при спокойной речи
const words = i => S[String(i)].split(/\s+/).filter(Boolean).length;
const sec = i => Math.max(5, Math.round(words(i) / WPM * 60 / 5) * 5);
const total = Array.from({ length: N }, (_, i) => sec(i + 1)).reduce((a, b) => a + b, 0);
const mmss = s => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

const FONT = 'Times New Roman', BLUE = '005A9B', GRAY = '5B6773';
const run = (text, o = {}) => new TextRun({ text, font: FONT, size: 28, ...o });
const border = { style: BorderStyle.SINGLE, size: 4, color: 'BFC8D2' };
const borders = { top: border, bottom: border, left: border, right: border };

function cell(text, w, o = {}) {
  return new TableCell({
    width: { size: w, type: WidthType.DXA }, borders, margins: { top: 60, bottom: 60, left: 100, right: 100 },
    shading: o.fill ? { fill: o.fill, type: ShadingType.CLEAR, color: 'auto' } : undefined,
    children: [new Paragraph({ alignment: o.align || AlignmentType.LEFT, children: [run(text, { size: 24, bold: o.bold, color: o.color })] })],
  });
}

const children = [];
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [run('СЦЕНАРИЙ ВЫСТУПЛЕНИЯ', { bold: true, size: 36, color: BLUE })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [run('Прогнозирование электропотребления ОЭС Северо-Запада методами машинного обучения с учётом погодных факторов', { bold: true, size: 30 })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 360 }, children: [run('Нематжанов Мухаммадзохид Мухаммаджонович · НовГУ имени Ярослава Мудрого, Политехнический институт', { size: 24, color: GRAY })] }));

children.push(new Paragraph({ spacing: { after: 120 }, children: [
  run('Объём: ', { bold: true, size: 26 }), run(`${N} слайдов, ${words ? Object.keys(S).reduce((a, k) => a + words(+k), 0) : 0} слов, около ${mmss(total)} при спокойном темпе (${WPM} слов в минуту).`, { size: 26 })] }));
children.push(new Paragraph({ spacing: { after: 120 }, children: [
  run('Сайт проекта (QR-код на последнем слайде): ', { bold: true, size: 26 }), run('https://nematzhanov.github.io/rosseti/', { size: 26, color: BLUE })] }));
children.push(new Paragraph({ spacing: { after: 240 }, children: [
  run('Как пользоваться: ', { bold: true, size: 26 }), run('текст каждого слайда произносится целиком; в скобках после заголовка — ориентировочное время. Тот же текст встроен в заметки докладчика презентации.', { size: 26 })] }));

// таблица времени
const W = [900, 5900, 1500];
const rows = [new TableRow({ tableHeader: true, children: [
  cell('Слайд', W[0], { fill: BLUE, bold: true, color: 'FFFFFF', align: AlignmentType.CENTER }),
  cell('Название', W[1], { fill: BLUE, bold: true, color: 'FFFFFF' }),
  cell('Время', W[2], { fill: BLUE, bold: true, color: 'FFFFFF', align: AlignmentType.CENTER })] })];
for (let i = 1; i <= N; i++) rows.push(new TableRow({ children: [
  cell(String(i), W[0], { align: AlignmentType.CENTER }), cell(titles[i - 1], W[1]), cell(mmss(sec(i)), W[2], { align: AlignmentType.CENTER })] }));
rows.push(new TableRow({ children: [
  cell('', W[0], { fill: 'EEF4FA' }), cell('Итого', W[1], { fill: 'EEF4FA', bold: true }), cell(mmss(total), W[2], { fill: 'EEF4FA', bold: true, align: AlignmentType.CENTER })] }));
children.push(new Table({ width: { size: W.reduce((a, b) => a + b), type: WidthType.DXA }, columnWidths: W, rows }));

// текст по слайдам
for (let i = 1; i <= N; i++) {
  children.push(new Paragraph({
    heading: HeadingLevel.HEADING_2, keepNext: true, spacing: { before: i === 1 ? 480 : 300, after: 100 },
    children: [run(`Слайд ${i}. ${titles[i - 1]}`, { bold: true, size: 30, color: BLUE }), run(`   (${mmss(sec(i))})`, { size: 24, color: GRAY })],
  }));
  children.push(new Paragraph({
    alignment: AlignmentType.JUSTIFIED, spacing: { line: 360, after: 120 }, indent: { firstLine: 709 },
    children: [run(S[String(i)])],
  }));
}

const doc = new Document({
  creator: 'Нематжанов М. М.', title: 'Сценарий выступления',
  styles: { default: { document: { run: { font: FONT, size: 28 } } },
    paragraphStyles: [{ id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: FONT, size: 30, bold: true, color: BLUE }, paragraph: { spacing: { before: 300, after: 100 }, outlineLevel: 1 } }] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, right: 1134, bottom: 1134, left: 1701 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 22, color: GRAY })] })] }) },
    children,
  }],
});
Packer.toBuffer(doc).then(b => { fs.writeFileSync(path.join(__dirname, 'Сценарий выступления.docx'), b); console.log('ok', N, 'слайдов,', mmss(total)); });
