"""Статья в оформлении образца: берём стили, поля, колонтитулы и форматирование абзацев из docx автора
и подставляем новый текст, рисунки и таблицы.

Запуск: .venv/bin/python article/build_article.py
"""
import json
import re
import struct
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
SRC = Path("/Users/mukhammadzahidnematzhanov/Documents/НематжановМухаммадзохид_ статья1.docx")
OUT = HERE / "Нематжанов_статья_прогноз_электропотребления.docx"
D = json.loads((HERE.parent / "deck" / "data.json").read_text())
Y, S, ST, WK, BF = D["year"], D["seasons"], D["stats"], D["week"], D["best_ft"]

z = zipfile.ZipFile(SRC)
doc = z.read("word/document.xml").decode("utf-8")
P = re.findall(r"<w:p[ >].*?</w:p>", doc, flags=re.S)


def ppr(i):
    return re.search(r"<w:pPr>.*?</w:pPr>", P[i], re.S).group(0)


def rpr(i, k=0, need=None):
    runs = [m for m in re.findall(r"<w:r[ >].*?</w:r>", P[i], re.S) if "<w:t" in m]
    if need:
        runs = [r for r in runs if need(r)]
    return re.search(r"<w:rPr>.*?</w:rPr>", runs[k], re.S).group(0)


def en(r):
    return r.replace('w:val="ru-RU"', 'w:val="en-US"')


# Шаблоны абзацев и шрифтов, снятые с образца
T = {
    "udk": (ppr(0), rpr(0)), "author": (ppr(1), rpr(1)), "title": (ppr(3), rpr(3)), "blank_title": (ppr(5), None),
    "abs": (ppr(6), rpr(6, 0, lambda r: "<w:b/>" in r), rpr(6, 0, lambda r: "<w:b/>" not in r)),
    "blank": (ppr(7), None), "h_intro": (ppr(13), rpr(13)), "body": (ppr(14), rpr(14)), "h": (ppr(18), rpr(18)),
    "h_refs": (ppr(39), rpr(39)), "ref": (ppr(40), rpr(40)), "h_refs_en": (ppr(54), rpr(54)), "ref_en": (ppr(55), rpr(55)),
    "h_info": (ppr(68), rpr(68)), "info": (ppr(69), rpr(69)),
}
SUP = rpr(29, 0, lambda r: "superscript" in r)
for _k in ("h_intro", "h"):
    T[_k] = (T[_k][0].replace("<w:pPr>", "<w:pPr><w:keepNext/>", 1),) + T[_k][1:]
BODY_RPR = T["body"][1]
SMALL = re.sub(r"<w:sz w:val=\"\d+\"/><w:szCs w:val=\"\d+\"/>", '<w:sz w:val="24"/><w:szCs w:val="24"/>', BODY_RPR)


def run(text, rp):
    return f'<w:r>{rp}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def runs_with_cites(text, rp):
    """Разметка {1; 4} — ссылка на литературу верхним индексом, как в образце."""
    out = []
    for part in re.split(r"(\{[\d; ]+\})", text):
        if not part:
            continue
        out.append(run(f"[{part[1:-1]}]", SUP) if part.startswith("{") else run(part, rp))
    return "".join(out)


def para(kind, text="", lang_en=False):
    pp, rp = T[kind][0], T[kind][1]
    if rp and lang_en:
        rp, pp = en(rp), en(pp)
    return f"<w:p>{pp}{runs_with_cites(text, rp) if text else ''}</w:p>"


def labeled(label, text, lang_en=False):
    """Аннотация / Ключевые слова: жирная метка + обычный текст (12 pt, как в образце)."""
    pp, rb, rn = T["abs"]
    if lang_en:
        pp, rb, rn = en(pp), en(rb), en(rn)
    return f"<w:p>{pp}{run(label, rb)}{run(' ' + text, rn)}</w:p>"


def center_par(text, rp=BODY_RPR, after=0, before=0):
    pp = (f'<w:pPr><w:spacing w:before="{before}" w:after="{after}" w:line="360" w:lineRule="auto"/>'
          f'<w:jc w:val="center"/></w:pPr>')
    return f"<w:p>{pp}{run(text, rp)}</w:p>"


def caption_table(text):
    pp = '<w:pPr><w:keepNext/><w:spacing w:before="120" w:after="0" w:line="360" w:lineRule="auto"/><w:jc w:val="left"/></w:pPr>'
    return f"<w:p>{pp}{run(text, BODY_RPR)}</w:p>"


# ---------- рисунки ----------
media, rels = [], []


def png_size(p: Path):
    with open(p, "rb") as f:
        head = f.read(24)
    return struct.unpack(">II", head[16:24])


def figure(path: Path, caption, width_cm=15.0):
    n = len(media) + 1
    rid = f"rIdImg{n}"
    media.append((f"word/media/article_fig{n}.png", path.read_bytes()))
    rels.append(f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/article_fig{n}.png"/>')
    w, h = png_size(path)
    cx = int(width_cm * 360000)
    cy = int(cx * h / w)
    drawing = (
        f'<w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
        f'<wp:effectExtent l="0" t="0" r="0" b="0"/><wp:docPr id="{100 + n}" name="Рисунок {n}" descr="{escape(caption)}"/>'
        '<wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/></wp:cNvGraphicFramePr>'
        '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        f'<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr><pic:cNvPr id="{100 + n}" name="article_fig{n}.png"/><pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
        '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing>')
    pic = ('<w:p><w:pPr><w:keepNext/><w:spacing w:before="120" w:after="0" w:line="240" w:lineRule="auto"/><w:jc w:val="center"/></w:pPr>'
           f'<w:r><w:rPr><w:noProof/></w:rPr>{drawing}</w:r></w:p>')
    return pic + center_par(f"Рисунок {n} – {caption}", after=120)


# ---------- таблицы ----------
def table(widths, rows, header_rows=1):
    tw = sum(widths)
    border = ''.join(f'<w:{s} w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
                     for s in ["top", "left", "bottom", "right", "insideH", "insideV"])
    x = (f'<w:tbl><w:tblPr><w:tblW w:w="{tw}" w:type="dxa"/><w:jc w:val="center"/><w:tblBorders>{border}</w:tblBorders>'
         '<w:tblLayout w:type="fixed"/><w:tblCellMar><w:left w:w="85" w:type="dxa"/><w:right w:w="85" w:type="dxa"/></w:tblCellMar>'
         '</w:tblPr><w:tblGrid>' + "".join(f'<w:gridCol w:w="{w}"/>' for w in widths) + "</w:tblGrid>")
    for ri, row in enumerate(rows):
        head = ri < header_rows
        x += "<w:tr>" + ("<w:trPr><w:tblHeader/></w:trPr>" if head else "")
        for ci, (cell, w) in enumerate(zip(row, widths)):
            rp = SMALL.replace("<w:sz ", "<w:b/><w:bCs/><w:sz ") if head else SMALL
            jc = "left" if ci == 0 and not head else "center"
            x += (f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/><w:vAlign w:val="center"/></w:tcPr>'
                  f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:jc w:val="{jc}"/></w:pPr>{run(cell, rp)}</w:p></w:tc>')
        x += "</w:tr>"
    return x + "</w:tbl>"


def f2(v):
    return f"{v:.2f}".replace(".", ",")


def f0(v):
    return f"{v:,.0f}".replace(",", " ")


def mape(k):
    return Y[k]["MAPE_%"]


lw, lf, lo = mape("lgb_noweather"), mape("lgb_fcst"), mape("lgb_oracle")
cu, cc = mape("chronos_zs_uni"), mape("chronos_zs_cov_fcst")
best, full, lora, ens, naive = mape(BF), mape("chronos_ft_full_cov_fcst"), mape("chronos_ft_lora_cov_fcst"), mape("ens_lgb_chronos"), mape("naive_week")
ratio = f"{naive / best:.1f}".replace(".", ",")
w_lgb = round((1 - lf / lw) * 100)
w_chr = round((1 - cc / cu) * 100)
t_ft = {k: round(v / 60) for k, v in D["timing"].items()}
gw = lambda v: f"{v / 1000:.1f}".replace(".", ",")
corr = f"{ST['corr']:.2f}".replace(".", ",").replace("-", "−")
wk_best, wk_lgb = WK["mape"][BF], WK["mape"]["lgb_fcst"]
wk_t = f"{WK['temp_mean']:.1f}".replace(".", ",").replace("-", "−")
best_name = "дообученная методом LoRA модель Chronos-2" if "lora" in BF else "модель Chronos-2 после полного дообучения"

B = []  # тело документа (короткая версия, 4–5 страниц)
wk_best = WK["mape"][BF]
cold_pct = round((ST["cold_mean"] / ST["warm_mean"] - 1) * 100)
lora_min = t_ft.get("chronos_ft_lora_train", 47) if "lora" in BF else t_ft.get("chronos_ft_full_train", 22)
method = "методом низкоранговой адаптации LoRA" if "lora" in BF else "полным обновлением весов"
B.append(para("udk", "УДК 621.311:004.852"))
B.append(para("author", "Нематжанов М. М."))
B.append(para("author", "Nematzhanov M. M.", lang_en=True))
B.append(para("title", "ПРОГНОЗИРОВАНИЕ ЭЛЕКТРОПОТРЕБЛЕНИЯ ОЭС СЕВЕРО-ЗАПАДА МЕТОДАМИ МАШИННОГО ОБУЧЕНИЯ С УЧЁТОМ ПОГОДНЫХ ФАКТОРОВ"))
B.append(para("title", "FORECASTING ELECTRICITY CONSUMPTION OF THE NORTH-WEST POWER SYSTEM USING MACHINE LEARNING WITH WEATHER FACTORS", lang_en=True))
B.append(para("blank_title"))
B.append(labeled("Аннотация.",
    "Рассматривается прогнозирование почасового электропотребления ОЭС Северо-Запада на сутки вперёд с учётом "
    "погоды. По открытым данным АО «СО ЕЭС» за 2021–2026 гг. и прогнозам погоды для девяти городов региона "
    "сравниваются градиентный бустинг LightGBM и предобученная модель временных рядов Chronos-2. При проверке на "
    "целом годе с прогнозом погоды, выпущенным накануне, наименьшую ошибку показала модель Chronos-2, дообученная "
    f"{method}: {f2(best)} %, что в {ratio} раза меньше, чем у наивного прогноза. Учёт погоды снижает ошибку "
    f"LightGBM на {w_lgb} %."))
B.append(para("blank"))
B.append(labeled("Abstract.",
    "The paper addresses day-ahead forecasting of hourly electricity consumption of the North-West power system of "
    "Russia taking weather into account. Using open data of the System Operator for 2021–2026 and weather forecasts "
    "for nine cities of the region, the LightGBM gradient boosting model and the pretrained time series model "
    "Chronos-2 are compared. In a full-year test with weather forecasts issued the day before, Chronos-2 fine-tuned "
    f"with {'LoRA' if 'lora' in BF else 'full fine-tuning'} achieved the lowest error of {best:.2f} %, which is "
    f"{naive / best:.1f} times lower than that of the naive forecast. Weather data reduce the LightGBM error by {w_lgb} %.",
    lang_en=True))
B.append(para("blank"))
B.append(labeled("Ключевые слова:", "прогнозирование электропотребления, машинное обучение, погодные факторы, "
                 "ОЭС Северо-Запада, LightGBM, Chronos-2."))
B.append(para("blank"))
B.append(labeled("Keywords:", "electricity consumption forecasting, machine learning, weather factors, North-West "
                 "power system, LightGBM, Chronos-2.", lang_en=True))

B.append(para("h_intro", "Введение"))
B.append(para("body",
    "Прогноз электропотребления на сутки вперёд лежит в основе планирования режимов энергосистемы и торговли на "
    "рынке на сутки вперёд{1}. Для ОЭС Северо-Запада задача осложняется климатом: значительная часть нагрузки "
    "связана с отоплением и освещением, поэтому потребление сильно зависит от температуры. Наряду с градиентным "
    "бустингом{1; 2} появились предобученные модели временных рядов, среди которых выделяется Chronos-2, способная "
    "учитывать внешние факторы{3}; дообучение таких моделей на данных энергосистемы заметно повышает точность{4}. "
    "Цель работы — сравнить эти подходы на данных ОЭС Северо-Запада и оценить вклад погоды."))

B.append(para("h", "Данные"))
B.append(para("body",
    f"Использованы почасовые данные о потреблении ОЭС Северо-Запада с сайта АО «СО ЕЭС» за 01.01.2021–{ST['test_end']} "
    f"({f0(ST['hours_total'])} значений){{5}}, погода для девяти городов региона из сервиса Open-Meteo{{6}}, "
    "усреднённая с весами по численности населения, и производственный календарь. Для обучения использован "
    "реанализ ERA5{7}, для проверки — прогноз погоды, выпущенный за сутки. Коэффициент корреляции потребления и "
    f"температуры равен {corr} (рисунок 1): в морозы ниже −10 °C потребление в среднем на {cold_pct} % выше, чем в "
    "дни теплее +15 °C."))
B.append(figure(HERE / "fig1_temp.png", "Зависимость среднесуточного потребления ОЭС Северо-Запада от температуры воздуха, 2021–2026 гг.", width_cm=11.5))

B.append(para("h", "Модели и методика проверки"))
B.append(para("body",
    "Прогноз на сутки D выпускается в 09:00 предыдущих суток; модель рассчитывает 24 часовых значения, точность "
    "оценивается средней абсолютной процентной ошибкой (MAPE). LightGBM{2} использует потребление за 2–14 суток до "
    "целевого часа, прогноз погоды, градусо-часы отопления и тип дня и переобучается ежемесячно. Chronos-2 — "
    "предобученный трансформер со 120 млн параметров{3}, получающий погоду и календарь как внешние факторы; он "
    f"дообучен {method}{{8}} на данных 2021 – сентября 2025 г. за {lora_min} мин на ноутбуке Apple M3. Тестовый "
    f"период — {ST['test_start']}–{ST['test_end']} ({f0(ST['test_days'] * 24)} ч); при проверке использовался только "
    "прогноз погоды, известный накануне."))

B.append(para("h", "Результаты"))
B.append(para("body",
    f"Лучшую точность показала дообученная Chronos-2 (таблица 1): MAPE {f2(best)} %, средняя ошибка "
    f"{f0(Y[BF]['MAE_MW'])} МВт, что в {ratio} раза точнее наивного прогноза. Прогноз погоды снизил ошибку LightGBM "
    f"с {f2(lw)} до {f2(lf)} %, то есть на {w_lgb} %; с фактической погодой ошибка составила бы {f2(lo)} %, поэтому "
    "точности прогноза погоды достаточно."))
rows = [["Модель", "MAPE, %", "MAE, МВт"]]
for k, name in [("naive_week", "Наивный прогноз (неделю назад)"), ("lgb_noweather", "LightGBM без погоды"),
                ("lgb_fcst", "LightGBM + прогноз погоды"), ("chronos_zs_cov_fcst", "Chronos-2 без дообучения"),
                (BF, "Chronos-2 после дообучения")]:
    rows.append([name, f2(Y[k]["MAPE_%"]), f0(Y[k]["MAE_MW"])])
B.append(caption_table(f"Таблица 1 – Точность прогноза на сутки вперёд, {ST['test_start']}–{ST['test_end']}"))
B.append(table([5426, 1800, 1800], rows))
B.append(para("body",
    f"Преимущество Chronos-2 особенно заметно в морозы: в самую холодную неделю ({WK['start'][:5]}–{WK['end']}, "
    f"{wk_t} °C) её ошибка составила {f2(wk_best)} %, а LightGBM, не способный экстраполировать за пределы "
    f"обучающих данных, ошибался на {f2(wk_lgb)} % (рисунок 2)."))
B.append(figure(HERE / "fig2_cold_week.png", f"Фактическое и прогнозное потребление ОЭС Северо-Запада, {WK['start'][:5]}–{WK['end']}", width_cm=11.5))

B.append(para("h", "Заключение"))
B.append(para("body",
    f"Дообученная модель Chronos-2 обеспечила наилучший прогноз потребления ОЭС Северо-Запада на сутки вперёд "
    f"(MAPE {f2(best)} %), учёт погоды снизил ошибку на {w_lgb} %, а расчёты выполняются на персональном компьютере. "
    "Дальнейшее развитие — распространение подхода на другие ОЭС и федеральные округа."))

REFS = [
    ("Hong T., Fan S. Probabilistic electric load forecasting: A tutorial review // International Journal of Forecasting. 2016. Vol. 32, № 3. P. 914–938.",
     "Hong T., Fan S. Probabilistic electric load forecasting: A tutorial review // International Journal of Forecasting. 2016. Vol. 32, no. 3. P. 914–938."),
    ("Ke G., Meng Q., Finley T. [et al.] LightGBM: A Highly Efficient Gradient Boosting Decision Tree // Advances in Neural Information Processing Systems 30 (NIPS 2017). 2017. P. 3146–3154.",
     "Ke G., Meng Q., Finley T. [et al.] LightGBM: A Highly Efficient Gradient Boosting Decision Tree // Advances in Neural Information Processing Systems 30 (NIPS 2017). 2017. P. 3146–3154."),
    ("Chronos-2: From Univariate to Universal Forecasting : препринт. 2025. URL: https://arxiv.org/abs/2510.15821 (дата обращения: 28.09.2026).",
     "Chronos-2: From Univariate to Universal Forecasting : preprint. 2025. URL: https://arxiv.org/abs/2510.15821 (accessed: 28.09.2026)."),
    ("Assessing Covariate-Informed Grid Load Forecasting with a Time-Series Foundation Model : препринт. 2026. URL: https://arxiv.org/abs/2609.06656 (дата обращения: 28.09.2026).",
     "Assessing Covariate-Informed Grid Load Forecasting with a Time-Series Foundation Model : preprint. 2026. URL: https://arxiv.org/abs/2609.06656 (accessed: 28.09.2026)."),
    ("АО «СО ЕЭС». Генерация (час). URL: https://www.so-ups.ru/functioning/ees/ees-indicators/ees-gen-consump-hour/ (дата обращения: 28.09.2026).",
     "SO UPS. Generatsiya (chas). URL: https://www.so-ups.ru/functioning/ees/ees-indicators/ees-gen-consump-hour/ (accessed: 28.09.2026)."),
    ("Open-Meteo. Free Weather API. URL: https://open-meteo.com/ (дата обращения: 30.09.2026).",
     "Open-Meteo. Free Weather API. URL: https://open-meteo.com/ (accessed: 30.09.2026)."),
    ("Hersbach H., Bell B., Berrisford P. [et al.] The ERA5 global reanalysis // Quarterly Journal of the Royal Meteorological Society. 2020. Vol. 146, № 730. P. 1999–2049.",
     "Hersbach H., Bell B., Berrisford P. [et al.] The ERA5 global reanalysis // Quarterly Journal of the Royal Meteorological Society. 2020. Vol. 146, no. 730. P. 1999–2049."),
    ("Hu E. J., Shen Y., Wallis P. [et al.] LoRA: Low-Rank Adaptation of Large Language Models // International Conference on Learning Representations (ICLR 2022). 2022. URL: https://arxiv.org/abs/2106.09685 (дата обращения: 28.09.2026).",
     "Hu E. J., Shen Y., Wallis P. [et al.] LoRA: Low-Rank Adaptation of Large Language Models // International Conference on Learning Representations (ICLR 2022). 2022. URL: https://arxiv.org/abs/2106.09685 (accessed: 28.09.2026)."),
]
B.append(para("h_refs", "Список литературы"))
for i, (ru, _) in enumerate(REFS, 1):
    B.append(para("ref", f"{i}. {ru}"))
B.append(para("h_refs_en", "References", lang_en=True))
for i, (_, enr) in enumerate(REFS, 1):
    B.append(para("ref_en", f"{i}. {enr}", lang_en=True))

B.append(para("h_info", "Информация об авторах"))
B.append(para("info", "Нематжанов Мухаммадзохид Мухаммаджонович – студент, Новгородский государственный университет "
              "имени Ярослава Мудрого, Политехнический институт (Великий Новгород, Россия), e-mail: nematzhanov.m@gmail.com"))
B.append(para("h_info", "Information about the authors", lang_en=True))
B.append(para("info", "Nematzhanov Mukhammadzokhid Mukhammadjonovich – student, Yaroslav-the-Wise Novgorod State "
              "University, Polytechnic Institute (Veliky Novgorod, Russia), e-mail: nematzhanov.m@gmail.com", lang_en=True))

# Проверка ссылок: каждая позиция списка процитирована, номера идут по порядку первого упоминания
body = "".join(B)
cited = []
for grp in re.findall(r"\[([\d; ]+)\]</w:t>", body):
    for n in grp.split(";"):
        n = int(n)
        if n not in cited:
            cited.append(n)
assert sorted(cited) == list(range(1, len(REFS) + 1)), cited
assert cited == sorted(cited), f"порядок первого упоминания: {cited}"

root_open = doc[:doc.index("<w:body>") + len("<w:body>")]
assert 'xmlns:wp=' in root_open and 'xmlns:r=' in root_open, "в корне нет пространств имён wp/r"
sect = re.findall(r"<w:sectPr.*?</w:sectPr>", doc, flags=re.S)[-1]
new_doc = root_open + body + sect + "</w:body></w:document>"

rels_xml = z.read("word/_rels/document.xml.rels").decode().replace("</Relationships>", "".join(rels) + "</Relationships>")
ct = z.read("[Content_Types].xml").decode()
if 'Extension="png"' not in ct:
    ct = ct.replace("<Default Extension=\"xml\"", '<Default Extension="png" ContentType="image/png"/><Default Extension="xml"', 1)
core = z.read("docProps/core.xml").decode()
core = re.sub(r"<dc:title>.*?</dc:title>", "<dc:title>Прогнозирование электропотребления ОЭС Северо-Запада</dc:title>", core)

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zo:
    for item in z.infolist():
        name = item.filename
        if name == "word/document.xml":
            zo.writestr(name, new_doc)
        elif name == "word/_rels/document.xml.rels":
            zo.writestr(name, rels_xml)
        elif name == "[Content_Types].xml":
            zo.writestr(name, ct)
        elif name == "docProps/core.xml":
            zo.writestr(name, core)
        else:
            zo.writestr(item, z.read(name))
    for name, data in media:
        zo.writestr(name, data)
words = len(re.findall(r"\w+", " ".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", body))))
print(f"{OUT.name}: абзацев {body.count('<w:p>')}, таблиц {body.count('<w:tbl>')}, рисунков {len(media)}, слов {words}")
