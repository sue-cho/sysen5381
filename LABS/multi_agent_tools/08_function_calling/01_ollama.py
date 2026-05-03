# 01_ollama.py
# Launch Ollama from Python
# Pairs with 01_ollama.sh / 01_ollama.R
# Tim Fraser (Python adaptation)

# Launch on powershell with:
# python 08_function_calling/01_ollama.py

# This script configures environment variables for Ollama,
# then starts `ollama serve` in the background without blocking
# the Python session. Useful for starting a local LLM server
# from within Python notebooks or scripts.

import os
import shutil
import subprocess
import time

# 0. Setup #################################

## 0.1 Resolve Ollama binary ####################

# macOS app bundle is often not on PATH when Python runs from an IDE or conda env.
def resolve_ollama_exe():
    candidates = [
        "/Applications/Ollama.app/Contents/Resources/ollama",
        "/Applications/Ollama.app/Contents/MacOS/ollama",
    ]
    for path in candidates:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    which = shutil.which("ollama")
    if which:
        return which
    raise FileNotFoundError(
        "Ollama not found. Install from https://ollama.com/download "
        "or add `ollama` to your PATH."
    )


OLLAMA_EXE = resolve_ollama_exe()

## 0.2 Configuration ############################

PORT = 11434  # Match 01_ollama.sh
OLLAMA_HOST = f"0.0.0.0:{PORT}"
OLLAMA_CONTEXT_LENGTH = 32000

# Set environment variables for this process and any child processes
os.environ["OLLAMA_HOST"] = OLLAMA_HOST
os.environ["OLLAMA_CONTEXT_LENGTH"] = str(OLLAMA_CONTEXT_LENGTH)

## 0.3 Start Ollama Server #######################

# Start `ollama serve` in the background.
# stdout/stderr are redirected to DEVNULL so the console is not flooded.
process = subprocess.Popen(
    [OLLAMA_EXE, "serve"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

# Give the server a moment to start listening before use
time.sleep(1)

# Optional: you can keep a reference to `process` if you want to stop it later
# For example:
# process.terminate()  # or process.kill()

# On Windows, from a separate shell you can also stop it with:
#   taskkill /F /IM ollama.exe