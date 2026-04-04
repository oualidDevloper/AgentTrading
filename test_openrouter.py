import os
from dotenv import load_dotenv
from tradingagents.llm_clients.factory import create_llm_client
from langchain_core.messages import HumanMessage

def test_openrouter():
    load_dotenv()
    print("Testing OpenRouter integration...")
    provider = "openrouter"
    model = "google/gemini-2.0-pro-exp-02-05:free"
    
    if not os.getenv('OPENROUTER_API_KEY'):
        print("❌ Error: OPENROUTER_API_KEY is not set.")
        return
        
    try:
        client = create_llm_client(
            provider=provider,
            model=model,
            openrouter_api_key=os.getenv('OPENROUTER_API_KEY')
        )
        
        llm = client.get_llm()
        response = llm.invoke([HumanMessage(content="Hello! Which model are you processing this with? Respond with a short sentence.")])
        
        print("\n✅ Success! OpenRouter is working perfectly.")
        print("System response ->", response.content)
        
    except Exception as e:
        print(f"\n❌ Execution Failed: {e}")

if __name__ == "__main__":
    test_openrouter()
