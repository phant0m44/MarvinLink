from flask import Flask, request
import time

app = Flask(__name__)

@app.route('/upload', methods=['POST'])
def upload():
    data = request.data
    fname = time.strftime("upload_%Y%m%d_%H%M%S.wav")
    with open(f"uploads/{fname}", "wb") as f:
        f.write(data)
    print(f"[SAVED] {fname} ({len(data)} bytes)")
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
