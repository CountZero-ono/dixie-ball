import os
import json
import requests
import subprocess
from flask import Flask, request, Response, stream_with_context

app = Flask(__name__)
TARGET_URL = "http://127.0.0.1:1235"

def generate_fake_stream(message):
    """Convert a non-streamed OpenAI message into a fake SSE stream for Home Assistant."""
    yield b'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n'
    
    content = message.get('content')
    if content:
        chunk = json.dumps({"choices":[{"delta":{"content": content}}]})
        yield f'data: {chunk}\n\n'.encode('utf-8')
        
    tool_calls = message.get('tool_calls')
    if tool_calls:
        for i, tc in enumerate(tool_calls):
            # Start of tool call with name and ID
            start_chunk = {"choices":[{"delta":{"tool_calls":[{"index":i,"id":tc.get("id", ""),"type":"function","function":{"name":tc["function"]["name"],"arguments":""}}]}}]}
            yield f'data: {json.dumps(start_chunk)}\n\n'.encode('utf-8')
            # The arguments
            arg_chunk = {"choices":[{"delta":{"tool_calls":[{"index":i,"function":{"arguments":tc["function"].get("arguments", "")}}]}}]}
            yield f'data: {json.dumps(arg_chunk)}\n\n'.encode('utf-8')
            
    yield b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
    yield b'data: [DONE]\n\n'

@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        data = {}

    print("\n=== INCOMING REQUEST ===")
    user_msg = ""
    if data.get('messages'):
        user_msg = data['messages'][-1].get('content', '').strip()
        print(f"User: {user_msg}")


    if 'tools' in data:
        data['tools'].extend([
            {
                "type": "function",
                "function": {
                    "name": "run_ser7_command",
                    "description": "Execute a bash command on the SER7 host computer and return the output. Use this to run scripts or check system status.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "The exact bash command to execute"}
                        },
                        "required": ["command"]
                    }
                }
            }
        ])
        print("Injected 'run_ser7_command' tool into prompt.")

    # Force enable_thinking to false
    if 'chat_template_kwargs' not in data:
        data['chat_template_kwargs'] = {}
    data['chat_template_kwargs']['enable_thinking'] = False
    data['thinking_budget_tokens'] = 0

    headers = {k: v for k, v in request.headers if k.lower() != 'host'}
    original_stream = data.get('stream', False)
    
    # We MUST disable stream for the first request so we can intercept the tool call
    data['stream'] = False

    def make_request(payload):
        return requests.request(
            method=request.method,
            url=f"{TARGET_URL}/v1/chat/completions",
            headers=headers,
            json=payload,
            stream=False
        )

    print("Sending request to Qwen...")
    resp = make_request(data)
    
    if resp.status_code != 200:
        print(f"Error from Qwen: {resp.status_code}")
        return Response(resp.text, status=resp.status_code, headers=dict(resp.headers))

    resp_json = resp.json()
    message = resp_json.get('choices', [{}])[0].get('message', {})
    
    # INTERCEPT OUR SER7 TOOLS
    if message.get('tool_calls'):
        ser7_tool_tc = None
        for tc in message['tool_calls']:
            if tc.get('function', {}).get('name') == 'run_ser7_command':
                ser7_tool_tc = tc
                break
                
        if ser7_tool_tc:
            print(f"\n>>> INTERCEPTED SER7 COMMAND EXECUTION <<<")
            try:
                args = json.loads(ser7_tool_tc['function']['arguments'])
                cmd = args.get('command', '')
                print(f"Command: {cmd}")
                
                # Execute on the SER7
                proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                output = proc.stdout + proc.stderr
                if not output.strip():
                    output = "Command executed successfully with no output."
                print(f"Output: {output[:200]}")
            except Exception as e:
                output = f"Error executing command: {str(e)}"
                print(output)
            
            # Send the result back to Qwen for a final spoken answer!
            data['messages'].append(message)
            data['messages'].append({
                "role": "tool",
                "tool_call_id": ser7_tool_tc['id'],
                "name": "run_ser7_command",
                "content": output
            })
            
            # Make the final request
            print("Sending tool output back to Qwen for final answer...")
            final_resp = make_request(data)
            final_message = final_resp.json().get('choices', [{}])[0].get('message', {})
            
            if original_stream:
                return Response(stream_with_context(generate_fake_stream(final_message)), content_type='text/event-stream')
            else:
                return Response(final_resp.text, status=final_resp.status_code, headers=dict(final_resp.headers))


    # INTERCEPT FOR PC SPEAKERS (edge-tts)
    content_to_speak = message.get('content', '').strip()
    if content_to_speak:
        print(f"Playing TTS locally on PC: {content_to_speak[:50]}...")
        safe_content = content_to_speak.replace('"', '\\"')
        # Run edge-tts in the background so it doesn't block the HTTP response
        subprocess.Popen(f'edge-tts --voice en-US-ChristopherNeural --text "{safe_content}" | mpv -', shell=True)
        # Change the text sent back to the ball so the ball stays silent!
        message['content'] = "."

    # If no SER7 tool was called, return the response normally
    if original_stream:
        return Response(stream_with_context(generate_fake_stream(message)), content_type='text/event-stream')
    else:
        # Re-encode the modified message
        resp_json['choices'][0]['message'] = message
        return Response(json.dumps(resp_json), status=resp.status_code, headers=dict(resp.headers))

# Forward all other endpoints (like /v1/models) transparently
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy(path):
    url = f"{TARGET_URL}/{path}"
    resp = requests.request(
        method=request.method,
        url=url,
        headers={k: v for k, v in request.headers if k.lower() != 'host'},
        data=request.get_data(),
        cookies=request.cookies,
        allow_redirects=False
    )
    headers = [(name, value) for (name, value) in resp.raw.headers.items()]
    return Response(resp.content, resp.status_code, headers)

if __name__ == '__main__':
    print("Starting Llama Qwen Proxy for Dixie Ball (Port 1238) with SER7 Terminal injection...")
    app.run(host='0.0.0.0', port=1238)
