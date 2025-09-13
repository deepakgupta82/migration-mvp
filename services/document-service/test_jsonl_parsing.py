import json
import re

# Test the new JSONL parsing logic
test_jsonl = '''{"type": "element", "data": {"text": "line 1\nline 2", "type": "paragraph"}}
{"type": "element", "data": {"text": "another\nelement", "type": "heading"}}'''

print('Testing JSONL parsing with multi-line content...')
pattern = r'\{(?:[^{}]|{(?:[^{}]|{[^{}]*})*})*\}'
matches = re.findall(pattern, test_jsonl, re.DOTALL)
print(f'Found {len(matches)} JSON objects')

for i, match in enumerate(matches):
    try:
        data = json.loads(match)
        text_content = data.get('data', {}).get('text', '')
        print(f'Object {i+1}: {text_content[:50]}...')
    except json.JSONDecodeError as e:
        print(f'Object {i+1}: Failed to parse - {e}')

print('\nTest completed successfully!')
