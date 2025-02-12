import fitz
import tempfile
import io
import re
import spacy
import pymupdf4llm
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from langchain_text_splitters import MarkdownHeaderTextSplitter
from docling.datamodel.base_models import InputFormat
from docling.pipeline.simple_pipeline import SimplePipeline
from docling.document_converter import (
    DocumentConverter,
    WordFormatOption,
    PowerpointFormatOption,
    HTMLFormatOption,
)


class ReadingFunctions:
    def __init__(self):
        self.nlp = spacy.load(
            "en_core_web_sm",
            disable=[
                "tagger",
                "attribute_ruler",
                "lemmatizer",
                "ner",
                "textcat",
                "custom",
            ],
        )
        self.max_file_size_mb = 50
        self.headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
            ("####", "Header 4"),
        ]
        self.markdown_splitter = MarkdownHeaderTextSplitter(
            self.headers_to_split_on, strip_headers=False, return_each_line=True
        )
        self.converter = DocumentConverter(
            allowed_formats=[
                InputFormat.DOCX,
                InputFormat.PPTX,
                InputFormat.XLSX,
                InputFormat.PDF,
                InputFormat.HTML,
            ],
            format_options={
                InputFormat.DOCX: WordFormatOption(pipeline_cls=SimplePipeline),
                InputFormat.PPTX: PowerpointFormatOption(pipeline_cls=SimplePipeline),
                InputFormat.HTML: HTMLFormatOption(pipeline_cls=SimplePipeline),
            },
        )

    def read_file(self, file_bytes: bytes, file_name: str):
        """Read and process file content from bytes"""
        file_size_mb = self._get_file_size(file_bytes=file_bytes)
        file_type = file_name.split(".")[-1].lower()

        if file_size_mb > self.max_file_size_mb:
            raise ValueError(f"File size exceeds {self.max_file_size_mb}MB limit")

        try:
            if file_type == "pdf":
                return self._process_pdf(file_bytes=file_bytes)
            elif file_type == "docx":
                return self._process_docx(file_bytes=file_bytes)
            elif file_type == "pptx":
                return self._process_pptx(file_bytes=file_bytes)
            elif file_type == "xlsx":
                return self._process_xlsx(file_bytes=file_bytes)
            elif file_type == "udf":
                return self._process_udf(file_bytes=file_bytes)
            elif file_type in ["txt", "rtf"]:
                return self._process_txt(file_bytes=file_bytes)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")

        except Exception as e:
            raise ValueError(f"Error processing {file_name}: {str(e)}")

    def read_url(self, html_content: tuple):
        html_data = {
            "sentences": [],
            "page_number": [],
            "is_header": [],
            "is_table": [],
        }

        try:
            with tempfile.NamedTemporaryFile(delete=True, suffix=".html") as temp_file:
                temp_file.write(html_content.encode("utf-8"))
                temp_file.flush()
                html_path = Path(temp_file.name)
                md_text = self.converter.convert(
                    html_path
                ).document.export_to_markdown()
                splits = self.markdown_splitter.split_text(md_text)

                for split in splits:
                    if (
                        not len(split.page_content) > 5
                        or re.match(r"^[^\w]*$", split.page_content)
                        or split.page_content[:4] == "<!--"
                    ):
                        continue
                    elif split.metadata and split.page_content[0] == "#":
                        html_data["sentences"].append(split.page_content)
                        html_data["is_header"].append(True)
                        html_data["is_table"].append(False)
                        html_data["page_number"].append(1)
                    elif split.page_content[0] == "|" and split.page_content[-1] == "|":
                        html_data["sentences"].append(split.page_content)
                        html_data["is_header"].append(False)
                        html_data["is_table"].append(True)
                        html_data["page_number"].append(1)
                    else:
                        html_data["sentences"].append(split.page_content)
                        html_data["is_header"].append(False)
                        html_data["is_table"].append(False)
                        html_data["page_number"].append(1)
            return self._chunk_html(html_data)
        except Exception as e:
            raise ValueError(f"Error processing HTML content: {str(e)}")

    def _process_pdf(self, file_bytes: bytes):
        pdf_data = {"sentences": [], "page_number": [], "is_header": [], "is_table": []}
        pdf_file = io.BytesIO(file_bytes)
        with fitz.open(stream=pdf_file, filetype="pdf") as pdf:
            # Process each page
            markdown_pages = pymupdf4llm.to_markdown(
                pdf, page_chunks=True, show_progress=False, margins=0
            )
            for i, page in enumerate(markdown_pages):
                splits = self.markdown_splitter.split_text(page["text"])
                for split in splits:
                    if not len(split.page_content) > 5 or re.match(
                        r"^[^\w]*$", split.page_content
                    ):
                        continue
                    elif (
                        split.metadata and split.page_content[0] == "#"
                    ):  # Header detection
                        pdf_data["sentences"].append(split.page_content)
                        pdf_data["is_header"].append(True)
                        pdf_data["is_table"].append(False)
                        pdf_data["page_number"].append(i + 1)
                    elif (
                        split.page_content[0] == "*"
                        and split.page_content[-1] == "*"
                        and (
                            re.match(
                                r"(\*{2,})(\d+(?:\.\d+)*)\s*(\*{2,})?(.*)$",
                                split.page_content,
                            )
                            or re.match(
                                r"(\*{1,3})?([A-Z][a-zA-Z\s\-]+)(\*{1,3})?$",
                                split.page_content,
                            )
                        )
                    ):  # Sub-Header and Header variant detection
                        pdf_data["sentences"].append(split.page_content)
                        pdf_data["is_header"].append(True)
                        pdf_data["is_table"].append(False)
                        pdf_data["page_number"].append(i + 1)
                    elif (
                        split.page_content[0] == "|" and split.page_content[-1] == "|"
                    ):  # Table detection
                        pdf_data["sentences"].append(split.page_content)
                        pdf_data["is_header"].append(False)
                        pdf_data["is_table"].append(True)
                        pdf_data["page_number"].append(i + 1)
                    else:
                        pdf_data["sentences"].append(split.page_content)
                        pdf_data["is_header"].append(False)
                        pdf_data["is_table"].append(False)
                        pdf_data["page_number"].append(i + 1)
        return pdf_data

    def _process_docx(self, file_bytes: bytes):
        docx_data = {
            "sentences": [],
            "page_number": [],
            "is_header": [],
            "is_table": [],
        }
        current_length = 0
        chars_per_page = 2000
        current_page = 1

        docx_file = io.BytesIO(file_bytes)
        with tempfile.NamedTemporaryFile(delete=True, suffix=".docx") as temp_file:
            temp_file.write(docx_file.getvalue())
            docx_path = Path(temp_file.name)
            md_text = self.converter.convert(docx_path).document.export_to_markdown()
            splits = self.markdown_splitter.split_text(md_text)
            for split in splits:
                if current_length + len(split.page_content) > chars_per_page:
                    current_page += 1
                    current_length = 0

                if (
                    not len(split.page_content) > 5
                    or re.match(r"^[^\w]*$", split.page_content)
                    or split.page_content[:4] == "<!--"
                ):
                    continue
                elif (
                    split.metadata and split.page_content[0] == "#"
                ):  # Header detection
                    docx_data["sentences"].append(split.page_content)
                    docx_data["is_header"].append(True)
                    docx_data["is_table"].append(False)
                    docx_data["page_number"].append(current_page)
                    current_length += len(split.page_content)
                elif (
                    split.page_content[0] == "*"
                    and split.page_content[-1] == "*"
                    and (
                        re.match(
                            r"(\*{2,})(\d+(?:\.\d+)*)\s*(\*{2,})?(.*)$",
                            split.page_content,
                        )
                        or re.match(
                            r"(\*{1,3})?([A-Z][a-zA-Z\s\-]+)(\*{1,3})?$",
                            split.page_content,
                        )
                    )
                ):  # Sub-Header and Header variant detection
                    docx_data["sentences"].append(split.page_content)
                    docx_data["is_header"].append(True)
                    docx_data["is_table"].append(False)
                    docx_data["page_number"].append(current_page)
                    current_length += len(split.page_content)
                elif (
                    split.page_content[0] == "|" and split.page_content[-1] == "|"
                ):  # Table detection
                    docx_data["sentences"].append(split.page_content)
                    docx_data["is_header"].append(False)
                    docx_data["is_table"].append(True)
                    docx_data["page_number"].append(current_page)
                    current_length += len(split.page_content)
                else:
                    docx_data["sentences"].append(split.page_content)
                    docx_data["is_header"].append(False)
                    docx_data["is_table"].append(False)
                    docx_data["page_number"].append(current_page)
                    current_length += len(split.page_content)
        return docx_data

    def _process_pptx(self, file_bytes: bytes):
        pptx_data = {
            "sentences": [],
            "page_number": [],
            "is_header": [],
            "is_table": [],
        }
        current_length = 0
        chars_per_page = 500
        current_page = 1
        pptx_file = io.BytesIO(file_bytes)
        with tempfile.NamedTemporaryFile(delete=True, suffix=".pptx") as temp_file:
            temp_file.write(pptx_file.getvalue())
            pptx_path = Path(temp_file.name)
            md_text = self.converter.convert(pptx_path).document.export_to_markdown()
            splits = self.markdown_splitter.split_text(md_text)
            for split in splits:
                if current_length + len(split.page_content) > chars_per_page:
                    current_page += 1
                    current_length = 0
                if (
                    not len(split.page_content) > 5
                    or re.match(r"^[^\w]*$", split.page_content)
                    or split.page_content[:4] == "<!--"
                ):
                    continue
                elif (
                    split.metadata and split.page_content[0] == "#"
                ):  # Header detection
                    pptx_data["sentences"].append(split.page_content)
                    pptx_data["is_header"].append(True)
                    pptx_data["is_table"].append(False)
                    pptx_data["page_number"].append(current_page)
                    current_length += len(split.page_content)
                elif (
                    split.page_content[0] == "*"
                    and split.page_content[-1] == "*"
                    and (
                        re.match(
                            r"(\*{2,})(\d+(?:\.\d+)*)\s*(\*{2,})?(.*)$",
                            split.page_content,
                        )
                        or re.match(
                            r"(\*{1,3})?([A-Z][a-zA-Z\s\-]+)(\*{1,3})?$",
                            split.page_content,
                        )
                    )
                ):  # Sub-Header and Header variant detection
                    pptx_data["sentences"].append(split.page_content)
                    pptx_data["is_header"].append(True)
                    pptx_data["is_table"].append(False)
                    pptx_data["page_number"].append(current_page)
                    current_length += len(split.page_content)
                elif (
                    split.page_content[0] == "|" and split.page_content[-1] == "|"
                ):  # Table detection
                    pptx_data["sentences"].append(split.page_content)
                    pptx_data["is_header"].append(False)
                    pptx_data["is_table"].append(True)
                    pptx_data["page_number"].append(current_page)
                    current_length += len(split.page_content)
                else:
                    pptx_data["sentences"].append(split.page_content)
                    pptx_data["is_header"].append(False)
                    pptx_data["is_table"].append(False)
                    pptx_data["page_number"].append(current_page)
                    current_length += len(split.page_content)
        return pptx_data

    def _process_xlsx(self, file_bytes: bytes):
        xlsx_data = {
            "sentences": [],
            "page_number": [],
            "is_header": [],
            "is_table": [],
        }
        current_length = 0
        chars_per_page = 2000
        current_page = 1
        xlsx_file = io.BytesIO(file_bytes)
        with tempfile.NamedTemporaryFile(delete=True, suffix=".xlsx") as temp_file:
            temp_file.write(xlsx_file.getvalue())
            xlsx_path = Path(temp_file.name)
            md_text = self.converter.convert(xlsx_path).document.export_to_markdown()
            splits = self.markdown_splitter.split_text(md_text)
            for split in splits:
                if current_length + len(split.page_content) > chars_per_page:
                    current_page += 1
                    current_length = 0
                if (
                    not len(split.page_content) > 5
                    or re.match(r"^[^\w]*$", split.page_content)
                    or split.page_content[:4] == "<!--"
                ):
                    continue
                elif (
                    split.metadata and split.page_content[0] == "#"
                ):  # Header detection
                    xlsx_data["sentences"].append(split.page_content)
                    xlsx_data["is_header"].append(True)
                    xlsx_data["is_table"].append(False)
                    xlsx_data["page_number"].append(current_page)
                    current_length += len(split.page_content)
                elif (
                    split.page_content[0] == "*"
                    and split.page_content[-1] == "*"
                    and (
                        re.match(
                            r"(\*{2,})(\d+(?:\.\d+)*)\s*(\*{2,})?(.*)$",
                            split.page_content,
                        )
                        or re.match(
                            r"(\*{1,3})?([A-Z][a-zA-Z\s\-]+)(\*{1,3})?$",
                            split.page_content,
                        )
                    )
                ):  # Sub-Header and Header variant detection
                    xlsx_data["sentences"].append(split.page_content)
                    xlsx_data["is_header"].append(True)
                    xlsx_data["is_table"].append(False)
                    xlsx_data["page_number"].append(current_page)
                    current_length += len(split.page_content)
                elif (
                    split.page_content[0] == "|" and split.page_content[-1] == "|"
                ):  # Table detection
                    xlsx_data["sentences"].append(split.page_content)
                    xlsx_data["is_header"].append(False)
                    xlsx_data["is_table"].append(True)
                    xlsx_data["page_number"].append(current_page)
                    current_length += len(split.page_content)
                else:
                    xlsx_data["sentences"].append(split.page_content)
                    xlsx_data["is_header"].append(False)
                    xlsx_data["is_table"].append(False)
                    xlsx_data["page_number"].append(current_page)
                    current_length += len(split.page_content)
        return xlsx_data

    def _process_udf(self, file_bytes: bytes):
        udf_data = {
            "sentences": [],
            "page_number": [],
            "is_header": [],
            "is_table": [],
        }
        current_length = 0
        chars_per_page = 2000
        current_page = 1

        udf_file = io.BytesIO(file_bytes)
        with zipfile.ZipFile(udf_file, "r") as zip_ref:
            xml_content = zip_ref.read("content.xml")
            dataTree = ET.parse(io.BytesIO(xml_content))
            splits = self.markdown_splitter.split_text(
                dataTree.find(".//content").text.strip()
            )
            for split in splits:
                if current_length + len(split.page_content) > chars_per_page:
                    current_page += 1
                    current_length = 0

                if (
                    not len(split.page_content) > 5
                    or re.match(r"^[^\w]*$", split.page_content)
                    or split.page_content[:4] == "<!--"
                ):
                    continue
                elif (
                    split.metadata and split.page_content[0] == "#"
                ):  # Header detection
                    udf_data["sentences"].append(split.page_content)
                    udf_data["is_header"].append(True)
                    udf_data["is_table"].append(False)
                    udf_data["page_number"].append(current_page)
                    current_length += len(split.page_content)
                elif (
                    split.page_content[0] == "*"
                    and split.page_content[-1] == "*"
                    and (
                        re.match(
                            r"(\*{2,})(\d+(?:\.\d+)*)\s*(\*{2,})?(.*)$",
                            split.page_content,
                        )
                        or re.match(
                            r"(\*{1,3})?([A-Z][a-zA-Z\s\-]+)(\*{1,3})?$",
                            split.page_content,
                        )
                    )
                ):  # Sub-Header and Header variant detection
                    udf_data["sentences"].append(split.page_content)
                    udf_data["is_header"].append(True)
                    udf_data["is_table"].append(False)
                    udf_data["page_number"].append(current_page)
                    current_length += len(split.page_content)
                elif (
                    split.page_content[0] == "|" and split.page_content[-1] == "|"
                ):  # Table detection
                    udf_data["sentences"].append(split.page_content)
                    udf_data["is_header"].append(False)
                    udf_data["is_table"].append(True)
                    udf_data["page_number"].append(current_page)
                    current_length += len(split.page_content)
                else:
                    udf_data["sentences"].append(split.page_content)
                    udf_data["is_header"].append(False)
                    udf_data["is_table"].append(False)
                    udf_data["page_number"].append(current_page)
                    current_length += len(split.page_content)
        return udf_data

    def _process_txt(self, file_bytes: bytes):
        text_data = {
            "sentences": [],
            "page_number": [],
            "is_header": [],
            "is_table": [],
        }
        text = file_bytes.decode("utf-8", errors="ignore")
        valid_sentences = self._process_text(text=text)
        text_data["sentences"].extend(valid_sentences)
        text_data["page_number"].extend([1] * len(valid_sentences))
        text_data["is_header"].extend([False] * len(valid_sentences))

        text_data["is_table"] = [False] * len(text_data["sentences"])
        return text_data

    def _process_text(self, text):
        docs = self.nlp(text)
        sentences = [sent.text.replace("\n", " ").strip() for sent in docs.sents]
        return [sentence for sentence in sentences if len(sentence) > 15]

    def _chunk_html(self, html_text: str, max_tokens: int = 2000):
        chunked_data = {
            "sentences": [],
            "page_number": [],
            "is_header": [],
            "is_table": [],
        }

        current_length = 0

        for i, sentence in enumerate(html_text["sentences"]):
            estimated_tokens = len(sentence.split())

            if estimated_tokens > max_tokens:
                words = sentence.split()
                for j in range(0, len(words), max_tokens):
                    chunk = " ".join(words[j : j + max_tokens])
                    chunked_data["sentences"].append(chunk)
                    chunked_data["page_number"].append(html_text["page_number"][i])
                    chunked_data["is_header"].append(html_text["is_header"][i])
                    chunked_data["is_table"].append(html_text["is_table"][i])
            else:
                if current_length + estimated_tokens > max_tokens:
                    chunked_data["sentences"].append(sentence)
                    chunked_data["page_number"].append(html_text["page_number"][i])
                    chunked_data["is_header"].append(html_text["is_header"][i])
                    chunked_data["is_table"].append(html_text["is_table"][i])
                    current_length = 0
                else:
                    chunked_data["sentences"].append(sentence)
                    chunked_data["page_number"].append(html_text["page_number"][i])
                    chunked_data["is_header"].append(html_text["is_header"][i])
                    chunked_data["is_table"].append(html_text["is_table"][i])
                    current_length += estimated_tokens

        return chunked_data

    def _get_file_size(self, file_bytes: bytes) -> None:
        return len(file_bytes) / (1024 * 1024)

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"(\b\w+)\s*\n\s*(\w+\b)", r"\1 \2", text)
        text = re.sub(r"(\w+)-\s+(\w+)", r"\1\2", text)
        text = re.sub(r"[,()]\s*\n\s*(\w+)", r" \1", text)
        text = re.sub(r"(\b\w+)\s*-\s*(\w+\b)", r"\1 \2", text)
        text = re.sub(r"(\w+)\s*[-–]\s*(\w+)", r"\1\2", text)
        text = re.sub(
            r"(?:[\s!\"#$%&\'()*+,\-.:;<=>?@\[\\\]^_`{|}~]+)(?!\w)", r" ", text
        )
        text = text.replace("\n", " ").strip()
        return " ".join(text.split())
