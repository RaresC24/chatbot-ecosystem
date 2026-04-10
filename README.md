# AI Chatbot Ecosystem
<img width="400" height="306" alt="image" src="https://github.com/user-attachments/assets/21756693-d3ff-41aa-8105-eacaae9fa457" />
<img width="300" height="600" alt="image" src="https://github.com/user-attachments/assets/ee9fad88-5e4a-434b-888a-0673bd9acf7b" />

## Project Goal
The goal of this project is to provide a complete, secure, and drop-in AI chatbot ecosystem capable of being integrated into any website (such as Odoo or raw HTML pages). The system functions as a highly optimized lead generation tool that serves localized greetings, uses an OpenAI API key for GPT-powered conversations, enforces strict rate limits to prevent abuse, continuously logs interactions, and automatically captures leads via email without ever exposing sensitive backend credentials to the client.

## Architecture and File Integration

The project is structured into several interconnected layers: a customizable JavaScript frontend, a secure serverless backend proxy, an automated Python-based knowledge scraper, and GitHub Actions for continuous updates.

### 1. Frontend Interface (`index.html`)
This file contains the UI and client-side logic of the chatbot. Built with raw HTML, CSS, and Vanilla JavaScript, it is designed to operate cleanly within any website without conflicting with existing styling frameworks.
- **Dynamic Localization & Credits Optimization (`greeting.json`)**: To prevent wasting OpenAI API credits on every new visitor, the frontend detects the user's IP region and fetches a predefined, localized welcome message directly from `greeting.json`. The GPT model is only engaged *after* the user interacts.
- **Rate Limiting & Timeout Restrictions**: To prevent API abuse and control costs, the frontend tracks user interactions. If a user sends too many messages within a given timeframe, they are placed in a timeout state, and the chat automatically pushes the contact form forward.
- **Lead Capture & Automated Emails (EmailJS)**: When the chatbot detects buying intent, lacks the required knowledge to answer a question, or when the user hits the rate limit, it presents an embedded contact form. Upon completion, this form leverages the **EmailJS** library to trigger an automated email directly to the administrative/sales team, ensuring instant lead capture.

### 2. Serverless Security Proxy (`worker.js`)
To maintain strict security, the frontend never communicates directly with the OpenAI API or the GitHub repository. Instead, it sends requests to a **Cloudflare Worker**, which acts as a secure middleware proxy.
- **Credentials Masking**: The worker securely stores the OpenAI API Key and the GitHub Personal Access Token as environment variables, ensuring they are never exposed in the browser or the repository code. 
- **Centralized Routing**: The worker receives the user's message, compiles the context fetched from the GitHub repository, hits the OpenAI API to generate the GPT response, and finally pipes the output back to the frontend.
- **Conversation Logging**: As chats occur, the Cloudflare Worker automatically pushes and appends the live dialogue, user IP, and timestamp to a `conversations.csv` file stored in the GitHub repository.

### 3. Configuration & Prompt Engineering (`instructiuni.txt`)
The personality, boundaries, and rules of the GPT model are strictly defined in `instructiuni.txt`. 
- The Cloudflare worker reads this prompt file and prepends it to the OpenAI API request as a system instruction. 
- It contains detailed rules on how the bot should behave, dictating that its primary purpose is to capture interest and redirect users to the contact form rather than acting as a general-purpose AI.

### 4. The Knowledge Scraper (`preprocess_training_data.py` & `upload_to_github.py`)
Rather than manually compiling and updating the chatbot's knowledge, a custom Python scraper builds the context window dynamically.
- `training_links.txt` contains a list of relevant URLs that the bot should know about.
- `preprocess_training_data.py` uses Selenium to crawl these links. It is designed to force-expand hidden DOM elements (like drop-downs or Odoo-specific hidden blocks) to extract 100% of the site's text and construct a large `training_data.json` file.
- `upload_to_github.py` allows the system to seamlessly push the newly compiled JSON data back to GitHub. The Cloudflare Worker seamlessly retrieves this updated file, keeping the GPT model's knowledge accurate with zero downtime.

### 5. Automation & Maintenance (GitHub Workflows)
To ensure the ecosystem remains autonomous, GitHub Actions (`.github/workflows`) are configured to handle maintenance:
- **`update_training_data.yml`**: Automatically triggers the Python scraper on a schedule to revisit the target URLs, extract any new or changed information, and push updated `training_data.json` directly to the system.
- **`daily_log.yml` / `reset_log.yml`**: Automates routine tasks involving the `conversations.csv` file, ensuring the backlog of logs is routinely processed or cleared out so that the CSV file remains manageable.

---

### File Summary Breakdown

| File / Folder | Purpose |
|------|---------|
| `index.html` | The frontend UI. Contains logic for rate-limits, IP-based localization, and uses EmailJS for rendering and submitting lead capture forms. |
| `worker.js` | The secure Cloudflare proxy. Holds the OpenAI API key, manages Github tokens, requests GPT completions, and logs conversations. |
| `greeting.json` | Stores multilingual introductory messages to load natively, saving OpenAI API credits on initial interactions. |
| `instructiuni.txt` | The system prompt injected into the OpenAI API, defining the bot's behavior, tone, and constraints. |
| `preprocess_training_data.py` | A Python web scraper using Selenium that extracts text from targeted websites to automatically build the bot's knowledge base. |
| `training_links.txt` | The list of target URLs the Python scraper will read and extract text from. |
| `upload_to_github.py` | A pipeline script to upload the compiled `training_data.json` back to the GitHub database after scraping. |
| `conversations.example.csv` | The structured format used by the backend to continuously log user chat transcripts (`conversations.csv` in backend). |
| `.github/workflows/` | GitHub Actions YAML files responsible for keeping the training data updated and managing system logs automatically. |

---

## 🛠️ Developer Notes & Considerations

- **Single-File Frontend Design**: You might notice that `index.html` is a large, ~2000-line file combining HTML, CSS, and JavaScript. This was a deliberate architectural choice. It ensures the entire chatbot frontend can be rapidly copied and pasted as a single "HTML Embed" block into CMS platforms (like Odoo or WordPress) without having to manage external stylesheets or script files.
- **Company-Specific Logic**: This exact iteration of the showcase was originally built and tailored for a robotics company. While the ecosystem is highly adaptable, there may be a few company-specific UI strings, translations, or fallback logic hardcoded within `index.html` (such as the company default translation fallbacks). If you are adapting this for a different business, keep in mind you may need to comb through `index.html` to tweak these localized fallback strings to fit your specific brand!
