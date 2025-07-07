import os
import torch
from tqdm import tqdm
from transformers import AutoTokenizer, AutoModelForCausalLM

# -----------------------------------------------
# 🔧 Configuration
# -----------------------------------------------
INPUT_DIR = "data/intermediate"
OUTPUT_DIR = "data/output"
MODEL_PATH = "models/phi-2"
PROMPT_PATH = "prompt_template.txt"
MAX_PROMPT_TOKENS = 1024   # ⬅️ Reduced for performance
MAX_GEN_TOKENS = 256       # ⬅️ Reduced for faster & safer generation

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# -----------------------------------------------
# 📄 Load Prompt Template
# -----------------------------------------------
def load_prompt_template():
    print("[DEBUG] Loading prompt template...")
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()

# -----------------------------------------------
# 🧠 Clean citation candidates using Phi-2
# -----------------------------------------------
def clean_with_phi2(text, prompt_template, model, tokenizer, device):
    prompt = prompt_template.replace("{{TEXT}}", text)

    # Tokenize and show token count
    print("[DEBUG] Tokenizing prompt...")
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=MAX_PROMPT_TOKENS).to(device)
    input_token_count = inputs['input_ids'].shape[-1]
    print(f"[INFO] Prompt token count: {input_token_count}/{MAX_PROMPT_TOKENS}")

    # Generate safely with no_grad
    try:
        print("[DEBUG] Generating model output...")
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=MAX_GEN_TOKENS,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
                use_cache=False,  # ⬅️ Reduces memory footprint
                return_dict_in_generate=True
            )
    except RuntimeError as e:
        print("[ERROR] Generation failed due to memory limits:", e)
        return "[ERROR] Generation failed."

    generated_token_count = outputs.sequences.shape[-1] - input_token_count
    print(f"[INFO] Generated token count: {generated_token_count}/{MAX_GEN_TOKENS}")

    decoded = tokenizer.decode(outputs.sequences[0], skip_special_tokens=True)
    return decoded.split("Text:")[-1].strip() if "Text:" in decoded else decoded.strip()

# -----------------------------------------------
# 🚀 Main Pipeline
# -----------------------------------------------
def main():
    print("[INFO] Loading Phi-2 model...")
    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"[INFO] Using device: {device}")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH,
        torch_dtype=torch.float16 if device != "cpu" else torch.float32
    ).to(device)

    prompt_template = load_prompt_template()

    files = [f for f in os.listdir(INPUT_DIR) if f.endswith("_candidates.txt")]

    for filename in tqdm(files, desc="Processing files"):
        title = filename.replace("_candidates.txt", "")
        input_path = os.path.join(INPUT_DIR, filename)

        print(f"\n[DEBUG] Processing: {title}")
        with open(input_path, "r", encoding="utf-8") as f:
            text = f.read()

        cleaned = clean_with_phi2(text, prompt_template, model, tokenizer, device)

        output_path = os.path.join(OUTPUT_DIR, f"{title}_final.txt")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(cleaned)

        print(f"[INFO] ✅ Final citations saved to: {output_path}")

# -----------------------------------------------
# 🔧 Run
# -----------------------------------------------
if __name__ == "__main__":
    main()
