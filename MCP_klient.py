import requests
import json

def main():
    # Prompt user for input
    user_message = input("Enter your message: ")

    # Prepare the payload
    payload = {"message": user_message}
    headers = {"Content-Type": "application/json"}

    # Send POST request to Flask server
    try:
        response = requests.post("http://localhost:5000/chat", headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        print("Server response:", response.json())
    except requests.exceptions.RequestException as e:
        print("Error communicating with server:", e)

if __name__ == "__main__":
    main()
