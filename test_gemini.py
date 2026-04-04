import os
from dotenv import load_dotenv
from tradingagents.llm_clients.factory import create_llm_client
from langchain_core.messages import HumanMessage

def test_gemini():
    load_dotenv()
    print("Testing Gemini integration...")
    print(f"Provider: {os.getenv('LLM_PROVIDER')}")
    print(f"Model: {os.getenv('LLM_MODEL')}")
    
    # Check if API key is loaded
    if not os.getenv('GOOGLE_API_KEY'):
        print("❌ Error: GOOGLE_API_KEY is not set in environment or .env file.")
        return
        
    try:
        # Create LLM client through the factory just like the system does
        client = create_llm_client(
            provider="google",
            model="gemini-2.0-flash",
            google_api_key=os.getenv('GOOGLE_API_KEY')
        )
        
        # Invoke a simple prompt (simulating the system's process)
        llm = client.get_llm()
        response = llm.invoke([HumanMessage(content="Hello! Are you Gemini 2.0 Flash? Respond with a short sentence.")])
        
        print("\n✅ Success! Gemini is working perfectly.")
        print("System response ->", response.content)
        
    except Exception as e:
        print(f"\n❌ Execution Failed: {e}")

if __name__ == "__main__":
    test_gemini()
