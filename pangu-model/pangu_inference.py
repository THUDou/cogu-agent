import sys
import json
import os

MODEL_DIR = os.environ.get("PANGU_MODEL_DIR", "")
MAX_NEW_TOKENS = int(os.environ.get("PANGU_MAX_NEW_TOKENS", "512"))

def main():
    sys.path.insert(0, MODEL_DIR)
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_DIR, use_fast=False, trust_remote_code=True, local_files_only=True
    )
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_DIR, trust_remote_code=True, torch_dtype="auto", device_map="auto", local_files_only=True
    )

    print("READY", flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        if line == "EXIT":
            break
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        prompt = req.get("prompt", "")
        system = req.get("system", "")
        max_new_tokens = req.get("max_new_tokens", MAX_NEW_TOKENS)

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

        outputs = model.generate(**model_inputs, max_new_tokens=max_new_tokens, eos_token_id=45892)
        input_length = model_inputs.input_ids.shape[1]
        generated_tokens = outputs[0, input_length:]
        content = tokenizer.decode(generated_tokens, skip_special_tokens=True)

        resp = json.dumps({"content": content}, ensure_ascii=False)
        print(resp, flush=True)

if __name__ == "__main__":
    main()