#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
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
import os
import threading
from abc import ABC

import numpy as np
import requests

from common.token_utils import num_tokens_from_string
from common import settings
import logging


class Base(ABC):
    def __init__(self, key, model_name, **kwargs):
        """
        Constructor for abstract base class.
        Parameters are accepted for interface consistency but are not stored.
        Subclasses should implement their own initialization as needed.
        """
        pass

    def encode(self, texts: list):
        raise NotImplementedError("Please implement encode method!")

    def encode_queries(self, text: str):
        raise NotImplementedError("Please implement encode method!")

    def total_token_count(self, resp):
        try:
            return resp.usage.total_tokens
        except Exception:
            pass
        try:
            return resp["usage"]["total_tokens"]
        except Exception:
            pass
        return 0


class BuiltinEmbed(Base):
    _FACTORY_NAME = "Builtin"
    MAX_TOKENS = {"Qwen/Qwen3-Embedding-0.6B": 30000, "BAAI/bge-m3": 8000, "BAAI/bge-small-en-v1.5": 500}
    _model = None
    _model_name = ""
    _max_tokens = 500
    _model_lock = threading.Lock()

    def __init__(self, key, model_name, **kwargs):
        logging.info(f"Initialize BuiltinEmbed according to settings.EMBEDDING_CFG: {settings.EMBEDDING_CFG}")
        embedding_cfg = settings.EMBEDDING_CFG
        if not BuiltinEmbed._model and "tei-" in os.getenv("COMPOSE_PROFILES", ""):
            with BuiltinEmbed._model_lock:
                BuiltinEmbed._model_name = settings.EMBEDDING_MDL
                BuiltinEmbed._max_tokens = BuiltinEmbed.MAX_TOKENS.get(settings.EMBEDDING_MDL, 500)
                BuiltinEmbed._model = HuggingFaceEmbed(embedding_cfg["api_key"], settings.EMBEDDING_MDL, base_url=embedding_cfg["base_url"])
        self._model = BuiltinEmbed._model
        self._model_name = BuiltinEmbed._model_name
        self._max_tokens = BuiltinEmbed._max_tokens

    def encode(self, texts: list):
        batch_size = 16
        # TEI is able to auto truncate inputs according to https://github.com/huggingface/text-embeddings-inference.
        token_count = 0
        ress = None
        for i in range(0, len(texts), batch_size):
            embeddings, token_count_delta = self._model.encode(texts[i : i + batch_size])
            token_count += token_count_delta
            if ress is None:
                ress = embeddings
            else:
                ress = np.concatenate((ress, embeddings), axis=0)
        return ress, token_count

    def encode_queries(self, text: str):
        return self._model.encode_queries(text)

class HuggingFaceEmbed(Base):
    _FACTORY_NAME = "HuggingFace"

    def __init__(self, key, model_name, base_url=None, **kwargs):
        if not model_name:
            raise ValueError("Model name cannot be None")
        self.key = key
        self.model_name = model_name.split("___")[0]
        self.base_url = base_url or "http://127.0.0.1:8080"

    def encode(self, texts: list):
        response = requests.post(f"{self.base_url}/embed", json={"inputs": texts}, headers={"Content-Type": "application/json"})
        if response.status_code == 200:
            embeddings = response.json()
        else:
            raise Exception(f"Error: {response.status_code} - {response.text}")
        return np.array(embeddings), sum([num_tokens_from_string(text) for text in texts])

    def encode_queries(self, text: str):
        response = requests.post(f"{self.base_url}/embed", json={"inputs": text}, headers={"Content-Type": "application/json"})
        if response.status_code == 200:
            embedding = response.json()[0]
            return np.array(embedding), num_tokens_from_string(text)
        else:
            raise Exception(f"Error: {response.status_code} - {response.text}")

