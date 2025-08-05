import os

from opentelemetry import trace
from pydantic_ai import ModelRetry, Tool

from utils import Logger


class FileReadTool:
    def __init__(self):
        pass

    def get_tool(self):
        return Tool(self._run, name="Read-File", takes_ctx=False, max_retries=2)

    def _run(self, file_path: str, line_number: int = 0, line_count: int = 200) -> str:
        """Read a file and return its contents.

        Args:
            file_path (str): The path to the file to read.
            line_number (int, optional): The starting line number to read from. Defaults to 0.
            line_count (int, optional): The number of lines to read. Defaults to 200.

        Returns:
            str: The contents of the file from the specified line number for the specified number of lines.
                If the file is a .go file, returns an error message directing to use the Go-Analyzer-Tool.
                If the file cannot be read, returns an error message with details about the failure.
        """
        Logger.debug("Tool Call: Read File", data={"file_path": file_path})

        trace.get_current_span().set_attribute("input", file_path)

        if not os.path.exists(file_path):
            raise ModelRetry(message="File not found")

        try:
            with open(file_path, "r") as file:
                lines = file.readlines()
                total_lines = len(lines)

                if line_number > 0:
                    lines = lines[line_number:]
                if line_count > 0:
                    lines = lines[:line_count]

                output = (
                    f"File Line:{line_number} to {line_number + line_count} from: {total_lines}\n--- start---\n"
                    + "".join(lines)
                    + "\n--- end ---\n"
                )
                trace.get_current_span().set_attribute("output", output)

                return output
        except PermissionError:
            raise ModelRetry(message="Permission denied when trying to read file")
        except Exception as e:
            raise ModelRetry(message=f"Failed to read file {file_path}. {str(e)}")
