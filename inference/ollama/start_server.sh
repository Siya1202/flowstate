#!/bin/bash
mkdir -p ../logs  # Ensure logs folder exists
ollama serve >> ../logs/ollama.log 2>&1