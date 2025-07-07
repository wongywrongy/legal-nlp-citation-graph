import os
import re
import pdfplumber

INPUT_DIR = "data/input"
INTERMEDIATE_DIR = "data/intermediate"
os.makedirs(INTERMEDIATE_DIR, exist_ok=True)

# Simple regex pattern for "Name v. Name" style
CASE_REGEX = re.compile(r"\b([A-Z][\w&.,'’\- ]+ v\. [A-Z][\w&.,'’\- ]+)\b")

def extract_case_names(text):
    return list(set(m.group(1).strip() for m in CASE_REGEX.finditer(text)))

def extract_from_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)

def main():
    for filename in os.listdir(INPUT_DIR):
        if not filename.endswith(".pdf"):
            continue
        title = os.path.splitext(filename)[0]
        pdf_path = os.path.join(INPUT_DIR, filename)
        print(f"[DEBUG] Extracting from: {pdf_path}")
        raw_text = extract_from_pdf(pdf_path)

        cases = extract_case_names(raw_text)
        output_path = os.path.join(INTERMEDIATE_DIR, f"{title}_candidates.txt")
        with open(output_path, "w", encoding="utf-8") as f:
            for case in cases:
                f.write(case + "\n")
        print(f"[DEBUG] Saved candidates to: {output_path}")

if __name__ == "__main__":
    main()
