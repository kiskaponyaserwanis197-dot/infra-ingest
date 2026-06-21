"""Document and text extraction helpers for infra-ingest."""

from .converters import (
    PLAIN_TEXT_EXTENSIONS,
    convert_local_file_to_markdown,
    read_plain_text,
    should_try_markitdown,
)


def extract_pdf_text(pdf_path, console):
    """Extract text from a PDF using PyMuPDF first, then pypdf."""
    console.log(f"[yellow]正在解析 PDF 文件: {pdf_path}[/yellow]")
    text_content = []

    try:
        import fitz

        doc = fitz.open(pdf_path)
        for page in doc:
            text_content.append(page.get_text())
        doc.close()
        console.log(f"[green]使用 PyMuPDF 提取成功 (共 {len(text_content)} 页)[/green]")
        return "\n".join(text_content)
    except Exception as exc:
        console.log(f"[yellow]PyMuPDF 提取失败，尝试使用 pypdf 备用. 错误: {exc}[/yellow]")

    try:
        import pypdf

        reader = pypdf.PdfReader(pdf_path)
        for page in reader.pages:
            text_content.append(page.extract_text() or "")
        console.log(f"[green]使用 pypdf 提取成功 (共 {len(reader.pages)} 页)[/green]")
        return "\n".join(text_content)
    except Exception as exc:
        raise RuntimeError(f"PDF 提取完全失败: {exc}") from exc


def extract_document_text(input_path, file_ext, console):
    """Extract text from plain text or MarkItDown-supported documents."""
    if file_ext in PLAIN_TEXT_EXTENSIONS:
        return read_plain_text(input_path)

    if should_try_markitdown(input_path):
        try:
            console.log(f"[yellow]正在使用 MarkItDown 转换文件为 Markdown: {input_path}[/yellow]")
            raw_text = convert_local_file_to_markdown(input_path)
            console.log("[green]MarkItDown 转换成功。[/green]")
            return raw_text
        except Exception as exc:
            if file_ext == ".pdf":
                console.log(f"[yellow]MarkItDown 转换 PDF 失败，回退到 PyMuPDF/pypdf. 错误: {exc}[/yellow]")
                return extract_pdf_text(input_path, console)
            raise RuntimeError(f"文件转换失败: {exc}") from exc

    raise RuntimeError(f"暂不支持该文件类型: {file_ext}")
