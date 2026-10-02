"""テスト用の架空PDF（テキストあり・テキストなし）を作る。python tests/fixtures/web/make_pdfs.py"""

from pathlib import Path


def pdf(lines: list[str], with_text: bool = True, creation: str = "D:20260914090000+09'00'") -> bytes:
    content = "BT /F1 12 Tf 72 720 Td 14 TL " + " ".join(f"({line}) Tj T*" for line in lines) + " ET" if with_text else "0.9 g 72 600 200 100 re f"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Title (Fictional survey report) /CreationDate ({creation}) >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R /Info 6 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


if __name__ == "__main__":
    here = Path(__file__).parent
    (here / "report.pdf").write_bytes(pdf([
        "Fictional survey report on child health (test fixture)",
        "Published: 2026/09/15",
        "This document is entirely fictional.",
    ]))
    (here / "scan.pdf").write_bytes(pdf([], with_text=False))
