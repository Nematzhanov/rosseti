"""raw.pptx -> итоговая презентация: переход «Трансформация» на каждом слайде, анимация появления
элементов (по очереди, после перехода, без кликов) и чистка пустых точек в диаграммах.

Запуск: python3 postprocess.py raw.pptx out.pptx
"""
import json
import re
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEP, DUR = 350, 500  # мс между появлениями и длительность растворения
MORPH = ('<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">'
         '<mc:Choice xmlns:p159="http://schemas.microsoft.com/office/powerpoint/2015/09/main" Requires="p159">'
         '<p:transition xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main" spd="slow" p14:dur="1250">'
         '<p159:morph option="byObject"/></p:transition></mc:Choice>'
         '<mc:Fallback><p:transition spd="slow"><p:fade/></p:transition></mc:Fallback></mc:AlternateContent>')


def shape_index(xml: str) -> dict:
    """name -> (id, тип элемента: sp / pic / graphicFrame)."""
    out = {}
    for m in re.finditer(r'<p:cNvPr id="(\d+)" name="([^"]*)"', xml):
        head = xml[:m.start()]
        kind = max(("sp", "pic", "graphicFrame"),
                   key=lambda k: max(head.rfind(f"<p:{k}>"), head.rfind(f"<p:{k} ")))
        out[m.group(2)] = (m.group(1), kind)
    return out


def timing(groups: list) -> str:
    ids = iter(range(4, 10 ** 6))
    pars, bld, t = [], {}, 0
    for grp in groups:
        effs = []
        tpar = next(ids)
        for j, (spid, kind) in enumerate(grp):
            eff, sid, aid = next(ids), next(ids), next(ids)
            grp_attr = ' grpId="0"' if kind != "pic" else ""
            node = "afterEffect" if j == 0 else "withEffect"
            effs.append(
                f'<p:par><p:cTn id="{eff}" presetID="10" presetClass="entr" presetSubtype="0" fill="hold"{grp_attr} '
                f'nodeType="{node}"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
                f'<p:set><p:cBhvr><p:cTn id="{sid}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst>'
                f'</p:cTn><p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl><p:attrNameLst><p:attrName>style.visibility'
                f'</p:attrName></p:attrNameLst></p:cBhvr><p:to><p:strVal val="visible"/></p:to></p:set>'
                f'<p:animEffect transition="in" filter="fade"><p:cBhvr><p:cTn id="{aid}" dur="{DUR}"/>'
                f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cBhvr></p:animEffect></p:childTnLst></p:cTn></p:par>')
            if kind == "sp":
                bld[spid] = f'<p:bldP spid="{spid}" grpId="0" animBg="1"/>'
            elif kind == "graphicFrame":
                bld[spid] = f'<p:bldGraphic spid="{spid}" grpId="0"><p:bldAsOne/></p:bldGraphic>'
        pars.append(f'<p:par><p:cTn id="{tpar}" fill="hold"><p:stCondLst><p:cond delay="{t}"/></p:stCondLst>'
                    f'<p:childTnLst>{"".join(effs)}</p:childTnLst></p:cTn></p:par>')
        t += STEP
    return ('<p:timing><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst>'
            '<p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst>'
            '<p:par><p:cTn id="3" fill="hold"><p:stCondLst><p:cond delay="indefinite"/>'
            '<p:cond evt="onBegin" delay="0"><p:tn val="2"/></p:cond></p:stCondLst>'
            f'<p:childTnLst>{"".join(pars)}</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn>'
            '<p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>'
            '<p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst>'
            '</p:seq></p:childTnLst></p:cTn></p:par></p:tnLst>'
            f'<p:bldLst>{"".join(bld.values())}</p:bldLst></p:timing>')


def main(src: str, dst: str, flags=()):
    anim = json.loads((HERE / "anim.json").read_text())
    zin = zipfile.ZipFile(src)
    files = {n: zin.read(n) for n in zin.namelist()}
    report = []
    for name in list(files):
        m = re.fullmatch(r"ppt/slides/slide(\d+)\.xml", name)
        if m:
            n = m.group(1)
            xml = files[name].decode("utf-8")
            assert "<p:transition" not in xml and "<p:timing" not in xml, name
            # pptxgenjs закрывает внутреннюю тень тегом outerShdw — исправляем
            xml, k = re.subn(r"(<a:innerShdw\b[^>]*>(?:(?!</a:outerShdw>).)*?)</a:outerShdw>", r"\1</a:innerShdw>", xml)
            if k:
                report.append(f"слайд {n}: исправлено внутренних теней {k}")
            idx = shape_index(xml)
            groups = []
            for item in anim.get(n, []):
                names = item if isinstance(item, list) else [item]
                grp = [idx[x] for x in names if x in idx]
                missing = [x for x in names if x not in idx]
                if missing:
                    raise SystemExit(f"slide {n}: нет объектов {missing}")
                groups.append(grp)
            extra = ("" if "nomorph" in flags else MORPH) + (timing(groups) if groups and "notiming" not in flags else "")
            anchor = "</p:clrMapOvr>"
            assert anchor in xml, f"{name}: нет {anchor}"
            if extra:
                xml = xml.replace(anchor, anchor + extra, 1)
            files[name] = xml.encode("utf-8")
            report.append(f"слайд {n}: групп анимации {len(groups)}")
        if re.fullmatch(r"ppt/charts/chart\d+\.xml", name) and "nochartfix" not in flags:
            xml = files[name].decode("utf-8")
            if "<c:scatterChart>" in xml:  # подписи осей — у края графика, а не посередине (ось потребления проходит через 0 °C)
                xml, kk = re.subn(r'<c:tickLblPos val="nextTo"/>', '<c:tickLblPos val="low"/>', xml)
                report.append(f"{name}: подписи осей перенесены к краю ({kk})")
            new, k = re.subn(r'<c:pt idx="\d+"><c:v></c:v></c:pt>', "", xml)
            files[name] = new.encode("utf-8")
            if k:
                report.append(f"{name}: убрано пустых точек {k}")
    order = ["[Content_Types].xml"] + sorted(n for n in files if n != "[Content_Types].xml")
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for n in order:
            z.writestr(n, files[n])
    print("\n".join(sorted(report, key=lambda s: (len(s), s))))
    print("готово:", dst)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
