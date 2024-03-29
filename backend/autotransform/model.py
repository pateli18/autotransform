import json
import logging
import re
from typing import AsyncGenerator

import httpx

from autotransform.autotransform_types import OpenAiChatInput
from autotransform.utils import settings

logger = logging.getLogger(__name__)

TIMEOUT = 30
model_client = httpx.AsyncClient()


async def send_openai_request(
    client: httpx.AsyncClient,
    request_payload: dict,
    route: str,
) -> dict:
    url = f"https://api.openai.com/v1/{route}"
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    response = await client.post(
        url,
        headers=headers,
        json=request_payload,
        timeout=httpx.Timeout(TIMEOUT),
    )
    response.raise_for_status()
    response_output = response.json()
    return response_output


async def _stream_openai_chat_api(
    client: httpx.AsyncClient,
    openai_input: OpenAiChatInput,
) -> AsyncGenerator[str, None]:
    async with client.stream(
        "POST",
        "https://api.openai.com/v1/chat/completions",
        timeout=httpx.Timeout(TIMEOUT),
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
        },
        json=openai_input.data,
    ) as response:
        logger.debug(f"received response status_code={response.status_code}")
        response.raise_for_status()
        async for chunk in response.aiter_text():
            yield chunk


async def openai_stream_response_generator(
    client: httpx.AsyncClient,
    openai_chat_input: OpenAiChatInput,
) -> AsyncGenerator[dict, None]:
    content = ""
    func_call = {"arguments": ""}
    error_message = None
    try:
        async for response in _stream_openai_chat_api(
            client, openai_chat_input
        ):
            for block_raw in response.split("\n\n"):
                for line in block_raw.split("\n"):
                    if line.startswith("data:"):
                        json_str = line.replace("data:", "").strip()
                        if json_str == "[DONE]":
                            break
                        else:
                            try:
                                block = json.loads(json_str)
                            # skip any json decode errors
                            except Exception as e:
                                logger.debug(e)
                                continue

                            # we assume that we only need to look at the first choice
                            choice = block["choices"][0]
                            delta = choice.get("delta")
                            if delta is None:
                                continue
                            elif "function_call" in delta:
                                name = delta["function_call"].get("name")
                                if name:
                                    func_call["name"] = name
                                arguments = delta["function_call"].get(
                                    "arguments"
                                )
                                if arguments:
                                    func_call["arguments"] += arguments
                            elif "content" in delta:
                                content += delta["content"]
                                yield {"content": content}
        if func_call.get("name"):
            yield {"func_call": func_call}

    except Exception as e:
        logger.exception("Error in openai_stream_response_generator")
        error_message = str(e)
        yield {"error": error_message}


def parse_json_output(raw_output: str) -> dict:
    groups = re.search(r"```json(.*)```", raw_output, re.DOTALL)
    if groups is None:
        model_output = json.loads(raw_output)
    else:
        model_output = json.loads(groups.group(1).strip())

    return model_output
