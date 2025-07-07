from pathlib import Path
import fitz

path = Path("../../data/23939_trump_v_us.pdf")
title = path.stem

doc = fitz.open(path)

output_path = Path(f"{title}_output.txt")
out = open(output_path, "wb")

for page in doc:
    text = page.get_text().encode("utf8")
    out.write(text)
    out.write(bytes((12,)))
out.close()
