"""PHP Template Agent - Creates WordPress ACF block templates using create_agent pattern."""

from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic
from langchain.tools import tool


PHP_TEMPLATE_SYSTEM_PROMPT = """You are an expert WordPress developer specializing in Advanced Custom Fields (ACF) block development.

Your task is to create a PHP template file for an ACF block based on the user's description.

Follow these guidelines:
1. Use ACF's get_field() function to retrieve field values
2. Include proper escaping with esc_html(), esc_attr(), esc_url() as appropriate
3. Use WordPress coding standards
4. Include helpful comments explaining the template structure
5. Use semantic HTML5 elements
6. Include BEM-style CSS class naming for easy styling
7. Handle empty/missing field values gracefully

When you have created the template, use the save_template tool to save it.

Example structure:
```php
<?php
/**
 * Block Name: [Block Name]
 * Description: [Brief description]
 */

// Get block ID and classes
$block_id = 'block-' . $block['id'];
$block_classes = 'acf-block block-name';
if (!empty($block['className'])) {
    $block_classes .= ' ' . $block['className'];
}

// Get field values
$field_name = get_field('field_name');
?>

<div id="<?php echo esc_attr($block_id); ?>" class="<?php echo esc_attr($block_classes); ?>">
    <!-- Block content here -->
</div>
```
"""


class PHPTemplateAgent:
    """Agent that creates PHP template files for ACF blocks."""

    def __init__(self, model_name: str = "claude-sonnet-4-20250514"):
        self.model = ChatAnthropic(model=model_name, temperature=0.3)
        self.generated_template = None

        # Define the tool for saving templates
        @tool
        def save_template(php_code: str) -> str:
            """Save the generated PHP template code. Call this when you have finished creating the template.

            Args:
                php_code: The complete PHP template code starting with <?php
            """
            self.generated_template = php_code
            return "Template saved successfully."

        self.tools = [save_template]

        self.agent = create_agent(
            model=self.model,
            tools=self.tools,
            system_prompt=PHP_TEMPLATE_SYSTEM_PROMPT
        )

    def create_template(self, block_description: str) -> str:
        """Generate a PHP template based on the block description."""
        from langchain_core.messages import HumanMessage

        self.generated_template = None

        response = self.agent.invoke({
            "messages": [HumanMessage(content=f"Create a PHP template for the following WordPress block:\n\n{block_description}")]
        })

        # Return the saved template or extract from response
        if self.generated_template:
            return self.generated_template

        # Fallback: try to extract PHP from the response
        last_message = response["messages"][-1].content
        if "<?php" in last_message:
            start = last_message.find("<?php")
            return last_message[start:]

        return last_message

    def extract_fields_from_template(self, template: str) -> list[dict]:
        """Extract field information from the generated template for the ACF agent."""
        import re
        fields = []

        # Find all get_field() calls
        pattern = r"get_field\(['\"]([^'\"]+)['\"]\)"
        matches = re.findall(pattern, template)

        for field_name in matches:
            fields.append({
                "name": field_name,
                "label": field_name.replace("_", " ").title()
            })

        return fields
