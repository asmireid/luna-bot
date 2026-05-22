# Luna Agent

Luna is a sophisticated Discord agent powered by `discord.py`. More than just a bot, Luna features an autonomous tool-execution system, Model Context Protocol (MCP) integration, and multimodal capabilities, allowing it to perceive and interact with the world through a variety of extensible "skills."

---

## 🤖 Core Agentic Features

### Autonomous Tool Execution
- **Tool-Call Loop:** Luna can identify when a task requires external tools, execute them (sequentially or in parallel), and synthesize the results into a final response.
- **Multimodal Perception:** Built-in support for visual analysis—send images or files, and Luna can use tools to "see" and describe them.
- **Extensible Registry:** Easily add new capabilities via the Local Tool Provider or remote MCP servers.

### Model Context Protocol (MCP) Support
- **Dynamic Tool Discovery:** Connect to any MCP-compliant server (e.g., Google Search, Filesystem, specialized APIs) to instantly expand Luna's capabilities.
- **Multiple Transports:** Supports both `stdio` (local subprocesses) and `http` (remote endpoints) for MCP servers.
- **Unified Tool Interface:** Remote tools are seamlessly integrated into the chat flow with status updates and error handling.

### Advanced Knowledge & Memory
- **Multiple Backends:** Supports Google Gemini (with native tool-calling), OpenAI-compatible APIs, and local LLMs.
- **Context Management:** Maintains deep conversation history with automatic summarization to manage long-term interactions.
- **Asset Store:** A robust system for managing files, images, and tool outputs, ensuring data persistence across tool calls.

---

## 🎨 Image & Media Capabilities

### ComfyUI Integration (Paint)
- **Workflow-Based Generation:** Generate images and videos directly from Discord using ComfyUI.
- **Dynamic Variable Injection:** Pass CLI-style flags (e.g., `--negative`, `--steps`) to override workflow parameters on the fly.
- **Real-time Status:** Tracks generation progress and provides immediate feedback in the channel.

### Voice & TTS
- **High-Quality Speech:** Powered by [BangDream-Bert-VITS2](https://huggingface.co/spaces/Mahiruoshi/BangDream-Bert-VITS2).
- **Audio Streaming:** Seamless playback from YouTube, SoundCloud, and other platforms via `yt-dlp`.
- **Intelligent Queueing:** Full-featured audio controller with play, skip, pause, and local storage playback.

---

## 🛠️ Tooling & Extension

### Adding Tools
Luna can be extended in two ways:
1.  **Local Tools:** Add Python scripts to `util/tools/` and register them using the `@manager.register` decorator.
2.  **MCP Servers:** Add external servers to `config/tool_providers.json`.

Example `tool_providers.json` configuration:
```json
{
  "providers": [
    {
      "id": "web-search",
      "type": "mcp",
      "enabled": true,
      "settings": {
        "transport": "stdio",
        "command": "npx -y @modelcontextprotocol/server-google-search"
      }
    }
  ]
}
```

---

## 🚀 Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/luna-bot.git
   cd luna-bot
   ```

2. **Set up a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configuration:**
   - Copy `config/template_config.ini` to `config.ini` and fill in your API keys.
   - Configure tool providers in `config/tool_providers.json`.

5. **Run the agent:**
   ```bash
   python bot.py
   ```

---

## ⌨️ Primary Commands

- `!chat <message>`: Start an agentic conversation (supports attachments).
- `!reset_chat`: Clear conversation context and memory.
- `!display_context`: Inspect the current agent state and history.
- `!paint <prompt> [flags]`: Trigger a ComfyUI image generation.
- `!tts <text>`: Synthesize speech from text.
- `!set <option> <value>`: Configure the agent at runtime.

---

## 📜 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
