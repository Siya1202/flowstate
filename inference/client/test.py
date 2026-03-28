import requests

def test_ollama():
    url = "http://localhost:11434/api/chat"
    response = requests.post(
        url,
        json={
            "model": "mistral:7b-instruct",
            "messages": [{"role": "user", "content": "Test Ollama inference"}]
        }
    )
    return response.json()

if __name__ == "__main__":
    print(test_ollama())
