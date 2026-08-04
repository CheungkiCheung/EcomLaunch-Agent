"""
Last30Days Tool - Research topics across Reddit, YouTube, Hacker News, and Polymarket.
"""

import json
import logging
import os
import subprocess

from langchain.tools import tool

from deerflow.config import get_app_config

# Set SSL environment variable at module load time
os.environ["LAST30DAYS_DISABLE_SSL_VERIFY"] = "1"

logger = logging.getLogger(__name__)

# Default path to last30days script (relative to deer-flow root)
DEFAULT_SCRIPT_PATH = None  # Will be auto-detected or configured


def _find_last30days_script() -> str | None:
    """Find the last30days script in common locations."""
    # Check environment variable first
    env_path = os.environ.get("LAST30DAYS_SCRIPT_PATH")
    if env_path and os.path.exists(env_path):
        return env_path

    # Check config
    config = get_app_config().get_tool_config("last30days")
    if config and hasattr(config, "model_extra"):
        config_path = config.model_extra.get("script_path")
        if config_path and os.path.exists(config_path):
            return config_path

    # Auto-detect: look for last30days in testGithub directory
    possible_paths = [
        # Project root relative
        os.path.join(os.path.dirname(__file__), "../../../../../../../../testGithub/last30days-skill-main/skills/last30days/scripts/last30days.py"),
        # User's testGithub directory
        os.path.expanduser("~/0_2实习/deepagents/testGithub/last30days-skill-main/skills/last30days/scripts/last30days.py"),
        # Common install locations
        os.path.expanduser("~/.agents/skills/last30days/scripts/last30days.py"),
        os.path.expanduser("~/.claude/skills/last30days/scripts/last30days.py"),
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return os.path.abspath(path)

    return None


def _find_python312() -> str:
    """Find Python 3.12+ interpreter."""
    for py in ["python3.12", "python3.13", "python3.14", "python3"]:
        try:
            result = subprocess.run(
                [py, "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return py
        except (subprocess.SubprocessError, FileNotFoundError):
            continue

    return "python3"  # Fallback


def _run_last30days(
    topic: str,
    sources: list[str] | None = None,
    depth: str = "quick",
    emit: str = "compact",
    extra_args: list[str] | None = None,
) -> dict:
    """
    Run last30days script and return results.

    Args:
        topic: Research topic
        sources: List of sources to search (e.g., ["reddit", "youtube", "hackernews"])
        depth: Search depth ("quick", "default", "deep")
        emit: Output format ("compact", "json", "md")
        extra_args: Additional command-line arguments

    Returns:
        Dictionary with results or error
    """
    script_path = _find_last30days_script()
    if not script_path:
        return {
            "error": "last30days script not found",
            "help": "Set LAST30DAYS_SCRIPT_PATH environment variable or configure in config.yaml",
        }

    python_cmd = _find_python312()

    # Build command
    cmd = [
        python_cmd,
        script_path,
        topic,
        f"--emit={emit}",
        f"--{depth}" if depth != "default" else "",
    ]

    # Add sources filter
    if sources:
        cmd.extend(["--search", ",".join(sources)])

    # Add extra arguments
    if extra_args:
        cmd.extend(extra_args)

    # Remove empty strings
    cmd = [arg for arg in cmd if arg]

    # Set environment for SSL handling
    env = os.environ.copy()
    env["LAST30DAYS_DISABLE_SSL_VERIFY"] = "1"
    # Also set in current process environment
    os.environ["LAST30DAYS_DISABLE_SSL_VERIFY"] = "1"

    try:
        logger.info(f"Running last30days: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minutes timeout
            env=env,
            cwd=os.path.dirname(script_path) if script_path else None,
        )

        if result.returncode != 0:
            logger.warning(f"last30days stderr: {result.stderr[:500]}")

        # Parse output - extract the synthesis part
        output = result.stdout
        if not output.strip():
            return {"error": "No output from last30days", "stderr": result.stderr[:500]}

        # Try to parse as JSON if emit=json
        if emit == "json":
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                pass

        # Return raw output for compact/md
        return {
            "topic": topic,
            "sources": sources or ["auto"],
            "output": output,
            "success": True,
        }

    except subprocess.TimeoutExpired:
        return {"error": "last30days timed out (120s)", "topic": topic}
    except FileNotFoundError as e:
        return {"error": f"Command not found: {e}", "script_path": script_path}
    except Exception as e:
        return {"error": f"last30days failed: {str(e)}", "topic": topic}


@tool("last30days", parse_docstring=True)
def last30days_tool(
    topic: str,
    sources: str = "reddit,youtube,hackernews,polymarket",
    depth: str = "quick",
) -> str:
    """Research a topic across Reddit, YouTube, Hacker News, and Polymarket to find real user discussions, reviews, and opinions from the last 30 days.

    Args:
        topic: The topic to research (e.g., "portable coffee cup", "AI coding tools")
        sources: Comma-separated list of sources to search. Options: reddit, youtube, hackernews, polymarket, github. Default: reddit,youtube,hackernews,polymarket
        depth: Search depth - "quick" (fast, fewer results), "default" (balanced), or "deep" (comprehensive). Default: quick
    """
    # Parse sources string to list
    source_list = [s.strip() for s in sources.split(",") if s.strip()]

    results = _run_last30days(
        topic=topic,
        sources=source_list,
        depth=depth,
        emit="compact",
    )

    if "error" in results:
        return json.dumps({"error": results["error"], "topic": topic}, ensure_ascii=False)

    # Extract key information from the output
    output = results.get("output", "")

    # Parse the structured output to extract key findings
    findings = {
        "topic": topic,
        "sources_searched": source_list,
        "summary": _extract_summary(output),
        "key_insights": _extract_insights(output),
        "stats": _extract_stats(output),
        "raw_output_length": len(output),
    }

    return json.dumps(findings, indent=2, ensure_ascii=False)


def _extract_summary(output: str) -> str:
    """Extract summary from last30days output."""
    lines = output.split("\n")
    summary_lines = []

    # Look for Ranked Evidence Clusters section
    in_clusters = False
    for line in lines:
        if "## Ranked Evidence Clusters" in line:
            in_clusters = True
            continue
        if in_clusters and line.startswith("### "):
            # Extract cluster title
            title_match = line.replace("### ", "").strip()
            if title_match:
                summary_lines.append(title_match)
                if len(summary_lines) >= 3:
                    break

    if not summary_lines:
        # Fallback: look for "What I learned:" section
        for i, line in enumerate(lines):
            if "What I learned:" in line:
                # Get next few non-empty lines
                for j in range(i + 1, min(i + 10, len(lines))):
                    if lines[j].strip() and not lines[j].startswith("#"):
                        summary_lines.append(lines[j].strip())
                        if len(summary_lines) >= 3:
                            break
                break

    return " | ".join(summary_lines[:3]) if summary_lines else "Research completed"


def _extract_insights(output: str) -> list[str]:
    """Extract key insights from last30days output."""
    insights = []
    lines = output.split("\n")

    # Look for evidence items with score tuples
    for line in lines:
        # Match patterns like "(score 44, 1 item, sources: Hacker News)"
        if "(score" in line and "sources:" in line:
            # Extract the evidence description
            match = line.strip()
            if match.startswith("### "):
                match = match[4:]
            # Clean up
            match = match.split("(score")[0].strip()
            if match and len(match) > 10:
                insights.append(match[:150])
                if len(insights) >= 5:
                    break

    # Also look for direct evidence quotes
    if len(insights) < 3:
        for line in lines:
            if line.strip().startswith("- ") and "Evidence:" in line:
                evidence = line.strip()[2:]
                if len(evidence) > 20:
                    insights.append(evidence[:150])
                    if len(insights) >= 5:
                        break

    return insights


def _extract_stats(output: str) -> dict:
    """Extract statistics from last30days output."""
    stats = {
        "reddit_threads": 0,
        "youtube_videos": 0,
        "hn_stories": 0,
        "polymarket_markets": 0,
    }

    lines = output.split("\n")
    for line in lines:
        # Look for stats in the footer section
        if "Reddit:" in line and "thread" in line.lower():
            try:
                # Extract number before "thread"
                part = line.split("thread")[0]
                num = part.split(":")[-1].strip()
                stats["reddit_threads"] = int(num)
            except (ValueError, IndexError):
                pass
        elif "YouTube:" in line and "video" in line.lower():
            try:
                part = line.split("video")[0]
                num = part.split(":")[-1].strip()
                stats["youtube_videos"] = int(num)
            except (ValueError, IndexError):
                pass
        elif ("HN:" in line or "Hacker News:" in line) and "stor" in line.lower():
            try:
                part = line.split("stor")[0]
                num = part.split(":")[-1].strip()
                stats["hn_stories"] = int(num)
            except (ValueError, IndexError):
                pass
        elif "Polymarket:" in line and "market" in line.lower():
            try:
                part = line.split("market")[0]
                num = part.split(":")[-1].strip()
                stats["polymarket_markets"] = int(num)
            except (ValueError, IndexError):
                pass

    # Also check for stats in Source Coverage section
    for line in lines:
        if "Reddit:" in line and "items" in line.lower():
            try:
                num = line.split("items")[0].split(":")[-1].strip()
                stats["reddit_threads"] = int(num)
            except (ValueError, IndexError):
                pass
        elif "Polymarket:" in line and "items" in line.lower():
            try:
                num = line.split("items")[0].split(":")[-1].strip()
                stats["polymarket_markets"] = int(num)
            except (ValueError, IndexError):
                pass
        elif "Polymarket:" in line and "markets" in line.lower():
            try:
                num = line.split("markets")[0].split(":")[-1].strip()
                stats["polymarket_markets"] = int(num)
            except (ValueError, IndexError):
                pass

    return stats
