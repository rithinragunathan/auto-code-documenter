import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from ingestion import IngestionPipeline, ingest_file
import chromadb_store as db
import requests

# ═════════════════════════════════════════════════════════════════════════════
# GLOBAL CONFIG
# ═════════════════════════════════════════════════════════════════════════════
OUTPUT_FILE = "code_documentation.md"
LLM_MODEL = "gemini-2.5-flash"
DEFAULT_WEBHOOK_URL = None
WEBHOOK_TIMEOUT = 5


# ═════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def format_chunks(chunks: list[dict]) -> str:
    """Format chunk list into context string."""
    context = ""
    for chunk in chunks:
        context += f"\n--- File: {chunk.get('file_path', 'unknown')} | Type: {chunk.get('kind', 'unknown')} | Name: {chunk.get('qualified_name', 'unknown')} ---\n"
        context += f"{chunk.get('chunk_text', '')}\n"
    return context


def init_llm_client():
    """Initialize LangChain ChatGoogleGenerativeAI client."""
    load_dotenv()
    try:
        llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            temperature=0.7,
            convert_system_message_to_human=True
        )
        return llm
    except Exception as e:
        print(f"Failed to initialize LangChain Gemini client: {e}")
        print("Ensure .env file has GOOGLE_API_KEY set.")
        sys.exit(1)


def generate_prompt() -> PromptTemplate:
    """Generate LangChain prompt template."""
    template = """You are an expert software engineer and technical writer. 
Analyze the following codebase and generate comprehensive documentation. 
Focus on relationships between functions, classes, and modules.
Explain how they interact to achieve system functionality.

Codebase Context:
{code_context}
"""
    return PromptTemplate(template=template, input_variables=["code_context"])


def save_and_output(text: str, filename: str) -> None:
    """Save to file and print output."""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"✓ Documentation saved to {filename}\n")
    print("=" * 80)
    print("CODEBASE DOCUMENTATION AND RELATIONSHIPS")
    print("=" * 80 + "\n")
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"))


def post_to_webhook(documentation, webhook_url: str) -> bool:
    """Post documentation to webhook endpoint with error handling."""
    try:
        print(f"→ Posting to {webhook_url}...", flush=True)
        response = requests.post(
            webhook_url,
            json={"documentation": documentation.text},
            auth=("user", "afc4e2c6-4e07-4ff3-97d8-13fcc2a873a8"),
            timeout=WEBHOOK_TIMEOUT
        )
        response.raise_for_status()
        print(f"✓ Webhook received (Status: {response.status_code})", flush=True)
        return True
    except requests.exceptions.ConnectionError:
        print(f"⚠ Cannot connect to {webhook_url} (server not running?)", flush=True)
        return False
    except requests.exceptions.Timeout:
        print(f"⚠ Webhook request timed out after {WEBHOOK_TIMEOUT}s", flush=True)
        return False
    except requests.exceptions.RequestException as e:
        print(f"⚠ Webhook error: {e}", flush=True)
        return False


def post_to_webhook_langchain(documentation: str, webhook_url: str) -> bool:
    """Post LangChain documentation to webhook endpoint with error handling."""
    try:
        print(f"→ Posting to {webhook_url}...", flush=True)
        response = requests.post(
            webhook_url,
            json={"documentation": documentation},
            auth=("user", "afc4e2c6-4e07-4ff3-97d8-13fcc2a873a8"),
            timeout=WEBHOOK_TIMEOUT
        )
        response.raise_for_status()
        print(f"✓ Webhook received (Status: {response.status_code})", flush=True)
        return True
    except requests.exceptions.ConnectionError:
        print(f"⚠ Cannot connect to {webhook_url} (server not running?)", flush=True)
        return False
    except requests.exceptions.Timeout:
        print(f"⚠ Webhook request timed out after {WEBHOOK_TIMEOUT}s", flush=True)
        return False
    except requests.exceptions.RequestException as e:
        print(f"⚠ Webhook error: {e}", flush=True)
        return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate documentation for a source file or directory."
    )
    parser.add_argument(
        "source",
        help="Path to a source file or folder to ingest."
    )
    parser.add_argument(
        "--output", "-o",
        default=OUTPUT_FILE,
        help="Output markdown filename."
    )
    parser.add_argument(
        "--model", "-m",
        default=LLM_MODEL,
        help="LLM model name."
    )
    parser.add_argument(
        "--webhook-url",
        default=DEFAULT_WEBHOOK_URL,
        help="Optional webhook URL to post documentation. If omitted, no webhook is called."
    )
    return parser.parse_args()


def collect_chunks(source_path: str) -> list[dict]:
    """Ingest a source file or directory and return chunks for prompt generation."""
    path = Path(source_path)

    if not path.exists():
        print(f"Error: path not found: {source_path}")
        return []

    if path.is_file():
        result = ingest_file(str(path))
        if result["status"] != "ok":
            print(f"Error during ingestion: {result.get('error', 'Unknown error')}")
            return []

        file_chunks = []
        for chunk in db.get_all_chunks():
            try:
                if Path(chunk.get("file_path", "")).resolve() == path.resolve():
                    file_chunks.append(chunk)
            except Exception:
                continue
        return file_chunks

    if path.is_dir():
        print(f"Ingesting code from directory: {source_path}", flush=True)
        pipeline = IngestionPipeline()
        pipeline.process(str(path))

        root_path = path.resolve()
        dir_chunks = []
        for chunk in db.get_all_chunks():
            try:
                if Path(chunk.get("file_path", "")).resolve().is_relative_to(root_path):
                    dir_chunks.append(chunk)
            except Exception:
                continue
        return dir_chunks

    print(f"Error: unsupported source type: {source_path}")
    return []


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

def main():
    args = parse_args()

    print(f"Ingesting code from {args.source}...", flush=True)
    chunks = collect_chunks(args.source)
    print(f"✓ Got {len(chunks)} chunks from source", flush=True)

    if not chunks:
        print("No code chunks found in the provided source path.")
        return

    code_context = format_chunks(chunks)
    print(f"✓ Formatted {len(chunks)} chunks. Sending to LLM...", flush=True)

    # Initialize LangChain LLM and create chain using LCEL
    llm = init_llm_client()
    prompt = generate_prompt()
    parser = StrOutputParser()
    
    # Create chain using LCEL (LangChain Expression Language)
    chain = prompt | llm | parser

    print(f"→ Waiting for {args.model} response...", flush=True)
    try:
        documentation_text = chain.invoke({"code_context": code_context})
        save_and_output(documentation_text, args.output)
        if args.webhook_url:
            post_to_webhook_langchain(documentation_text, args.webhook_url)
    except Exception as e:
        print(f"Error during LLM generation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
