import requests
import re

OLLAMA_URL = "http://localhost:11434/api/generate"

def text_query_response(user_input):
    """
    Sends the user's query to the LLM model and returns a helpful response.
    """
    prompt = f"""You are a helpful assistant. Please respond to the user query:

{user_input}

Response:"""

    data = {
        "model": "gemma3:1b",
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_URL, json=data)
        result = response.json()
        output = result.get("response", "").strip()
        return output
    
    except Exception as e:
        return f"Error generating response: {str(e)}"

# For direct module testing
if __name__ == "__main__":
    query = input("Enter your query: ")
    print("Assistant Response:", text_query_response(query))
