#!/usr/bin/env python3
"""
WordPress Block Agent - A LangChain-powered agent for generating ACF blocks.

Uses the supervisor pattern with create_agent and HITL for field approval.
"""

import os
import re
import sys
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent, AgentState
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.tools import tool, ToolRuntime
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agents import PHPTemplateAgent, ACFJsonAgent


load_dotenv()


class BlockState(AgentState):
    """State for the block generation workflow."""
    block_description: str
    block_name: str
    proposed_fields: list
    approved_fields: list
    php_template: str
    acf_json: dict
    output_dir: str

# block name creator
def sanitize_block_name(description: str) -> str:
    """Generate a sanitized block name from the description."""
    words = description.lower().split()[:4]
    slug = "-".join(words)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")[:50]

# Helper for statuses with emojis
def print_status(message: str, status: str = "info"):
    """Print a status message with formatting."""
    icons = {
        "info": "ℹ️ ",
        "working": "⏳",
        "success": "✅",
        "error": "❌",
        "output": "📄",
        "review": "👀"
    }
    icon = icons.get(status, "")
    print(f"\n{icon} {message}")

# Helper to save output to file
def save_output(content: str, filename: str, output_dir: Path) -> Path:
    """Save content to a file in the output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / filename
    filepath.write_text(content)
    return filepath


def get_current_state(orchestrator, config: dict) -> dict:
    """Retrieve current state from orchestrator checkpoint."""
    try:
        snapshot = orchestrator.get_state(config)
        return snapshot.values if snapshot else {}
    except Exception:
        return {}


def is_block_complete(state: dict) -> bool:
    """Check if block generation workflow is complete."""
    has_php = bool(state.get("php_template"))
    has_acf = bool(state.get("acf_json")) and "error" not in state.get("acf_json", {})
    return has_php and has_acf


def classify_user_intent(user_input: str) -> str:
    """Classify user input into workflow intents."""
    # TODO: Run a cheap classifier model here instead of naive text detection
    input_lower = user_input.lower().strip()

    if input_lower in ("exit", "quit", "q"):
        return "exit"

    new_block_phrases = ["new block", "another block", "start over", "different block", "next block"]
    if any(phrase in input_lower for phrase in new_block_phrases):
        return "new_block"

    return "continue"


# Helper to show proposed fields - could move this into tool...
def display_proposed_fields(fields: list) -> None:
    """Display proposed fields for user review."""
    print("\n" + "=" * 50)
    print("👀 PROPOSED FIELDS FOR REVIEW")
    print("=" * 50)

    for i, field in enumerate(fields, 1):
        field_type = field.get("type", "text")
        field_name = field.get("name", "unnamed")
        field_label = field.get("label", field_name)
        required = "required" if field.get("required") else "optional"
        print(f"\n  {i}. {field_label}")
        print(f"     Name: {field_name}")
        print(f"     Type: {field_type} ({required})")
        if field.get("description"):
            print(f"     Description: {field.get('description')}")

    print("\n" + "-" * 50)

# Helper to capture user input - returns an object to be used in Command - update
def get_user_field_decision(fields: list) -> dict:
    """Get user decision on proposed fields."""
    display_proposed_fields(fields)

    print("\nOptions:")
    print("  [a] Approve these fields and continue")
    print("  [e] Edit fields (provide modifications)")
    print("  [r] Reject and provide feedback")
    print()

    while True:
        choice = input("Your choice (a/e/r): ").strip().lower()

        if choice == 'a':
            print("-" * 60)
            print("✅ Approved! Let's build your block...")
            print("-" * 60)
            return {"type": "approve"}

        elif choice == 'e':
            print("\nProvide your edited fields as JSON.")
            print("Example: [{\"name\": \"title\", \"type\": \"text\", \"label\": \"Title\", \"required\": true}]")
            print("Or type 'cancel' to go back.\n")

            edited_input = input("Edited fields JSON: ").strip()
            if edited_input.lower() == 'cancel':
                continue

            try:
                edited_fields = json.loads(edited_input)
                return {
                    "type": "edit",
                    "edited_action": {
                        "name": "propose_fields",
                        "args": {"fields": json.dumps(edited_fields)}
                    }
                }
            except json.JSONDecodeError as e:
                print(f"Invalid JSON: {e}. Try again.")
                continue

        elif choice == 'r':
            feedback = input("\nYour feedback for the agent: ").strip()
            if not feedback:
                print("Please provide feedback.")
                continue
            return {"type": "reject", "message": feedback}

        else:
            print("Invalid choice. Please enter 'a', 'e', or 'r'.")
    
    


def create_orchestrator():
    """Create the main orchestrator agent with sub-agent tools and HITL."""

    model = ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0.3)
    output_base = Path(__file__).parent / "output"

    # Initialize sub-agents
    php_agent = PHPTemplateAgent()
    acf_agent = ACFJsonAgent()

    @tool
    def update_block_info(block_name: str, block_description: str, runtime: ToolRuntime) -> str:
        """Initialize block information from the user's description.

        Args:
            block_name: The sanitized block name/slug
            block_description: The user's description of the block they want
        """
        output_dir = str(output_base / block_name)

        return Command(update={
            "block_description": block_description,
            "block_name": block_name,
            "output_dir": output_dir,
            "messages": [ToolMessage(f"Block info initialized: {block_name}", tool_call_id=runtime.tool_call_id)],
        })

    # All this does is trigger an interupt and the update state with the approved fields
    @tool
    def propose_fields(fields: str, runtime: ToolRuntime) -> str:
        """Propose the ACF fields needed for this block. This will be reviewed by the user.

        Args:
            fields: JSON string array of field objects with name, type, label, required, and description
        """
        try:
            parsed_fields = json.loads(fields)
        except json.JSONDecodeError:
            return "Error: Invalid JSON for fields"

        return Command(update={
            "proposed_fields": parsed_fields,
            "approved_fields": parsed_fields,  # Will be updated if user edits
            "messages": [ToolMessage(f"Proposed {len(parsed_fields)} fields for review", tool_call_id=runtime.tool_call_id)],
        })

    # This tool calls the subagent to create the template, then saves out
    @tool
    def generate_php_template(runtime: ToolRuntime) -> str:
        """Generate a PHP template for the ACF block using the approved fields."""
        description = runtime.state.get("block_description", "")
        block_name = runtime.state.get("block_name", "")
        approved_fields = runtime.state.get("approved_fields", [])
        output_dir = Path(runtime.state.get("output_dir", "output"))

        # Enhance description with approved fields
        fields_desc = "\n".join([
            f"- {f.get('name')} ({f.get('type', 'text')}): {f.get('label', f.get('name'))}"
            for f in approved_fields
        ])
        enhanced_description = f"{description}\n\nApproved fields:\n{fields_desc}"

        print_status("Generating PHP template with approved fields...", "working")

        try:
            template = php_agent.create_template(enhanced_description)
            php_path = save_output(template, f"{block_name}.php", output_dir)
            print_status(f"PHP template saved to: {php_path}", "success")

            # update state with the template - used in next step for ACF JSON
            return Command(update={
                "php_template": template,
                "messages": [ToolMessage(f"PHP template generated: {php_path}", tool_call_id=runtime.tool_call_id)],
            })

        except Exception as e:
            print_status(f"Failed to generate PHP template: {e}", "error")
            return f"Error generating template: {e}"

    # This tools calls the ACF JSON subagent
    @tool
    def generate_acf_json(runtime: ToolRuntime) -> str:
        """Generate ACF JSON field configuration using the approved fields."""
        description = runtime.state.get("block_description", "")
        block_name = runtime.state.get("block_name", "")
        php_template = runtime.state.get("php_template", "")
        approved_fields = runtime.state.get("approved_fields", [])
        output_dir = Path(runtime.state.get("output_dir", "output"))

        if not php_template:
            return "Error: PHP template must be generated first."

        # Enhance description with approved fields
        fields_desc = "\n".join([
            f"- {f.get('name')} ({f.get('type', 'text')}): {f.get('label', f.get('name'))}"
            for f in approved_fields
        ])
        enhanced_description = f"{description}\n\nApproved fields (use these exact fields):\n{fields_desc}"

        print_status("Generating ACF JSON with approved fields...", "working")

        try:
            acf_json = acf_agent.create_field_group(
                block_description=enhanced_description,
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

            acf_formatted = acf_agent.format_json(acf_json)
            group_key = acf_json.get("key", f"group_{block_name}")
            acf_path = save_output(acf_formatted, f"{group_key}.json", output_dir)
            print_status(f"ACF JSON saved to: {acf_path}", "success")

            return Command(update={
                "acf_json": acf_json,
                "messages": [ToolMessage(f"ACF JSON generated: {acf_path}", tool_call_id=runtime.tool_call_id)],
            })

        except Exception as e:
            print_status(f"Failed to generate ACF JSON: {e}", "error")
            return f"Error generating ACF JSON: {e}"
    
    # This tool just creates a nice summary
    @tool
    def summarize_results(runtime: ToolRuntime) -> str:
        """Summarize what was generated for the user."""
        block_name = runtime.state.get("block_name", "unknown")
        output_dir = runtime.state.get("output_dir", "output")
        php_template = runtime.state.get("php_template")
        acf_json = runtime.state.get("acf_json")
        approved_fields = runtime.state.get("approved_fields", [])

        results = [f"Block '{block_name}' generated successfully!"]
        results.append(f"Output directory: {output_dir}")

        if approved_fields:
            results.append(f"\nFields included ({len(approved_fields)}):")
            for f in approved_fields:
                results.append(f"  - {f.get('name')} ({f.get('type', 'text')})")

        results.append("\nGenerated files:")
        if php_template:
            results.append(f"  - PHP template: {block_name}.php")
        if acf_json and "error" not in acf_json:
            group_key = acf_json.get("key", f"group_{block_name}")
            results.append(f"  - ACF JSON: {group_key}.json")

        return "\n".join(results)


    # Create the main agent with HITL middleware
    orchestrator = create_agent(
        model=model,
        tools=[update_block_info, propose_fields, generate_php_template, generate_acf_json, summarize_results],
        state_schema=BlockState,
        checkpointer=InMemorySaver(),
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "update_block_info": False,
                    "propose_fields": True,  # Interrupt for field approval
                    "generate_php_template": False,
                    "generate_acf_json": False,
                    "summarize_results": False,
                },
                description_prefix="Field proposal requires your approval",
            ),
        ],
        system_prompt="""You are a WordPress block development assistant that orchestrates the creation of ACF blocks.

When a user describes a block they want, execute these steps IN ORDER without stopping:

1. Call update_block_info to initialize the block details
2. Call propose_fields with a JSON array of fields. Each field needs: name (snake_case), type (ACF field type), label, required (boolean), description
3. After field approval, IMMEDIATELY call generate_php_template - do not explain or discuss
4. IMMEDIATELY call generate_acf_json - do not explain or discuss
5. IMMEDIATELY call summarize_results

IMPORTANT: After each tool call completes, immediately call the next tool. DO NOT RESPOND WITH TEXT UNTIL ALL STEPS HAVE BEEN COMPLETED.

The only time to pause is when propose_fields triggers the human review. After approval, continue executing tools without commentary."""
    )

    return orchestrator


def print_welcome():
    """Print welcome message and instructions."""
    print("\n" + "=" * 60)
    print("🚀 WordPress Block Agent")
    print("=" * 60)
    print("\nI'll help you create WordPress ACF blocks!")
    print("\nDescribe the block you want to create, and I'll:")
    print("  1. Propose fields for your review")
    print("  2. Generate a PHP template with approved fields")
    print("  3. Create an ACF JSON field configuration")
    print("\nType 'exit' to quit.\n")


def main():
    """Main conversational loop with HITL support."""
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
    config = None
    in_block_session = False
    response = None

    while True:
        # ============================================
        # PHASE A: Start new block if not in session
        # ============================================
        if not in_block_session:
            print("\n" + "-" * 40)
            try:
                user_input = input("📝 Describe your block (or 'exit'): ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n\nGoodbye! 👋")
                break

            if not user_input:
                continue

            if classify_user_intent(user_input) == "exit":
                print("\nGoodbye! 👋")
                break

            try:
                user_block_name = input("📝 Provide a name for the block: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n\nGoodbye! 👋")
                break

            if not user_block_name:
                print("Please enter a block name...")
                continue

            # Start new session
            thread_id += 1
            config = {"configurable": {"thread_id": str(thread_id)}}
            sanitized_name = sanitize_block_name(user_block_name)

            print(f"\n🚀 Creating block: \"{user_block_name}\"")

            kickoff_message = f"Block Title: {user_block_name} \n\n Block Name (slug): {sanitized_name} \n\n Block Description: {user_input}"

            try:
                response = orchestrator.invoke(
                    {"messages": [HumanMessage(content=kickoff_message)]},
                    config=config
                )
                in_block_session = True
            except Exception as e:
                print_status(f"Error during generation: {e}", "error")
                import traceback
                traceback.print_exc()
                continue

        # ============================================
        # PHASE B: Conversational block session
        # ============================================
        while in_block_session:
            state = get_current_state(orchestrator, config)

            # B1: Handle HITL interrupt
            if response and response.get('__interrupt__'):
                interrupt = response['__interrupt__'][0]
                action_request = interrupt.value.get('action_requests', [{}])[0]
                tool_name = action_request.get('name', '')

                if tool_name == 'propose_fields':
                    fields_json = action_request.get('args', {}).get('fields', '[]')
                    try:
                        fields = json.loads(fields_json)
                    except json.JSONDecodeError:
                        fields = []

                    decision = get_user_field_decision(fields)

                    try:
                        response = orchestrator.invoke(
                            Command(resume={"decisions": [decision]}),
                            config=config
                        )
                    except Exception as e:
                        print_status(f"Error resuming: {e}", "error")
                        import traceback
                        traceback.print_exc()
                else:
                    # Unknown interrupt, approve by default
                    try:
                        response = orchestrator.invoke(
                            Command(resume={"decisions": [{"type": "approve"}]}),
                            config=config
                        )
                    except Exception as e:
                        print_status(f"Error resuming: {e}", "error")
                        import traceback
                        traceback.print_exc()
                continue  # Re-evaluate after resume

            # B2: Check if block is complete
            if is_block_complete(state):
                if response and response.get("messages"):
                    final_message = response["messages"][-1].content
                    print("\n" + "=" * 40)
                    print(final_message)

                print_status("Block generation finished!", "success")
                print("\nWhat would you like to do?")
                print("  - Describe a new block to create another")
                print("  - Type 'exit' to quit\n")

                # Exit to new loop by turning off block session
                in_block_session = False
                response = None
                break

            # B3: Block not complete and no interrupt - LLM returned text
            # This is the conversational continuation case
            if response and response.get("messages"):
                last_message = response["messages"][-1].content
                print("\n" + "-" * 40)
                print(f"🤖 Assistant: {last_message}")

            # Get user feedback/continuation
            print()
            try:
                user_feedback = input("💬 You: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n\nGoodbye! 👋")
                return

            if not user_feedback:
                user_feedback = "Please continue with the next step."

            intent = classify_user_intent(user_feedback)

            if intent == "exit":
                print("\nGoodbye! 👋")
                return

            if intent == "new_block":
                if not is_block_complete(state) and state.get("block_name"):
                    print(f"\n⚠️  Warning: Block '{state.get('block_name')}' is incomplete.")
                    try:
                        confirm = input("Start new block anyway? (y/n): ").strip().lower()
                    except (KeyboardInterrupt, EOFError):
                        print("\n\nGoodbye! 👋")
                        return
                    if confirm != 'y':
                        continue
                # Exit to new loop by turning off block session
                in_block_session = False
                response = None
                break

            # Continue conversation with user feedback
            try:
                response = orchestrator.invoke(
                    {"messages": [HumanMessage(content=user_feedback)]},
                    config=config
                )
            except Exception as e:
                print_status(f"Error: {e}", "error")
                import traceback
                traceback.print_exc()


if __name__ == "__main__":
    main()
