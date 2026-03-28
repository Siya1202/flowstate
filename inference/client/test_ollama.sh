#!/bin/bash
curl http://localhost:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{"model": "mistral:7b-instruct", "messages": [{"role": "user", "content": "Test Ollama"}]}'
