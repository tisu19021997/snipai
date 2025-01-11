# SnipAI

SnipAI is your screenshot companion that runs entirely on your MacOS machine.

Take screenshots, let local AI describe and tag them, then find them instantly through semantic search - all without sending your data anywhere.

Youtube Demo below
[![Demo Video](/assets/screenshot.png)](https://www.youtube.com/watch?v=ftmSr9TE6wA)

Graph View
![Graph View](/assets/screenshot-graph.png)

## Features

- Take, organize, and search for screenshots in a PyQt application
- All local small language models
- Use `ollama` for all generation tasks:
  - `moondream` for generating description from images - super fast and accurate
  - `qwen2:1.5b` for image tagging - super fast and good at structured outputs
- Search images by natural language using binary vector embeddings
  - `mxbai-embed-large` for text embedding - with [binary quantization](https://www.mixedbread.ai/blog/binary-mrl) to minize storage and speed up retrieval
  - use [sqlite-vec](https://github.com/asg017/sqlite-vec) for retrieval
- Interactive graph view to explore similar screenshots (work in progress)

## Installation

### Prerequisites

1. Install Python 3.11.11 using pyenv (recommended):

```bash
brew install pyenv

pyenv install 3.11.11

# Set Python 3.11.11 as your global version (optional)
pyenv global 3.11.11
```

2. Install Homebrew:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

3. Install LLVM 14:

```bash
brew install llvm@14
```

4. Install [Poetry](https://python-poetry.org/docs/)

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

5. Configure Poetry to use Python 3.11.11:

```
poetry env use 3.11.11

poetry run python --version  # Should output: Python 3.11.11
```

6. Download [ollama](https://ollama.com/download) for MacOS

### Setting up snipai

1. Clone the repository:

```bash
git clone git@github.com:tisu19021997/snipai.git
cd snipai
```

2. Install dependencies using Poetry:

```bash
poetry install
```

3. Download required AI models using Ollama (or snipai will when app starts):

```bash
ollama pull moondream
ollama pull qwen2:1.5b
ollama pull mxbai-embed-large
```

4. Activate the Poetry environment:

```bash
poetry shell
```

5. Run SnipAI:

```bash
python -m snipai.app
```

### Roadmap

- [ ] Graph view improvements
  - [ ] UX
  - [ ] Switch to image embeddings from text descriptions
- [x] Native OS metadata integration - [file over app](https://stephango.com/file-over-app)
  - [x] Sync tags to file system
- [ ] Obsidian integration development
