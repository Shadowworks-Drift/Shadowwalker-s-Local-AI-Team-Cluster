from crewai import Agent, LLM
from dotenv import load_dotenv

load_dotenv()

fast_llm = LLM(
    model="ollama/coder-fast",
    base_url="http://localhost:11434"
)

reasoning_llm = LLM(
    model="ollama/reasoning-fast",
    base_url="http://localhost:11434"
)

architect = Agent(
    role="Systems Architect",
    goal="Decompose complex problems into clear, detailed implementation plans",
    backstory=(
        "Expert in systems design with deep knowledge of distributed systems, "
        "cryptographic protocols, and production-grade Python. "
        "Your plans are specific enough that a developer can implement without ambiguity."
    ),
    llm=reasoning_llm,
    verbose=True
)

coder = Agent(
    role="Senior Developer",
    goal=(
        "Implement clean, efficient, well-documented code from architectural specifications. "
        "When receiving revision requests, address ALL flagged issues specifically. "
        "Never ignore Critic feedback."
    ),
    backstory=(
        "Expert Python developer focused on production-quality implementations. "
        "You write code that handles edge cases, has proper error handling, "
        "and is immediately runnable."
    ),
    llm=fast_llm,
    verbose=True
)

critic = Agent(
    role="Code Critic",
    goal=(
        "Review implementations rigorously. "
        "Always return a structured verdict starting with exactly 'VERDICT: PASS' or 'VERDICT: FAIL'. "
        "If FAIL, provide numbered list of specific issues with exact fixes required."
    ),
    backstory=(
        "Experienced code reviewer with focus on security, performance, and correctness. "
        "You structure every response as:\n"
        "VERDICT: PASS or FAIL\n"
        "ISSUES: (numbered list or 'None')\n"
        "REQUIRED FIXES: (specific instructions or 'None')"
    ),
    llm=fast_llm,
    verbose=True
)

print("✅ Flow agents initialised")
print(f"   Architect: reasoning-fast")
print(f"   Coder:     coder-fast")
print(f"   Critic:    coder-fast")
