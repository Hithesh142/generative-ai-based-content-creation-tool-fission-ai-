import requests

def summarize_text(text):
    url = "http://localhost:11434/api/generate"
    prompt = f"Summarize the following text:\n\n{text}"

    data = {
        "model": "gemma3:1b",  # or gemma3:1b
        "prompt": prompt,
        "stream": False
    }

    response = requests.post(url, json=data)
    result = response.json()
    return result.get("response", "").strip()
