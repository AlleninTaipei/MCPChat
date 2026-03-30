import json
from typing import Optional
from mcp.types import CallToolResult, TextContent
from mcp_client import MCPClient


class ToolManager:
    @classmethod
    async def get_all_tools(cls, clients: dict[str, MCPClient]) -> list[dict]:
        """Gets all tools from the provided clients in OpenAI function-calling format."""
        tools = []
        for client in clients.values():
            tool_models = await client.list_tools()
            tools += [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.inputSchema,
                    },
                }
                for t in tool_models
            ]
        return tools

    @classmethod
    async def _find_client_with_tool(
        cls, clients: list[MCPClient], tool_name: str
    ) -> Optional[MCPClient]:
        """Finds the first client that has the specified tool."""
        for client in clients:
            tools = await client.list_tools()
            tool = next((t for t in tools if t.name == tool_name), None)
            if tool:
                return client
        return None

    @classmethod
    async def execute_tool_requests(
        cls, clients: dict[str, MCPClient], response
    ) -> list[dict]:
        """Executes tool calls from an OpenAI response and returns role='tool' messages."""
        tool_calls = response.choices[0].message.tool_calls or []
        results = []

        for tc in tool_calls:
            tool_name = tc.function.name
            tool_use_id = tc.id
            try:
                tool_input = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                tool_input = {}

            client = await cls._find_client_with_tool(
                list(clients.values()), tool_name
            )

            if not client:
                results.append({
                    "role": "tool",
                    "tool_call_id": tool_use_id,
                    "content": "Could not find that tool",
                })
                continue

            try:
                tool_output: CallToolResult | None = await client.call_tool(
                    tool_name, tool_input
                )
                items = tool_output.content if tool_output else []
                content_list = [
                    item.text for item in items if isinstance(item, TextContent)
                ]
                content = json.dumps(content_list)
            except Exception as e:
                content = json.dumps({"error": f"Error executing tool '{tool_name}': {e}"})

            results.append({
                "role": "tool",
                "tool_call_id": tool_use_id,
                "content": content,
            })

        return results
