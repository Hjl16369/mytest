import fitz  # PyMuPDF

doc = fitz.open("人工智能医疗健康行业应用白皮书-副本.pdf")
for i in range(len(doc)):
    for img in doc.get_page_images(i):
        xref = img[0]
        pix = fitz.Pixmap(doc, xref)
        if pix.n - pix.alpha > 3:  # 检查是否为RGB
            pix = fitz.Pixmap(fitz.csRGB, pix)
        pix.save(f"image_{i}_{xref}.png")