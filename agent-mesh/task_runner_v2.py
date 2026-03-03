from agents import manager, architect, coder, critic
from crewai import Task, Crew, Process

def run_task(objective: str, max_revisions: int = 3):
    print(f"\n🌑 Starting hierarchical mesh for: {objective}")
    print(f"   Max revision cycles: {max_revisions}\n")

    # Step 1: Architect plans
    plan = Task(
        description=f"Create a detailed implementation plan for: {objective}",
        agent=architect,
        expected_output=(
            "A numbered implementation plan with:\n"
            "- Component breakdown\n"
            "- Technical decisions explained\n"
            "- Edge cases identified\n"
            "- Dependencies listed"
        )
    )

    # Step 2: Coder implements
    implement = Task(
        description=(
            "Implement the architect's plan. "
            "Write complete, runnable Python code. "
            "Include all imports, error handling, and a working example in __main__."
        ),
        agent=coder,
        expected_output="Complete, runnable Python code with inline comments",
        context=[plan]
    )

    # Step 3: Critic reviews with structured verdict
    review = Task(
        description=(
            "Review the implementation thoroughly. "
            "Your response MUST follow this exact structure:\n\n"
            "VERDICT: PASS or FAIL\n\n"
            "ISSUES:\n"
            "1. [specific issue with line reference if possible]\n"
            "2. [specific issue]\n"
            "(or 'None' if PASS)\n\n"
            "REQUIRED FIXES:\n"
            "1. [exact fix required]\n"
            "2. [exact fix required]\n"
            "(or 'None' if PASS)"
        ),
        agent=critic,
        expected_output="Structured verdict with PASS/FAIL and specific issues",
        context=[implement]
    )

    # Step 4: Manager decides — delegates revision if needed
    manage = Task(
        description=(
            f"Review the Critic's verdict. "
            f"Maximum {max_revisions} revision cycles allowed.\n\n"
            "If VERDICT is PASS: Accept the implementation and return the final code.\n\n"
            "If VERDICT is FAIL: Delegate to the Senior Developer with clear instructions "
            "listing exactly what must be fixed. After revision, delegate back to Code Critic "
            "for re-review. Repeat until PASS or max revisions reached.\n\n"
            "When complete, return the final implementation with a summary of "
            "what was changed across revision cycles."
        ),
        agent=manager,
        expected_output=(
            "Final approved code with revision summary. "
            "Format: REVISION_CYCLES: N\nFINAL_CODE: [code]\nSUMMARY: [what changed]"
        ),
        context=[plan, implement, review]
    )

    crew = Crew(
        agents=[architect, coder, critic],
        tasks=[plan, implement, review, manage],
        process=Process.hierarchical,
        manager_agent=manager,
        verbose=True
    )

    return crew.kickoff()


if __name__ == "__main__":
    result = run_task(
        "A Python class that manages a SQLite job queue with priority levels, "
        "retry logic on failure, and a status tracking system",
        max_revisions=3
    )
    print("\n🌑 FINAL APPROVED OUTPUT:\n")
    print(result)
