from agno.agent import Agent
from agno.cli.console import console
from agno.models.anthropic import Claude
from agno.models.deepseek import DeepSeek
from agno.models.openai import OpenAIChat

task = "9.11 and 9.9 -- which is bigger?"

reasoning_agent_claude = Agent(
    model=Claude("claude-3-5-sonnet-20241022"),
    reasoning=True,
    reasoning_model=DeepSeek(id="deepseek-reasoner"),
)

reasoning_agent_openai = Agent(
    model=OpenAIChat(id="gpt-4o"),
    reasoning=True,
    reasoning_model=DeepSeek(id="deepseek-reasoner"),
)

console.rule("[bold green]Claude Reasoning Agent[/bold green]")
reasoning_agent_claude.print_response(task, stream=True)
console.rule("[bold yellow]OpenAI Reasoning Agent[/bold yellow]")
reasoning_agent_openai.print_response(task, stream=True, show_full_reasoning=True)
