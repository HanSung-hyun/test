# Python Code Execution Policy
When executing or testing Python code, you must strictly follow these rules to avoid terminal parsing errors, permission prompts, and redundant round-trips:

1. NEVER use inline execution like `python -c "..."`.
2. Always write the code to a file named `temp.py` in the project root directory.
3. CRITICAL: Always overwrite `temp.py` completely (`Overwrite: true`). Never append to it, ensuring no stale code from previous turns remains.
4. Execute the file using the exact fixed command: `python temp.py`
5. Do not ask for user confirmation in the chat; proceed directly with the execution tool call.
6. Ensure the script handles UTF-8 encoding properly (e.g., include `# -*- coding: utf-8 -*-`) to prevent Windows console encoding errors.
