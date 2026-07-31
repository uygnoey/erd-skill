#!/usr/bin/env python3
"""ERD 문서 생성 — 어떤 DB에도 쓸 수 있게 내용은 erd.spec.json 의 doc 절에서 읽는다.

  doc.title        표지 제목            doc.subtitle   표지 부제
  doc.meta         [[구분, 내용], …]     표지 정보표
  doc.purpose      1.1 목적             doc.scope      1.2 범위
  doc.sources      [[근거, 내용], …]     1.3 산출 근거
  doc.mapping      [[…], …]             6장 대조표 (없으면 장 생략)
  doc.open_items   [[…], …]             7장 미반영 항목 (없으면 장 생략)
  doc.mapping_note / doc.open_note      각 장 끝 보충 문단
"""
import json
import os
from pathlib import Path

from PIL import Image
from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

import erd
from erd import AREAS, AREA_NAME, AREA_SCHEMA, LAYERS, ROLE, SCHEMA, layer

from config import DOCNAME, OUT, PROJ
from erd import SPEC

DOC = SPEC.get('doc', {})
TITLE = DOC.get('title', DOCNAME)

# 문서 폰트는 이름으로 지정한다 — 그림과 달리 여는 PC에 그 폰트가 있어야 한다.
# Pretendard 가 없는 PC에서는 Word 가 알아서 대체하므로 레이아웃만 조금 달라진다.
FONT = os.environ.get('ERD_DOC_FONT', 'Pretendard')
MONO = os.environ.get('ERD_DOC_MONO', 'D2Coding')   # 없으면 Word 가 대체 — 코드 식별자용


# ── 서식 헬퍼 ────────────────────────────────────────────────────────────────
def set_font(run, name=FONT, size=10, bold=False, color=None):
    run.font.name = name
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = RGBColor.from_string(color)
    rPr = run._element.get_or_add_rPr()
    rf = rPr.find(qn('w:rFonts'))
    if rf is None:
        rf = OxmlElement('w:rFonts')
        rPr.append(rf)
    rf.set(qn('w:eastAsia'), name)
    rf.set(qn('w:ascii'), name)
    rf.set(qn('w:hAnsi'), name)


def para(doc, text='', size=10, bold=False, name=FONT, align=None, space_after=6,
         color=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.3
    if align:
        p.alignment = align
    if text:
        set_font(p.add_run(text), name, size, bold, color)
    return p


def heading(doc, text, level=1):
    sizes = {1: 15, 2: 12.5, 3: 11}
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(16 if level == 1 else 10)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    set_font(p.add_run(text), FONT, sizes[level], True,
             '1F3864' if level == 1 else ('2E5C8A' if level == 2 else '404040'))
    return p


def shade(cell, color):
    tcPr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement('w:shd')
    sh.set(qn('w:val'), 'clear')
    sh.set(qn('w:fill'), color)
    tcPr.append(sh)


def table(doc, headers, widths=None, style='Table Grid', font_size=8.5):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = style
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    hdr = t.rows[0]
    for i, h in enumerate(headers):
        cell = hdr.cells[i]
        cell.text = ''
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        set_font(p.add_run(h), FONT, font_size, True)
        shade(cell, 'D9E2F3')
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    _mark_header_repeat(hdr)
    return t


def _mark_header_repeat(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement('w:tblHeader')
    el.set(qn('w:val'), 'true')
    trPr.append(el)


def row(t, values, widths=None, font_size=8.5, mono_cols=(), bold_cols=(),
        colors=None, aligns=None):
    cells = t.add_row().cells
    for i, v in enumerate(values):
        cell = cells[i]
        cell.text = ''
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.1
        if aligns and aligns[i]:
            p.alignment = aligns[i]
        set_font(p.add_run(str(v)), MONO if i in mono_cols else FONT, font_size,
                 i in bold_cols, (colors or {}).get(i))
        if widths:
            cell.width = Cm(widths[i])
    return cells


def picture(doc, path, width_cm, caption, max_h_cm=16.2):
    """폭·높이 둘 다에 맞춘다. 폭만 지정하면 세로가 긴 그림이 페이지를 넘어 잘린다.

    가로 A4(29.7×21cm) · 여백 1.5cm → 가용 26.7×18cm. 제목·캡션 몫을 빼고 16.2cm 를 쓴다.
    """
    iw, ih = Image.open(path).size
    w_cm = min(width_cm, max_h_cm * iw / ih)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(4)
    p.add_run().add_picture(str(path), width=Cm(w_cm))
    c = doc.add_paragraph()
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    c.paragraph_format.space_after = Pt(14)
    set_font(c.add_run(caption), FONT, 9, False, '595959')


def landscape(doc):
    s = doc.add_section(WD_SECTION.NEW_PAGE)
    s.orientation = WD_ORIENT.LANDSCAPE
    s.page_width, s.page_height = Cm(29.7), Cm(21.0)
    s.left_margin = s.right_margin = Cm(1.5)
    s.top_margin = s.bottom_margin = Cm(1.5)
    return s


def portrait(doc):
    s = doc.add_section(WD_SECTION.NEW_PAGE)
    s.orientation = WD_ORIENT.PORTRAIT
    s.page_width, s.page_height = Cm(21.0), Cm(29.7)
    s.left_margin = s.right_margin = Cm(2.0)
    s.top_margin = s.bottom_margin = Cm(2.0)
    return s


# ── 6장 대조표 — spec 의 doc.mapping 이 있으면 그것을 쓴다 ────────────────────
# 6장(설계안 대조) · 7장(미반영 항목) 데이터는 spec 의 doc.mapping / doc.open_items
# 에서 온다. 없으면 그 장을 통째로 생략한다.


MAPPING_TABLE = [list(r) for r in DOC.get('mapping', [])]
OPEN_ITEMS = [list(r) for r in DOC.get('open_items', [])]


def build():
    doc = Document()
    s = doc.sections[0]
    s.page_width, s.page_height = Cm(21.0), Cm(29.7)
    s.left_margin = s.right_margin = Cm(2.0)
    s.top_margin = s.bottom_margin = Cm(2.0)
    st = doc.styles['Normal']
    st.font.name = FONT
    st.font.size = Pt(10)
    st.element.rPr.rFonts.set(qn('w:eastAsia'), FONT)

    # ── 표지 ──
    p = para(doc, DOC.get('title', DOCNAME), size=20, bold=True,
             align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    p.paragraph_format.space_before = Pt(40)
    para(doc, DOC.get('subtitle', ''),
         size=11, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=26, color='595959')

    t = table(doc, ['구분', '내용', '구분', '내용'], [2.6, 5.6, 2.4, 5.4], font_size=9.5)
    meta = [list(r) + [''] * (4 - len(r)) for r in DOC.get('meta', [
        ['문서명', DOC.get('title', DOCNAME), '테이블', str(len(SCHEMA))],
        ['컬럼', str(sum(len(t['columns']) for t in SCHEMA.values())),
         '외래키', str(sum(len(t['fks']) for t in SCHEMA.values()))],
    ])]
    for r in meta:
        cells = row(t, r, [2.6, 5.6, 2.4, 5.4], font_size=9.5, bold_cols=(0, 2))
        shade(cells[0], 'F2F2F2')
        shade(cells[2], 'F2F2F2')
    if True:  # 마지막 행 병합 (요청 근거)
        last = t.rows[-1]
        last.cells[1].merge(last.cells[3])

    doc.add_page_break()

    # ── 1. 개요 ──
    heading(doc, '1. 개요')
    heading(doc, '1.1 목적', 2)
    para(doc, DOC.get('purpose',
                      '대상 DB 의 테이블 구조와 관계를 ERD 로 제시한다. '
                      '실제 스키마를 읽어 생성하므로 그림과 DB 가 어긋나지 않는다.'))
    heading(doc, '1.2 범위', 2)
    for line in DOC.get('scope', [
            f'포함: 테이블 {len(SCHEMA)}개의 구조·컬럼·관계, 스키마 및 레이어 구분.',
            '제외: Migration 절차, API 명세, 화면 설계.']):
        para(doc, line)
    heading(doc, '1.3 산출 근거', 2)
    para(doc, DOC.get('sources_note',
                      '본 ERD 는 실제 DB 와 DDL 을 읽어 생성했다. 따라서 테이블명·컬럼명·'
                      '타입·제약은 실제 스키마와 일치한다.'))
    t = table(doc, ['근거', '내용'], [5.6, 11.4], font_size=9)
    for r in DOC.get('sources', [
            ('information_schema', '테이블·컬럼·타입·PK·FK·삭제 규칙의 실제 값'),
            ('테이블·컬럼 코멘트', '설명 1순위'),
            ('ORM 모델 주석', '코멘트가 없는 컬럼의 설명')]):
        row(t, r, [5.6, 11.4], font_size=9, mono_cols=(0,))
    para(doc, '')

    heading(doc, '1.4 표기 규칙', 2)
    t = table(doc, ['표기', '의미'], [4.2, 12.8], font_size=9)
    for code, (_f, _h, _b, label) in LAYERS.items():
        row(t, (f'{code} (색상 구분)', label), [4.2, 12.8], font_size=9)
    for r in [('NEW', '신규 생성 테이블'),
              ('확장', '기존 운영 테이블 · 컬럼 추가'),
              ('원천', '외부 원천 · 읽기 전용'),
              ('[추가]', '이번 보완으로 추가되는 컬럼'),
              ('실선', '외래키(FK) · 라벨은 「자식 컬럼 : 부모 컬럼」'),
              ('점선 (갈색)', 'ETL 적재 흐름 — FK 가 아니라 데이터 흐름'),
              ('반원', '선이 교차할 때 넘어가는 표시 (연결 아님)'),
              ('까치발 / 직교선', '관계의 N 쪽(자식) / 1 쪽(부모)'),
              ('NN', 'NOT NULL')]:
        row(t, r, [4.2, 12.8], font_size=9)
    para(doc, '')

    # ── 2~3. 그림 (가로 섹션) ──
    landscape(doc)
    heading(doc, '2. 스키마 · 레이어 구조')
    para(doc, '아래 그림에서 색은 레이어를, 묶음은 스키마와 기능 영역을 나타낸다.')
    picture(doc, OUT / 'erd_overview.png', 26.0,
            f'[그림 1] {TITLE} — 전체 관계 개요')

    heading(doc, '2.1 전체 ERD', 2)
    para(doc, f'전체 {len(SCHEMA)}개 테이블의 모든 컬럼과 설명을 한 장에 표시한다. '
              '인쇄본에서는 축소되어 읽기 어려우므로, 세부 확인은 3장의 영역별 ERD 또는 '
              f'원본 이미지(assets/erd/06-erd-proposed-full.png)를 사용한다.')
    picture(doc, OUT / 'erd_full.png', 26.0,
            f'[그림 2] {TITLE} — 전체 (컬럼 · 설명 포함)')

    heading(doc, '3. 영역별 ERD')
    para(doc, '영역별로 전체 컬럼과 설명을 표시한다. 해당 영역 밖의 참조 대상은 회색 테두리의 '
              '축약 박스로 표기했다.')
    for i, (code, name, schema, tables) in enumerate(AREAS, start=3):
        heading(doc, f'3.{i - 2} 영역 {code} · {name} ({schema} 스키마 · {len(tables)}개)', 2)
        picture(doc, OUT / f'erd_area_{code}.png', 26.0,
                f'[그림 {i}] 영역 {code} · {name}')

    # ── 4. 테이블별 역할 및 컬럼 설명 ──
    portrait(doc)
    heading(doc, '4. 테이블별 역할 및 컬럼 설명')
    para(doc, f'전체 {len(SCHEMA)}개 테이블 · '
              f'{sum(len(t["columns"]) for t in SCHEMA.values())}개 컬럼. '
              '구분 열의 PK 는 기본키, FK 는 외래키, [추가] 는 이번 보완으로 추가되는 컬럼이다.')
    n = 0
    for ai, (code, name, schema, tables) in enumerate(AREAS, start=1):
        heading(doc, f'4.{ai} 영역 {code} · {name}', 2)
        for ti, tname in enumerate(tables, start=1):
            n += 1
            t_ = SCHEMA[tname]
            bd, _c = erd.badge(tname)
            heading(doc, f'4.{ai}.{ti} {tname} · {ROLE.get(tname, "")}', 3)
            meta = table(doc, ['스키마', '구분', '레이어', '컬럼', '외래키'],
                         [2.4, 2.2, 4.6, 1.8, 1.8], font_size=8.5)
            row(meta, (t_.get('schema', 'public'), bd, LAYERS[layer(tname)][3],
                       len(t_['columns']), len(t_['fks'])),
                [2.4, 2.2, 4.6, 1.8, 1.8], font_size=8.5,
                aligns=[None, WD_ALIGN_PARAGRAPH.CENTER, None,
                        WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.CENTER])
            if t_.get('note'):
                para(doc, t_['note'], size=9, color='595959', space_after=3)
            ct = table(doc, ['구분', '컬럼', '타입', '설명'], [1.3, 4.2, 3.0, 8.5], font_size=8)
            for c in t_['columns']:
                mark = erd.col_role(t_, c)
                desc = ('[추가] ' if c['added'] else '') + c['comment']
                ct.rows  # noqa
                row(ct, (mark, c['name'], c['type'] + (' NN' if c['not_null'] else ''), desc),
                    [1.3, 4.2, 3.0, 8.5], font_size=8, mono_cols=(1, 2), bold_cols=(1,),
                    aligns=[WD_ALIGN_PARAGRAPH.CENTER, None, None, None],
                    colors={0: 'B03A2E' if mark == 'PK' else '1F618D'} if mark else None)
            para(doc, '', space_after=8)

    # ── 5. 관계 정의 ──
    heading(doc, '5. 관계 정의')
    heading(doc, '5.1 외래키 (FK)', 2)
    fks = [(n_, fk) for n_, t_ in SCHEMA.items() for fk in t_['fks']]
    para(doc, f'전체 {len(fks)}건. 삭제 규칙이 CASCADE 인 관계는 부모 삭제 시 자식 행이 함께 '
              '지워지고, SET NULL 인 관계는 참조만 끊고 행은 남긴다.')
    t = table(doc, ['자식 테이블', '컬럼', '부모 테이블', '컬럼', '삭제 규칙'],
              [4.4, 3.5, 4.2, 2.3, 2.6], font_size=8)
    for n_, fk in sorted(fks, key=lambda x: (x[0], x[1]['column'])):
        row(t, (n_, fk['column'], fk['ref_table'], fk['ref_column'],
                f"ON DELETE {fk['on_delete']}"),
            [4.4, 3.5, 4.2, 2.3, 2.6], font_size=8, mono_cols=(0, 1, 2, 3),
            colors={4: 'B03A2E' if fk['on_delete'] == 'CASCADE' else '595959'})
    para(doc, '')

    heading(doc, '5.2 ETL 적재 흐름', 2)
    para(doc, 'FK 가 아니라 데이터 흐름이다. ref 스키마는 읽기 전용이므로 물리적 제약을 걸 수 없다.')
    t = table(doc, ['원천 (ref 스키마)', '대상 (public 스키마)', '내용'],
              [5.0, 5.4, 6.6], font_size=8.5)
    for src, dst, label in erd.DERIVES:
        row(t, (src, dst, label), [5.0, 5.4, 6.6], font_size=8.5, mono_cols=(0, 1))
    para(doc, '')

    # ── 6. 대조표 (spec 에 doc.mapping 이 있을 때만) ──
    if MAPPING_TABLE:
        _chapter_mapping(doc)
    if OPEN_ITEMS:
        _chapter_open(doc)

    path = PROJ / f'{DOCNAME}.docx'
    doc.save(path)
    return path


def _chapter_mapping(doc):
    heading(doc, '6. 설계안 대비 반영 결과')
    para(doc, DOC.get('mapping_intro',
                      '설계안의 테이블명과 실제 DDL 의 명칭이 다르다. 각 항목이 실제로 '
                      '어떻게 반영되었는지 아래와 같이 대조한다.'))
    t = table(doc, ['No', '설계안 (가안)', '실제 테이블', '반영', '사유'],
              [1.0, 3.6, 4.6, 1.8, 6.0], font_size=8)
    for r in MAPPING_TABLE:
        row(t, r, [1.0, 3.6, 4.6, 1.8, 6.0], font_size=8, mono_cols=(1, 2),
            aligns=[WD_ALIGN_PARAGRAPH.CENTER, None, None, WD_ALIGN_PARAGRAPH.CENTER, None])
    para(doc, '')
    if DOC.get('mapping_note'):
        para(doc, DOC['mapping_note'], size=9)


def _chapter_open(doc):
    heading(doc, '7. 미반영 항목 및 판단 필요 사항')
    para(doc, '본 ERD 는 구조를 정의한 것이며, 구조가 있다고 해서 동작하는 것은 아니다. '
              '아래 항목은 구조 밖의 결정이 선행되어야 값이 채워진다.')
    t = table(doc, ['우선', '항목', '대상', '현재 상태', '필요 조치'],
              [1.0, 3.0, 3.4, 5.4, 4.2], font_size=8)
    for r in OPEN_ITEMS:
        row(t, r, [1.0, 3.0, 3.4, 5.4, 4.2], font_size=8, mono_cols=(2,),
            aligns=[WD_ALIGN_PARAGRAPH.CENTER, None, None, None, None])
    para(doc, '')
    if DOC.get('open_note'):
        para(doc, DOC['open_note'], size=9)


if __name__ == '__main__':
    p = build()
    print('저장:', p.name, f'({p.stat().st_size / 1024:.0f} KB)')
