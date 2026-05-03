# 01_ollama.sh - Ollama Startup Script
# Serves Ollama on a specific port, pulls a small model, runs it, and provides stop controls
# 🛑🌐🤖📡🚀
# Load your local paths and variables
source .bashrc



# If you haven't yet, let's pull this model:
MODEL="smollm2:1.7b"  # medium model (1.7 GB)
# Pull model of interest
# ollama pull $MODEL


# Configuration
PORT=11434  # Default Ollama port (change as needed)
# Set environment variable for port
export OLLAMA_HOST="0.0.0.0:$PORT"
SERVER_PID=""
MODEL_PID=""

# Start server in background, and assign the process ID to the SERVER_PID variable
ollama serve > /dev/null 2>&1 & SERVER_PID=$!
# View the process ID of ollama
echo $SERVER_PID


# Need to kill the server and model if they are running? These might help.
# kill $SERVER_PID 2>/dev/null
# pkill -f "ollama serve" 2>/dev/null
# pkill -f "ollama run" 2>/dev/null
