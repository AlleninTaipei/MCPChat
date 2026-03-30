from openai import OpenAI


class Claude:
    def __init__(self, model: str):
        self.client = OpenAI()  # reads OPENAI_API_KEY from environment
        self.model = model

    def add_user_message(self, messages: list, content):
        if isinstance(content, list):
            # List of individual tool result messages — extend directly
            messages.extend(content)
        else:
            messages.append({"role": "user", "content": content})

    def add_assistant_message(self, messages: list, response):
        msg = response.choices[0].message
        assistant_msg = {"role": "assistant", "content": msg.content}
        if msg.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ]
        messages.append(assistant_msg)

    def text_from_message(self, response) -> str:
        return response.choices[0].message.content or ""

    def chat(
        self,
        messages,
        system=None,
        temperature=1.0,
        stop_sequences=None,
        tools=None,
        **kwargs,
    ):
        all_messages = messages
        if system:
            all_messages = [{"role": "system", "content": system}] + messages

        params = {
            "model": self.model,
            "max_tokens": 8000,
            "messages": all_messages,
            "temperature": temperature,
        }

        if stop_sequences:
            params["stop"] = stop_sequences

        if tools:
            params["tools"] = tools

        return self.client.chat.completions.create(**params)
