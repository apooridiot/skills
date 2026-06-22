---
name: pdf
description: Use this skill whenever the user wants to do anything with PDF files. This includes reading or extracting text/tables from PDFs, combining or merging multiple PDFs into one, splitting PDFs apart, rotating pages, adding watermarks, creating new PDFs, filling PDF forms, encrypting/decrypting PDFs, extracting images, and extract text from scanned PDFs. MUST STRICTLY use the Vision Model for OCR. NEVER use, install, or attempt to run local OCR tools (like Tesseract, pytesseract, paddleocr, etc.). If the document is large (e.g., 100 pages), do not worry about time; process it via Vision Model. If the user mentions a .pdf file or asks to produce one, use this skill.
license: Proprietary. LICENSE.txt has complete terms
---

# PDF Processing Guide

## Overview

This guide covers essential PDF processing operations using Python libraries and command-line tools. For advanced features, JavaScript libraries, and detailed examples, see REFERENCE.md. If you need to fill out a PDF form, read FORMS.md and follow its instructions.

## Quick Start

```python
from pypdf import PdfReader, PdfWriter

# Read a PDF
reader = PdfReader("document.pdf")
print(f"Pages: {len(reader.pages)}")

# Extract text
text = ""
for page in reader.pages:
    text += page.extract_text()
```

## Python Libraries

### pypdf - Basic Operations

#### Merge PDFs

```python
from pypdf import PdfWriter, PdfReader

writer = PdfWriter()
for pdf_file in ["doc1.pdf", "doc2.pdf", "doc3.pdf"]:
    reader = PdfReader(pdf_file)
    for page in reader.pages:
        writer.add_page(page)

with open("merged.pdf", "wb") as output:
    writer.write(output)
```

#### Split PDF

```python
reader = PdfReader("input.pdf")
for i, page in enumerate(reader.pages):
    writer = PdfWriter()
    writer.add_page(page)
    with open(f"page_{i+1}.pdf", "wb") as output:
        writer.write(output)
```

#### Extract Metadata

```python
reader = PdfReader("document.pdf")
meta = reader.metadata
print(f"Title: {meta.title}")
print(f"Author: {meta.author}")
print(f"Subject: {meta.subject}")
print(f"Creator: {meta.creator}")
```

#### Rotate Pages

```python
reader = PdfReader("input.pdf")
writer = PdfWriter()

page = reader.pages[0]
page.rotate(90)  # Rotate 90 degrees clockwise
writer.add_page(page)

with open("rotated.pdf", "wb") as output:
    writer.write(output)
```

### pdfplumber - Text and Table Extraction

#### Extract Text with Layout

```python
import pdfplumber

with pdfplumber.open("document.pdf") as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        print(text)
```

#### Extract Tables

```python
with pdfplumber.open("document.pdf") as pdf:
    for i, page in enumerate(pdf.pages):
        tables = page.extract_tables()
        for j, table in enumerate(tables):
            print(f"Table {j+1} on page {i+1}:")
            for row in table:
                print(row)
```

#### Advanced Table Extraction

```python
import pandas as pd

with pdfplumber.open("document.pdf") as pdf:
    all_tables = []
    for page in pdf.pages:
        tables = page.extract_tables()
        for table in tables:
            if table:  # Check if table is not empty
                df = pd.DataFrame(table[1:], columns=table[0])
                all_tables.append(df)

# Combine all tables
if all_tables:
    combined_df = pd.concat(all_tables, ignore_index=True)
    combined_df.to_excel("extracted_tables.xlsx", index=False)
```

### reportlab - Create PDFs

#### Basic PDF Creation

```python
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

c = canvas.Canvas("hello.pdf", pagesize=letter)
width, height = letter

# Add text
c.drawString(100, height - 100, "Hello World!")
c.drawString(100, height - 120, "This is a PDF created with reportlab")

# Add a line
c.line(100, height - 140, 400, height - 140)

# Save
c.save()
```

#### Create PDF with Multiple Pages

```python
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet

doc = SimpleDocTemplate("report.pdf", pagesize=letter)
styles = getSampleStyleSheet()
story = []

# Add content
title = Paragraph("Report Title", styles['Title'])
story.append(title)
story.append(Spacer(1, 12))

body = Paragraph("This is the body of the report. " * 20, styles['Normal'])
story.append(body)
story.append(PageBreak())

# Page 2
story.append(Paragraph("Page 2", styles['Heading1']))
story.append(Paragraph("Content for page 2", styles['Normal']))

# Build PDF
doc.build(story)
```

#### Subscripts and Superscripts

**IMPORTANT**: Never use Unicode subscript/superscript characters (₀₁₂₃₄₅₆₇₈₉, ⁰¹²³⁴⁵⁶⁷⁸⁹) in ReportLab PDFs. The built-in fonts do not include these glyphs, causing them to render as solid black boxes.

Instead, use ReportLab's XML markup tags in Paragraph objects:

```python
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet

styles = getSampleStyleSheet()

# Subscripts: use <sub> tag
chemical = Paragraph("H<sub>2</sub>O", styles['Normal'])

# Superscripts: use <super> tag
squared = Paragraph("x<super>2</super> + y<super>2</super>", styles['Normal'])
```

For canvas-drawn text (not Paragraph objects), manually adjust font the size and position rather than using Unicode subscripts/superscripts.

## Command-Line Tools

### pdftotext (poppler-utils)

```bash
# Extract text
pdftotext input.pdf output.txt

# Extract text preserving layout
pdftotext -layout input.pdf output.txt

# Extract specific pages
pdftotext -f 1 -l 5 input.pdf output.txt  # Pages 1-5
```

### qpdf

```bash
# Merge PDFs
qpdf --empty --pages file1.pdf file2.pdf -- merged.pdf

# Split pages
qpdf input.pdf --pages . 1-5 -- pages1-5.pdf
qpdf input.pdf --pages . 6-10 -- pages6-10.pdf

# Rotate pages
qpdf input.pdf output.pdf --rotate=+90:1  # Rotate page 1 by 90 degrees

# Remove password
qpdf --password=mypassword --decrypt encrypted.pdf decrypted.pdf
```

### pdftk (if available)

```bash
# Merge
pdftk file1.pdf file2.pdf cat output merged.pdf

# Split
pdftk input.pdf burst

# Rotate
pdftk input.pdf rotate 1east output rotated.pdf
```

## Common Tasks

### Extract Text from Scanned PDFs (Strictly via Vision Model)

**CRITICAL RULE:** Do NOT write scripts using `tesseract`, `pytesseract`, or any local OCR libraries.
You must divide the task into two rigorous steps: First, run a Python script to convert the PDF to images. Second, use your native Vision/Multimodal capabilities to read the images.

#### Step 1: Run this Python script to safely extract high-res images

```python
# Requires: pip install pypdfium2
import os
import pypdfium2 as pdfium

def extract_pdf_to_images(pdf_path, output_dir="pdf_images", scale=2):
    """
    Safely converts a scanned PDF into PNG images page by page.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Cannot find PDF file: {pdf_path}")

    os.makedirs(output_dir, exist_ok=True)
    image_paths = []

    try:
        # Load PDF
        pdf = pdfium.PdfDocument(pdf_path)
        total_pages = len(pdf)
        print(f"Successfully loaded '{pdf_path}' with {total_pages} pages.")

        for i in range(total_pages):
            page = pdf[i]
            # Use zero-padded filenames for correct sorting (e.g., page_001.png)
            image_path = os.path.join(output_dir, f"page_{i+1:03d}.png")

            # Render and save
            pil_image = page.render(scale=scale).to_pil()
            pil_image.save(image_path, format="PNG")
            image_paths.append(image_path)

            print(f"Saved: {image_path}")

        print("\n[SUCCESS] All pages rendered. Proceed to Step 2 using Vision Tool.")
        return image_paths

    except Exception as e:
        print(f"[ERROR] Failed to process PDF: {str(e)}")
        raise e
    finally:
        # Strictly ensure the document is closed to free memory
        if 'pdf' in locals():
            pdf.close()

# Execute the extraction (Modify 'scanned.pdf' to your actual file name)
if __name__ == "__main__":
    extract_pdf_to_images("scanned.pdf", output_dir="pdf_pages_output")
```

#### Step 2: Extract text using Vision Tool (Iterative Process)

Once the images are generated in the `pdf_pages_output` directory, **DO NOT write another Python script for OCR.**
Instead, take these actions:

1. Use your built-in Vision/Multimodal tool to read the generated `.png` files.
2. For long documents (e.g., 60 pages), process them in small batches (e.g., 3-5 pages at a time) to prevent context overflow.
3. Immediately append the text results from your Vision tool into a local `extracted_text.txt` file (using bash `echo` or a simple Python file writer).
4. Repeat the process until all images in the folder are processed.

### Add Watermark

```python
from pypdf import PdfReader, PdfWriter

# Create watermark (or load existing)
watermark = PdfReader("watermark.pdf").pages[0]

# Apply to all pages
reader = PdfReader("document.pdf")
writer = PdfWriter()

for page in reader.pages:
    page.merge_page(watermark)
    writer.add_page(page)

with open("watermarked.pdf", "wb") as output:
    writer.write(output)
```

### Extract Images

```bash
# Using pdfimages (poppler-utils)
pdfimages -j input.pdf output_prefix

# This extracts all images as output_prefix-000.jpg, output_prefix-001.jpg, etc.
```

### Password Protection

```python
from pypdf import PdfReader, PdfWriter

reader = PdfReader("input.pdf")
writer = PdfWriter()

for page in reader.pages:
    writer.add_page(page)

# Add password
writer.encrypt("userpassword", "ownerpassword")

with open("encrypted.pdf", "wb") as output:
    writer.write(output)
```

## Quick Reference

| Task               | Best Tool                       | Command/Code                                          |
| ------------------ | ------------------------------- | ----------------------------------------------------- |
| Merge PDFs         | pypdf                           | `writer.add_page(page)`                               |
| Split PDFs         | pypdf                           | One page per file                                     |
| Extract text       | pdfplumber                      | `page.extract_text()`                                 |
| Extract tables     | pdfplumber                      | `page.extract_tables()`                               |
| Create PDFs        | reportlab                       | Canvas or Platypus                                    |
| Command line merge | qpdf                            | `qpdf --empty --pages ...`                            |
| OCR scanned PDFs   | pypdfium2 + Vision Model        | Render to PNG -> Vision Model (STRICTLY NO Tesseract) |
| Fill PDF forms     | pdf-lib or pypdf (see FORMS.md) | See FORMS.md                                          |

## Next Steps

- For advanced pypdfium2 usage, see REFERENCE.md
- For JavaScript libraries (pdf-lib), see REFERENCE.md
- If you need to fill out a PDF form, follow the instructions in FORMS.md
- For troubleshooting guides, see REFERENCE.md
