import requests

GEMINI_API_KEY = "AIzaSyBxs4bx9nfsoxIgRDXMl164ycysfrjx4lQ"
LIST_MODELS_URL = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"

response = requests.get(LIST_MODELS_URL)
print(response.json())