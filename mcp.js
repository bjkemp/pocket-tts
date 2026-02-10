#!/usr/bin/env node

/**
 * Pocket TTS MCP Server
 *
 * This server provides tools for interacting with the Pocket TTS engine.
 * It allows listing available voices, generating speech from text,
 * and exporting voice embeddings.
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { spawn } from "child_process";
import { z } from "zod";
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const PREDEFINED_VOICES = [
  "alba",
  "marius",
  "javert",
  "jean",
  "fantine",
  "cosette",
  "eponine",
  "azelma",
];

/**
 * Executes a pocket-tts command using uv.
 * @param {string[]} args - The arguments for the pocket-tts command.
 * @returns {Promise<{stdout: string, stderr: string, code: number}>}
 */
async function runPocketTts(args) {
  return new Promise((resolve) => {
    const process = spawn("uv", ["run", "pocket-tts", ...args]);
    let stdout = "";
    let stderr = "";

    process.stdout.on("data", (data) => {
      stdout += data.toString();
    });

    process.stderr.on("data", (data) => {
      stderr += data.toString();
    });

    process.on("close", (code) => {
      resolve({ stdout, stderr, code });
    });
  });
}

const server = new Server(
  {
    name: "pocket-tts",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

/**
 * List of available tools and their schemas.
 */
const tools = [
  {
    name: "list_voices",
    description: "List all available predefined voices for text-to-speech generation.",
    inputSchema: {
      type: "object",
      properties: {},
    },
    async handler() {
      return {
        content: [
          {
            type: "text",
            text: `Available predefined voices: ${PREDEFINED_VOICES.join(", ")}`,
          },
        ],
      };
    },
  },
  {
    name: "generate_audio",
    description: "Generate speech audio from text using a specified voice.",
    inputSchema: {
      type: "object",
      properties: {
        text: {
          type: "string",
          description: "The text to convert to speech.",
        },
        voice: {
          type: "string",
          description: `The voice to use. Can be a predefined voice (${PREDEFINED_VOICES.join(
            ", "
          )}) or a path to an audio file/safetensors embedding.`,
          default: "alba",
        },
        output_path: {
          type: "string",
          description: "The path where the generated .wav file should be saved.",
          default: "./tts_output.wav",
        },
      },
      required: ["text"],
    },
    async handler(args) {
      const { text, voice = "alba", output_path = "./tts_output.wav" } = args;
      const cmdArgs = ["generate", "--text", text, "--voice", voice, "--output-path", output_path];

      const { stdout, stderr, code } = await runPocketTts(cmdArgs);

      if (code !== 0) {
        return {
          isError: true,
          content: [{ type: "text", text: `Error generating audio: ${stderr || stdout}` }],
        };
      }

      return {
        content: [
          {
            type: "text",
            text: `Successfully generated audio to ${output_path}.
${stdout}`,
          },
        ],
      };
    },
  },
  {
    name: "say",
    description: "Generate and play speech audio from text immediately (macOS only).",
    inputSchema: {
      type: "object",
      properties: {
        text: {
          type: "string",
          description: "The text to convert to speech and play.",
        },
        voice: {
          type: "string",
          description: `The voice to use. Can be a predefined voice (${PREDEFINED_VOICES.join(
            ", "
          )}) or a path to an audio file/safetensors embedding.`,
        },
      },
      required: ["text"],
    },
    async handler(args) {
      const { text, voice } = args;
      const cmdArgs = [text];
      if (voice) {
        cmdArgs.unshift("-v", voice);
      }

      const pocketSayPath = join(__dirname, "pocket-say");

      return new Promise((resolve) => {
        const process = spawn(pocketSayPath, cmdArgs);
        let stdout = "";
        let stderr = "";

        process.stdout.on("data", (data) => {
          stdout += data.toString();
        });

        process.stderr.on("data", (data) => {
          stderr += data.toString();
        });

        process.on("close", (code) => {
          if (code !== 0) {
            resolve({
              isError: true,
              content: [{ type: "text", text: `Error playing audio: ${stderr || stdout}` }],
            });
          } else {
            resolve({
              content: [
                {
                  type: "text",
                  text: `Successfully played: "${text}"`,
                },
              ],
            });
          }
        });
      });
    },
  },
  {
    name: "export_voice",
    description: "Export a voice embedding from an audio file to a .safetensors file for faster loading.",
    inputSchema: {
      type: "object",
      properties: {
        audio_path: {
          type: "string",
          description: "Path to the source audio file (e.g., .wav, .mp3).",
        },
        export_path: {
          type: "string",
          description: "Path where the .safetensors embedding should be saved.",
        },
        truncate: {
          type: "boolean",
          description: "Whether to truncate long audio files.",
          default: false,
        },
      },
      required: ["audio_path", "export_path"],
    },
    async handler(args) {
      const { audio_path, export_path, truncate = false } = args;
      const cmdArgs = ["export-voice", audio_path, export_path];
      if (truncate) cmdArgs.push("--truncate");

      const { stdout, stderr, code } = await runPocketTts(cmdArgs);

      if (code !== 0) {
        return {
          isError: true,
          content: [{ type: "text", text: `Error exporting voice: ${stderr || stdout}` }],
        };
      }

      return {
        content: [
          {
            type: "text",
            text: `Successfully exported voice embedding to ${export_path}.
${stdout}`,
          },
        ],
      };
    },
  },
];

// Register Tool Listing
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: tools.map(({ name, description, inputSchema }) => ({
    name,
    description,
    inputSchema,
  })),
}));

// Register Tool Handling
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const tool = tools.find((t) => t.name === request.params.name);
  if (!tool) {
    throw new Error(`Unknown tool: ${request.params.name}`);
  }

  try {
    return await tool.handler(request.params.arguments);
  } catch (error) {
    return {
      isError: true,
      content: [{ type: "text", text: `Error: ${error.message}` }],
    };
  }
});

/**
 * Main execution
 */
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Pocket TTS MCP Server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error in main():", error);
  process.exit(1);
});
