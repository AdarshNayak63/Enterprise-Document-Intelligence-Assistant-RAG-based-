from typing import List, Tuple
from pypdf import PdfReader
from docx import Document as DocxDocument
import pandas as pd


def parse_pdf(path: str) -> List[Tuple[int, str]]:
    pages = []
    reader = PdfReader(path)
    for i, page in enumerate(reader.pages, start=1):
        pages.append((i, page.extract_text() or ""))
    return pages


def parse_docx(path: str) -> List[Tuple[int, str]]:
    doc = DocxDocument(path)
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return [(1, text)]


def parse_csv(path: str) -> List[Tuple[int, str]]:
    df = pd.read_csv(path)
    return [(1, df.to_csv(index=False))]


def parse_xlsx(path: str) -> List[Tuple[int, str]]:
    sheets = pd.read_excel(path, sheet_name=None)
    parts = []
    for name, df in sheets.items():
        parts.append(f"[Sheet: {name}]\n{df.to_csv(index=False)}")
    return [(1, "\n\n".join(parts))]


def parse_txt(path: str) -> List[Tuple[int, str]]:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return [(1, f.read())]
