from crewai import Agent, Crew, Task, Process


def build_crew(agent_name: str, input_data: dict) -> Crew:
    """
    Returns a single-agent Crew for the requested agent.
    Phase 3 will expand each agent with real tools.
    """
    agent = Agent(
        role=f"{agent_name.capitalize()} Agent",
        goal=f"Execute the {agent_name} workflow for the YouTube automation system",
        backstory="AI agent in the NemoClaw YouTube automation pipeline",
        verbose=True,
        allow_delegation=False,
    )
    task = Task(
        description=f"Run {agent_name} workflow with input: {input_data}",
        agent=agent,
        expected_output=f"JSON result from {agent_name} agent",
    )
    return Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True)
