#!/usr/bin/env python3
"""Quick test to see if Gemini API works"""

from dotenv import load_dotenv
import os
import sys

print("1️⃣  Loading environment...")
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ GEMINI_API_KEY not set in .env!")
    sys.exit(1)
    
print(f"✅ API key found (length: {len(api_key)})")

print("2️⃣  Initializing Gemini...")

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.prompts import PromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    print("✅ Imports successful")
except Exception as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

try:
    print("3️⃣  Creating LLM client...")
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.7,
        convert_system_message_to_human=True
    )
    print("✅ LLM client created")
except Exception as e:
    print(f"❌ Failed to create LLM: {e}")
    sys.exit(1)

try:
    print("4️⃣  Creating prompt chain...")
    prompt_template = PromptTemplate(template="{input}", input_variables=["input"])
    chain = prompt_template | llm | StrOutputParser()
    print("✅ Chain created")
except Exception as e:
    print(f"❌ Failed to create chain: {e}")
    sys.exit(1)

try:
    print("5️⃣  Testing with simple prompt (this will call Gemini API)...")
    print("    ⏳ Waiting for response...")
    result = chain.invoke({"input": "Say 'Hello from Gemini' briefly in one sentence"})
    print(f"✅ Success! Gemini response:\n   {result}")
except Exception as e:
    print(f"❌ Failed to invoke chain: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n🎉 All tests passed! The Gemini API is working correctly.")
