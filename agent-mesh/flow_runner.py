from crewai.flow.flow import Flow, listen, start, router
from crewai import Task, Crew, Process
from pydantic import BaseModel
from agents import architect, coder, critic
from typing import Optional

# ── State ─────────────────────────────────────────────────────────────────────
class MeshState(BaseModel):
    objective: str = ""
    plan: str = ""
    code: str = ""
    review: str = ""
    verdict: str = ""           # PASS or FAIL
    revision_count: int = 0
    max_revisions: int = 3
    history: list = []          # revision log — seed of braid memory

# ── Helpers ───────────────────────────────────────────────────────────────────
def run_single_agent(agent, description: str, context_str: str = "") -> str:
    """Run a single agent task and return its output as a string."""
    full_description = f"{description}\n\nCONTEXT:\n{context_str}" if context_str else description
    task = Task(
        description=full_description,
        agent=agent,
        expected_output="Complete response as specified"
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()
    return str(result)

def extract_verdict(review_text: str) -> str:
    """Parse PASS or FAIL from Critic output."""
    upper = review_text.upper()
    if "VERDICT: PASS" in upper:
        return "PASS"
    elif "VERDICT: FAIL" in upper:
        return "FAIL"
    # Fallback — if Critic didn't follow format, treat as FAIL
    return "FAIL"

# ── Flow ──────────────────────────────────────────────────────────────────────
class AgentMeshFlow(Flow[MeshState]):

    @start()
    def plan_phase(self):
        print(f"\n{'='*60}")
        print(f"🏗️  ARCHITECT — Planning")
        print(f"{'='*60}")

        self.state.plan = run_single_agent(
            architect,
            description=(
                f"Create a detailed implementation plan for: {self.state.objective}\n\n"
                "Include:\n"
                "- Component breakdown\n"
                "- Technical decisions with reasoning\n"
                "- Edge cases to handle\n"
                "- Dependencies required"
            )
        )
        print(f"\n✅ Plan complete ({len(self.state.plan)} chars)")

    @listen(plan_phase)
    def code_phase(self):
        print(f"\n{'='*60}")
        if self.state.revision_count == 0:
            print(f"💻  CODER — Initial Implementation")
        else:
            print(f"💻  CODER — Revision {self.state.revision_count}/{self.state.max_revisions}")
        print(f"{'='*60}")

        context = f"ARCHITECTURAL PLAN:\n{self.state.plan}"

        # On revisions, include the Critic's feedback
        if self.state.review:
            context += f"\n\nCRITIC REVIEW (must address ALL issues):\n{self.state.review}"
            context += f"\n\nPREVIOUS CODE (revise this):\n{self.state.code}"

        self.state.code = run_single_agent(
            coder,
            description=(
                "Implement complete, runnable Python code based on the plan. "
                "Include all imports, full error handling, and a working __main__ example. "
                "If revision feedback is provided, address every single issue listed."
            ),
            context_str=context
        )
        print(f"\n✅ Code complete ({len(self.state.code)} chars)")

    @listen(code_phase)
    def review_phase(self):
        print(f"\n{'='*60}")
        print(f"🔍  CRITIC — Review")
        print(f"{'='*60}")

        self.state.review = run_single_agent(
            critic,
            description=(
                "Review this implementation. "
                "Your response MUST start with exactly 'VERDICT: PASS' or 'VERDICT: FAIL'.\n\n"
                "Then:\n"
                "ISSUES:\n1. [specific issue]\n(or 'None')\n\n"
                "REQUIRED FIXES:\n1. [exact fix]\n(or 'None')"
            ),
            context_str=f"CODE TO REVIEW:\n{self.state.code}"
        )

        self.state.verdict = extract_verdict(self.state.review)

        # Log this revision cycle to history
        self.state.history.append({
            "revision": self.state.revision_count,
            "verdict": self.state.verdict,
            "issues": self.state.review[:500]  # truncated for log
        })

        print(f"\n{'='*60}")
        print(f"⚖️   VERDICT: {self.state.verdict} (cycle {self.state.revision_count})")
        print(f"{'='*60}")

    @router(review_phase)
    def route_verdict(self):
        """Python controls the loop — no LLM involved in routing."""
        if self.state.verdict == "PASS":
            return "approved"
        elif self.state.revision_count >= self.state.max_revisions:
            print(f"\n⚠️  Max revisions ({self.state.max_revisions}) reached — accepting best output")
            return "approved"
        else:
            self.state.revision_count += 1
            return "revise"

    @listen("revise")
    def revise(self):
        """Route back to code_phase for another cycle."""
        print(f"\n🔄  Routing back to Coder for revision {self.state.revision_count}...")
        self.code_phase()
        self.review_phase()
        return self.route_verdict()

    @listen("approved")
    def finalise(self):
        print(f"\n{'='*60}")
        print(f"🌑  MESH COMPLETE")
        print(f"    Revision cycles: {self.state.revision_count}")
        print(f"    Final verdict:   {self.state.verdict}")
        print(f"{'='*60}\n")
        return self.state.code


# ── Entry point ───────────────────────────────────────────────────────────────
def run_mesh(objective: str, max_revisions: int = 3) -> str:
    flow = AgentMeshFlow()
    flow.state.objective = objective
    flow.state.max_revisions = max_revisions

    result = flow.kickoff()

    print("\n📋 REVISION HISTORY:")
    for entry in flow.state.history:
        print(f"   Cycle {entry['revision']}: {entry['verdict']}")

    return result


if __name__ == "__main__":
    result = run_mesh(
        objective=(
            "A Python class that manages a SQLite job queue with priority levels, "
            "retry logic on failure, and a status tracking system"
        ),
        max_revisions=3
    )
    print("\n🌑 FINAL APPROVED CODE:\n")
    print(result)
