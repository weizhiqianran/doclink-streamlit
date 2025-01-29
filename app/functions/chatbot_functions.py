from openai import OpenAI
from dotenv import load_dotenv
from langdetect import detect
import textwrap
import yaml
import re
from typing import Dict, Any, Match


class ChatbotFunctions:
    def __init__(self):
        load_dotenv()
        self.client = OpenAI()

        with open("app/utils/prompts.yaml", "r", encoding="utf-8") as file:
            self.prompt_data = yaml.safe_load(file)

    def _prompt_query_generation(self, query, file_lang):
        return textwrap.dedent(
            self.get_prompt(category="queries", query=query, file_lang=file_lang)
        )

    def _prompt_answer_generation(self, query, context, lang, intention):
        return textwrap.dedent(
            self.get_prompt(category=intention, query=query, context=context, lang=lang)
        )

    def response_generation(self, query, context, intention):
        lang = self.detect_language(query=query)
        prompt = self._prompt_answer_generation(
            query=query, context=context, lang=lang, intention=intention
        )
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": query},
            ],
            temperature=0,
        )
        answer = response.choices[0].message.content.strip()
        return answer

    def query_generation(self, query, file_lang):
        lang = self.detect_language(query=query)
        prompt = self._prompt_query_generation(query, file_lang=file_lang)
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": query},
            ],
            temperature=0,
        )
        new_queries = response.choices[0].message.content.strip()
        return new_queries, lang

    def detect_language(self, query):
        if query.isalpha():
            lang = detect(text=query)
            return "tr" if lang == "tr" else "en"
        return None

    def replace_variables(self, match: Match, kwargs: Dict[str, Any]):
        variables = match.group(1) or match.group(2)
        value = kwargs.get(variables)
        return str(value)

    def get_prompt(self, category, **kwargs):
        variable_pattern = r"\${?(\w+)}?|\{(\w+)\}"
        try:
            prompt = self.prompt_data["prompts"]["languages"]["en"][category.strip()][
                0
            ]["text"]

            def replace_wrapper(match):
                return self.replace_variables(match, kwargs)

            full_prompt = re.sub(variable_pattern, replace_wrapper, prompt)
            return full_prompt
        except KeyError:
            print(f"No template found for {category}")
            return None
