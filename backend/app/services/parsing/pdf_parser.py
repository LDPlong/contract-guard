"""PDF 文本与坐标抽取（PyMuPDF）。

职责边界：只负责"把每一行文字连同它的页码和矩形拿出来"，不做任何语义切分。
坐标系遵循文档 9.2：PDF point、左上原点、y 向下、绝对坐标。
"""

from __future__ import annotations

from pathlib import Path

try:  # PyMuPDF 2.x 推荐 pymupdf 包名，1.x 为 fitz
    import pymupdf as fitz  # type: ignore
except ImportError:  # pragma: no cover
    import fitz  # type: ignore

from app.core.constants import MAX_PAGES
from app.core.errors import ParseFailed
from app.core.logging import get_logger
from app.services.parsing.models import BBox, PageInfo, ParsedDocument, TextLine

log = get_logger(__name__)


def _sort_lines(lines: list[TextLine]) -> list[TextLine]:
    """按阅读顺序排序：页 → 纵向 → 横向。

    同一行被 PyMuPDF 拆成多个 span 时，y 会有微小差异，
    这里先用 2pt 的容差把同一视觉行的元素归到一起，再按 x 排序。
    """
    return sorted(lines, key=lambda ln: (ln.page_no, round(ln.bbox[1] / 2), ln.bbox[0]))


def parse_pdf(path: str | Path, max_pages: int = MAX_PAGES) -> ParsedDocument:
    """解析 PDF，返回带坐标的文本行。

    失败一律抛 ParseFailed（对应错误码 2001），不向上抛原生异常。
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise ParseFailed(f"文件不存在：{file_path.name}")

    try:
        doc = fitz.open(file_path)
    except Exception as exc:  # noqa: BLE001
        raise ParseFailed("PDF 打开失败，文件可能已损坏或加密") from exc

    try:
        if doc.needs_pass:
            raise ParseFailed("PDF 已加密，请先去除密码后重新上传")
        if doc.page_count > max_pages:
            raise ParseFailed(f"页数 {doc.page_count} 超过上限 {max_pages} 页")

        warnings: list[str] = []
        pages: list[PageInfo] = []
        lines: list[TextLine] = []

        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            rect = page.rect
            pages.append(PageInfo(page_index + 1, float(rect.width), float(rect.height)))

            page_text = page.get_text("dict")
            page_line_count = 0
            for block in page_text.get("blocks", []):
                if block.get("type") != 0:  # 0 = 文本块，1 = 图片
                    continue
                for line in block.get("lines", []):
                    text = "".join(span.get("text", "") for span in line.get("spans", []))
                    text = text.strip()
                    if not text:
                        continue
                    bbox = line.get("bbox")
                    if not bbox or len(bbox) != 4:
                        continue
                    lines.append(
                        TextLine(
                            page_no=page_index + 1,
                            bbox=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
                            text=text,
                            char_start=0,  # 排序后由 _reindex_offsets 统一回填
                            char_end=0,
                        )
                    )
                    page_line_count += 1

            if page_line_count == 0:
                warnings.append(f"第 {page_index + 1} 页未提取到文本层，可能需要 OCR")

        if not lines:
            raise ParseFailed("未提取到任何文本，请确认是文字版 PDF（扫描件需开启 OCR）")

        ordered = _sort_lines(lines)
        full_text = "\n".join(ln.text for ln in ordered)
        _reindex_offsets(ordered)

        return ParsedDocument(
            page_count=doc.page_count,
            pages=pages,
            lines=ordered,
            full_text=full_text,
            warnings=warnings,
        )
    finally:
        doc.close()


def _reindex_offsets(lines: list[TextLine]) -> None:
    """排序后重算 char_start/char_end，保证与 full_text 的拼接方式一致。"""
    cursor = 0
    for idx, line in enumerate(lines):
        lines[idx] = TextLine(
            page_no=line.page_no,
            bbox=line.bbox,
            text=line.text,
            char_start=cursor,
            char_end=cursor + len(line.text),
        )
        cursor += len(line.text) + 1


def union_bbox(boxes: list[BBox]) -> BBox | None:
    """合并多个矩形，用于把一行的 span 框或一条条款的多行框并成一个。"""
    if not boxes:
        return None
    xs0 = [b[0] for b in boxes]
    ys0 = [b[1] for b in boxes]
    xs1 = [b[2] for b in boxes]
    ys1 = [b[3] for b in boxes]
    return (min(xs0), min(ys0), max(xs1), max(ys1))
