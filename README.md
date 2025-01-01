# SnipAI

SnipAI is your screenshot companion that runs entirely on your MacOS machine.

Take screenshots, let local AI describe and tag them, then find them instantly through semantic search - all without sending your data anywhere.

Youtube Demo below
[![Demo Video](/assets/screenshot.png)](https://www.youtube.com/watch?v=ftmSr9TE6wA)

## Features

- Take and organize screenshots
- Generate tags and descriptions using local AI models
  - `moondream` for generating description from images
  - `qwen2:1.5b` for image tagging
- Search using binary vector embeddings, running offline
  - `mxbai-embed-large` for text embedding
  - use [sqlite-vec](https://github.com/asg017/sqlite-vec)
- Only open-source models, right on your machine
- Zero setup - uses `SQLite` for both database and vector embeddings
- Interactive graph view to explore similar screenshots (work in progress)

## Installation

### Prerequisites

1. Install Homebrew:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

2. Install LLVM 14:

```bash
brew install llvm@14
```

3. Install [Poetry](https://python-poetry.org/docs/)

4. Download [ollama](https://ollama.com/download) for MacOS

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

### Milestones

- [ ] Finish interactive graph view
- [ ] Use image embedding models instead of description embeddings
- [ ] Reflect tags and descriptions to native OS file system metadata - [files over apps](https://stephango.com/file-over-app)
- [ ] Obsidian integration
