#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import asyncio
import json
import logging
import os
import random
import re
import threading
import time
from abc import ABC
from copy import deepcopy
from urllib.parse import urljoin

import json_repair
import litellm
import openai
from openai import AsyncOpenAI, OpenAI
from openai.lib.azure import AzureOpenAI
from strenum import StrEnum

from common.token_utils import num_tokens_from_string, total_token_count_from_response
from rag.llm import FACTORY_DEFAULT_BASE_URL, LITELLM_PROVIDER_PREFIX, SupportedLiteLLMProvider
from rag.nlp import is_chinese, is_english


# Error message constants
class LLMErrorCode(StrEnum):
    ERROR_RATE_LIMIT = "RATE_LIMIT_EXCEEDED"
    ERROR_AUTHENTICATION = "AUTH_ERROR"
    ERROR_INVALID_REQUEST = "INVALID_REQUEST"
    ERROR_SERVER = "SERVER_ERROR"
    ERROR_TIMEOUT = "TIMEOUT"
    ERROR_CONNECTION = "CONNECTION_ERROR"
    ERROR_MODEL = "MODEL_ERROR"
    ERROR_MAX_ROUNDS = "ERROR_MAX_ROUNDS"
    ERROR_CONTENT_FILTER = "CONTENT_FILTERED"
    ERROR_QUOTA = "QUOTA_EXCEEDED"
    ERROR_MAX_RETRIES = "MAX_RETRIES_EXCEEDED"
    ERROR_GENERIC = "GENERIC_ERROR"


class ReActMode(StrEnum):
    FUNCTION_CALL = "function_call"
    REACT = "react"


ERROR_PREFIX = "**ERROR**"
LENGTH_NOTIFICATION_CN = "······\n由于大模型的上下文窗口大小限制，回答已经被大模型截断。"
LENGTH_NOTIFICATION_EN = "...\nThe answer is truncated by your chosen LLM due to its limitation on context length."


class Base(ABC):
    def __init__(self, key, model_name, base_url, **kwargs):
        timeout = int(os.environ.get("LLM_TIMEOUT_SECONDS", 600))
        self.client = OpenAI(api_key=key, base_url=base_url, timeout=timeout)
        self.async_client = AsyncOpenAI(api_key=key, base_url=base_url, timeout=timeout)
        self.model_name = model_name
        # Configure retry parameters
        self.max_retries = kwargs.get("max_retries", int(os.environ.get("LLM_MAX_RETRIES", 5)))
        self.base_delay = kwargs.get("retry_interval", float(os.environ.get("LLM_BASE_DELAY", 2.0)))
        self.max_rounds = kwargs.get("max_rounds", 5)
        self.is_tools = False
        self.tools = []
        self.toolcall_sessions = {}

    def _get_delay(self):
        """Calculate retry delay time"""
        return self.base_delay * random.uniform(10, 150)

    def _classify_error(self, error):
        """Classify error based on error message content"""
        error_str = str(error).lower()

        keywords_mapping = [
            (["quota", "capacity", "credit", "billing", "balance", "欠费"], LLMErrorCode.ERROR_QUOTA),
            (["rate limit", "429", "tpm limit", "too many requests", "requests per minute"], LLMErrorCode.ERROR_RATE_LIMIT),
            (["auth", "key", "apikey", "401", "forbidden", "permission"], LLMErrorCode.ERROR_AUTHENTICATION),
            (["invalid", "bad request", "400", "format", "malformed", "parameter"], LLMErrorCode.ERROR_INVALID_REQUEST),
            (["server", "503", "502", "504", "500", "unavailable"], LLMErrorCode.ERROR_SERVER),
            (["timeout", "timed out"], LLMErrorCode.ERROR_TIMEOUT),
            (["connect", "network", "unreachable", "dns"], LLMErrorCode.ERROR_CONNECTION),
            (["filter", "content", "policy", "blocked", "safety", "inappropriate"], LLMErrorCode.ERROR_CONTENT_FILTER),
            (["model", "not found", "does not exist", "not available"], LLMErrorCode.ERROR_MODEL),
            (["max rounds"], LLMErrorCode.ERROR_MODEL),
        ]
        for words, code in keywords_mapping:
            if re.search("({})".format("|".join(words)), error_str):
                return code

        return LLMErrorCode.ERROR_GENERIC

    def _clean_conf(self, gen_conf):
        if "max_tokens" in gen_conf:
            del gen_conf["max_tokens"]

        allowed_conf = {
            "temperature",
            "max_completion_tokens",
            "top_p",
            "stream",
            "stream_options",
            "stop",
            "n",
            "presence_penalty",
            "frequency_penalty",
            "functions",
            "function_call",
            "logit_bias",
            "user",
            "response_format",
            "seed",
            "tools",
            "tool_choice",
            "logprobs",
            "top_logprobs",
            "extra_headers",
        }

        gen_conf = {k: v for k, v in gen_conf.items() if k in allowed_conf}

        model_name_lower = (self.model_name or "").lower()
        # gpt-5 and gpt-5.1 endpoints have inconsistent parameter support, clear custom generation params to prevent unexpected issues
        if "gpt-5" in model_name_lower:
            gen_conf = {}

        return gen_conf

    def _bridge_sync_stream(self, gen):
        """Run a sync generator in a thread and yield asynchronously."""
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def worker():
            try:
                for item in gen:
                    loop.call_soon_threadsafe(queue.put_nowait, item)
            except Exception as exc:  # pragma: no cover - defensive
                loop.call_soon_threadsafe(queue.put_nowait, exc)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, StopAsyncIteration)

        threading.Thread(target=worker, daemon=True).start()
        return queue

    def _chat(self, history, gen_conf, **kwargs):
        logging.info("[HISTORY]" + json.dumps(history, ensure_ascii=False, indent=2))
        if self.model_name.lower().find("qwq") >= 0:
            logging.info(f"[INFO] {self.model_name} detected as reasoning model, using _chat_streamly")

            final_ans = ""
            tol_token = 0
            for delta, tol in self._chat_streamly(history, gen_conf, with_reasoning=False, **kwargs):
                if delta.startswith("<think>") or delta.endswith("</think>"):
                    continue
                final_ans += delta
                tol_token = tol

            if len(final_ans.strip()) == 0:
                final_ans = "**ERROR**: Empty response from reasoning model"

            return final_ans.strip(), tol_token

        if self.model_name.lower().find("qwen3") >= 0:
            kwargs["extra_body"] = {"enable_thinking": False}

        response = self.client.chat.completions.create(model=self.model_name, messages=history, **gen_conf, **kwargs)

        if not response.choices or not response.choices[0].message or not response.choices[0].message.content:
            return "", 0
        ans = response.choices[0].message.content.strip()
        if response.choices[0].finish_reason == "length":
            ans = self._length_stop(ans)
        return ans, total_token_count_from_response(response)

    def _chat_streamly(self, history, gen_conf, **kwargs):
        logging.info("[HISTORY STREAMLY]" + json.dumps(history, ensure_ascii=False, indent=4))
        reasoning_start = False

        if kwargs.get("stop") or "stop" in gen_conf:
            response = self.client.chat.completions.create(model=self.model_name, messages=history, stream=True, **gen_conf, stop=kwargs.get("stop"))
        else:
            response = self.client.chat.completions.create(model=self.model_name, messages=history, stream=True, **gen_conf)

        for resp in response:
            if not resp.choices:
                continue
            if not resp.choices[0].delta.content:
                resp.choices[0].delta.content = ""
            if kwargs.get("with_reasoning", True) and hasattr(resp.choices[0].delta, "reasoning_content") and resp.choices[0].delta.reasoning_content:
                ans = ""
                if not reasoning_start:
                    reasoning_start = True
                    ans = "<think>"
                ans += resp.choices[0].delta.reasoning_content + "</think>"
            else:
                reasoning_start = False
                ans = resp.choices[0].delta.content

            tol = total_token_count_from_response(resp)
            if not tol:
                tol = num_tokens_from_string(resp.choices[0].delta.content)

            if resp.choices[0].finish_reason == "length":
                if is_chinese(ans):
                    ans += LENGTH_NOTIFICATION_CN
                else:
                    ans += LENGTH_NOTIFICATION_EN
            yield ans, tol

    async def _async_chat_stream(self, history, gen_conf, **kwargs):
        logging.info("[HISTORY STREAMLY]" + json.dumps(history, ensure_ascii=False, indent=4))
        reasoning_start = False

        request_kwargs = {"model": self.model_name, "messages": history, "stream": True, **gen_conf}
        stop = kwargs.get("stop")
        if stop:
            request_kwargs["stop"] = stop

        response = await self.async_client.chat.completions.create(**request_kwargs)

        async for resp in response:
            if not resp.choices:
                continue
            if not resp.choices[0].delta.content:
                resp.choices[0].delta.content = ""
            if kwargs.get("with_reasoning", True) and hasattr(resp.choices[0].delta, "reasoning_content") and resp.choices[0].delta.reasoning_content:
                ans = ""
                if not reasoning_start:
                    reasoning_start = True
                    ans = "<think>"
                ans += resp.choices[0].delta.reasoning_content + "</think>"
            else:
                reasoning_start = False
                ans = resp.choices[0].delta.content

            tol = total_token_count_from_response(resp)
            if not tol:
                tol = num_tokens_from_string(resp.choices[0].delta.content)

            finish_reason = resp.choices[0].finish_reason if hasattr(resp.choices[0], "finish_reason") else ""
            if finish_reason == "length":
                if is_chinese(ans):
                    ans += LENGTH_NOTIFICATION_CN
                else:
                    ans += LENGTH_NOTIFICATION_EN
            yield ans, tol

    async def async_chat_streamly(self, system, history, gen_conf: dict = {}, **kwargs):
        if system and history and history[0].get("role") != "system":
            history.insert(0, {"role": "system", "content": system})
        gen_conf = self._clean_conf(gen_conf)
        ans = ""
        total_tokens = 0
        try:
            async for delta_ans, tol in self._async_chat_stream(history, gen_conf, **kwargs):
                ans = delta_ans
                total_tokens += tol
                yield delta_ans
        except openai.APIError as e:
            yield ans + "\n**ERROR**: " + str(e)

        yield total_tokens

    def _length_stop(self, ans):
        if is_chinese([ans]):
            return ans + LENGTH_NOTIFICATION_CN
        return ans + LENGTH_NOTIFICATION_EN

    @property
    def _retryable_errors(self) -> set[str]:
        return {
            LLMErrorCode.ERROR_RATE_LIMIT,
            LLMErrorCode.ERROR_SERVER,
        }

    def _should_retry(self, error_code: str) -> bool:
        return error_code in self._retryable_errors

    def _exceptions(self, e, attempt) -> str | None:
        logging.exception("OpenAI chat_with_tools")
        # Classify the error
        error_code = self._classify_error(e)
        if attempt == self.max_retries:
            error_code = LLMErrorCode.ERROR_MAX_RETRIES

        if self._should_retry(error_code):
            delay = self._get_delay()
            logging.warning(f"Error: {error_code}. Retrying in {delay:.2f} seconds... (Attempt {attempt + 1}/{self.max_retries})")
            time.sleep(delay)
            return None

        msg = f"{ERROR_PREFIX}: {error_code} - {str(e)}"
        logging.error(f"sync base giving up: {msg}")
        return msg

    async def _exceptions_async(self, e, attempt) -> str | None:
        logging.exception("OpenAI async completion")
        error_code = self._classify_error(e)
        if attempt == self.max_retries:
            error_code = LLMErrorCode.ERROR_MAX_RETRIES

        if self._should_retry(error_code):
            delay = self._get_delay()
            logging.warning(f"Error: {error_code}. Retrying in {delay:.2f} seconds... (Attempt {attempt + 1}/{self.max_retries})")
            await asyncio.sleep(delay)
            return None

        msg = f"{ERROR_PREFIX}: {error_code} - {str(e)}"
        logging.error(f"async base giving up: {msg}")
        return msg

    def _verbose_tool_use(self, name, args, res):
        return "<tool_call>" + json.dumps({"name": name, "args": args, "result": res}, ensure_ascii=False, indent=2) + "</tool_call>"

    def _append_history(self, hist, tool_call, tool_res):
        hist.append(
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "index": tool_call.index,
                        "id": tool_call.id,
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                        "type": "function",
                    },
                ],
            }
        )
        try:
            if isinstance(tool_res, dict):
                tool_res = json.dumps(tool_res, ensure_ascii=False)
        finally:
            hist.append({"role": "tool", "tool_call_id": tool_call.id, "content": str(tool_res)})
        return hist

    def bind_tools(self, toolcall_session, tools):
        if not (toolcall_session and tools):
            return
        self.is_tools = True
        self.toolcall_session = toolcall_session
        self.tools = tools

    def chat_with_tools(self, system: str, history: list, gen_conf: dict = {}):
        gen_conf = self._clean_conf(gen_conf)
        if system and history and history[0].get("role") != "system":
            history.insert(0, {"role": "system", "content": system})

        ans = ""
        tk_count = 0
        hist = deepcopy(history)
        # Implement exponential backoff retry strategy
        for attempt in range(self.max_retries + 1):
            history = hist
            try:
                for _ in range(self.max_rounds + 1):
                    logging.info(f"{self.tools=}")
                    response = self.client.chat.completions.create(model=self.model_name, messages=history, tools=self.tools, tool_choice="auto", **gen_conf)
                    tk_count += total_token_count_from_response(response)
                    if any([not response.choices, not response.choices[0].message]):
                        raise Exception(f"500 response structure error. Response: {response}")

                    if not hasattr(response.choices[0].message, "tool_calls") or not response.choices[0].message.tool_calls:
                        if hasattr(response.choices[0].message, "reasoning_content") and response.choices[0].message.reasoning_content:
                            ans += "<think>" + response.choices[0].message.reasoning_content + "</think>"

                        ans += response.choices[0].message.content
                        if response.choices[0].finish_reason == "length":
                            ans = self._length_stop(ans)

                        return ans, tk_count

                    for tool_call in response.choices[0].message.tool_calls:
                        logging.info(f"Response {tool_call=}")
                        name = tool_call.function.name
                        try:
                            args = json_repair.loads(tool_call.function.arguments)
                            tool_response = self.toolcall_session.tool_call(name, args)
                            history = self._append_history(history, tool_call, tool_response)
                            ans += self._verbose_tool_use(name, args, tool_response)
                        except Exception as e:
                            logging.exception(msg=f"Wrong JSON argument format in LLM tool call response: {tool_call}")
                            history.append({"role": "tool", "tool_call_id": tool_call.id, "content": f"Tool call error: \n{tool_call}\nException:\n" + str(e)})
                            ans += self._verbose_tool_use(name, {}, str(e))

                logging.warning(f"Exceed max rounds: {self.max_rounds}")
                history.append({"role": "user", "content": f"Exceed max rounds: {self.max_rounds}"})
                response, token_count = self._chat(history, gen_conf)
                ans += response
                tk_count += token_count
                return ans, tk_count
            except Exception as e:
                e = self._exceptions(e, attempt)
                if e:
                    return e, tk_count

        assert False, "Shouldn't be here."

    async def async_chat_with_tools(self, system: str, history: list, gen_conf: dict = {}):
        gen_conf = self._clean_conf(gen_conf)
        if system and history and history[0].get("role") != "system":
            history.insert(0, {"role": "system", "content": system})

        ans = ""
        tk_count = 0
        hist = deepcopy(history)
        for attempt in range(self.max_retries + 1):
            history = deepcopy(hist)
            try:
                for _ in range(self.max_rounds + 1):
                    logging.info(f"{self.tools=}")
                    response = await self.async_client.chat.completions.create(model=self.model_name, messages=history, tools=self.tools, tool_choice="auto", **gen_conf)
                    tk_count += total_token_count_from_response(response)
                    if any([not response.choices, not response.choices[0].message]):
                        raise Exception(f"500 response structure error. Response: {response}")

                    if not hasattr(response.choices[0].message, "tool_calls") or not response.choices[0].message.tool_calls:
                        if hasattr(response.choices[0].message, "reasoning_content") and response.choices[0].message.reasoning_content:
                            ans += "<think>" + response.choices[0].message.reasoning_content + "</think>"

                        ans += response.choices[0].message.content
                        if response.choices[0].finish_reason == "length":
                            ans = self._length_stop(ans)

                        return ans, tk_count

                    for tool_call in response.choices[0].message.tool_calls:
                        logging.info(f"Response {tool_call=}")
                        name = tool_call.function.name
                        try:
                            args = json_repair.loads(tool_call.function.arguments)
                            tool_response = await asyncio.to_thread(self.toolcall_session.tool_call, name, args)
                            history = self._append_history(history, tool_call, tool_response)
                            ans += self._verbose_tool_use(name, args, tool_response)
                        except Exception as e:
                            logging.exception(msg=f"Wrong JSON argument format in LLM tool call response: {tool_call}")
                            history.append({"role": "tool", "tool_call_id": tool_call.id, "content": f"Tool call error: \n{tool_call}\nException:\n" + str(e)})
                            ans += self._verbose_tool_use(name, {}, str(e))

                logging.warning(f"Exceed max rounds: {self.max_rounds}")
                history.append({"role": "user", "content": f"Exceed max rounds: {self.max_rounds}"})
                response, token_count = await self._async_chat(history, gen_conf)
                ans += response
                tk_count += token_count
                return ans, tk_count
            except Exception as e:
                e = await self._exceptions_async(e, attempt)
                if e:
                    return e, tk_count

        assert False, "Shouldn't be here."

    def chat(self, system, history, gen_conf={}, **kwargs):
        if system and history and history[0].get("role") != "system":
            history.insert(0, {"role": "system", "content": system})
        gen_conf = self._clean_conf(gen_conf)

        # Implement exponential backoff retry strategy
        for attempt in range(self.max_retries + 1):
            try:
                return self._chat(history, gen_conf, **kwargs)
            except Exception as e:
                e = self._exceptions(e, attempt)
                if e:
                    return e, 0
        assert False, "Shouldn't be here."

    def _wrap_toolcall_message(self, stream):
        final_tool_calls = {}

        for chunk in stream:
            for tool_call in chunk.choices[0].delta.tool_calls or []:
                index = tool_call.index

                if index not in final_tool_calls:
                    final_tool_calls[index] = tool_call

                final_tool_calls[index].function.arguments += tool_call.function.arguments

        return final_tool_calls

    def chat_streamly_with_tools(self, system: str, history: list, gen_conf: dict = {}):
        gen_conf = self._clean_conf(gen_conf)
        tools = self.tools
        if system and history and history[0].get("role") != "system":
            history.insert(0, {"role": "system", "content": system})

        total_tokens = 0
        hist = deepcopy(history)
        # Implement exponential backoff retry strategy
        for attempt in range(self.max_retries + 1):
            history = hist
            try:
                for _ in range(self.max_rounds + 1):
                    reasoning_start = False
                    logging.info(f"{tools=}")
                    response = self.client.chat.completions.create(model=self.model_name, messages=history, stream=True, tools=tools, tool_choice="auto", **gen_conf)
                    final_tool_calls = {}
                    answer = ""
                    for resp in response:
                        if resp.choices[0].delta.tool_calls:
                            for tool_call in resp.choices[0].delta.tool_calls or []:
                                index = tool_call.index

                                if index not in final_tool_calls:
                                    if not tool_call.function.arguments:
                                        tool_call.function.arguments = ""
                                    final_tool_calls[index] = tool_call
                                else:
                                    final_tool_calls[index].function.arguments += tool_call.function.arguments if tool_call.function.arguments else ""
                            continue

                        if any([not resp.choices, not resp.choices[0].delta, not hasattr(resp.choices[0].delta, "content")]):
                            raise Exception("500 response structure error.")

                        if not resp.choices[0].delta.content:
                            resp.choices[0].delta.content = ""

                        if hasattr(resp.choices[0].delta, "reasoning_content") and resp.choices[0].delta.reasoning_content:
                            ans = ""
                            if not reasoning_start:
                                reasoning_start = True
                                ans = "<think>"
                            ans += resp.choices[0].delta.reasoning_content + "</think>"
                            yield ans
                        else:
                            reasoning_start = False
                            answer += resp.choices[0].delta.content
                            yield resp.choices[0].delta.content

                        tol = total_token_count_from_response(resp)
                        if not tol:
                            total_tokens += num_tokens_from_string(resp.choices[0].delta.content)
                        else:
                            total_tokens = tol

                        finish_reason = resp.choices[0].finish_reason if hasattr(resp.choices[0], "finish_reason") else ""
                        if finish_reason == "length":
                            yield self._length_stop("")

                    if answer:
                        yield total_tokens
                        return

                    for tool_call in final_tool_calls.values():
                        name = tool_call.function.name
                        try:
                            args = json_repair.loads(tool_call.function.arguments)
                            yield self._verbose_tool_use(name, args, "Begin to call...")
                            tool_response = self.toolcall_session.tool_call(name, args)
                            history = self._append_history(history, tool_call, tool_response)
                            yield self._verbose_tool_use(name, args, tool_response)
                        except Exception as e:
                            logging.exception(msg=f"Wrong JSON argument format in LLM tool call response: {tool_call}")
                            history.append({"role": "tool", "tool_call_id": tool_call.id, "content": f"Tool call error: \n{tool_call}\nException:\n" + str(e)})
                            yield self._verbose_tool_use(name, {}, str(e))

                logging.warning(f"Exceed max rounds: {self.max_rounds}")
                history.append({"role": "user", "content": f"Exceed max rounds: {self.max_rounds}"})
                response = self.client.chat.completions.create(model=self.model_name, messages=history, stream=True, **gen_conf)
                for resp in response:
                    if any([not resp.choices, not resp.choices[0].delta, not hasattr(resp.choices[0].delta, "content")]):
                        raise Exception("500 response structure error.")
                    if not resp.choices[0].delta.content:
                        resp.choices[0].delta.content = ""
                        continue
                    tol = total_token_count_from_response(resp)
                    if not tol:
                        total_tokens += num_tokens_from_string(resp.choices[0].delta.content)
                    else:
                        total_tokens = tol
                    answer += resp.choices[0].delta.content
                    yield resp.choices[0].delta.content

                yield total_tokens
                return

            except Exception as e:
                e = self._exceptions(e, attempt)
                if e:
                    yield e
                    yield total_tokens
                    return

        assert False, "Shouldn't be here."

    async def async_chat_streamly_with_tools(self, system: str, history: list, gen_conf: dict = {}):
        gen_conf = self._clean_conf(gen_conf)
        tools = self.tools
        if system and history and history[0].get("role") != "system":
            history.insert(0, {"role": "system", "content": system})

        total_tokens = 0
        hist = deepcopy(history)

        for attempt in range(self.max_retries + 1):
            history = deepcopy(hist)
            try:
                for _ in range(self.max_rounds + 1):
                    reasoning_start = False
                    logging.info(f"{tools=}")

                    response = await self.async_client.chat.completions.create(model=self.model_name, messages=history, stream=True, tools=tools, tool_choice="auto", **gen_conf)

                    final_tool_calls = {}
                    answer = ""

                    async for resp in response:
                        if not hasattr(resp, "choices") or not resp.choices:
                            continue

                        delta = resp.choices[0].delta

                        if hasattr(delta, "tool_calls") and delta.tool_calls:
                            for tool_call in delta.tool_calls:
                                index = tool_call.index
                                if index not in final_tool_calls:
                                    if not tool_call.function.arguments:
                                        tool_call.function.arguments = ""
                                    final_tool_calls[index] = tool_call
                                else:
                                    final_tool_calls[index].function.arguments += tool_call.function.arguments or ""
                            continue

                        if not hasattr(delta, "content") or delta.content is None:
                            delta.content = ""

                        if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                            ans = ""
                            if not reasoning_start:
                                reasoning_start = True
                                ans = "<think>"
                            ans += delta.reasoning_content + "</think>"
                            yield ans
                        else:
                            reasoning_start = False
                            answer += delta.content
                            yield delta.content

                        tol = total_token_count_from_response(resp)
                        if not tol:
                            total_tokens += num_tokens_from_string(delta.content)
                        else:
                            total_tokens = tol

                        finish_reason = getattr(resp.choices[0], "finish_reason", "")
                        if finish_reason == "length":
                            yield self._length_stop("")

                    if answer:
                        yield total_tokens
                        return

                    for tool_call in final_tool_calls.values():
                        name = tool_call.function.name
                        try:
                            args = json_repair.loads(tool_call.function.arguments)
                            yield self._verbose_tool_use(name, args, "Begin to call...")
                            tool_response = await asyncio.to_thread(self.toolcall_session.tool_call, name, args)
                            history = self._append_history(history, tool_call, tool_response)
                            yield self._verbose_tool_use(name, args, tool_response)
                        except Exception as e:
                            logging.exception(msg=f"Wrong JSON argument format in LLM tool call response: {tool_call}")
                            history.append({"role": "tool", "tool_call_id": tool_call.id, "content": f"Tool call error: \n{tool_call}\nException:\n" + str(e)})
                            yield self._verbose_tool_use(name, {}, str(e))

                logging.warning(f"Exceed max rounds: {self.max_rounds}")
                history.append({"role": "user", "content": f"Exceed max rounds: {self.max_rounds}"})

                response = await self.async_client.chat.completions.create(model=self.model_name, messages=history, stream=True, tools=tools, tool_choice="auto", **gen_conf)

                async for resp in response:
                    if not hasattr(resp, "choices") or not resp.choices:
                        continue
                    delta = resp.choices[0].delta
                    if not hasattr(delta, "content") or delta.content is None:
                        continue
                    tol = total_token_count_from_response(resp)
                    if not tol:
                        total_tokens += num_tokens_from_string(delta.content)
                    else:
                        total_tokens = tol
                    yield delta.content

                yield total_tokens
                return

            except Exception as e:
                e = await self._exceptions_async(e, attempt)
                if e:
                    logging.error(f"async_chat_streamly failed: {e}")
                    yield e
                    yield total_tokens
                    return

        assert False, "Shouldn't be here."

    async def _async_chat(self, history, gen_conf, **kwargs):
        logging.info("[HISTORY]" + json.dumps(history, ensure_ascii=False, indent=2))
        if self.model_name.lower().find("qwq") >= 0:
            logging.info(f"[INFO] {self.model_name} detected as reasoning model, using async_chat_streamly")
            final_ans = ""
            tol_token = 0
            async for delta, tol in self._async_chat_stream(history, gen_conf, with_reasoning=False, **kwargs):
                if delta.startswith("<think>") or delta.endswith("</think>"):
                    continue
                final_ans += delta
                tol_token = tol

            if len(final_ans.strip()) == 0:
                final_ans = "**ERROR**: Empty response from reasoning model"

            return final_ans.strip(), tol_token

        if self.model_name.lower().find("qwen3") >= 0:
            kwargs["extra_body"] = {"enable_thinking": False}

        response = await self.async_client.chat.completions.create(model=self.model_name, messages=history, **gen_conf, **kwargs)

        if not response.choices or not response.choices[0].message or not response.choices[0].message.content:
            return "", 0
        ans = response.choices[0].message.content.strip()
        if response.choices[0].finish_reason == "length":
            ans = self._length_stop(ans)
        return ans, total_token_count_from_response(response)

    async def async_chat(self, system, history, gen_conf={}, **kwargs):
        if system and history and history[0].get("role") != "system":
            history.insert(0, {"role": "system", "content": system})
        gen_conf = self._clean_conf(gen_conf)

        for attempt in range(self.max_retries + 1):
            try:
                return await self._async_chat(history, gen_conf, **kwargs)
            except Exception as e:
                e = await self._exceptions_async(e, attempt)
                if e:
                    return e, 0
        assert False, "Shouldn't be here."

    def chat_streamly(self, system, history, gen_conf: dict = {}, **kwargs):
        if system and history and history[0].get("role") != "system":
            history.insert(0, {"role": "system", "content": system})
        gen_conf = self._clean_conf(gen_conf)
        ans = ""
        total_tokens = 0
        try:
            for delta_ans, tol in self._chat_streamly(history, gen_conf, **kwargs):
                yield delta_ans
                total_tokens += tol
        except openai.APIError as e:
            yield ans + "\n**ERROR**: " + str(e)

        yield total_tokens

    def _calculate_dynamic_ctx(self, history):
        """Calculate dynamic context window size"""

        def count_tokens(text):
            """Calculate token count for text"""
            # Simple calculation: 1 token per ASCII character
            # 2 tokens for non-ASCII characters (Chinese, Japanese, Korean, etc.)
            total = 0
            for char in text:
                if ord(char) < 128:  # ASCII characters
                    total += 1
                else:  # Non-ASCII characters (Chinese, Japanese, Korean, etc.)
                    total += 2
            return total

        # Calculate total tokens for all messages
        total_tokens = 0
        for message in history:
            content = message.get("content", "")
            # Calculate content tokens
            content_tokens = count_tokens(content)
            # Add role marker token overhead
            role_tokens = 4
            total_tokens += content_tokens + role_tokens

        # Apply 1.2x buffer ratio
        total_tokens_with_buffer = int(total_tokens * 1.2)

        if total_tokens_with_buffer <= 8192:
            ctx_size = 8192
        else:
            ctx_multiplier = (total_tokens_with_buffer // 8192) + 1
            ctx_size = ctx_multiplier * 8192

        return ctx_size


class HuggingFaceChat(Base):
    _FACTORY_NAME = "HuggingFace"

    def __init__(self, key=None, model_name="", base_url="", **kwargs):
        if not base_url:
            raise ValueError("Local llm url cannot be None")
        base_url = urljoin(base_url, "v1")
        super().__init__(key, model_name.split("___")[0], base_url, **kwargs)


class LiteLLMBase(ABC):
    """LiteLLM-based chat model for OpenRouter support."""
    _FACTORY_NAME = ["OpenRouter"]

    def __init__(self, key, model_name, base_url=None, **kwargs):
        self.timeout = int(os.environ.get("LLM_TIMEOUT_SECONDS", 600))
        self.provider = kwargs.get("provider", "")
        self.prefix = LITELLM_PROVIDER_PREFIX.get(self.provider, "")
        self.model_name = f"{self.prefix}{model_name}"
        self.api_key = key
        self.base_url = (base_url or FACTORY_DEFAULT_BASE_URL.get(self.provider, "")).rstrip("/")
        # Configure retry parameters
        self.max_retries = kwargs.get("max_retries", int(os.environ.get("LLM_MAX_RETRIES", 5)))
        self.base_delay = kwargs.get("retry_interval", float(os.environ.get("LLM_BASE_DELAY", 2.0)))
        self.max_rounds = kwargs.get("max_rounds", 5)
        self.is_tools = False
        self.tools = []
        self.toolcall_sessions = {}

        # OpenRouter specific fields
        if self.provider == SupportedLiteLLMProvider.OpenRouter:
            self.api_key = json.loads(key).get("api_key", "")
            self.provider_order = json.loads(key).get("provider_order", "")

    def _get_delay(self):
        """Calculate retry delay time"""
        return self.base_delay * random.uniform(10, 150)

    def _classify_error(self, error):
        """Classify error based on error message content"""
        error_str = str(error).lower()

        keywords_mapping = [
            (["quota", "capacity", "credit", "billing", "balance", "欠费"], LLMErrorCode.ERROR_QUOTA),
            (["rate limit", "429", "tpm limit", "too many requests", "requests per minute"], LLMErrorCode.ERROR_RATE_LIMIT),
            (["auth", "key", "apikey", "401", "forbidden", "permission"], LLMErrorCode.ERROR_AUTHENTICATION),
            (["invalid", "bad request", "400", "format", "malformed", "parameter"], LLMErrorCode.ERROR_INVALID_REQUEST),
            (["server", "503", "502", "504", "500", "unavailable"], LLMErrorCode.ERROR_SERVER),
            (["timeout", "timed out"], LLMErrorCode.ERROR_TIMEOUT),
            (["connect", "network", "unreachable", "dns"], LLMErrorCode.ERROR_CONNECTION),
            (["filter", "content", "policy", "blocked", "safety", "inappropriate"], LLMErrorCode.ERROR_CONTENT_FILTER),
            (["model", "not found", "does not exist", "not available"], LLMErrorCode.ERROR_MODEL),
            (["max rounds"], LLMErrorCode.ERROR_MODEL),
        ]
        for words, code in keywords_mapping:
            if re.search("({})".format("|".join(words)), error_str):
                return code

        return LLMErrorCode.ERROR_GENERIC

    def _clean_conf(self, gen_conf):
        if "max_tokens" in gen_conf:
            del gen_conf["max_tokens"]
        return gen_conf

    def _chat(self, history, gen_conf, **kwargs):
        logging.info("[HISTORY]" + json.dumps(history, ensure_ascii=False, indent=2))
        if self.model_name.lower().find("qwen3") >= 0:
            kwargs["extra_body"] = {"enable_thinking": False}

        completion_args = self._construct_completion_args(history=history, stream=False, tools=False, **gen_conf)
        response = litellm.completion(
            **completion_args,
            drop_params=True,
            timeout=self.timeout,
        )
        # response = self.client.chat.completions.create(model=self.model_name, messages=history, **gen_conf, **kwargs)
        if any([not response.choices, not response.choices[0].message, not response.choices[0].message.content]):
            return "", 0
        ans = response.choices[0].message.content.strip()
        if response.choices[0].finish_reason == "length":
            ans = self._length_stop(ans)

        return ans, total_token_count_from_response(response)

    def _chat_streamly(self, history, gen_conf, **kwargs):
        logging.info("[HISTORY STREAMLY]" + json.dumps(history, ensure_ascii=False, indent=4))
        gen_conf = self._clean_conf(gen_conf)
        reasoning_start = False

        completion_args = self._construct_completion_args(history=history, stream=True, tools=False, **gen_conf)
        stop = kwargs.get("stop")
        if stop:
            completion_args["stop"] = stop
        response = litellm.completion(
            **completion_args,
            drop_params=True,
            timeout=self.timeout,
        )

        for resp in response:
            if not hasattr(resp, "choices") or not resp.choices:
                continue

            delta = resp.choices[0].delta
            if not hasattr(delta, "content") or delta.content is None:
                delta.content = ""

            if kwargs.get("with_reasoning", True) and hasattr(delta, "reasoning_content") and delta.reasoning_content:
                ans = ""
                if not reasoning_start:
                    reasoning_start = True
                    ans = "<think>"
                ans += delta.reasoning_content + "</think>"
            else:
                reasoning_start = False
                ans = delta.content

            tol = total_token_count_from_response(resp)
            if not tol:
                tol = num_tokens_from_string(delta.content)

            finish_reason = resp.choices[0].finish_reason if hasattr(resp.choices[0], "finish_reason") else ""
            if finish_reason == "length":
                if is_chinese(ans):
                    ans += LENGTH_NOTIFICATION_CN
                else:
                    ans += LENGTH_NOTIFICATION_EN

            yield ans, tol

    async def async_chat(self, system, history, gen_conf, **kwargs):
        hist = list(history) if history else []
        if system:
            if not hist or hist[0].get("role") != "system":
                hist.insert(0, {"role": "system", "content": system})

        logging.info("[HISTORY]" + json.dumps(hist, ensure_ascii=False, indent=2))
        if self.model_name.lower().find("qwen3") >= 0:
            kwargs["extra_body"] = {"enable_thinking": False}

        completion_args = self._construct_completion_args(history=hist, stream=False, tools=False, **gen_conf)

        for attempt in range(self.max_retries + 1):
            try:
                response = await litellm.acompletion(
                    **completion_args,
                    drop_params=True,
                    timeout=self.timeout,
                )

                if any([not response.choices, not response.choices[0].message, not response.choices[0].message.content]):
                    return "", 0
                ans = response.choices[0].message.content.strip()
                if response.choices[0].finish_reason == "length":
                    ans = self._length_stop(ans)

                return ans, total_token_count_from_response(response)
            except Exception as e:
                e = await self._exceptions_async(e, attempt)
                if e:
                    return e, 0

        assert False, "Shouldn't be here."

    async def async_chat_streamly(self, system, history, gen_conf, **kwargs):
        if system and history and history[0].get("role") != "system":
            history.insert(0, {"role": "system", "content": system})
        logging.info("[HISTORY STREAMLY]" + json.dumps(history, ensure_ascii=False, indent=4))
        gen_conf = self._clean_conf(gen_conf)
        reasoning_start = False
        total_tokens = 0

        completion_args = self._construct_completion_args(history=history, stream=True, tools=False, **gen_conf)
        stop = kwargs.get("stop")
        if stop:
            completion_args["stop"] = stop

        for attempt in range(self.max_retries + 1):
            try:
                stream = await litellm.acompletion(
                    **completion_args,
                    drop_params=True,
                    timeout=self.timeout,
                )

                async for resp in stream:
                    if not hasattr(resp, "choices") or not resp.choices:
                        continue

                    delta = resp.choices[0].delta
                    if not hasattr(delta, "content") or delta.content is None:
                        delta.content = ""

                    if kwargs.get("with_reasoning", True) and hasattr(delta, "reasoning_content") and delta.reasoning_content:
                        ans = ""
                        if not reasoning_start:
                            reasoning_start = True
                            ans = "<think>"
                        ans += delta.reasoning_content + "</think>"
                    else:
                        reasoning_start = False
                        ans = delta.content

                    tol = total_token_count_from_response(resp)
                    if not tol:
                        tol = num_tokens_from_string(delta.content)
                    total_tokens += tol

                    finish_reason = resp.choices[0].finish_reason if hasattr(resp.choices[0], "finish_reason") else ""
                    if finish_reason == "length":
                        if is_chinese(ans):
                            ans += LENGTH_NOTIFICATION_CN
                        else:
                            ans += LENGTH_NOTIFICATION_EN

                    yield ans
                yield total_tokens
                return
            except Exception as e:
                e = await self._exceptions_async(e, attempt)
                if e:
                    yield e
                    yield total_tokens
                    return

    def _length_stop(self, ans):
        if is_chinese([ans]):
            return ans + LENGTH_NOTIFICATION_CN
        return ans + LENGTH_NOTIFICATION_EN

    @property
    def _retryable_errors(self) -> set[str]:
        return {
            LLMErrorCode.ERROR_RATE_LIMIT,
            LLMErrorCode.ERROR_SERVER,
        }

    def _should_retry(self, error_code: str) -> bool:
        return error_code in self._retryable_errors

    def _exceptions(self, e, attempt) -> str | None:
        logging.exception("OpenAI chat_with_tools")
        # Classify the error
        error_code = self._classify_error(e)
        if attempt == self.max_retries:
            error_code = LLMErrorCode.ERROR_MAX_RETRIES

        if self._should_retry(error_code):
            delay = self._get_delay()
            logging.warning(f"Error: {error_code}. Retrying in {delay:.2f} seconds... (Attempt {attempt + 1}/{self.max_retries})")
            time.sleep(delay)
            return None

        return f"{ERROR_PREFIX}: {error_code} - {str(e)}"

    async def _exceptions_async(self, e, attempt) -> str | None:
        logging.exception("LiteLLMBase async completion")
        error_code = self._classify_error(e)
        if attempt == self.max_retries:
            error_code = LLMErrorCode.ERROR_MAX_RETRIES

        if self._should_retry(error_code):
            delay = self._get_delay()
            logging.warning(f"Error: {error_code}. Retrying in {delay:.2f} seconds... (Attempt {attempt + 1}/{self.max_retries})")
            await asyncio.sleep(delay)
            return None
        msg = f"{ERROR_PREFIX}: {error_code} - {str(e)}"
        logging.error(f"async_chat_streamly giving up: {msg}")
        return msg

    def _verbose_tool_use(self, name, args, res):
        return "<tool_call>" + json.dumps({"name": name, "args": args, "result": res}, ensure_ascii=False, indent=2) + "</tool_call>"

    def _append_history(self, hist, tool_call, tool_res):
        hist.append(
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "index": tool_call.index,
                        "id": tool_call.id,
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                        "type": "function",
                    },
                ],
            }
        )
        try:
            if isinstance(tool_res, dict):
                tool_res = json.dumps(tool_res, ensure_ascii=False)
        finally:
            hist.append({"role": "tool", "tool_call_id": tool_call.id, "content": str(tool_res)})
        return hist

    def bind_tools(self, toolcall_session, tools):
        if not (toolcall_session and tools):
            return
        self.is_tools = True
        self.toolcall_session = toolcall_session
        self.tools = tools

    def _construct_completion_args(self, history, stream: bool, tools: bool, **kwargs):
        completion_args = {
            "model": self.model_name,
            "messages": history,
            "api_key": self.api_key,
            "num_retries": self.max_retries,
            **kwargs,
        }
        if stream:
            completion_args.update(
                {
                    "stream": stream,
                }
            )
        if tools and self.tools:
            completion_args.update(
                {
                    "tools": self.tools,
                    "tool_choice": "auto",
                }
            )
        if self.provider in FACTORY_DEFAULT_BASE_URL:
            completion_args.update({"api_base": self.base_url})

        # OpenRouter-specific configuration
        if self.provider == SupportedLiteLLMProvider.OpenRouter:
            if self.provider_order:

                def _to_order_list(x):
                    if x is None:
                        return []
                    if isinstance(x, str):
                        return [s.strip() for s in x.split(",") if s.strip()]
                    if isinstance(x, (list, tuple)):
                        return [str(s).strip() for s in x if str(s).strip()]
                    return []

                extra_body = {}
                provider_cfg = {}
                provider_order = _to_order_list(self.provider_order)
                provider_cfg["order"] = provider_order
                provider_cfg["allow_fallbacks"] = False
                extra_body["provider"] = provider_cfg
                completion_args.update({"extra_body": extra_body})

        return completion_args

    def chat_with_tools(self, system: str, history: list, gen_conf: dict = {}):
        gen_conf = self._clean_conf(gen_conf)
        if system and history and history[0].get("role") != "system":
            history.insert(0, {"role": "system", "content": system})

        ans = ""
        tk_count = 0
        hist = deepcopy(history)

        # Implement exponential backoff retry strategy
        for attempt in range(self.max_retries + 1):
            history = deepcopy(hist)  # deepcopy is required here
            try:
                for _ in range(self.max_rounds + 1):
                    logging.info(f"{self.tools=}")

                    completion_args = self._construct_completion_args(history=history, stream=False, tools=True, **gen_conf)
                    response = litellm.completion(
                        **completion_args,
                        drop_params=True,
                        timeout=self.timeout,
                    )

                    tk_count += total_token_count_from_response(response)

                    if not hasattr(response, "choices") or not response.choices or not response.choices[0].message:
                        raise Exception(f"500 response structure error. Response: {response}")

                    message = response.choices[0].message

                    if not hasattr(message, "tool_calls") or not message.tool_calls:
                        if hasattr(message, "reasoning_content") and message.reasoning_content:
                            ans += f"<think>{message.reasoning_content}</think>"
                        ans += message.content or ""
                        if response.choices[0].finish_reason == "length":
                            ans = self._length_stop(ans)
                        return ans, tk_count

                    for tool_call in message.tool_calls:
                        logging.info(f"Response {tool_call=}")
                        name = tool_call.function.name
                        try:
                            args = json_repair.loads(tool_call.function.arguments)
                            tool_response = self.toolcall_session.tool_call(name, args)
                            history = self._append_history(history, tool_call, tool_response)
                            ans += self._verbose_tool_use(name, args, tool_response)
                        except Exception as e:
                            logging.exception(msg=f"Wrong JSON argument format in LLM tool call response: {tool_call}")
                            history.append({"role": "tool", "tool_call_id": tool_call.id, "content": f"Tool call error: \n{tool_call}\nException:\n" + str(e)})
                            ans += self._verbose_tool_use(name, {}, str(e))

                logging.warning(f"Exceed max rounds: {self.max_rounds}")
                history.append({"role": "user", "content": f"Exceed max rounds: {self.max_rounds}"})

                response, token_count = self._chat(history, gen_conf)
                ans += response
                tk_count += token_count
                return ans, tk_count

            except Exception as e:
                e = self._exceptions(e, attempt)
                if e:
                    return e, tk_count

        assert False, "Shouldn't be here."

    def chat(self, system, history, gen_conf={}, **kwargs):
        if system and history and history[0].get("role") != "system":
            history.insert(0, {"role": "system", "content": system})
        gen_conf = self._clean_conf(gen_conf)

        # Implement exponential backoff retry strategy
        for attempt in range(self.max_retries + 1):
            try:
                response = self._chat(history, gen_conf, **kwargs)
                return response
            except Exception as e:
                e = self._exceptions(e, attempt)
                if e:
                    return e, 0
        assert False, "Shouldn't be here."

    def _wrap_toolcall_message(self, stream):
        final_tool_calls = {}

        for chunk in stream:
            for tool_call in chunk.choices[0].delta.tool_calls or []:
                index = tool_call.index

                if index not in final_tool_calls:
                    final_tool_calls[index] = tool_call

                final_tool_calls[index].function.arguments += tool_call.function.arguments

        return final_tool_calls

    def chat_streamly_with_tools(self, system: str, history: list, gen_conf: dict = {}):
        gen_conf = self._clean_conf(gen_conf)
        tools = self.tools
        if system and history and history[0].get("role") != "system":
            history.insert(0, {"role": "system", "content": system})

        total_tokens = 0
        hist = deepcopy(history)

        # Implement exponential backoff retry strategy
        for attempt in range(self.max_retries + 1):
            history = deepcopy(hist)  # deepcopy is required here
            try:
                for _ in range(self.max_rounds + 1):
                    reasoning_start = False
                    logging.info(f"{tools=}")

                    completion_args = self._construct_completion_args(history=history, stream=True, tools=True, **gen_conf)
                    response = litellm.completion(
                        **completion_args,
                        drop_params=True,
                        timeout=self.timeout,
                    )

                    final_tool_calls = {}
                    answer = ""

                    for resp in response:
                        if not hasattr(resp, "choices") or not resp.choices:
                            continue

                        delta = resp.choices[0].delta

                        if hasattr(delta, "tool_calls") and delta.tool_calls:
                            for tool_call in delta.tool_calls:
                                index = tool_call.index
                                if index not in final_tool_calls:
                                    if not tool_call.function.arguments:
                                        tool_call.function.arguments = ""
                                    final_tool_calls[index] = tool_call
                                else:
                                    final_tool_calls[index].function.arguments += tool_call.function.arguments or ""
                            continue

                        if not hasattr(delta, "content") or delta.content is None:
                            delta.content = ""

                        if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                            ans = ""
                            if not reasoning_start:
                                reasoning_start = True
                                ans = "<think>"
                            ans += delta.reasoning_content + "</think>"
                            yield ans
                        else:
                            reasoning_start = False
                            answer += delta.content
                            yield delta.content

                        tol = total_token_count_from_response(resp)
                        if not tol:
                            total_tokens += num_tokens_from_string(delta.content)
                        else:
                            total_tokens += tol

                        finish_reason = getattr(resp.choices[0], "finish_reason", "")
                        if finish_reason == "length":
                            yield self._length_stop("")

                    if answer:
                        yield total_tokens
                        return

                    for tool_call in final_tool_calls.values():
                        name = tool_call.function.name
                        try:
                            args = json_repair.loads(tool_call.function.arguments)
                            yield self._verbose_tool_use(name, args, "Begin to call...")
                            tool_response = self.toolcall_session.tool_call(name, args)
                            history = self._append_history(history, tool_call, tool_response)
                            yield self._verbose_tool_use(name, args, tool_response)
                        except Exception as e:
                            logging.exception(msg=f"Wrong JSON argument format in LLM tool call response: {tool_call}")
                            history.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "content": f"Tool call error: \n{tool_call}\nException:\n{str(e)}",
                                }
                            )
                            yield self._verbose_tool_use(name, {}, str(e))

                logging.warning(f"Exceed max rounds: {self.max_rounds}")
                history.append({"role": "user", "content": f"Exceed max rounds: {self.max_rounds}"})

                completion_args = self._construct_completion_args(history=history, stream=True, tools=True, **gen_conf)
                response = litellm.completion(
                    **completion_args,
                    drop_params=True,
                    timeout=self.timeout,
                )

                for resp in response:
                    if not hasattr(resp, "choices") or not resp.choices:
                        continue
                    delta = resp.choices[0].delta
                    if not hasattr(delta, "content") or delta.content is None:
                        continue
                    tol = total_token_count_from_response(resp)
                    if not tol:
                        total_tokens += num_tokens_from_string(delta.content)
                    else:
                        total_tokens += tol
                    yield delta.content

                yield total_tokens
                return

            except Exception as e:
                e = self._exceptions(e, attempt)
                if e:
                    yield e
                    yield total_tokens
                    return

        assert False, "Shouldn't be here."

    def chat_streamly(self, system, history, gen_conf: dict = {}, **kwargs):
        if system and history and history[0].get("role") != "system":
            history.insert(0, {"role": "system", "content": system})
        gen_conf = self._clean_conf(gen_conf)
        ans = ""
        total_tokens = 0
        try:
            for delta_ans, tol in self._chat_streamly(history, gen_conf, **kwargs):
                yield delta_ans
                total_tokens += tol
        except openai.APIError as e:
            yield ans + "\n**ERROR**: " + str(e)

        yield total_tokens

    def _calculate_dynamic_ctx(self, history):
        """Calculate dynamic context window size"""

        def count_tokens(text):
            """Calculate token count for text"""
            # Simple calculation: 1 token per ASCII character
            # 2 tokens for non-ASCII characters (Chinese, Japanese, Korean, etc.)
            total = 0
            for char in text:
                if ord(char) < 128:  # ASCII characters
                    total += 1
                else:  # Non-ASCII characters (Chinese, Japanese, Korean, etc.)
                    total += 2
            return total

        # Calculate total tokens for all messages
        total_tokens = 0
        for message in history:
            content = message.get("content", "")
            # Calculate content tokens
            content_tokens = count_tokens(content)
            # Add role marker token overhead
            role_tokens = 4
            total_tokens += content_tokens + role_tokens

        # Apply 1.2x buffer ratio
        total_tokens_with_buffer = int(total_tokens * 1.2)

        if total_tokens_with_buffer <= 8192:
            ctx_size = 8192
        else:
            ctx_multiplier = (total_tokens_with_buffer // 8192) + 1
            ctx_size = ctx_multiplier * 8192

        return ctx_size
