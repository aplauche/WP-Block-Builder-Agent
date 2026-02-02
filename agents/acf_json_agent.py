"""ACF JSON Agent - Creates ACF field group JSON files using create_agent pattern."""

import json
import uuid
from pathlib import Path

from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic
from langchain.tools import tool


def load_acf_reference() -> str:
    """Load the ACF reference documentation."""
    ref_path = Path(__file__).parent.parent / "docs" / "acf_reference.md"
    if ref_path.exists():
        return ref_path.read_text()
    return "ACF reference not found."


ACF_JSON_SYSTEM_PROMPT = """You are an expert WordPress developer specializing in Advanced Custom Fields (ACF) configuration.

Your task is to create an ACF field group JSON file based on:
1. The user's block description
2. The PHP template that was generated (analyze the get_field() calls)
3. The ACF reference documentation provided below

## ACF Reference Documentation:
{acf_reference}

## Guidelines:
1. Analyze the PHP template to identify all fields used via get_field()
2. Infer appropriate field types based on:
   - Variable naming (e.g., "image" suggests image field, "items" suggests repeater)
   - How the field is used in the template (e.g., wp_get_attachment_image suggests image)
   - Context from the block description
3. Generate unique keys using the format shown in the reference
4. Set appropriate field properties (required, defaults, etc.)
5. Use the block name for the location rule

When you have created the JSON configuration, use the save_json tool to save it.
Output ONLY valid JSON when calling save_json - no explanations or markdown.
"""


class ACFJsonAgent:
    """Agent that creates ACF JSON field group files."""

    def __init__(self, model_name: str = "claude-sonnet-4-20250514"):
        self.model = ChatAnthropic(model=model_name, temperature=0.2)
        self.acf_reference = load_acf_reference()
        self.generated_json = None

        # Define the tool for saving JSON
        @tool
        def save_json(json_config: str) -> str:
            """Save the generated ACF JSON configuration. Call this when you have finished creating the field group.

            Args:
                json_config: The complete ACF field group JSON as a string
            """
            self.generated_json = json_config
            return "JSON configuration saved successfully."

        self.tools = [save_json]

        # Inject the ACF reference into the system prompt
        system_prompt = ACF_JSON_SYSTEM_PROMPT.format(acf_reference=self.acf_reference)

        self.agent = create_agent(
            model=self.model,
            tools=self.tools,
            system_prompt=system_prompt
        )

    def _generate_unique_key(self, prefix: str = "field") -> str:
        """Generate a unique ACF-style key."""
        return f"{prefix}_{uuid.uuid4().hex[:13]}"

    def create_field_group(self, block_description: str, block_name: str, php_template: str) -> dict:
        """Generate an ACF field group JSON based on the block and template."""
        from langchain_core.messages import HumanMessage

        self.generated_json = None

        response = self.agent.invoke({
            "messages": [HumanMessage(content=f"""Create an ACF field group JSON for this block:

## Block Description:
{block_description}

## Block Name (for registration):
{block_name}

## Generated PHP Template:
```php
{php_template}
```

Generate the complete ACF JSON field group configuration and save it using the save_json tool.""")]
        })

        # Parse the saved JSON
        if self.generated_json:
            result = self.generated_json.strip()
            # Clean up in case it includes markdown code blocks
            if result.startswith("```json"):
                result = result[7:]
            if result.startswith("```"):
                result = result[3:]
            if result.endswith("```"):
                result = result[:-3]
            result = result.strip()

            try:
                return json.loads(result)
            except json.JSONDecodeError as e:
                return {
                    "error": f"Failed to parse JSON: {e}",
                    "raw_output": result
                }

        # Fallback: try to extract JSON from response
        last_message = response["messages"][-1].content
        return {
            "error": "No JSON was saved by the agent",
            "raw_output": last_message
        }

    def format_json(self, field_group: dict) -> str:
        """Format the field group as pretty JSON."""
        return json.dumps(field_group, indent=4)
