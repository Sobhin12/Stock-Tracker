"""Workbook storage: per company a Summary, NSE and BSE sheet, laid out like the sample."""
from datetime import date, datetime

from openpyxl import Workbook, load_workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.chart.data_source import StrRef
from openpyxl.chart.label import DataLabelList
from openpyxl.chart.series import SeriesLabel
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.chart.text import RichText
from openpyxl.drawing.text import CharacterProperties, Paragraph, ParagraphProperties
from openpyxl.drawing.line import LineProperties
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import storage
from config import BSE_URL, COMPANIES, NSE_URL, XLSX_PATH
from fetchers import bse, nse

HEADER_FILL = PatternFill("solid", fgColor="002060")
HEADER_FONT = Font(bold=True, color="FFFFFF")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

SUMMARY_HEADERS = [
    "Month", "Date", "High Price", "Low Price", "Close Price", "Average Price",
    "Total Traded Quantity (NSE)", "Total Turnover\n(INR Cr)", "No. of Trades",
    "Quantity per Trade", "Deliverable Qty", "% Dly Qt to Traded Qty",
    "Total Traded Quantity - BSE", "Total Traded Quantity (NSE+BSE)",
]


def nse_sheet(sym: str) -> str:
    return f"{sym} NSE"


def bse_sheet(sym: str) -> str:
    return f"{sym} BSE"


def summary_sheet(sym: str) -> str:
    return f"{sym} Summary"


def _as_date(v) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return None


def load_data() -> dict[str, dict[str, list[list]]]:
    """{sym: {"nse": rows, "bse": rows}} read from the data sheets (empty if no workbook)."""
    data = {sym: {"nse": [], "bse": []} for sym in COMPANIES}
    storage.pull(XLSX_PATH)
    if not XLSX_PATH.exists():
        return data
    wb = load_workbook(XLSX_PATH, read_only=True)
    for sym in COMPANIES:
        for key, name, date_col in (("nse", nse_sheet(sym), 2), ("bse", bse_sheet(sym), 0)):
            if name not in wb.sheetnames:
                continue
            for row in wb[name].iter_rows(min_row=2, values_only=True):
                d = _as_date(row[date_col]) if row else None
                if d:
                    row = list(row)
                    row[date_col] = d
                    data[sym][key].append(row)
    wb.close()
    return data


def last_dates(data) -> dict[str, dict[str, date | None]]:
    return {
        sym: {
            "nse": d["nse"][-1][2] if d["nse"] else None,
            "bse": d["bse"][-1][0] if d["bse"] else None,
        }
        for sym, d in data.items()
    }


def merge(rows: list[list], new: list[list], date_col: int) -> list[list]:
    by_date = {r[date_col]: r for r in rows}
    by_date.update({r[date_col]: r for r in new})
    return [by_date[d] for d in sorted(by_date)]


# ---------------------------------------------------------------- writing

def _header(ws, row: int, headers: list[str], first_col: int = 1):
    for i, h in enumerate(headers):
        c = ws.cell(row=row, column=first_col + i, value=h)
        c.fill, c.font, c.border = HEADER_FILL, HEADER_FONT, BORDER
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _write_data_sheet(ws, headers, rows, date_col, num_formats):
    _header(ws, 1, headers)
    for r in rows:
        ws.append(r)
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        row[date_col].number_format = "dd-mmm-yy"
        for idx, fmt in num_formats.items():
            row[idx].number_format = fmt
    for i in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(i)].width = 14
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def _write_summary(ws, sym: str, n_nse: int):
    nse_ref, bse_ref = f"'{nse_sheet(sym)}'", f"'{bse_sheet(sym)}'"
    ws.merge_cells("D2:M2")
    ws["D2"] = "NSE"
    ws["D2"].fill, ws["D2"].font = HEADER_FILL, HEADER_FONT
    ws["D2"].alignment = Alignment(horizontal="center")
    _header(ws, 3, SUMMARY_HEADERS, first_col=2)
    ws.row_dimensions[3].height = 45
    for i in range(n_nse):
        r, s = i + 4, i + 2  # summary row, NSE sheet row
        f = {
            "B": f"=DATE(YEAR(C{r}),MONTH(C{r}),1)",
            "C": f"={nse_ref}!C{s}",
            "D": f"={nse_ref}!F{s}",
            "E": f"={nse_ref}!G{s}",
            "F": f"={nse_ref}!I{s}",
            "G": f"={nse_ref}!J{s}",
            "H": f"={nse_ref}!K{s}",
            "I": f"={nse_ref}!L{s}/10^7",
            "J": f"={nse_ref}!M{s}",
            "K": f"=IFERROR(H{r}/J{r},0)",
            "L": f"={nse_ref}!N{s}",
            "M": f"=IFERROR(L{r}/H{r},0)",
            "N": f"=IFERROR(INDEX({bse_ref}!G:G,MATCH(C{r},{bse_ref}!A:A,0)),0)",
            "O": f"=H{r}+N{r}",
        }
        for col, formula in f.items():
            ws[f"{col}{r}"] = formula
        ws[f"B{r}"].number_format = "mmm-yy"
        ws[f"C{r}"].number_format = "dd-mmm"
        for col in "DEFG":
            ws[f"{col}{r}"].number_format = "0.00"
        for col in "HJLNO":
            ws[f"{col}{r}"].number_format = "#,##0"
        ws[f"I{r}"].number_format = "#,##0.00"
        ws[f"K{r}"].number_format = "0.0"
        ws[f"M{r}"].number_format = "0%"
    ws.column_dimensions["A"].width = 2
    for col in "BCDEFGHIJKLMNO":
        ws.column_dimensions[col].width = 13
    ws.freeze_panes = "B4"
    ws.auto_filter.ref = f"B3:O{n_nse + 3}"


def _month_span(dates: list[date]) -> tuple[int, int] | None:
    """0-based (first, last) indexes of the latest month in an ascending date list."""
    if not dates:
        return None
    last = dates[-1]
    first = next(i for i, d in enumerate(dates) if (d.year, d.month) == (last.year, last.month))
    return first, len(dates) - 1


def _font(size: int) -> RichText:
    """Chart text properties with the given size in hundredths of a point."""
    return RichText(p=[Paragraph(pPr=ParagraphProperties(defRPr=CharacterProperties(sz=size)),
                                 endParaRPr=CharacterProperties())])


def _price_chart(ws_data, title, cat_col, high_col, low_col, close_col, avg_col, avg_name,
                 header_row, r1, r2):
    """Clustered columns High/Low/Close + line Average, styled like the sample."""
    bar = BarChart()
    bar.type, bar.grouping, bar.overlap, bar.gapWidth = "col", "clustered", -10, 80
    bar.title = title
    bar.height, bar.width = 9.5, 26
    colours = {high_col: ("00B0F0", None), low_col: ("002060", None), close_col: ("FFFFFF", "404040")}
    # Data starts at the month's first row, so series names point at the header cell.
    for col in (high_col, low_col, close_col):
        bar.add_data(Reference(ws_data, min_col=col, min_row=r1, max_row=r2), titles_from_data=False)
    for s, col in zip(bar.series, (high_col, low_col, close_col)):
        fill, line = colours[col]
        s.tx = SeriesLabel(strRef=StrRef(f"'{ws_data.title}'!${get_column_letter(col)}${header_row}"))
        s.graphicalProperties = GraphicalProperties(solidFill=fill)
        if line:
            s.graphicalProperties.line = LineProperties(solidFill=line)
    bar.set_categories(Reference(ws_data, min_col=cat_col, min_row=r1, max_row=r2))
    # Excel treats every flag left out as "on", so switch the others off explicitly;
    # otherwise each label reads "High Price, 02-Nov-26, 536.05" with a legend key.
    bar.dataLabels = DataLabelList(showVal=True, showSerName=False, showCatName=False,
                                   showLegendKey=False, showPercent=False, showBubbleSize=False)
    bar.dataLabels.position = "outEnd"
    bar.dataLabels.numFmt = "0.00"
    bar.dataLabels.txPr = _font(800)

    line = LineChart()
    line.add_data(Reference(ws_data, min_col=avg_col, min_row=r1, max_row=r2), titles_from_data=False)
    s = line.series[0]
    s.tx = SeriesLabel(v=avg_name)
    s.graphicalProperties.line = LineProperties(solidFill="FFC000", w=28575)
    s.smooth = False

    bar.y_axis.title = "INR"
    bar.y_axis.majorGridlines = None
    bar.x_axis.number_format = "dd-mmm"
    # Keep a text axis: with dates Excel would switch to a date axis and leave empty
    # slots for weekends and holidays.
    bar.x_axis.auto = False
    bar.x_axis.axPos = "b"
    bar.x_axis.delete = False
    bar.y_axis.delete = False
    bar.legend.position = "b"
    bar.legend.overlay = False  # give the legend its own space below the date labels
    bar += line
    return bar


def _add_charts(ws_sum, ws_nse, ws_bse, sym: str, nse_rows, bse_rows):
    name = COMPANIES[sym]["name"]
    span = _month_span([r[2] for r in nse_rows])
    if span:
        d = nse_rows[span[1]][2]
        # Read the NSE sheet's plain values, not the Summary formulas: Excel doesn't
        # recalculate a downloaded file in Protected View, so formula cells chart as 0.
        chart = _price_chart(ws_nse, f"{name} Share Price {d:%b'%y} (INR) - NSE", 3, 6, 7, 9, 10,
                             "WAP", 1, span[0] + 2, span[1] + 2)
        ws_sum.add_chart(chart, "Q3")
    span = _month_span([r[0] for r in bse_rows])
    if span:
        d = bse_rows[span[1]][0]
        chart = _price_chart(ws_bse, f"{name} Share Price {d:%b'%y} (INR) - BSE", 1, 3, 4, 5, 6,
                             "WAP", 1, span[0] + 2, span[1] + 2)
        ws_sum.add_chart(chart, "Q24")


def save(data) -> None:
    wb = Workbook()
    wb.remove(wb.active)
    for sym in COMPANIES:
        nse_rows, bse_rows = data[sym]["nse"], data[sym]["bse"]
        ws_sum = wb.create_sheet(summary_sheet(sym))
        ws_nse = wb.create_sheet(nse_sheet(sym))
        ws_bse = wb.create_sheet(bse_sheet(sym))
        _write_data_sheet(ws_nse, nse.COLUMNS, nse_rows, 2,
                          {i: "0.00" for i in range(3, 10)} | {10: "#,##0", 11: "#,##0.00", 12: "#,##0", 13: "#,##0"})
        _write_data_sheet(ws_bse, bse.COLUMNS, bse_rows, 0,
                          {i: "0.00" for i in range(1, 6)} | {6: "#,##0", 7: "#,##0", 8: "#,##0", 9: "#,##0"})
        _write_summary(ws_sum, sym, len(nse_rows))
        _add_charts(ws_sum, ws_nse, ws_bse, sym, nse_rows, bse_rows)
    src = wb.create_sheet("Sources")
    src["B3"], src["C3"] = "NSE", NSE_URL
    src["B5"], src["C5"] = "BSE", BSE_URL
    src["C8"] = "BSE>Market>Market Data>Historical Information>Equity>Historical Stock Price (data from BSE Bhavcopy & delivery files)"
    src["C10"] = "NSE>Home>Report Detail>Security-wise Archives (Equities)"
    src.sheet_state = "hidden"
    wb.calculation.fullCalcOnLoad = True
    XLSX_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = XLSX_PATH.with_suffix(".tmp.xlsx")
    wb.save(tmp)
    tmp.replace(XLSX_PATH)
    storage.push(XLSX_PATH)
