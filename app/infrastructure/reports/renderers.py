"""Exportação de relatórios em CSV e PDF (o JSON é o próprio ReportDTO)."""
import csv
from datetime import date, datetime
from decimal import Decimal
import io

from fpdf import FPDF
from fpdf.fonts import FontFace

from app.application.services.report_catalog import ColumnKind, code_label
from app.application.use_cases.report_use_case import DISCLAIMER, ReportTable

# Células de texto que começam com estes caracteres seriam interpretadas como fórmula por planilhas.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
# As fontes padrão do PDF só cobrem Latin-1: troca a tipografia que estiver fora dela.
PDF_REPLACEMENTS = str.maketrans({"—": "-", "–": "-", "•": "-", "≤": "<=", "≥": ">=", "…": "...",
                                  "“": '"', "”": '"', "‘": "'", "’": "'"})
NUMERIC_KINDS = (ColumnKind.MONEY, ColumnKind.NUMBER)


def _number(value, decimals: int) -> str:
    text = f"{Decimal(str(value)):,.{decimals}f}"
    return text.replace(",", "_").replace(".", ",").replace("_", ".")  # 1,234.50 -> 1.234,50


def format_value(value, kind: ColumnKind) -> str:
    """Valor de célula no padrão brasileiro."""
    if value is None:
        return ""
    if kind == ColumnKind.DATETIME and isinstance(value, datetime):
        return f"{value:%d/%m/%Y %H:%M}"
    if kind == ColumnKind.DATE and isinstance(value, (date, datetime)):
        return f"{value:%d/%m/%Y}"
    if kind == ColumnKind.MONEY:
        return _number(value, 2)
    if kind == ColumnKind.NUMBER:
        return _number(value, 0 if float(value).is_integer() else 2)
    if kind == ColumnKind.CODE:
        return code_label(str(value))
    return str(value)


def _safe_text(text: str) -> str:
    return "'" + text if text.startswith(FORMULA_PREFIXES) else text


def file_name(table: ReportTable, extension: str) -> str:
    period = f"_{table.start:%Y%m%d}-{table.end:%Y%m%d}" if table.start else f"_{table.generated_at:%Y%m%d}"
    return f"healthos_{table.definition.key}{period}.{extension}"


def to_csv(table: ReportTable) -> bytes:
    """CSV para Excel em português: separador ";", vírgula decimal e BOM UTF-8."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    columns = table.definition.columns
    writer.writerow([c.label for c in columns])
    for row in table.rows:
        writer.writerow([format_value(row.get(c.key), c.kind) if c.kind in NUMERIC_KINDS
                         else _safe_text(format_value(row.get(c.key), c.kind)) for c in columns])
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def _pdf_text(value: str) -> str:
    return value.translate(PDF_REPLACEMENTS).encode("latin-1", "replace").decode("latin-1")


class _ReportPDF(FPDF):
    def __init__(self, table: ReportTable, orientation: str):
        super().__init__(orientation=orientation, unit="mm", format="A4")
        self.table_data = table
        self.set_margins(10, 12, 10)
        self.set_auto_page_break(auto=True, margin=14)
        self.set_title(_pdf_text(table.definition.title))
        self.set_creator("HealthOS (ambiente didático)")

    def header(self):
        t = self.table_data
        self.set_font("helvetica", "B", 13)
        self.cell(0, 7, _pdf_text(f"HealthOS - {t.definition.title}"), new_x="LMARGIN", new_y="NEXT")
        self.set_font("helvetica", "", 8.5)
        self.set_text_color(90, 90, 90)
        scope = (f"Período: {t.start:%d/%m/%Y} a {t.end:%d/%m/%Y}" if t.start else "Posição na data de geração")
        if t.status:
            scope += f" | Situação: {t.status}"
        self.cell(0, 5, _pdf_text(f"{scope} | Gerado em {t.generated_at:%d/%m/%Y %H:%M} | {len(t.rows)} linha(s)"
                                  + (" (limite atingido)" if t.truncated else "")), new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def footer(self):
        self.set_y(-10)
        self.set_font("helvetica", "I", 7.5)
        self.set_text_color(110, 110, 110)
        self.cell(0, 5, _pdf_text(DISCLAIMER), align="L")
        self.cell(0, 5, f"Página {self.page_no()}/{{nb}}", align="R")


def to_pdf(table: ReportTable) -> bytes:
    columns = table.definition.columns
    landscape = sum(c.width for c in columns) > 8
    pdf = _ReportPDF(table, "L" if landscape else "P")
    pdf.add_page()
    pdf.set_font("helvetica", "", 8)
    if not table.rows:
        pdf.cell(0, 8, _pdf_text("Nenhum registro no período."))
        return bytes(pdf.output())
    aligns = tuple("RIGHT" if c.kind in NUMERIC_KINDS else "LEFT" for c in columns)
    with pdf.table(col_widths=tuple(c.width for c in columns), text_align=aligns, line_height=4.6,
                   headings_style=FontFace(emphasis="BOLD", fill_color=(232, 238, 247)),
                   cell_fill_color=(247, 249, 252), cell_fill_mode="ROWS") as pdf_table:
        heading = pdf_table.row()
        for column in columns:
            heading.cell(_pdf_text(column.label))
        for row in table.rows:
            cells = pdf_table.row()
            for column in columns:
                cells.cell(_pdf_text(format_value(row.get(column.key), column.kind)))
    return bytes(pdf.output())
