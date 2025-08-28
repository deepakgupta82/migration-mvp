#!/usr/bin/env python3
"""
Debug JSONL Structure
Quick script to examine the JSONL file and understand the data structure
"""
import asyncio
import json
import httpx

async def debug_jsonl():
    project_id = "7d1e347c-efdd-4bc5-a112-98ec17fdf31c"
    filename = "Sevenseas HPE Servers 2025_structured.jsonl"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"http://localhost:8010/api/storage/projects/{project_id}/download/structured/{filename}",
                headers={"Authorization": "Bearer service-backend-token"}
            )
            
            if response.status_code == 200:
                content = response.text
                print(f"✅ JSONL file found: {len(content)} characters")
                
                lines = content.strip().split('\n')
                print(f"📄 Number of lines: {len(lines)}")
                
                text_found = 0
                content_found = 0
                
                # Analyze first 10 lines to understand structure
                for i, line in enumerate(lines[:10]):
                    if line.strip():
                        try:
                            element = json.loads(line)
                            print(f"\n🔍 Line {i+1}:")
                            print(f"   Keys: {list(element.keys())}")
                            
                            # Check for text content
                            if "text" in element and element["text"]:
                                text_found += 1
                                text_content = element["text"]
                                print(f"   ✅ text: '{text_content[:100]}{'...' if len(text_content) > 100 else ''}'")
                            else:
                                print(f"   ❌ No 'text' field or empty")
                            
                            # Check for content field
                            if "content" in element and element["content"]:
                                content_found += 1
                                content_content = element["content"]
                                print(f"   ✅ content: '{content_content[:100]}{'...' if len(content_content) > 100 else ''}'")
                            else:
                                print(f"   ❌ No 'content' field or empty")
                            
                            # Check element type
                            if "type" in element:
                                print(f"   📋 type: {element['type']}")
                            
                            # Check metadata
                            if "metadata" in element:
                                print(f"   📊 metadata keys: {list(element['metadata'].keys()) if isinstance(element['metadata'], dict) else 'not dict'}")
                            
                        except json.JSONDecodeError as e:
                            print(f"   ❌ JSON parse error: {e}")
                        except Exception as e:
                            print(f"   ❌ Error: {e}")
                
                print(f"\n📊 Summary:")
                print(f"   Lines with 'text' field: {text_found}")
                print(f"   Lines with 'content' field: {content_found}")
                print(f"   Total lines examined: {min(10, len(lines))}")
                
                # Count total text/content across all lines
                total_text_elements = 0
                total_content_elements = 0
                
                for line in lines:
                    if line.strip():
                        try:
                            element = json.loads(line)
                            if "text" in element and element["text"]:
                                total_text_elements += 1
                            if "content" in element and element["content"]:
                                total_content_elements += 1
                        except:
                            pass
                
                print(f"\n🔢 Full file statistics:")
                print(f"   Total elements with text: {total_text_elements}")
                print(f"   Total elements with content: {total_content_elements}")
                
            else:
                print(f"❌ Error fetching JSONL: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    asyncio.run(debug_jsonl())