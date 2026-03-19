# Luna Bot

Luna Bot is a versatile Discord bot powered by `discord.py`. It provides AI-driven chat, image generation through ComfyUI, high-quality Text-to-Speech (TTS), and a range of utility and moderation tools.

---

## Features

### AI Chat
- **Multiple Backends:** Supports Google Gemini, OpenAI-compatible APIs, and local LLMs.
- **Multimodal Support:** Users can send images for visual analysis.
- **Context Memory:** Maintains conversation history with automatic summarization to manage long interactions.
- **Dynamic Prompting:** Supports customizable system, jailbreak, and summary prompts.
- **Mention Trigger:** Responds directly when mentioned in a channel.

### Image Generation (Paint)
- **ComfyUI Integration:** Generate images and videos directly from Discord.
- **Workflow Management:** Switch between different ComfyUI JSON workflows dynamically.
- **Customizable Parameters:** Fine-tune generations with CLI-style flags such as `--negative`, `--steps`, and `--cfg`.

### Voice & TTS
- **High-Quality TTS:** Powered by [BangDream-Bert-VITS2](https://huggingface.co/spaces/Mahiruoshi/BangDream-Bert-VITS2).
- **Audio Streaming:** Play audio from YouTube, SoundCloud, and other platforms via `yt-dlp`.
- **Local Playback:** Play audio files directly from the server's local storage.
- **Queue System:** Manage playback with pause, resume, skip, and queue management.

### Utilities & Moderation
- **Calculations:** Evaluate mathematical expressions and number representations (binary, hex, etc.).
- **Randomization:** Includes a dice roller, Magic 8-Ball, and a joke system.
- **Moderation Tools:** Essential commands for managing members (kick, ban, unban) and clearing messages.
- **Runtime Configuration:** Modify bot settings like prefix, name, and activity without restarting.

---

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/luna-bot.git
   cd luna-bot
   ```

2. **Set up a virtual environment (Recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure the bot:**
   - Copy `config/template_config.ini` to `config.ini`.
   - Fill in your `bot_token` and the necessary API keys for Gemini or OpenAI.
   - (Optional) Configure ComfyUI URL and workflow paths if utilizing image generation.

5. **Run the bot:**
   ```bash
   python bot.py
   ```

---

## Configuration

Luna Bot is configured via `config.ini`. Key sections include:
- `[credentials]`: API keys and bot tokens.
- `[customizations]`: Bot name, activity, and embed footers.
- `[chat_settings]`: LLM parameters such as temperature, model selection, and context limits.
- `[paint_settings]`: ComfyUI connection details and workflow defaults.
- `[tts_settings]`: Speaker selection for TTS.

---

## Command Reference

### AI Chat
- `!chat <message>`: Chat with the AI (supports image attachments).
- `!reset_chat`: Clear the current conversation history.
- `!display_context`: Show the current stored conversation context.

### Image Generation (Paint)
- `!paint <prompt> [--flag value]`: Generate an image or video.
- `!list_workflows`: List available ComfyUI workflows.
- `!list_paint_vars`: List customizable variables for the current workflow.

### Voice & Audio
- `!play_url <url>`: Play audio from a URL.
- `!play_local <path>`: Play a local file or all files in a directory.
- `!tts <text>`: Convert text to speech.
- `!queue`: Display the current audio queue.
- `!skip`, `!pause`, `!resume`: Control current playback.

### Utilities & Fun
- `!roll <xdy+z>`: Roll dice (e.g., `2d20+5`).
- `!calculator <expression>`: Evaluate math (e.g., `sin(pi/2) * 10`).
- `!represent <number>`: Show decimal, binary, octal, and hex forms.
- `!joke`: Get a random joke.
- `!8ball <question>`: Get an answer from the Magic 8-Ball.
- `!choose <option1> <option2> ...`: Pick between multiple choices.

### Moderation
- `!clear <amount>`: Delete a specified number of recent messages.
- `!kick`, `!ban`, `!unban`: Manage server members.
- `!userinfo`, `!serverinfo`: View detailed information about a user or the server.

### Configuration
- `!set <option> <value>`: Update a configuration setting at runtime.
- `!get <option>`: Retrieve the current value of a setting.
- `!list_config`: List all non-sensitive configuration settings.

---

## Contributing

Contributions are welcome. Please submit a Pull Request or open an issue for any bugs or feature requests.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
