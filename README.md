# 🔗 Doclink.io
Doclink is an AI document assistant that transforms how you interact with your documents. Upload your files, create custom folders, and ask questions to quickly retrieve relevant information across your entire document collection. Doclinky connects related information between documents, making complex data analysis simple and intuitive.
We're on the early stage. And want to help everyone on their information processing. Thus, you can use doclink completely for free plus all of our implementation is open source.

## ✨ Features

- **📊 Custom Knowledge Bases**: Create and organize multiple document collections for different topics or projects
- **📑 Multi-Format Support**: Upload and analyze PDF, DOCX, XLSX, PPTX, TXT, and web content
- **🔍 Intelligent Search**: Ask questions in natural language and get precise answers from your documents
- **🧠 Context-Aware Responses**: AI understands the relationships between your documents for comprehensive answers
- **📌 Source Citations**: Every answer includes references to specific document sources for easy verification
- **🌐 Web Interface**: Intuitive, responsive design works across all devices
- **🔒 Secure Authentication**: Google authentication ensures your document library remains private

## 🚀 Get Started

1. **Sign Up**: Create an account using your google account on doclink.io
2. **Create a Folder**: Organize your documents into custom folders
3. **Upload Documents**: Add PDFs, Word documents, excel tables, and more
4. **Ask Questions**: Just ask to get information
5. **Analyze Responses**: Review AI-generated answers with source references
6. **Export Insights**: Save and share your findings

# 🛠️ Tech Stack

We have a very lean tech stack. We mostly trust our from scratch RAG implementation and RAG understanding. On every benchmark, we have 95% relevancy level on our answers.
We're not very experienced web developers. But we trust our AI & RAG implementation.

## 🖥️ Frontend
- Next.js
- Bootstrap & Custom CSS
- JavaScript

## 🔧 Backend
- FastAPI
- PostgreSQL
- Redis

## 🧠 AI & RAG
- OpenAI: Embeddings and answer generation
- FAISS: Semantic search

## 📝 Document Processing
- PyMuPDF/Fitz: PDF processing and content extraction
- Docx/XLSX Processing: Support for Microsoft Office document formats
- Web Scraping: Ability to process and index web content

# 🔍 RAG Implementation

## 📊 Relational Database Approach

Doclink implements a custom Retrieval-Augmented Generation (RAG) system using PostgreSQL rather than specialized vector databases. This unique approach offers several advantages:

- **🧩 Simplicity**: Using a single PostgreSQL database for both document metadata and embeddings simplifies the architecture and maintenance
- **💰 Cost Efficiency**: Eliminates the need for additional vector database services or infrastructure
- **⚙️ Flexibility**: Allows for complex queries that combine traditional SQL filtering with vector similarity search

## 🏗️ How It Works

Our RAG implementation functions through several key components:

1. **📄 Document Processing**: Documents are processed, split into meaningful chunks, and transformed into embeddings using OpenAI's embedding models
2. **💾 Storage**: These embeddings are stored in PostgreSQL using the `BYTEA` data type, alongside document metadata and user information
3. **🔎 Retrieval**: When a query is submitted, it's converted to an embedding and similarity search is performed against stored document embeddings
4. **🧠 Context Building**: The most relevant document chunks are assembled into a context window using custom logic that considers:
   - Semantic relevance scores
   - Document structure (headers, paragraphs, tables)
   - User-selected file filters
5. **✍️ Response Generation**: The retrieved context is sent to the language model along with the original query to generate accurate, contextually relevant responses

## 🔐 Security Layer

Unlike many RAG implementations, Doclink adds an encryption layer to stored document content:

- **🔒 AES-GCM Encryption**: Document content is encrypted before storage, with each file having a unique authentication tag
- **🔑 Secure Decryption**: Content is only decrypted when needed for response generation
- **🛡️ Privacy Preservation**: Original document content remains protected even if the database is compromised

This approach combines the power of modern vector search techniques with the reliability and familiarity of relational databases, creating a robust, secure, and maintainable RAG system.

This architecture enables Doclink to securely handle document processing, embedding generation, and sophisticated question-answering capabilities while maintaining a responsive user experience.

# 👥 Contributing

We welcome contributions to Doclink! If you need a specific update, please open an issue we will be on it.
If you want to be part of our team, please reach us.

# 🙏 Acknowledgments

Doclink stands on the shoulders of giants. We'd like to acknowledge the following projects and libraries that make our work possible:

- **OpenAI** - For their powerful language models and embeddings
- **PyMuPDF (Fitz)** - Document processing library, licensed under GNU GPL v3
- **FAISS** - Efficient similarity search library from Facebook Research
- **FastAPI** - Modern, fast web framework for building APIs
- **PostgreSQL** - Robust, open-source relational database
- **Next.js** - React framework for production-grade web applications
- **Spacy** - Industrial-strength natural language processing
- **Redis** - In-memory data structure store
- **Bootstrap** - Front-end framework for responsive web design

Special thanks to:
- All contributors who have invested their time and expertise
- The open-source community for continued inspiration and support
- Our users for valuable feedback and suggestions

# 📜 License

Doclink is released under the MIT License.
