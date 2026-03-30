from core.claude import Claude
from mcp_client import MCPClient
from core.tools import ToolManager


class Chat:
    def __init__(self, claude_service: Claude, clients: dict[str, MCPClient]):
        self.claude_service: Claude = claude_service
        self.clients: dict[str, MCPClient] = clients
        self.messages: list[dict] = []

    async def _process_query(self, query: str):
        self.messages.append({"role": "user", "content": query})

    async def run(self, query: str) -> str:
        final_text_response = ""

        await self._process_query(query)

        while True:
            response = self.claude_service.chat(
                messages=self.messages,
                tools=await ToolManager.get_all_tools(self.clients),
            )

            self.claude_service.add_assistant_message(self.messages, response)

            if response.choices[0].finish_reason == "tool_calls":
                print(self.claude_service.text_from_message(response))
                tool_result_messages = await ToolManager.execute_tool_requests(
                    self.clients, response
                )
                # Each tool result is its own message in OpenAI's format
                self.messages.extend(tool_result_messages)
            else:
                final_text_response = self.claude_service.text_from_message(response)
                break

        return final_text_response
