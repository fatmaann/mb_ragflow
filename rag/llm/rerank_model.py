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
from abc import ABC

import numpy as np
import requests

from common.token_utils import num_tokens_from_string

class Base(ABC):
    def __init__(self, key, model_name, **kwargs):
        """
        Abstract base class constructor.
        Parameters are not stored; initialization is left to subclasses.
        """
        pass

    def similarity(self, query: str, texts: list):
        raise NotImplementedError("Please implement encode method!")



class HuggingfaceRerank(Base):
    _FACTORY_NAME = "HuggingFace"

    @staticmethod
    def post(query: str, texts: list, url="127.0.0.1"):
        exc = None
        scores = [0 for _ in range(len(texts))]
        batch_size = 8
        for i in range(0, len(texts), batch_size):
            try:
                res = requests.post(
                    f"http://{url}/rerank", headers={"Content-Type": "application/json"}, json={"query": query, "texts": texts[i : i + batch_size], "raw_scores": False, "truncate": True}
                )

                for o in res.json():
                    scores[o["index"] + i] = o["score"]
            except Exception as e:
                exc = e

        if exc:
            raise exc
        return np.array(scores)

    def __init__(self, key, model_name="BAAI/bge-reranker-v2-m3", base_url="http://127.0.0.1"):
        self.model_name = model_name.split("___")[0]
        self.base_url = base_url

    def similarity(self, query: str, texts: list) -> tuple[np.ndarray, int]:
        if not texts:
            return np.array([]), 0
        token_count = 0
        for t in texts:
            token_count += num_tokens_from_string(t)
        return HuggingfaceRerank.post(query, texts, self.base_url), token_count

