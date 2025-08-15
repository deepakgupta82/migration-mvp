#!/usr/bin/env python3
"""
Simple direct test of Gemini LLM with both LangChain and direct API
"""

import os
import sys
from dotenv import load_dotenv

# Load environment
load_dotenv()

def test_direct_gemini_api():
    """Test direct Google Generative AI"""
    print("🔥 Testing Direct Gemini API")
    print("-" * 30)
    
    try:
        import google.generativeai as genai
        
        api_key = os.environ.get('GOOGLE_API_KEY')
        if not api_key:
            print("❌ No GOOGLE_API_KEY found")
            return False
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        test_prompt = """Extract IT entities from this text and return as JSON:

Web Server: Apache HTTP Server 2.4 on RHEL 8 at 192.168.1.10
Database: Oracle 19c at 192.168.1.20  
Switch: Cisco Catalyst 6500

Format: {"entities": ["entity1", "entity2"], "relationships": []}"""

        print(f"📝 Sending prompt: {test_prompt[:100]}...")
        
        response = model.generate_content(test_prompt)
        
        print(f"✅ Direct API Response Type: {type(response)}")
        print(f"✅ Response Text: {response.text}" if hasattr(response, 'text') else "❌ No text attribute")
        
        if hasattr(response, 'text') and response.text:
            print("🎉 DIRECT GEMINI API WORKS!")
            return True
        else:
            print("❌ DIRECT GEMINI API FAILED - No text")
            return False
            
    except Exception as e:
        print(f"❌ Direct API Error: {e}")
        return False

def test_langchain_gemini():
    """Test LangChain Gemini wrapper"""
    print("\n🔗 Testing LangChain Gemini Wrapper")  
    print("-" * 35)
    
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage
        
        api_key = os.environ.get('GOOGLE_API_KEY')
        
        # Create LangChain instance
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key,
            temperature=0.1
        )
        
        print(f"✅ LangChain LLM Created: {type(llm)}")
        print(f"✅ Model: {getattr(llm, 'model', 'unknown')}")
        
        # Test message
        test_message = HumanMessage(content="""Extract IT entities from this text:

Web Server: Apache HTTP Server 2.4 on RHEL 8 at 192.168.1.10
Database: Oracle 19c at 192.168.1.20
Switch: Cisco Catalyst 6500

Return as JSON: {"entities": ["entity1", "entity2"]}""")

        print("📝 Sending LangChain message...")
        
        response = llm.invoke([test_message])
        
        print(f"📦 LangChain Response Type: {type(response)}")
        print(f"📦 Response has content attr: {hasattr(response, 'content')}")
        
        if hasattr(response, 'content'):
            print(f"📦 Response content: '{response.content}'")
            print(f"📦 Content length: {len(response.content or '')}")
            
            if response.content and response.content.strip():
                print("🎉 LANGCHAIN GEMINI WORKS!")
                return True
            else:
                print("❌ LANGCHAIN GEMINI FAILED - Empty content")
                print(f"📦 Full response object: {response}")
                return False
        else:
            print("❌ LANGCHAIN GEMINI FAILED - No content attribute")
            print(f"📦 Response attributes: {dir(response)}")
            return False
            
    except Exception as e:
        print(f"❌ LangChain Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🚀 Gemini LLM Debugging Script")
    print("=" * 40)
    
    # Check API key
    api_key = os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        print("❌ GOOGLE_API_KEY not found in environment")
        return
    
    print(f"✅ API Key loaded: {api_key[:10]}...")
    print()
    
    # Test both approaches
    direct_works = test_direct_gemini_api()
    langchain_works = test_langchain_gemini()
    
    print("\n" + "=" * 40)
    print("🎯 DIAGNOSIS SUMMARY")
    print("=" * 40)
    
    if direct_works and langchain_works:
        print("✅ BOTH APIs WORK - No issues found!")
    elif direct_works and not langchain_works:
        print("⚠️  DIRECT API WORKS, LANGCHAIN FAILS")
        print("   Problem: LangChain wrapper issue")
        print("   Solution: Check LangChain configuration")
    elif not direct_works and langchain_works:
        print("⚠️  LANGCHAIN WORKS, DIRECT API FAILS")
        print("   Problem: Direct API setup issue")
    elif not direct_works and not langchain_works:
        print("❌ BOTH APIS FAIL")
        print("   Problem: API key or network issue")
        print("   Solution: Check API key and connectivity")
    else:
        print("❓ Unexpected result combination")

if __name__ == "__main__":
    main()
