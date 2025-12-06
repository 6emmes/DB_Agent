from flask import Flask, request, jsonify
import requests
import json
import calculator as CAL
import io

app = Flask(__name__)

OLLAMA_API_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen3:8b"

SYSTEM_PROMPT = {
    "role": "system",
    "content": """You are a helpful assistant. You can call tools when needed.
    Results from tools are to be fully trusted and can be used in your responses.

Tools:
[
  {
  "name": "count_items_by_tag",
  "description": "Counts the number of items in the Database with a specific tag.",
  "parameters": {
    "type": "object",
    "properties": {
      "tag": {
        "type": "string",
        "description": "The tag to search for in the Database."
      }
    },
    "required": ["tag"]
  },
  "run": "count_items_by_tag"
}


]

When the user asks to run the tool, respond with a tool_call using the correct name and parameters. Do not hallucinate the result — wait for the tool response before continuing.

Example tool call:
{
  "tool_calls": [
    {
      "id": CALL_ID,
      "name": TOOL_NAME,
      "parameters": {}
    }
  ]
}
End of example
"""
}

def count_items_by_tag(tag: str) -> int:
    headers = {
        "Hydrus-Client-API-Access-Key": ""
    }
    params = {
        "tags": f'["{tag}"]'
    }
    response = requests.get(f"{"http://127.0.0.1:45870"}/get_files/search_files", headers=headers, params=params)
    response.raise_for_status()
    data = response.json()
    return len(data.get("file_ids", []))


@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message", "")
    if not user_input:
        return jsonify({"error": "Missing 'message' in request"}), 400

    # Step 1: Initial request to Qwen
    messages = [
        SYSTEM_PROMPT,
        {"role": "user", "content": user_input}
    ]

    try:
        response = requests.post(OLLAMA_API_URL, json={
            "model": MODEL_NAME,
            "messages": messages
        }, stream=True)
        response.raise_for_status()

        full_reply = ""
        tool_calls = []

        
        tool_calls = []
        full_reply = ""
        buffer = io.StringIO()
        for line in response.iter_lines():
            if line:
                decoded = line.decode("utf-8")
                chunk = json.loads(decoded)
                message = chunk.get("message", {})
                content = message.get("content", "")
                if len(content) > 0:
                    print("Ollama response chunk:", content)
                    buffer.write(content)

        # Now parse the full JSON from the buffer
        buffer.seek(0)
        print("Raw buffer:", buffer.getvalue())

        for raw in buffer.getvalue().split("\n\n") :
            try:
                chunk = json.loads(raw)
                content = chunk.get("message", {}).get("content", "")
                full_reply += content

                if "tool_calls" in chunk:
                    tool_calls.extend(chunk["tool_calls"])
            except json.JSONDecodeError as e:
                print("Skipping malformed chunk:", raw)

        # Step 2: If tool was called, execute it
        if tool_calls:
            tool_results = []
            for call in tool_calls:
                if call["name"] == "count_items_by_tag":
                    tag = call["parameters"].get("tag", "")
                    result = count_items_by_tag(tag)
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "name": "count_items_by_tag",
                        "content": json.dumps({"result": result})
                    })

            # Step 3: Send tool result back to Qwen
            messages += [
                {"role": "assistant", "tool_calls": tool_calls},
                *tool_results
            ]

            response2 = requests.post(OLLAMA_API_URL, json={
                "model": MODEL_NAME,
                "messages": messages
            }, stream=True)
            response2.raise_for_status()

            final_reply = ""
            for line in response2.iter_lines():
                if line:
                    chunk = json.loads(line.decode("utf-8"))
                    final_reply += chunk.get("message", {}).get("content", "")

            return jsonify({"response": final_reply})

        # No tool call — return initial reply
        return jsonify({"response": full_reply})

    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 500
    except json.JSONDecodeError as e:
        return jsonify({"error": f"JSON decode error: {str(e)}"}), 500


@app.route("/tool", methods=["GET"])
def tool_endpoint():
    return jsonify(tool())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
