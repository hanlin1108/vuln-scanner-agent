from google.adk.agents import LlmAgent, SequentialAgent, LoopAgent
from google.adk.tools import exit_loop
from .tools import list_files, read_file

MODEL = "gemini-2.5-flash"

planner = LlmAgent(
    name="planner",
    model=MODEL,
    instruction=(
        "You are a security planner. Use list_files to scan the target codebase. "
        "Pick the top 10 most security-relevant files (auth, API routes, DB queries, "
        "config, input handling). Output a prioritized list with reasons."
    ),
    tools=[list_files],
    output_key="files_to_review",
)

reviewer = LlmAgent(
    name="reviewer",
    model=MODEL,
    instruction=(
        "You are a security code reviewer. Use read_file to read each file from "
        "{files_to_review}. Find vulnerabilities: injection, XSS, hardcoded secrets, "
        "auth issues, misconfig, path traversal, missing input validation. For each "
        "finding: file, line number, severity (CRITICAL/HIGH/MEDIUM/LOW), category, "
        "description, fix suggestion. If you have {review_feedback}, focus on those "
        "specific areas."
    ),
    tools=[read_file],
    output_key="findings",
)

critic = LlmAgent(
    name="critic",
    model=MODEL,
    instruction=(
        "You are a security review critic. Evaluate the quality of {findings} against "
        "{files_to_review}. Check: Are findings specific (with line numbers)? Were "
        "high-risk files actually reviewed? Any obvious gaps? If the review is thorough "
        "enough, call the exit_loop tool. If not, write specific feedback on what the "
        "reviewer missed or should re-examine."
    ),
    tools=[exit_loop],
    output_key="review_feedback",
)

reporter = LlmAgent(
    name="reporter",
    model=MODEL,
    instruction=(
        "You are a security report writer. Using {findings}, write a clean vulnerability "
        "report in markdown: Executive summary (2-3 sentences), Stats table: count by "
        "severity, Detailed findings with file, line, severity, description, "
        "recommendation, Top 3 action items."
    ),
    output_key="final_report",
)

review_loop = LoopAgent(
    name="review_loop",
    sub_agents=[reviewer, critic],
    max_iterations=3,
)

root_agent = SequentialAgent(
    name="vuln_scanner",
    description="Scans a codebase for security vulnerabilities using a multi-agent review loop.",
    sub_agents=[planner, review_loop, reporter],
)
