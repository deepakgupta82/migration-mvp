## How to Think & Work
- Always analyze the request → break it into **clear, actionable tasks**.  
- Present the **task list and plan first**, then execute step by step.  
- Provide **progress updates** during execution, and summarize at the end.  


## Coding Standards
- Always read the **entire file** before modifying to avoid duplication or conflicts.  
- Deliver **complete, production-ready implementations** (never dummy code).  
- Use **modularity, readability, and maintainability** as guiding principles.  
- Run **linting and static analysis checks** mentally before finalizing code.  
- Organize code into **separate files and layers** when appropriate.  

## Development Discipline
- **Commit early and often** at logical milestones.  
- When using external libraries, **verify current syntax** (do not assume outdated APIs).  
- Never skip required libraries or say “not working”—investigate root cause.  
- Apply **defensive programming**: input validation, error handling, logging.  
- Always consider **edge cases and scalability constraints**.  

## Documentation
- Add **docstrings and inline comments** for clarity.  

## Problem-Solving Approach
- Break large requests into **smaller subtasks**.  
- If blocked, debug root cause instead of random guessing.  
- Provide **impact analysis** for every change (what files, what risks, what next).  

## For this particular project
- All the services are running locally on this dev machine except minio, weaviate, postgresql, promtail, loki, redis and neo4j
- Each service running locally is running in python 3.11 .venv present in its folder except for backend service which is running in python 3.10 in its .venv which is located in "c:\Users\deepakgupta13\forappbackendvenv\backend-venv\scripts" folder
