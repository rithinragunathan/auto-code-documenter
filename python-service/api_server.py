"""
Flask API Server for Code Analysis using Gemini LLM
Receives code from Spring Boot and returns analysis
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
from pathlib import Path
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for Spring Boot communication

# Global config
LLM_MODEL = "gemini-2.5-flash"
PORT = 5000

# Initialize LLM client
def init_llm_client():
    """Initialize LangChain ChatGoogleGenerativeAI client."""
    try:
        llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            temperature=0.7,
            convert_system_message_to_human=True
        )
        return llm
    except Exception as e:
        print(f"❌ Failed to initialize Gemini client: {e}")
        print("   Ensure .env file has GOOGLE_API_KEY set.")
        return None

# Initialize LLM
llm_client = init_llm_client()


def build_prompt(code: str, language: str, prompt: str, request_type: str) -> str:
    """Build the prompt based on analysis type."""
    
    base_prompts = {
        "documentation": f"""You are an expert software engineer and technical writer.
Analyze the following {language} code and generate comprehensive documentation.
Focus on what the code does, its purpose, and how to use it.

Code:
```{language}
{code}
```

{f"Additional instructions: {prompt}" if prompt else ""}

Please provide clear, professional documentation.""",

        "review": f"""You are an expert code reviewer.
Perform a thorough code review of the following {language} code.
Point out issues, potential bugs, improvements, and best practices.

Code:
```{language}
{code}
```

{f"Additional instructions: {prompt}" if prompt else ""}

Provide a constructive review with actionable suggestions.""",

        "optimization": f"""You are a performance optimization expert.
Analyze the following {language} code and suggest optimizations.
Focus on performance improvements, memory efficiency, and best practices.

Code:
```{language}
{code}
```

{f"Additional instructions: {prompt}" if prompt else ""}

Provide specific optimization recommendations.""",

        "bug_fix": f"""You are a debugging expert.
Analyze the following {language} code for potential bugs.
Identify issues, edge cases, and provide fixes.

Code:
```{language}
{code}
```

{f"Additional instructions: {prompt}" if prompt else ""}

List all potential bugs and suggest fixes.""",
    }
    
    return base_prompts.get(request_type.lower(), base_prompts["documentation"])


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "UP",
        "service": "AutoDocx Python LLM Service",
        "model": LLM_MODEL,
        "llm_initialized": llm_client is not None
    })


@app.route('/api/analyze', methods=['POST'])
def analyze_code():
    """
    Main analysis endpoint.
    
    Expected JSON:
    {
        "code": "code content",
        "language": "python|javascript|java|etc",
        "request_type": "documentation|review|optimization|bug_fix",
        "prompt": "optional custom instructions"
    }
    """
    try:
        data = request.json
        
        # Validate input
        if not data:
            return jsonify({"error": "No JSON body provided"}), 400
        
        code = data.get('code', '').strip()
        language = data.get('language', 'python').strip()
        request_type = data.get('request_type', 'documentation').strip()
        prompt = data.get('prompt', '').strip()
        
        if not code:
            return jsonify({"error": "Code parameter is required"}), 400
        
        # Check if LLM is initialized
        if not llm_client:
            return jsonify({
                "error": "LLM client not initialized. Check GOOGLE_API_KEY environment variable."
            }), 500
        
        # Build the prompt
        print(f"📝 Building prompt for {language} ({request_type})...")
        full_prompt = build_prompt(code, language, prompt, request_type)
        
        # Create chain
        print("🔗 Creating LangChain...")
        prompt_template = PromptTemplate(template="{input}", input_variables=["input"])
        chain = prompt_template | llm_client | StrOutputParser()
        
        # Run analysis
        print(f"🔍 Analyzing {language} code ({request_type})... (this may take 10-30 seconds)")
        import sys
        sys.stdout.flush()
        
        result = chain.invoke({"input": full_prompt})
        
        print(f"✨ Analysis complete!")
        
        # Return response
        return jsonify({
            "id": data.get('id', 'generated'),
            "code": code,
            "language": language,
            "request_type": request_type,
            "analysis": result,
            "status": "SUCCESS"
        }), 200
    
    except Exception as e:
        print(f"❌ Error in /api/analyze: {type(e).__name__}: {str(e)}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": str(e),
            "status": "ERROR"
        }), 500


@app.route('/api/analyze-batch', methods=['POST'])
def analyze_batch():
    """
    Batch analysis endpoint for multiple code snippets.
    
    Expected JSON:
    {
        "analyses": [
            {
                "code": "code content",
                "language": "python",
                "request_type": "documentation"
            }
        ]
    }
    """
    try:
        data = request.json
        
        if not data or 'analyses' not in data:
            return jsonify({"error": "analyses array is required"}), 400
        
        analyses = data['analyses']
        results = []
        
        for idx, analysis in enumerate(analyses):
            try:
                code = analysis.get('code', '').strip()
                language = analysis.get('language', 'python').strip()
                request_type = analysis.get('request_type', 'documentation').strip()
                prompt = analysis.get('prompt', '').strip()
                
                if not code:
                    results.append({
                        "id": idx,
                        "status": "ERROR",
                        "error": "Code is required"
                    })
                    continue
                
                full_prompt = build_prompt(code, language, prompt, request_type)
                prompt_template = PromptTemplate(template="{input}", input_variables=["input"])
                chain = prompt_template | llm_client | StrOutputParser()
                result = chain.invoke({"input": full_prompt})
                
                results.append({
                    "id": idx,
                    "analysis": result,
                    "status": "SUCCESS"
                })
            except Exception as e:
                results.append({
                    "id": idx,
                    "status": "ERROR",
                    "error": str(e)
                })
        
        return jsonify({"results": results}), 200
    
    except Exception as e:
        print(f"❌ Error in /api/analyze-batch: {str(e)}")
        return jsonify({
            "error": str(e),
            "status": "ERROR"
        }), 500


if __name__ == '__main__':
    print(f"""
    ╔════════════════════════════════════════╗
    ║   AutoDocx Python LLM Service          ║
    ║   Powered by Google Gemini             ║
    ╚════════════════════════════════════════╝
    
    🚀 Starting server on http://localhost:{PORT}
    📡 Available endpoints:
       - GET /health
       - POST /api/analyze
       - POST /api/analyze-batch
    
    ⚠️  Make sure GOOGLE_API_KEY is set in .env
    """)
    
    app.run(host='127.0.0.1', port=PORT, debug=True)
