/**
 * Cloudflare Worker to proxy OpenAI API requests
 * 
 * SETUP INSTRUCTIONS:
 * 1. Log in to Cloudflare Dashboard > Workers & Pages
 * 2. Create a new Worker (e.g., named "chat-proxy")
 * 3. Click "Edit Code" and paste this entire file
 * 4. Save and Deploy
 * 5. Go to Settings > Variables
 * 6. Add a variable named "OPENAI_API_KEY" with your actual sk-... key
 * 7. (Optional) Add "ALLOWED_ORIGIN" with your Odoo site URL to restrict access
 */

export default {
    async fetch(request, env, ctx) {
        // Handle CORS preflight requests
        if (request.method === "OPTIONS") {
            return new Response(null, {
                headers: {
                    "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN || "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization",
                },
            });
        }

        // Only allow POST requests
        if (request.method !== "POST") {
            return new Response("Method not allowed", { status: 405 });
        }

        try {
            const body = await request.json();

            // Handle config file request (to access private repo files)
            if (body.action === "get_config_file") {
                if (!env.GITHUB_TOKEN) {
                    throw new Error("GITHUB_TOKEN missing in Worker variables");
                }
                const filename = body.filename;
                if (!filename) {
                    throw new Error("Filename missing in request");
                }
                
                const apiUrl = `https://api.github.com/repos/YOUR_GITHUB_HANDLE/YOUR_PRIVATE_REPO/contents/${filename}`;
                
                const githubResponse = await fetch(apiUrl, {
                    headers: {
                        "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
                        "User-Agent": "Cloudflare-Worker",
                        "Accept": "application/vnd.github.v3+json"
                    }
                });
                
                if (!githubResponse.ok) {
                    const error = await githubResponse.text();
                    throw new Error(`GitHub API Error for ${filename}: ${error}`);
                }
                
                const data = await githubResponse.json();
                if (!data.content) {
                    throw new Error(`No content found for ${filename}`);
                }
                
                // Decode Base64 content properly (handling UTF-8)
                const binaryString = atob(data.content.replace(/\s/g, ''));
                const bytes = new Uint8Array(binaryString.length);
                for (let i = 0; i < binaryString.length; i++) {
                    bytes[i] = binaryString.charCodeAt(i);
                }
                const content = new TextDecoder().decode(bytes);
                
                // If it's a JSON file, parse it first to ensure valid JSON is returned
                let result = content;
                if (filename.endsWith(".json")) {
                    try {
                        result = JSON.parse(content);
                    } catch (e) {
                        console.warn(`Failed to parse ${filename} as JSON, returning as string`);
                    }
                }
                
                return new Response(JSON.stringify({ content: result }), {
                    headers: {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN || "*",
                    },
                });
            }

            // Handle logging request
            if (body.action === "log_conversation") {

                if (!env.GITHUB_TOKEN) {
                    throw new Error("GITHUB_TOKEN missing in Worker variables");
                }
                const apiUrl = `https://api.github.com/repos/YOUR_GITHUB_HANDLE/YOUR_PRIVATE_REPO/contents/conversations.csv`;

                // 1. Get current file content (to get SHA and append)
                let currentContent = "";
                let sha = "";

                try {
                    const getResponse = await fetch(apiUrl, {
                        headers: {
                            "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
                            "User-Agent": "Cloudflare-Worker",
                            "Accept": "application/vnd.github.v3+json"
                        }
                    });

                    if (getResponse.ok) {
                        const data = await getResponse.json();
                        if (data.content) {
                            // Decode Base64 content properly (handling UTF-8)
                            const binaryString = atob(data.content.replace(/\s/g, ''));
                            const bytes = new Uint8Array(binaryString.length);
                            for (let i = 0; i < binaryString.length; i++) {
                                bytes[i] = binaryString.charCodeAt(i);
                            }
                            currentContent = new TextDecoder().decode(bytes);
                            sha = data.sha;
                        }
                    } else if (getResponse.status === 404) {
                        // File doesn't exist yet, create header
                        currentContent = "ConversationID,Date,IP,Country,Languages,Transcript\n";
                        // File doesn't exist yet, currentContent remains empty, header will be added later
                    }
                } catch (e) {
                    console.error("Error fetching file:", e);
                }

                // 2. Prepare new content
                // Use a simple CSV format (escaping quotes). 
                // CRITICAL: Replace newlines with literal \n to ensure 1 row = 1 line in the file.
                // This ensures we can properly find and update the row by ID.
                const escapeCsv = (str) => {
                    if (!str) return "";
                    let stringValue = String(str);

                    // Replace newlines with a distinct separator or literal \n so the CSV structure stays 1 line per row
                    stringValue = stringValue.replace(/\r\n/g, "\\n").replace(/\n/g, "\\n").replace(/\r/g, "\\n");

                    if (stringValue.includes(",") || stringValue.includes("\"")) {
                        return `"${stringValue.replace(/"/g, '""')}"`;
                    }
                    return stringValue;
                };

                const newData = body.data;
                const newRow = `${escapeCsv(newData.id)},${escapeCsv(newData.date)},${escapeCsv(newData.ip)},${escapeCsv(newData.country)},${escapeCsv(newData.languages)},${escapeCsv(newData.transcript)}`;

                // Check if row with this ID already exists and update it, otherwise append
                let finalContent = "";
                let found = false;

                if (!currentContent) {
                    // Header if file is empty
                    finalContent = "ConversationID,Date,IP,Country,Languages,Transcript\n" + newRow + "\n";
                } else {
                    const lines = currentContent.split("\n");
                    const updatedLines = [];

                    for (const line of lines) {
                        if (!line.trim()) continue; // Skip empty lines

                        // Check if line starts with our ID (handling potential quotes around ID)
                        // Matches: ID,... or "ID",...
                        const id = newData.id;
                        if (line.startsWith(id + ",") || line.startsWith(`"${id}",`)) {
                            found = true;
                            updatedLines.push(newRow); // Replace entire line
                        } else {
                            updatedLines.push(line);
                        }
                    }

                    if (!found) {
                        updatedLines.push(newRow);
                    }

                    finalContent = updatedLines.join("\n") + "\n";
                }

                // 3. Update file on GitHub
                // Encode content to Base64 manually to ensure UTF-8 correctness
                const encoder = new TextEncoder();
                const utf8Bytes = encoder.encode(finalContent);
                let binaryString = "";
                for (let i = 0; i < utf8Bytes.length; i++) {
                    binaryString += String.fromCharCode(utf8Bytes[i]);
                }
                const base64Content = btoa(binaryString);

                const putResponse = await fetch(apiUrl, {
                    method: "PUT",
                    headers: {
                        "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
                        "User-Agent": "Cloudflare-Worker",
                        "Accept": "application/vnd.github.v3+json",
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        message: `Log conversation ${newData.id}`,
                        content: base64Content,
                        sha: sha || undefined
                    })
                });

                if (!putResponse.ok) {
                    const error = await putResponse.text();
                    throw new Error(`GitHub API Error: ${error}`);
                }

                return new Response(JSON.stringify({ success: true }), {
                    headers: {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN || "*",
                    },
                });
            }

            // Forward request to OpenAI
            const response = await fetch("https://api.openai.com/v1/chat/completions", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${env.OPENAI_API_KEY}`,
                },
                body: JSON.stringify(body),
            });

            // Get the response from OpenAI
            const data = await response.json();

            // Return response to client with CORS headers
            return new Response(JSON.stringify(data), {
                headers: {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN || "*",
                },
            });
        } catch (error) {
            return new Response(JSON.stringify({ error: error.message }), {
                status: 500,
                headers: {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN || "*",
                },
            });
        }
    },
};
