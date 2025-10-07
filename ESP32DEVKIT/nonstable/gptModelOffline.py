import requests

def ask_local_gpt(prompt):
    r = requests.post("http://localhost:11434/api/generate", json={
        "model": "mistral",
        "prompt": prompt
    }, stream=False)
    return r.json()["response"]

print(ask_local_gpt("Привіт"))
