import httpx

print("Testing non-streaming request...")
res = httpx.post(
    'http://localhost:8000/v1/chat/completions',
    json={
        'model': 'auto',
        'messages': [{'role': 'user', 'content': 'hello, who are you?'}]
    },
    timeout=60.0
)
print(f"Status Code: {res.status_code}")
print(f"Response: {res.text}")

print("\nTesting streaming request...")
with httpx.stream(
    "POST",
    'http://localhost:8000/v1/chat/completions',
    json={
        'model': 'auto',
        'stream': True,
        'messages': [{'role': 'user', 'content': 'count to 3 slowly'}]
    },
    timeout=60.0
) as res2:
    print(f"Stream Status: {res2.status_code}")
    for chunk in res2.iter_text():
        print(chunk, end="", flush=True)

print("\n\nChecking available models...")
res3 = httpx.get('http://localhost:8000/v1/models')
print(res3.json())

print("\nChecking health endpoint for exhausted models list...")
res4 = httpx.get('http://localhost:8000/health')
print(res4.json())
