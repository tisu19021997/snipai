# SnipAI

SnipAI is your screenshot companion that runs entirely on your MacOS machine.

Take screenshots, let local AI describe and tag them, then find them instantly through semantic search - all without sending your data anywhere.

Youtube Demo below
[![Demo Video](/assets/screenshot.png)](https://www.youtube.com/watch?v=ftmSr9TE6wA)

**Features:**

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

**Milestones:**

- [ ] Finish interactive graph view
- [ ] Use image embedding models instead of description embeddings
- [ ] Reflect tags and descriptions to native OS file system metadata - files over apps
