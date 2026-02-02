#!/usr/bin/env python3
"""
WordPress Block Agent - A LangChain-powered agent for generating ACF blocks.

Uses the supervisor pattern with create_agent to orchestrate sub-agents.
"""

import os
import re
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent, AgentState
from langchain.tools import tool, ToolRuntime
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from agents import PHPTemplateAgent, ACFJsonAgent


load_dotenv()


class BlockState(AgentState):
    """State for the block generation workflow."""
    block_description: str
    block_name: str
    php_template: str
    acf_json: dict
    output_dir: str


def sanitize_block_name(description: str) -> str:
    """Generate a sanitized block name from the description."""
    words = description.lower().split()[:4]
    slug = "-".join(words)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")[:50]


def print_status(message: str, status: str = "info"):
    """Print a status message with formatting."""
    icons = {
        "info": "ℹ️ ",
        "working": "⏳",
        "success": "✅",
        "error": "❌",
        "output": "📄"
    }
    icon = icons.get(status, "")
    print(f"\n{icon} {message}")


def save_output(content: str, filename: str, output_dir: Path) -> Path:
    """Save content to a file in the output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / filename
    filepath.write_text(content)
    return filepath


def create_orchestrator():
    """Create the main orchestrator agent with sub-agent tools."""

    model = ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0.3)
    output_base = Path(__file__).parent / "output"

    # Initialize sub-agents
    php_agent = PHPTemplateAgent()
    acf_agent = ACFJsonAgent()

    @tool
    def update_block_info(block_description: str, runtime: ToolRuntime) -> str:
        """Initialize block information from the user's description.

        Args:
            block_description: The user's description of the block they want
        """
        block_name = sanitize_block_name(block_description)
        output_dir = str(output_base / block_name)

        from langgraph.types import Command
        return Command(update={
            "block_description": block_description,
            "block_name": block_name,
            "output_dir": output_dir,
        })

    @tool
    def generate_php_template(runtime: ToolRuntime) -> str:
        """Generate a PHP template for the ACF block using the PHP template sub-agent."""
        description = runtime.state.get("block_description", "")
        block_name = runtime.state.get("block_name", "")
        output_dir = Path(runtime.state.get("output_dir", "output"))

        print_status("Generating PHP template...", "working")

        try:
            template = php_agent.create_template(description)

            # Save the template
            php_path = save_output(template, f"{block_name}.php", output_dir)
            print_status(f"PHP template saved to: {php_path}", "success")

            # Update state with template
            from langgraph.types import Command
            return Command(update={
                "php_template": template,
            })

        except Exception as e:
            print_status(f"Failed to generate PHP template: {e}", "error")
            return f"Error generating template: {e}"

    @tool
    def generate_acf_json(runtime: ToolRuntime) -> str:
        """Generate ACF JSON field configuration using the ACF JSON sub-agent."""
        description = runtime.state.get("block_description", "")
        block_name = runtime.state.get("block_name", "")
        php_template = runtime.state.get("php_template", "")
        output_dir = Path(runtime.state.get("output_dir", "output"))

        if not php_template:
            return "Error: PHP template must be generated first. Call generate_php_template first."

        print_status("Generating ACF field group JSON...", "working")

        try:
            acf_json = acf_agent.create_field_group(
                block_description=description,
                block_name=f"acf/{block_name}",
                php_template=php_template
            )

            if "error" in acf_json:
                print_status(f"Warning: {acf_json['error']}", "error")
                raw_path = save_output(
                    acf_json.get("raw_output", ""),
                    f"{block_name}-acf-raw.txt",
                    output_dir
                )
                return f"Partial success. Raw output saved to: {raw_path}"

            # Save the JSON
            acf_formatted = acf_agent.format_json(acf_json)
            group_key = acf_json.get("key", f"group_{block_name}")
            acf_path = save_output(acf_formatted, f"{group_key}.json", output_dir)
            print_status(f"ACF JSON saved to: {acf_path}", "success")

            from langgraph.types import Command
            return Command(update={
                "acf_json": acf_json,
            })

        except Exception as e:
            print_status(f"Failed to generate ACF JSON: {e}", "error")
            return f"Error generating ACF JSON: {e}"

    @tool
    def summarize_results(runtime: ToolRuntime) -> str:
        """Summarize what was generated for the user."""
        block_name = runtime.state.get("block_name", "unknown")
        output_dir = runtime.state.get("output_dir", "output")
        php_template = runtime.state.get("php_template")
        acf_json = runtime.state.get("acf_json")

        results = [f"Block '{block_name}' generated successfully!"]
        results.append(f"Output directory: {output_dir}")

        if php_template:
            results.append(f"- PHP template: {block_name}.php")
        if acf_json and "error" not in acf_json:
            group_key = acf_json.get("key", f"group_{block_name}")
            results.append(f"- ACF JSON: {group_key}.json")

        return "\n".join(results)

    orchestrator = create_agent(
        model=model,
        tools=[update_block_info, generate_php_template, generate_acf_json, summarize_results],
        state_schema=BlockState,
        checkpointer=InMemorySaver(),
        system_prompt="""You are a WordPress block development assistant that orchestrates the creation of ACF blocks.

When a user describes a block they want:
1. First call update_block_info to initialize the block details
2. Then call generate_php_template to create the PHP template
3. Then call generate_acf_json to create the ACF field configuration
4. Finally call summarize_results to tell the user what was created

Always execute these steps in order. The PHP template must be generated before the ACF JSON.
Be helpful and explain what you're doing at each step."""
    )

    return orchestrator


def print_welcome():
    """Print welcome message and instructions."""
    print("\n" + "=" * 60)
    print("🧱 WordPress Block Agent")
    print("=" * 60)
    print("\nI'll help you create WordPress ACF blocks!")
    print("\nDescribe the block you want to create, and I'll generate:")
    print("  • A PHP template file with ACF field integration")
    print("  • An ACF JSON field group configuration")
    print("\nType 'exit' to quit.\n")


def main():
    """Main chat loop."""
    if not os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY") == "your_api_key_here":
        print("\n❌ Error: Please set your ANTHROPIC_API_KEY in the .env file")
        print("   Get your API key from: https://console.anthropic.com/")
        sys.exit(1)

    print_welcome()

    print_status("Initializing orchestrator agent...", "working")
    try:
        orchestrator = create_orchestrator()
        print_status("Agent ready!", "success")
    except Exception as e:
        print(f"\n❌ Failed to initialize: {e}")
        sys.exit(1)

    thread_id = 0

    while True:
        print("\n" + "-" * 40)
        try:
            user_input = input("📝 Describe your block (or 'exit'): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nGoodbye! 👋")
            break

        if not user_input:
            print("Please enter a block description.")
            continue

        if user_input.lower() in ("exit", "quit", "q"):
            print("\nGoodbye! 👋")
            break

        thread_id += 1
        print(f"\n🚀 Creating block based on: \"{user_input}\"")

        try:
            response = orchestrator.invoke(
                {"messages": [HumanMessage(content=user_input)]},
                {"configurable": {"thread_id": str(thread_id)}}
            )

            # Print final response
            final_message = response["messages"][-1].content
            print("\n" + "=" * 40)
            print(final_message)

        except Exception as e:
            print_status(f"Error during generation: {e}", "error")


if __name__ == "__main__":
    main()
