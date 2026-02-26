from crewai.flow.flow import Flow, start
from crewai import Task, Crew, Process
from pydantic import BaseModel
from agents import architect, coder, critic
from typing import Optional, Callable

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

# ── Event Callback ────────────────────────────────────────────────────────────
_event_callback: Optional[Callable] = None

def set_event_callback(cb: Callable):
    global _event_callback
    _event_callback = cb

def emit(event_type: str, agent: str, message: str, data: dict = None):
    """Emit an event — routes to callback if set, otherwise prints."""
    if _event_callback:
        _event_callback(event_type, agent, message, data or {})
    else:
        print(message)

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
    return "FAIL"

# ── Flow ──────────────────────────────────────────────────────────────────────
class AgentMeshFlow(Flow[MeshState]):
    """
    Single-start flow. Python while loop controls the revision cycle.
    No @router, no @listen chains — just deterministic control.
    """

    @start()
    def run_mesh(self):
        # ── PLAN ──────────────────────────────────────────────────────
        self._do_plan()

        # ── CODE → REVIEW LOOP ────────────────────────────────────────
        while True:
            self._do_code()
            self._do_review()

            if self.state.verdict == "PASS":
                emit("routing", "system", "✅ PASS — approved")
                break

            if self.state.revision_count >= self.state.max_revisions:
                emit("routing", "system",
                     f"⚠️ Max revisions ({self.state.max_revisions}) reached — accepting best output")
                break

            self.state.revision_count += 1
            emit("routing", "system",
                 f"🔄 FAIL — routing to revision {self.state.revision_count}/{self.state.max_revisions}")

        # ── FINALISE ──────────────────────────────────────────────────
        self._do_finalise()
        return self.state.code

    # ── Phase Methods (not decorated — called by the loop) ────────────

    def _do_plan(self):
        emit("agent_status", "architect", "architect → working", {"status": "working"})
        emit("phase_start", "architect", "Planning phase started")

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

        emit("phase_complete", "architect",
             f"Plan complete ({len(self.state.plan)} chars)",
             {"plan_preview": self.state.plan[:500]})
        emit("agent_status", "architect", "architect → complete", {"status": "complete"})

    def _do_code(self):
        emit("agent_status", "coder", "coder → working", {"status": "working"})

        if self.state.revision_count == 0:
            emit("phase_start", "coder", "Initial implementation started")
        else:
            emit("phase_start", "coder",
                 f"Revision {self.state.revision_count}/{self.state.max_revisions} started")

        context = f"ARCHITECTURAL PLAN:\n{self.state.plan}"
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

        emit("phase_complete", "coder",
             f"Code complete ({len(self.state.code)} chars)",
             {"code_preview": self.state.code[:500]})
        emit("agent_status", "coder", "coder → complete", {"status": "complete"})

    def _do_review(self):
        emit("agent_status", "critic", "critic → working", {"status": "working"})
        emit("phase_start", "critic", "Review phase started")

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
        self.state.history.append({
            "revision": self.state.revision_count,
            "verdict": self.state.verdict,
            "issues": self.state.review[:500]
        })

        emit("verdict", "critic",
             f"VERDICT: {self.state.verdict} (cycle {self.state.revision_count})",
             {"verdict": self.state.verdict, "review_preview": self.state.review[:500]})
        emit("agent_status", "critic", "critic → complete", {"status": "complete"})

    def _do_finalise(self):
        emit("job_complete", "system",
             f"🌑 MESH COMPLETE — {self.state.revision_count} revision cycles, verdict: {self.state.verdict}",
             {"revision_count": self.state.revision_count, "verdict": self.state.verdict})

        for agent_name in ["architect", "coder", "critic"]:
            emit("agent_status", agent_name, f"{agent_name} → idle", {"status": "idle"})


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
