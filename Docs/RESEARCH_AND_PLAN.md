# Omni — Full Research & Plan
---

## Table of Contents

1. [Project Concept](#1-project-concept)
2. [Google ADK Research](#2-google-adk-research)
3. [Gemini Live API Research](#3-gemini-live-api-research)
    - [Interleaved Output — Image Generation in Live Sessions](#interleaved-output--image-generation-in-live-sessions)
    - [Client-Side SDK Research — gemini-live-sdk (npm)](#client-side-sdk-research--gemini-live-sdk-npm)
4. [E2B Sandbox Research](#4-e2b-sandbox-research)
5. [MCP Ecosystem Research](#5-mcp-ecosystem-research)
6. [WebMCP & Chrome AI Research](#6-webmcp--chrome-ai-research)
    - [Chrome Extension — Voice-Activated Tasks](#chrome-extension--voice-activated-tasks)
7. [Trending MCPs & Skills](#7-trending-mcps--skills)
8. [Desktop Client — Computer Use Agent](#8-desktop-client--computer-use-agent)
    - [How Claude Desktop / Computer Use Works](#how-claude-desktop--computer-use-works)
    - [Implementation for Agent Hub — Python Tray App](#implementation-for-agent-hub--python-tray-app)
    - [Desktop Client Use Cases](#desktop-client-use-cases)
    - [Reference: UFO³ by Microsoft](#reference-ufo³-by-microsoft)
9. [Architecture Design](#9-architecture-design)
    - [System Architecture](#system-architecture)
    - [ADK Multi-Agent Architecture](#adk-multi-agent-architecture--leveraging-all-agent-types)
    - [TaskArchitect — Dynamic Meta-Orchestrator](#taskarchitect--dynamic-meta-orchestrator)
    - [GenUI — Generative UI on Dashboard](#genui--generative-ui-on-dashboard)
10. [Implementation Plan](#10-implementation-plan)
11. [Tech Stack](#11-tech-stack)
12. [Scope & Decisions](#12-scope--decisions)

---

## 1. Project Concept

### One-Liner
A **multi-client, single-server AI agent hub** where users connect via eyeglasses, web dashboard, or mobile app — all managed by a centralized backend with live voice/video streaming, dynamic MCP plugin system, agent personas with distinct voices, and E2B sandboxed code execution.

### Problem Statement
Current AI assistants are **single-device, single-modality, and static**. You talk to ChatGPT in a text box on one screen. You can't seamlessly transition from your phone to your glasses to your desktop. You can't add new capabilities on the fly. You can't have different "experts" with different voices and knowledge.

### Solution
**Agent Hub** — a unified AI agent backend that:
- Connects to **multiple client types simultaneously** (web dashboard, mobile PWA, ESP32 smart glasses)
- Enables **cross-client actions** ("Hey glasses, save a note to my web dashboard")
- Provides **agent personas** with distinct voices, skills, and instructions (Gemini native audio per-agent voice config)
- Offers an **MCP plugin store** where users add/remove capabilities like installing apps
- Runs code safely in **E2B sandboxes** with 100+ built-in MCP servers
- Uses **proactive audio** and **affective dialog** for truly natural conversation

### Why This Wins
| Differentiator | Why It Matters |
|---|---|
| Multi-client hub (not just "another chat UI") | Breaks the single-device paradigm |
| Cross-client actions via agent tool calls | Novel interaction pattern never seen before |
| Per-agent voice personas | Distinct persona/voice per agent |
| MCP plugin store (user-expandable) | System extensibility and real-world value |
| Proactive audio + affective dialog | Cutting-edge Gemini native audio features |
| ESP32 glasses support | Hardware + software = immersive multimodal experience |

---

## 2. Google ADK Research

### What is ADK?
**Agent Development Kit** — Google's production-ready framework for building AI agents. Python-first (also TypeScript, Go, Java). `pip install google-adk`.

### Agent Types
| Type | Class | Purpose |
|---|---|---|
| **LLM Agent** | `Agent` / `LlmAgent` | Core agent powered by Gemini. Has instruction, tools, sub_agents |
| **Sequential Agent** | `SequentialAgent` | Runs sub-agents in order |
| **Parallel Agent** | `ParallelAgent` | Runs sub-agents concurrently |
| **Loop Agent** | `LoopAgent` | Repeats sub-agents until condition met |
| **Custom Agent** | `BaseAgent` | Full control, override `_run_async_impl()` |

### Core ADK Components
```
Agent(name, model, instruction, tools, sub_agents)
Runner(app_name, agent, session_service, memory_service, plugins)
SessionService → InMemorySessionService / DatabaseSessionService / VertexAiSessionService
MemoryService → InMemoryMemoryService / VertexAiMemoryBankService
LiveRequestQueue → send_content(), send_realtime(), send_activity_start/end(), close()
RunConfig(streaming_mode, response_modalities, speech_config, proactivity, enable_affective_dialog)
```

### MCP Integration in ADK
```python
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import SseConnectionParams

# Example: Connect to a remote MCP server
mcp_tools = McpToolset(
    connection_params=SseConnectionParams(url="https://mcp-server.example.com/sse")
)

# Or via Stdio (local process)
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
mcp_tools = McpToolset(
    connection_params=StdioConnectionParams(command="npx", args=["-y", "@anthropic/mcp-brave-search"])
)
```
- Supports: `StdioConnectionParams`, `SseConnectionParams`, `StreamableHTTPConnectionParams`
- Features: auth support, tool filtering, header providers, session management

### Skills System (Experimental, ADK v1.25.0+)
```python
from google.adk.skills import load_skill_from_dir
from google.adk.tools import skill_toolset

weather_skill = load_skill_from_dir(pathlib.Path(__file__).parent / "skills" / "weather_skill")
my_skill_toolset = skill_toolset.SkillToolset(skills=[weather_skill])

agent = Agent(model="gemini-2.5-flash", tools=[my_skill_toolset])
```
- Skills follow the Agent Skill specification (agentskills.io)
- Structure: `SKILL.md` (required) + `references/` + `assets/` + `scripts/`
- Loaded on-demand to minimize context window impact

### Plugin System (ADK v1.7.0+)
- Plugins extend `BasePlugin`, register on `Runner` via `plugins=[]`
- Global callbacks: `before_agent`, `after_agent`, `before_model`, `after_model`, `before_tool`, `after_tool`, `on_event`, `on_model_error`, `on_tool_error`
- Pre-built: Reflect & Retry Tools, BigQuery Analytics, Context Filter, Global Instruction, Logging
- Plugins run BEFORE agent-level callbacks (precedence)

### Memory System
- `InMemoryMemoryService` — keyword matching, no persistence (dev)
- `VertexAiMemoryBankService` — LLM-powered memory extraction, semantic search (prod)
- Tools: `PreloadMemoryTool` (always load), `LoadMemory` (agent decides)
- Memory workflow: `add_session_to_memory(session)` → `search_memory(query)`

### Session Management
- `Session` = single conversation thread with event history + state
- `State` = key-value data within a session
- `Memory` = cross-session searchable knowledge
- Services: `InMemorySessionService` (dev), `DatabaseSessionService` (SQLite/PostgreSQL/MySQL), `VertexAiSessionService` (managed)

### Callbacks System
- **Agent lifecycle**: `before_agent_callback`, `after_agent_callback`
- **Model lifecycle**: `before_model_callback`, `after_model_callback`
- **Tool lifecycle**: `before_tool_callback`, `after_tool_callback`
- Use for: guardrails, logging, state modification, response caching

### Deployment Options
| Platform | Best For |
|---|---|
| **Cloud Run** | WebSocket/Live agents, auto-scaling, recommended for streaming |
| **Agent Engine (Vertex AI)** | Managed hosting, enterprise features |
| **GKE** | Full Kubernetes control |
| **CLI** | `adk web` for local dev, `adk run` for CLI testing |

### A2A Protocol
- Agent-to-Agent communication protocol
- Allows ADK agents to communicate with agents built on other frameworks
- Out of scope for MVP but architecturally supported

---

## 3. Gemini Live API Research

### What is the Live API?
WebSocket-based bidirectional streaming with Gemini models. Supports continuous audio, video, and text in real-time.

### Technical Specifications
| Spec | Value |
|---|---|
| Audio Input | 16-bit PCM, 16kHz, mono |
| Audio Output | 16-bit PCM, 24kHz, mono (native audio models) |
| Video Input | JPEG, 1fps recommended, 768×768 px |
| Context Window | 32k-128k tokens (model-dependent) |
| Languages | 24+ with automatic detection |
| Session Duration (Gemini API) | Audio-only: 15 min, Audio+video: 2 min (unlimited with context compression) |
| Session Duration (Vertex AI) | 10 min (unlimited with context compression) |
| Concurrent Sessions | Tier-based (Gemini) / Up to 1,000 (Vertex AI) |

### Audio Model Architectures
| Architecture | Model | Features |
|---|---|---|
| **Native Audio** | `gemini-2.5-flash-native-audio-preview-12-2025` (Gemini API) / `gemini-live-2.5-flash-native-audio` (Vertex AI) | End-to-end audio, natural prosody, extended voice library, affective dialog, proactive audio, automatic language detection |
| **Half-Cascade** | `gemini-2.0-flash-live-001` (deprecated) / `gemini-live-2.5-flash` (Vertex AI, private GA) | Hybrid: native audio input + TTS output, TEXT modality support, explicit language control |

### Key Live API Features
- **Voice Activity Detection (VAD)**: Auto-detects speech start/end, manages turn-taking
- **Barge-in / Interruption**: Users interrupt mid-response, agent stops and addresses new input
- **Audio Transcription**: Built-in input/output transcription, auto-enabled for multi-agent
- **Session Resumption**: `SessionResumptionConfig()` — reconnect after disconnection
- **Proactive Audio**: Agent initiates responses without explicit prompts (native audio only)
- **Affective Dialog**: Agent detects emotional cues in voice tone, adapts response style (native audio only)

### Voice Configuration
```python
from google.adk.models.google_llm import Gemini
from google.genai import types

custom_llm = Gemini(
    model="gemini-2.5-flash-native-audio-preview-12-2025",
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
        ),
        language_code="en-US"
    )
)

agent = Agent(name="assistant", model=custom_llm, tools=[...], instruction="...")
```

**Available Voices (Half-cascade)**: Puck, Charon, Kore, Fenrir, Aoede, Leda, Orus, Zephyr  
**Native Audio Models**: All above + extended TTS voice library

### Per-Agent Voice in Multi-Agent
```python
# Each sub-agent gets its own voice
customer_service = Agent(name="service", model=Gemini(model=MODEL, speech_config=SpeechConfig(voice_name="Aoede")))
tech_support = Agent(name="tech", model=Gemini(model=MODEL, speech_config=SpeechConfig(voice_name="Charon")))
root = Agent(name="root", sub_agents=[customer_service, tech_support])
```
- Multi-agent auto-enables transcription for agent transfer context

### ADK Bidi Streaming Application Lifecycle
```
Phase 1: App Init (once) → Agent, SessionService, Runner
Phase 2: Session Init (per connection) → get/create Session, RunConfig, LiveRequestQueue
Phase 3: Bidi-streaming → upstream (WebSocket→Queue) + downstream (run_live()→WebSocket) via asyncio.gather()
Phase 4: Terminate → LiveRequestQueue.close()
```

### Complete FastAPI Pattern (from bidi-demo)
```python
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from google.adk.runners import Runner
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.adk.sessions import InMemorySessionService
from google.genai import types

app = FastAPI()
session_service = InMemorySessionService()
runner = Runner(app_name="agent-hub", agent=agent, session_service=session_service)

@app.websocket("/ws/{user_id}/{session_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, session_id: str):
    await websocket.accept()
    
    run_config = RunConfig(
        streaming_mode=StreamingMode.BIDI,
        response_modalities=["AUDIO"],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        session_resumption=types.SessionResumptionConfig(),
        proactivity=types.ProactivityConfig(proactive_audio=True),
        enable_affective_dialog=True,
    )
    
    session = await session_service.get_session(app_name="agent-hub", user_id=user_id, session_id=session_id)
    if not session:
        await session_service.create_session(app_name="agent-hub", user_id=user_id, session_id=session_id)
    
    live_request_queue = LiveRequestQueue()
    
    async def upstream():
        try:
            while True:
                data = await websocket.receive_bytes()  # Binary PCM audio
                audio_blob = types.Blob(mime_type="audio/pcm;rate=16000", data=data)
                live_request_queue.send_realtime(audio_blob)
        except WebSocketDisconnect:
            pass
    
    async def downstream():
        async for event in runner.run_live(
            user_id=user_id, session_id=session_id,
            live_request_queue=live_request_queue, run_config=run_config
        ):
            await websocket.send_text(event.model_dump_json(exclude_none=True, by_alias=True))
    
    try:
        await asyncio.gather(upstream(), downstream(), return_exceptions=True)
    finally:
        live_request_queue.close()
```

### Client-Side Audio (Browser)
- **Capture**: AudioContext(sampleRate: 16000) → AudioWorklet → Float32→PCM16 → binary WebSocket
- **Playback**: AudioContext(sampleRate: 24000) → AudioWorklet ring buffer (180s) → Int16→Float32 → speakers
- **Camera**: getUserMedia(video: 768×768) → canvas.drawImage → toBlob('image/jpeg', 0.85) → base64 → JSON WebSocket
- **Transcription**: `event.inputTranscription` / `event.outputTranscription` with `.text` and `.finished` fields

### Interleaved Output — Image Generation in Live Sessions

#### What Is Interleaved Output?
Gemini's Nano Banana image models (`gemini-3.1-flash-image-preview`, `gemini-3-pro-image-preview`, `gemini-2.5-flash-image`) support **interleaved output** — a single response that alternates between text parts and image parts naturally. Setting `response_modalities=['TEXT', 'IMAGE']` returns rich mixed content.

**Supported modes:**
| Mode | Input | Output | Example |
|---|---|---|---|
| Text → Text + Images | Text only | Alternating text + inline images | "Generate an illustrated recipe for paella" |
| Text + Images → Text + Images | Text + image(s) | Alternating text + inline images | *(with room photo)* "What other color sofas would work?" |

**Example response structure (macaron baking guide):**
```json
[
  {"text": "### Step 1: Piping the Batter\nThe first step..."},
  {"inline_data": {"data": "<image_data>", "mime_type": "image/png"}},
  {"text": "### Step 2: Baking and Developing Feet\nOnce piped..."},
  {"inline_data": {"data": "<image_data>", "mime_type": "image/png"}},
  {"text": "### Step 3: Assembling the Macaron\nThe final step..."},
  {"inline_data": {"data": "<image_data>", "mime_type": "image/png"}}
]
```

#### Critical Limitation — Live API Is Single-Modality Output

> **"You can only set one response modality (TEXT or AUDIO) per session."** — Gemini Live API docs

The Live API cannot return interleaved text+image. It's either TEXT or AUDIO per session. This means **Nano Banana interleaved output is not available inside `run_live()` sessions directly**.

#### Architecture Solution — Image Generation as a Tool, Not a Sub-Agent

Since `run_live()` locks all agents in the tree to the same Live API session & model, a sub-agent **cannot** independently call Nano Banana. Instead, image generation works as a **tool** (a Python function the live agent calls):

```
Live Agent (voice, run_live())
│
├── speaks to user via audio
├── calls tools when needed:
│   ├── generate_image_tool()     ← calls Nano Banana API separately
│   ├── search_tool()
│   ├── code_exec_tool()
│   └── ...
│
│   generate_image_tool() internally:
│     1. Calls client.models.generate_content(model="gemini-3.1-flash-image-preview")
│     2. Gets back interleaved text + image parts
│     3. Saves image to Firestore/GCS (session media)
│     4. Pushes image to dashboard via WebSocket
│     5. Returns TEXT ONLY back to the live agent
│        → "Generated a chart showing 15% growth. Image sent to dashboard."
│     6. Live agent SPEAKS this text description to the user
```

**Why tool, not sub-agent:**
| Approach | Works? | Reason |
|---|---|---|
| Sub-agent in same `run_live()` tree | **No** | Sub-agents share the Live API session — can't switch to Nano Banana mid-stream |
| Separate agent microservice | Yes but complex | Requires inter-service comms, adds latency |
| **Tool that calls Nano Banana API** | **Best** | Tool is a Python function — can call any API/model independently, returns text to live agent |

#### Implementation

```python
async def generate_image(prompt: str, session_id: str) -> str:
    """Generate an image based on the prompt. Image is sent to user's dashboard."""
    client = genai.Client()
    
    response = client.models.generate_content(
        model="gemini-3.1-flash-image-preview",
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_modalities=['TEXT', 'IMAGE'],  # interleaved output!
        )
    )
    
    text_parts = []
    image_count = 0
    
    for part in response.parts:
        if part.text:
            text_parts.append(part.text)
        elif part.inline_data:
            image_count += 1
            # Save to session storage
            await save_image_to_session(session_id, part.inline_data.data, part.inline_data.mime_type)
            # Push to dashboard via WebSocket
            await push_to_dashboard(session_id, {
                "type": "image",
                "data": base64.b64encode(part.inline_data.data).decode(),
                "mime_type": part.inline_data.mime_type,
                "description": prompt
            })
    
    summary = "\n".join(text_parts) if text_parts else f"Generated {image_count} image(s) for: {prompt}"
    return f"{summary}\n\nThe image has been sent to your dashboard."

# Register as tool on the live agent
root_agent = Agent(
    name="hub",
    model="gemini-2.5-flash-native-audio-preview-12-2025",
    instruction="When the user asks for visual content, use generate_image tool. "
                "Tell the user to check their dashboard for the image.",
    tools=[generate_image, ...]
)
```

#### User Experience Flow

```
User (voice): "Show me a chart of Tesla's stock performance this year"

1. Live agent understands intent → calls generate_image(prompt="Tesla stock chart 2026 YTD")
2. Tool calls Nano Banana → gets chart image + text explanation (interleaved)
3. Tool pushes image to dashboard via WebSocket → user sees it appear on screen
4. Tool saves image to session DB (Firestore/GCS) → persists in conversation history
5. Tool returns text → live agent SPEAKS:
   "I've generated a Tesla stock chart. It shows 15% growth year-to-date
    with a dip in February. Check your dashboard for the visual."
```

#### Rich Interleaved Content on Dashboard

For complex requests, Nano Banana returns **multi-step illustrated content** that renders beautifully on the dashboard:

```
User: "Explain photosynthesis with illustrations"

Tool calls Nano Banana → gets back:
  - Text: "Step 1: Light absorption by chlorophyll..."
  - Image: [diagram of chloroplast]
  - Text: "Step 2: Water splitting (photolysis)..."
  - Image: [diagram of H2O molecule splitting]
  - Text: "Step 3: Sugar synthesis (Calvin cycle)..."
  - Image: [diagram of glucose formation]

Dashboard: Renders full illustrated guide (text + images interleaved)
Live Agent speaks: "I've created an illustrated guide on photosynthesis with
                    3 diagrams. Check your dashboard for the visuals."
Session DB: Stores all images + text for history replay
```

#### Key Advantage

This dual-channel approach (voice + visual) is a **strong differentiator**:
- Agent Hub speaks explanations via Live API while simultaneously generating rich visual content on the dashboard
- It showcases Nano Banana (interleaved output) + Live API (native audio) + multi-client architecture in one experience
- The session DB stores images alongside conversation history, so users can review generated content later

---

### Client-Side SDK Research — `gemini-live-sdk` (npm)

> **Package**: `gemini-live-sdk` v1.1.3 · MIT · 365 KB unpacked · 0 weekly downloads  
> **Repo**: `github.com/omanandswami2005/gemini-live-sdk`  
> **Published**: ~9 months ago (June 2025) · 5 versions · 1 contributor  
> **Verdict**: **Extract audio modules only** — transport layer (socket.io) incompatible with our custom Python/FastAPI backend

#### Architecture Overview

```
gemini-live-sdk/
├── core/                 # GeminiLiveClient — Main class (socket.io based)
│   ├── gemini-client.js  # EventEmitter3 + socket.io-client transport
│   └── types.js          # JSDoc type defs
├── audio/
│   ├── audio-recorder.js # Mic → AudioWorklet → PCM16 → base64 (16kHz)
│   ├── audio-streamer.js # base64 → PCM16 → Float32 → AudioBufferQueue (24kHz)
│   └── worklets/
│       └── audio-recording-worklet.js  # AudioWorkletProcessor (Int16 buffer)
├── media/
│   └── media-handler.js  # Webcam + screen capture → base64 JPEG frames
├── react/
│   ├── hooks/use-gemini-live.js        # React hook wrapping GeminiLiveClient
│   └── components/GeminiLiveProvider.jsx # Context provider
├── server/
│   └── gemini-server.js  # Node.js WebSocket server (NOT relevant for us)
└── utils/
    ├── audio-utils.js    # createAudioContext(), base64↔ArrayBuffer
    ├── volume-meter.js   # AnalyserNode-based volume visualization
    └── worklet-registry.js # Blob URL worklet loader
```

#### Transport Layer — socket.io (❌ Incompatible) → Raw WebSocket (✅ Chosen)

The SDK uses **socket.io-client** (NOT raw WebSocket). Socket.io has a custom protocol layer (packet framing, event namespacing, heartbeat) that raw WS servers don't understand.

```javascript
// SDK's transport — socket.io
this.socket = io(this.config.endpoint, {
  auth: { token: this.config.token },
  transports: ['websocket'],
  reconnection: true,
  reconnectionAttempts: this.config.reconnectAttempts,
  reconnectionDelay: this.config.reconnectDelay,
  timeout: 20000
});

// Our backend — raw WebSocket (FINAL DECISION)
const ws = new WebSocket(`wss://host/ws/live/${sessionId}`);
```

**Conclusion**: Cannot use `GeminiLiveClient` directly. Must write our own WebSocket transport layer.

> **DECISION: Raw WebSocket over Socket.IO** — Evaluated both in depth. Raw WS wins for Omni because:
> 1. **Zero abstraction leaks** — binary audio frames visible directly in DevTools, no packet framing to decode
> 2. **ADK sample compatibility** — all Google ADK bidi-demos/Live API samples use raw WS; copy-paste directly
> 3. **5 diverse clients** — raw WS is natively supported on ESP32, Chrome extension service worker, Python `websockets`, browser `WebSocket` API — no per-client library compatibility issues
> 4. **FastAPI native** — `@app.websocket()` built-in, no separate ASGI app mount needed
> 5. **Binary audio is first-class** — WS protocol natively distinguishes binary frames (audio) from text frames (JSON)
>
> **What we build ourselves (Day 1 infra, ~100 lines server + ~60 lines per client):**
> - `ConnectionManager` class: user device registry, room broadcast, auth on first message, disconnect cleanup
> - `useWebSocket` hook: exponential backoff reconnection (delays: 1s, 2s, 4s, 8s, 16s)
> - Cross-client event routing via message `type` field dispatch

#### Audio Recorder (✅ Reusable Pattern)

The `AudioRecorder` class uses a clean AudioWorklet pattern worth replicating:

```
Browser Mic → getUserMedia() → MediaStreamSource → AudioWorkletNode → PCM16 chunks → base64 → WebSocket
```

**Key implementation details**:
- **Sample rate**: 16kHz (matches Gemini Live API input requirement)
- **Buffer size**: 2048 Int16 samples (~128ms per chunk at 16kHz)
- **Processing**: Float32 → Int16 conversion in AudioWorklet (off-main-thread)
- **Output**: base64-encoded PCM16 chunks emitted via `data` event
- **Mute**: Implemented by disconnecting source from worklet node (no audio data sent)

```javascript
// AudioWorklet code (runs on audio thread, not main thread)
class AudioProcessingWorklet extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new Int16Array(2048);
    this.bufferWriteIndex = 0;
  }
  process(inputs) {
    const channel0 = inputs[0][0];
    for (let i = 0; i < channel0.length; i++) {
      this.buffer[this.bufferWriteIndex++] = Math.max(-32768, Math.min(32767, channel0[i] * 32768));
      if (this.bufferWriteIndex >= this.buffer.length) {
        this.port.postMessage({ event: "chunk", data: { int16arrayBuffer: this.buffer.slice(0, this.bufferWriteIndex).buffer } });
        this.bufferWriteIndex = 0;
      }
    }
    return true;
  }
}
```

**Worklet loading** uses a clever Blob URL approach to avoid separate file hosting:
```javascript
const blob = new Blob([workletSourceCode], { type: 'application/javascript' });
const workletUrl = URL.createObjectURL(blob);
await audioContext.audioWorklet.addModule(workletUrl);
```

#### Audio Streamer / Playback (✅ Reusable Pattern)

Queue-based playback system for streaming PCM16 audio from Gemini:

```
WebSocket → base64 → ArrayBuffer → PCM16 → Float32 → AudioBuffer → BufferSource → GainNode → Speakers
```

**Key implementation details**:
- **Sample rate**: 24kHz (Gemini Live API output)
- **Queue**: `audioQueue[]` of AudioBuffers — ensures gapless playback
- **Stall detection**: 1-second timeout restarts playback if queue has data but nothing is playing
- **Barge-in**: `stop()` clears queue + ramps gain to 0 in 100ms (smooth cutoff)
- **Resume**: Handles `AudioContext.state === 'suspended'` (browser autoplay policy)
- **GainNode**: Used for volume control + AI volume meter visualization

```javascript
// PCM16 → Float32 conversion
convertPCM16ToFloat32(chunk) {
  const float32 = new Float32Array(chunk.length / 2);
  const view = new DataView(chunk.buffer);
  for (let i = 0; i < chunk.length / 2; i++) {
    float32[i] = view.getInt16(i * 2, true) / 32768; // little-endian
  }
  return float32;
}
```

#### Message Protocol (Valuable Reference)

The SDK reveals the Gemini Live API's actual message format:

**Client → Server (audio)**:
```json
{
  "realtime_input": {
    "media_chunks": [{ "mime_type": "audio/pcm", "data": "<base64_pcm16>" }]
  }
}
```

**Client → Server (text)**:
```json
{
  "client_content": {
    "turns": [{ "role": "user", "parts": [{ "text": "Hello" }] }],
    "turn_complete": true
  }
}
```

**Client → Server (video frame)**:
```json
{
  "realtime_input": {
    "media_chunks": [{ "mime_type": "image/jpeg", "data": "<base64_jpeg>" }]
  }
}
```

**Client → Server (tool response)**:
```json
{
  "tool_response": {
    "function_responses": [{ "name": "fn_name", "response": { "result": "..." } }]
  }
}
```

**Server → Client (audio)**:
```json
{
  "serverContent": {
    "modelTurn": {
      "parts": [{ "inlineData": { "data": "<base64_pcm16_24khz>" } }]
    }
  }
}
```

**Server → Client (turn complete / barge-in)**:
```json
{ "serverContent": { "turnComplete": true } }
{ "serverContent": { "interrupted": true } }
```

**Server → Client (transcription)**:
```json
{ "serverContent": { "outputTranscription": { "text": "AI said..." } } }
{ "serverContent": { "inputTranscription": { "text": "User said..." } } }
```

#### React Hook Pattern (✅ Good Reference, Need Custom Version)

The `useGeminiLive` hook pattern is well-structured but tightly coupled to `GeminiLiveClient` (socket.io):

```javascript
// What we'll adapt from the SDK's React pattern:
const {
  connectionState,    // { status: 'disconnected'|'connected'|'error' }
  isRecording,        // boolean
  isMuted,            // boolean
  error,              // string | null
  transcriptions,     // [{ type: 'ai'|'user', text, timestamp }]
  webcamActive,       // boolean
  screenActive,       // boolean
  // Methods
  startRecording, stopRecording, toggleMute,
  sendTextMessage, sendToolResponse,
  toggleWebcam, toggleScreenShare,
  createUserVolumeMeter, createAIVolumeMeter,
} = useGeminiLive(config);
```

**Our custom hook will differ**:
- Raw `WebSocket` transport instead of socket.io
- Firebase Auth token in first WS message (not socket.io `auth` handshake)
- GenUI event handling (SDK has no concept of this)
- Persona switching via control messages
- Cross-client events from backend
- Zustand store integration instead of local useState

#### What to Extract vs Build Custom

| Module | Action | Reason |
|---|---|---|
| `AudioRecorder` | **Extract & adapt** | Solid AudioWorklet pattern, just change output from socket.io emit to raw WS binary |
| `AudioStreamer` | **Extract & adapt** | Good queue + stall detection. Change input from socket.io event to raw WS `onmessage` |
| `AudioWorklet code` | **Copy directly** | Pure audio processing, no transport dependency |
| `audio-utils.js` | **Copy directly** | `createAudioContext()`, `base64ToArrayBuffer()`, `arrayBufferToBase64()` — pure utility |
| `worklet-registry.js` | **Copy directly** | Blob URL worklet loader — 5 lines, elegant |
| `volume-meter.js` | **Extract & adapt** | AnalyserNode visualization — useful for Voice Orb |
| `media-handler.js` | **Extract & adapt** | Webcam + screen capture to base64 JPEG frames |
| `GeminiLiveClient` | **❌ Rewrite** | socket.io transport incompatible with our FastAPI raw WS |
| `useGeminiLive` hook | **❌ Rewrite** | Tightly coupled to GeminiLiveClient, need Zustand + raw WS |
| `GeminiLiveProvider` | **❌ Skip** | We don't need a context provider; Zustand handles global state |
| `GeminiLiveServer` | **❌ Skip** | Completely replaced by Python/FastAPI + ADK backend |

#### Key Differences: SDK Server vs Our Backend

| Aspect | SDK's Node.js Server | Our Python/FastAPI Backend |
|---|---|---|
| Transport | socket.io (Node.js) | Raw WebSocket (FastAPI) |
| AI Framework | Direct Gemini API calls | Google ADK (agents, tools, sessions) |
| Multi-agent | None | Root → Persona sub-agents, TaskArchitect |
| Tool execution | Server-side function declarations | ADK tools + MCP + E2B sandbox |
| Auth | JWT middleware on socket.io | Firebase Auth token verification |
| Events | socket.io event names | JSON message types over raw WS |
| Transcription | Google's built-in transcription events | ADK's transcription via `run_live()` |
| Model | `gemini-2.0-flash-exp` (old) | `gemini-2.5-flash-native-audio-preview` |

#### Implementation Plan for Dashboard Audio

Based on SDK patterns, our dashboard audio pipeline will be:

```
┌─ Recording Pipeline ─────────────────────────────────────────┐
│ Browser Mic                                                   │
│   → getUserMedia({ audio: true })                             │
│   → AudioContext (16kHz)                                      │
│   → MediaStreamSource                                         │
│   → AudioWorkletNode (Float32 → Int16, 2048-sample buffer)   │
│   → base64-encode PCM16 chunks                                │
│   → WebSocket.send(JSON { type: 'audio', data: base64 })     │
└───────────────────────────────────────────────────────────────┘

┌─ Playback Pipeline ──────────────────────────────────────────┐
│ WebSocket.onmessage                                           │
│   → Parse JSON { type: 'response', audio: base64 }           │
│   → base64 → ArrayBuffer → PCM16 → Float32                   │
│   → AudioBuffer (24kHz)                                       │
│   → audioQueue[] (FIFO buffer)                                │
│   → BufferSource.start() → GainNode → speakers               │
│   → Stall detection (1s timeout, auto-restart)                │
│   → Barge-in: stop() → clear queue → gain ramp 0             │
└───────────────────────────────────────────────────────────────┘

┌─ Video/Screen Pipeline ──────────────────────────────────────┐
│ getUserMedia / getDisplayMedia                                │
│   → canvas.drawImage(video)                                   │
│   → canvas.toDataURL('image/jpeg', 0.8)                       │
│   → WebSocket.send(JSON { type: 'image', data: base64 })     │
│   → Frame rate: ~1 FPS (configurable)                         │
└───────────────────────────────────────────────────────────────┘
```

#### Binary vs JSON Audio Transport Decision

The SDK sends audio as **base64 inside JSON** (via socket.io events). For our raw WebSocket implementation, we have two options:

| Approach | Pros | Cons |
|---|---|---|
| **Binary frames** (raw PCM) | ~33% smaller, no encode/decode overhead, lower latency | Can't mix with JSON in same frame, need frame-type detection |
| **Base64 in JSON** (SDK approach) | Self-describing messages, easy to parse, works with JSON protocol | 33% size overhead, encode/decode CPU cost |

**Decision**: Use **binary WebSocket frames for audio** (both directions) and **JSON text frames for everything else** (text, control, GenUI, transcription). The browser WebSocket API natively distinguishes binary vs text frames via `event.data instanceof Blob`.

```javascript
// Our approach — mixed binary + JSON
ws.onmessage = (event) => {
  if (event.data instanceof Blob) {
    // Binary frame → PCM audio → playback pipeline
    playbackQueue.enqueue(event.data);
  } else {
    // Text frame → JSON message
    const msg = JSON.parse(event.data);
    handleMessage(msg);
  }
};

// Sending audio — binary for performance
ws.send(pcmInt16ArrayBuffer);  // Raw binary, no base64

// Sending text/control — JSON
ws.send(JSON.stringify({ type: 'text', content: 'Hello' }));
```

This gives us the best of both worlds: low-latency audio AND structured JSON for control messages.

---

## 4. E2B Sandbox Research

### What is E2B?
**Open-source secure Linux VMs** (Firecracker microVMs) for AI agents. <200ms cold start, up to 24h sessions.

### Key Features
| Feature | Detail |
|---|---|
| **Cold Start** | <200ms |
| **Max Session** | 24h (Pro) / 1h (Hobby) |
| **Concurrency** | 20 (Hobby) / 100 (Pro) |
| **SDK** | Python (`from e2b import Sandbox`) + JavaScript |
| **Capabilities** | Code execution, terminal commands, file operations, internet access, browser use |
| **MCP Gateway** | Built-in MCP server with 100+ pre-configured MCPs |
| **Computer Use** | Desktop Sandbox for visual UI interaction |
| **Users** | Perplexity, Hugging Face, Manus, Groq |

### Pricing
| vCPUs | Cost |
|---|---|
| 1 | $0.000014/s |
| 2 (default) | $0.000028/s |
| 4 | $0.000056/s |
| 8 | $0.000112/s |

- **Hobby tier**: Free + $100 credits, 1h max session, 20 concurrent
- **Pro tier**: $150/mo + usage, 24h max session, 100 concurrent

### Core API
```python
from e2b_code_interpreter import Sandbox

# Create sandbox
sandbox = Sandbox()

# Execute Python
execution = sandbox.run_code('print("hello")')
print(execution.logs)

# Run terminal command
result = sandbox.commands.run("ls -la")

# File operations
sandbox.files.write("/tmp/test.txt", "content")
content = sandbox.files.read("/tmp/test.txt")
files = sandbox.files.list("/")

# Lifecycle
await sandbox.set_timeout(30_000)  # Extend timeout
info = await sandbox.get_info()     # Get sandbox info
await sandbox.kill()                # Shutdown
```

### E2B Built-in MCP Gateway (100+ MCPs)
```javascript
// Create sandbox with MCP servers auto-started
const sandbox = await Sandbox.create({
    mcp: {
        notion: { internalIntegrationToken: "..." },
        context7: {},  // No config needed
        playwright: {},
        braveSearch: { apiKey: "..." },
        codeInterpreter: {},
        github: { personalAccessToken: "..." },
        mongodb: { connectionString: "..." },
        wolframAlpha: { appId: "..." },
        wikipedia: {},
        googleCalendar: { credentials: "..." },
    }
});

const mcpUrl = sandbox.getMcpUrl();
const mcpToken = sandbox.getMcpToken();
```

**Notable built-in MCPs**: notion, context7, github (archived + chat), mongodb, neo4jMemory, playwright, braveSearch, cloudRun, codeInterpreter, nodeCodeSandbox, airtable, atlassian, obsidian, wolframAlpha, wikipedia, googleCalendar, slack, linear, stripe, twilio, sendGrid, and 80+ more.

### Integration with ADK
```python
# 1. Create E2B sandbox with MCP gateway
sandbox = Sandbox.create(mcp={"braveSearch": {"apiKey": "..."}})

# 2. Get MCP endpoint
mcp_url = sandbox.get_mcp_url()
mcp_token = sandbox.get_mcp_token()

# 3. Connect ADK McpToolset to E2B's MCP gateway
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

e2b_mcp = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=mcp_url,
        headers={"Authorization": f"Bearer {mcp_token}"}
    )
)

agent = Agent(name="coder", tools=[e2b_mcp], instruction="...")
```

---

## 5. MCP Ecosystem Research

### What is MCP?
**Model Context Protocol** — open standard (by Anthropic) for connecting AI models to external tools and data sources. ADK has native support via `McpToolset`.

### Connection Types in ADK
| Type | Use Case | Class |
|---|---|---|
| **Stdio** | Local process (CLI tools) | `StdioConnectionParams(command, args)` |
| **SSE** | Remote server (Server-Sent Events) | `SseConnectionParams(url)` |
| **StreamableHTTP** | Remote server (HTTP streams) | `StreamableHTTPConnectionParams(url, headers)` |

### MCP Architecture in Our Project
```
User Dashboard → Enable/Disable MCPs → Firestore Config
                                            ↓
Session Start → MCPManager reads config → Build McpToolset[] → Inject into Agent tools
                                            ↓
Agent uses tools → McpToolset routes to MCP server → Result back to agent
```

---

## 6. WebMCP & Chrome AI Research

> **Status**: Early Preview Program (Feb 10, 2026) — bleeding-edge Chrome APIs that can be a **massive differentiator**

### 6.1 What is WebMCP?

WebMCP is Chrome's upcoming browser-native API that makes websites **"agent-ready"** — enabling AI agents to perform actions on any website with increased speed, reliability, and precision compared to raw DOM scraping/actuation.

**Source**: [developer.chrome.com/blog/webmcp-epp](https://developer.chrome.com/blog/webmcp-epp) — by André Cipriani Bandarra (Google), Feb 10, 2026

#### Two New APIs

| API | Type | How It Works | Use Case |
|---|---|---|---|
| **Declarative API** | HTML forms | Standard actions exposed via annotated HTML forms — browsers/agents discover them automatically | Simple structured actions: submit ticket, search products, fill checkout |
| **Imperative API** | JavaScript | Complex/dynamic interactions registered via JS — enables multi-step workflows | Dynamic filtering, SPA-style interactions, conditional flows |

#### Key Quotes from the Announcement
- *"WebMCP aims to provide a standard way for exposing structured tools, ensuring AI agents can perform actions on your site with increased speed, reliability, and precision"*
- *"These APIs serve as a bridge, making your website 'agent-ready' and enabling more reliable and performant agent workflows compared to raw DOM actuation"*

#### Example Use Cases (from Google)
- **Customer Support**: Agent creates support tickets via Declarative API form annotations
- **E-commerce**: Agent searches, filters, and completes checkout via Imperative API
- **Travel Booking**: Agent searches and books flights through structured tool definitions

### 6.2 Chrome DevTools MCP Server

**Package**: `chrome-devtools-mcp` (npm) — **v0.14.0** (latest as of Feb 2026)  
**Repo**: [ChromeDevTools/chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp)

This is a **production-grade MCP server** that wraps Chrome DevTools Protocol, giving AI agents full browser control.

#### 29+ Tools Across 7 Categories

| Category | Tools | What They Do |
|---|---|---|
| **Input Automation** (9) | `click`, `drag`, `fill`, `fill_form`, `handle_dialog`, `hover`, `press_key`, `type_text`, `upload_file` | Full user interaction simulation |
| **Navigation** (6) | `close_page`, `list_pages`, `navigate_page`, `new_page`, `select_page`, `wait_for` | Page management |
| **Emulation** (2) | `emulate` (geolocation, network, CPU, user agent), `resize_page` | Device/network simulation |
| **Performance** (4) | `performance_analyze_insight`, `performance_start_trace`, `performance_stop_trace`, `take_memory_snapshot` | Performance profiling |
| **Network** (2) | `get_network_request`, `list_network_requests` | Network monitoring |
| **Debugging** (6) | `evaluate_script`, `get_console_message`, `lighthouse_audit`, `list_console_messages`, `take_screenshot`, `take_snapshot` | Page debugging & screenshots |
| **Extensions** (4) | `install_extension`, `uninstall_extension`, `list_extensions`, `reload_extension` | Extension management |

#### Key Features
- `--auto-connect` flag: auto-discover and attach to running Chrome instance
- `--slim` mode: Only 3 tools (navigate, evaluate, screenshot) — lightweight for simple use
- `--experimental-vision`: Computer vision support for visual page understanding
- Preserved logs across navigations
- Compatible with: Gemini CLI, Claude, Cursor, Copilot, Windsurf, Factory CLI

### 6.3 Prompt API Function Calling (On-Device AI)

**Source**: Chromium Intent to Prototype (blink-dev, Aug 7, 2025) — by Sushanth Rajasankar (Microsoft) + Google engineers

Adds **function calling / tool use** to Chrome's on-device **Prompt API** (powered by Gemini Nano running locally in the browser).

#### Two Complementary APIs ("Two sides of the same coin")

| API | Direction | Who Controls | Purpose |
|---|---|---|---|
| **Prompt API Function Calling** | Inward-facing | Web page is orchestrator | Page enhances its own features — page defines tools, on-device LLM invokes them |
| **Script Tools API** | Outward-facing | External agent controls page | External agents (browser-level, OS-level) discover and invoke capabilities exposed by web pages |

#### Why Not Just MCP Directly?
Google/Microsoft considered exposing MCP directly to the web but chose a higher-level native API instead:
- *"We believe a higher-level, native API is better suited for the web platform"*
- Approach is **"isomorphic with concepts in MCP but abstracts away low-level protocol details"**
- Advantages: Direct DOM access, developer ergonomics, durability (not coupled to evolving MCP spec), **offline/privacy** (on-device Gemini Nano, no network needed)

### 6.4 How to Leverage WebMCP

#### Strategy 1: Make the Web Dashboard "Agent-Ready" with WebMCP
```
Web Dashboard (React)
  ├─ Declarative API: Annotate dashboard forms (MCP config, persona settings)
  │   → External agents can configure the hub without DOM scraping
  ├─ Imperative API: Register complex actions via JS
  │   → "enable_mcp", "switch_persona", "start_session", "view_transcript"
  └─ Result: Our own dashboard becomes an MCP-compatible tool that OTHER agents can use
```
**Why this matters**: Instead of just USING MCPs, our project BECOMES an MCP server that any AI agent can interact with. This is a meta-level innovation.

#### Strategy 2: Chrome DevTools MCP as a Plugin
```
Plugin Store → "Chrome Browser Control" plugin
  → Uses chrome-devtools-mcp
  → Agent can: navigate websites, fill forms, take screenshots, run Lighthouse audits
  → Demo: "Hey agent, open the competitor's website and run a performance audit"
```

#### Strategy 3: On-Device AI via Prompt API in Chrome Extension Client
```
Chrome Extension Client (future client type)
  ├─ Uses Prompt API Function Calling with Gemini Nano
  ├─ Runs LOCALLY in browser — no server round-trip for simple tasks
  ├─ Defines Script Tools so the main Agent Hub server can invoke page actions
  └─ Hybrid architecture: Simple queries → on-device, Complex queries → server
```

#### Strategy 4: Demo Wow-Factor
- Show the dashboard's WebMCP Declarative API → an external Claude/Gemini agent can **control our own dashboard** via MCP
- Live demo: "Agent A uses chrome-devtools-mcp to scrape a website → pipes data to Agent B for analysis → results displayed on dashboard"
- Mention: *"Our architecture is WebMCP-ready — when Chrome ships this API in stable, our hub is automatically agent-accessible"*

#### Impact
| Criterion | WebMCP Boost |
|---|---|
| **Innovation** | Using bleeding-edge Chrome APIs |
| **Technical Depth** | Multi-layer: WebMCP Declarative + Imperative + DevTools MCP + Prompt API |
| **Future-Proofing** | Architecture designed for the next generation of web-AI interaction |
| **Demo Polish** | Chrome DevTools MCP = visual, impressive browser automation |

### 6.5 Chrome Extension — Voice-Activated Tasks

With the Chrome extension client connected to Agent Hub, users can control their browser entirely by voice. The extension captures voice via the browser microphone, streams it to the Agent Hub backend, and the agent executes browser actions via Chrome DevTools MCP or extension APIs.

#### Tab & Navigation
| Voice Command | What Happens |
|---|---|
| "Open a new tab" | Opens blank tab |
| "Go to Gmail" | Navigates to gmail.com |
| "Close this tab" | Closes active tab |
| "Switch to tab 3" | Activates the 3rd tab |
| "Go back" / "Go forward" | Browser nav history |
| "Bookmark this page" | Adds to bookmarks |
| "Open my bookmarks for AI research" | Opens bookmark folder |
| "Reopen closed tab" | Restores last closed tab |

#### Search & Browse
| Voice Command | What Happens |
|---|---|
| "Search for latest Gemini API updates" | Opens Google search |
| "Find on this page: pricing" | Ctrl+F and searches for "pricing" |
| "Summarize this page" | Agent reads page content (via DevTools MCP `evaluate_script` or DOM extraction) and returns summary |
| "Read this article to me" | Agent extracts article text, speaks it via Live API audio |
| "What is this page about?" | Agent screenshots page → Gemini Vision analysis |
| "Save this page as PDF" | Triggers print-to-PDF |

#### Email (Gmail)
| Voice Command | What Happens |
|---|---|
| "Compose email to John about the meeting" | Opens Gmail compose, fills recipient + subject + draft body |
| "Read my latest email" | Navigates to inbox, extracts top email, reads aloud |
| "Reply saying I'll be there at 3pm" | Opens reply, types response |
| "Archive this email" | Clicks archive button |
| "Search emails from Sarah last week" | Uses Gmail search bar |
| "Mark all as read" | Bulk action on inbox |

#### Calendar (Google Calendar)
| Voice Command | What Happens |
|---|---|
| "What's on my schedule today?" | Opens Google Calendar, reads events aloud |
| "Create a meeting with Alex at 3pm tomorrow" | Opens event creation form, fills details |
| "Reschedule my 2pm to 4pm" | Finds event, drags or edits time |
| "What's my next meeting?" | Reads the upcoming event |

#### Content Interaction
| Voice Command | What Happens |
|---|---|
| "Fill this form with my info" | Agent reads form fields, fills with stored user profile data |
| "Download this file" | Clicks download link |
| "Screenshot this page" | Uses DevTools MCP `take_screenshot` → saves/sends to dashboard |
| "Translate this page to Spanish" | Triggers Chrome translate or Google Translate |
| "Extract all links from this page" | DOM extraction → returns link list |
| "Copy the main content" | Extracts article body to clipboard |

#### Productivity
| Voice Command | What Happens |
|---|---|
| "Save this to Notion" | Extracts page content → sends to Notion MCP |
| "Create a task in Linear: review API docs" | Calls Linear MCP to create task |
| "Add to my reading list" | Saves URL to Notion/bookmarks/reading list |
| "Start a 25-minute focus timer" | Sets browser notification timer |
| "Take a note: remember to check pricing page" | Saves note to session DB |

#### Accessibility
| Voice Command | What Happens |
|---|---|
| "Zoom in" / "Zoom out" | Adjusts page zoom level |
| "Enable dark mode" | Toggles dark reader / prefers-color-scheme |
| "Read this aloud" | TTS of selected or page content |
| "Increase font size" | Adjusts minimum font via extension CSS injection |
| "High contrast mode" | Applies accessibility overlay |

#### Developer Tools
| Voice Command | What Happens |
|---|---|
| "Open DevTools" | Opens Chrome DevTools panel |
| "Run a Lighthouse audit" | Uses DevTools MCP `lighthouse_audit` → reports scores |
| "Show me network requests" | Uses DevTools MCP `list_network_requests` |
| "Clear cache and hard reload" | Cache clear + reload |
| "What JavaScript errors are on this page?" | Uses DevTools MCP `list_console_messages` filtered to errors |
| "Take a performance trace" | Uses DevTools MCP `performance_start_trace` / `performance_stop_trace` |

#### Agent Hub–Specific
| Voice Command | What Happens |
|---|---|
| "Switch to Coder persona" | Sends persona switch command to backend |
| "Enable Brave Search plugin" | Toggles MCP in user config |
| "Show my dashboard" | Opens Agent Hub web dashboard in new tab |
| "What clients are connected?" | Queries Client Registry, reads aloud |
| "Send this page summary to my phone" | Cross-client action → pushes to mobile client |
| "Ask Sage to explain this page" | Delegates to Researcher persona with page context |

#### Why Voice-Activated Browser Matters
- **Hands-free browsing** — ideal when multitasking, cooking, exercising
- **Accessibility** — enables users with motor impairments to fully control the browser
- **Speed** — voice commands can be faster than mouse+keyboard for routine actions
- **Cross-client synergy** — say a command on glasses → executes on browser; results appear on dashboard
- **Differentiator** — voice-controlled browser is visually impressive in demos

---

## 7. Trending MCPs & Skills

### High-Value MCPs (Recommended for Plugin Store)

| MCP | Category | Why Trending | Demo Value |
|---|---|---|---|
| **Brave Search** | Web Search | Privacy-focused, widely adopted in AI agents | "Search the web for..." — instant demo |
| **Playwright** | Browser Automation | Hot trend: AI agents interacting with websites | "Open this webpage and extract..." |
| **Context7** | Dev Documentation | Real-time library docs lookup | "Look up the React useState docs" |
| **GitHub** | Developer Tools | Universal developer tool | "Create an issue on my repo" |
| **Notion** | Productivity | Popular knowledge management | "Save this note to my Notion" |
| **MongoDB** | Database | Data persistence for agents | "Store this data, query it later" |
| **Google Calendar** | Scheduling | Practical daily use case | "What's on my calendar today?" |
| **Wolfram Alpha** | Computation | Math / science problem solving | "Calculate the integral of..." |
| **Wikipedia** | Knowledge | Instant knowledge lookup | "Tell me about quantum computing" |
| **Filesystem** | Local Files | Desktop client file management | "Read the file at ~/documents/report.pdf" |
| **Slack** | Communication | Team messaging integration | "Send a message to #general" |
| **Linear** | Project Management | Engineering team workflow | "Create a task in Linear" |

### Skills to Define (via ADK Skills spec / agentskills.io)

| Skill | Description | MCPs Used |
|---|---|---|
| **Code Review** | Analyzes code quality, suggests improvements, runs tests | E2B code interpreter |
| **Research Assistant** | Compiles findings from multiple sources | Brave Search + Wikipedia |
| **Meeting Prep** | Briefs user on upcoming meetings with context | Google Calendar + Notion |
| **Visual Analysis** | Processes camera input, describes scenes | Camera + Google Search |
| **Data Analyst** | Queries databases, generates charts | MongoDB + E2B (matplotlib) |

### Non-Developer, Professional-Use Trending MCPs & Skills

These are the MCPs and skills that bring **real value to professionals outside of software engineering** — doctors, lawyers, marketers, educators, finance people, content creators, operations managers, and more. This is a **massive differentiator**: most AI agent projects target developers only. Building an agent hub that serves everyday professionals = wider real-world impact.

#### Healthcare & Biomedical

| MCP / Skill | What It Does | Professional Who Uses It |
|---|---|---|
| **BioMCP** | Access PubMed, ClinicalTrials.gov, MyVariant.info for biomedical research | Doctors, Clinical Researchers, Pharma teams |
| **DGIdb** | Drug-gene interaction lookups, druggable genome info, pharmacogenomics | Pharmacists, Drug Discovery researchers |
| **FHIR** | Healthcare data interoperability standard access | Health IT professionals, Clinical data analysts |
| **Dicom** | Query/retrieve medical images, parse DICOM-encapsulated documents | Radiologists, Medical Imaging techs |
| **Open Targets** | Target-disease associations, drug discovery data | Biomedical researchers, Pharma |
| **FitBit / Oura Ring** | Personal health data — sleep, HR, activity | Fitness coaches, Wellness professionals |

#### Finance & Business

| MCP / Skill | What It Does | Professional Who Uses It |
|---|---|---|
| **Financial Datasets** | Stock market data — income statements, balance sheets, cash flow | Financial Analysts, Investors |
| **Nasdaq Data Link** | Extensive financial and economic datasets | Quant researchers, Economists |
| **FRED** | Federal Reserve economic data | Economists, Policy analysts |
| **QuantConnect** | Algorithmic trading — design, backtest, deploy strategies | Quant traders, Portfolio managers |
| **Morningstar** | Research, editorial data, investment datapoints | Investment advisors, Wealth managers |
| **Stripe / Razorpay / Mercado Pago** | Payment processing — invoicing, customer management | Business owners, Freelancers |
| **HubSpot** | CRM integration — contacts, companies, pipelines | Sales teams, Account managers |
| **Salesforce** | Full CRM interactions with Salesforce | Enterprise sales, CRM admins |
| **Ramp** | Corporate spend analysis & insights | Finance ops, CFOs |
| **Windsor** | Full-stack business data integration & analysis | Business analysts, Data-driven managers |

#### Legal & Compliance

| MCP / Skill | What It Does | Professional Who Uses It |
|---|---|---|
| **Brazilian Law** | Agent-driven research on Brazilian law via official sources | Lawyers (Brazil-focused), Compliance |
| **Congress.gov API** | Real-time US Congressional data, bills, committees | Policy analysts, Legal researchers |
| **Companies House MCP** | UK company registry lookups (KRS, filings) | Corporate lawyers, Due diligence |
| **Drata** | Real-time compliance intelligence into AI workflows | Compliance officers, GRC teams |
| **SEC EDGAR (USPTO)** | Patent & trademark data, financial filings | IP attorneys, Patent analysts |
| **mcp-sanctions** | Screen individuals/orgs against global sanctions lists (OFAC, UN) | AML/KYC teams, Compliance officers |

#### Marketing & Content Creation

| MCP / Skill | What It Does | Professional Who Uses It |
|---|---|---|
| **Metricool** | Social media analytics — performance metrics & scheduling across platforms | Social media managers, Marketers |
| **Facebook Ads / TikTok Ads / Amazon Ads** | Campaign management, performance analytics, audience targeting | Digital marketers, Media buyers |
| **SEO MCP (kwrds.ai)** | Keyword research, SERP analysis, backlinks (Ahrefs data) | SEO specialists, Content strategists |
| **KeywordsPeopleUse** | Find questions people ask online — content ideation | Content creators, SEO writers |
| **Plus AI / 2slides / Slidespeak** | Automated PowerPoint/Google Slides creation from prompts | Marketers, Sales, Consultants (anyone making decks) |
| **Canva / Placid.app** | Template-based image and video creative generation | Graphic designers, Social media teams |
| **Substack/Medium** | Semantic search and analysis of published content | Writers, Newsletter operators |
| **LinkedIn MCP** | Write, edit, schedule LinkedIn posts | Personal branders, B2B marketers |
| **WaveSpeed / Fal AI** | AI image & video generation for campaigns | Creative directors, Content teams |
| **Open Strategy Partners** | Content editing codes, value map, positioning tools | Product marketing managers |

#### Education & Research

| MCP / Skill | What It Does | Professional Who Uses It |
|---|---|---|
| **Rember** | Spaced repetition flashcard creation from AI chats | Students, Teachers, Self-learners |
| **Anki** | Full Anki deck management — create, update, search cards | Students, Medical residents, Language learners |
| **Scholarly / OpenReview** | Search academic articles, fetch AI/ML conference papers | Researchers, PhD students |
| **bioRxiv** | Search and access bioRxiv preprints | Life science researchers |
| **OpenAlex** | ML-powered author disambiguation, researcher profiles | Academic researchers, Librarians |
| **Zettelkasten** | AI-powered knowledge management — atomic notes, link discovery | Researchers, Knowledge workers |
| **Wolfram Alpha** | Computational math & science problem solving | STEM educators, Students |
| **mcp-open-library** | Search books and author info via Open Library | Librarians, Readers, Educators |

#### Productivity & Office Automation

| MCP / Skill | What It Does | Professional Who Uses It |
|---|---|---|
| **Microsoft 365 (Lokka)** | Full M365 — Teams, SharePoint, Exchange, OneDrive, Entra, Intune | Enterprise workers (everyone) |
| **Google Workspace CLI** | Gmail, Calendar, Drive, Sheets from a single interface | Anyone using Google Workspace |
| **Notion** | Knowledge base — search, create, update pages/databases | PMs, Ops managers, Content teams |
| **Airtable** | Read/write access to Airtable databases | Ops managers, Marketers, Project leads |
| **Monday.com** | Board and item management | Project managers, Team leads |
| **Todoist / TickTick** | Task management and to-do list | Anyone managing tasks |
| **Slack** | Channel management and messaging | Team communication (universal) |
| **Obsidian Notes** | Note vault search, reading, writing, organizing | Knowledge workers, Writers |
| **Trello** | Board modification via prompts | Small team project management |
| **Excel File Manipulation** | Read/write Excel without installing MS Office | Data entry, Accountants, Ops |
| **Pandoc / Markdownify** | Document format conversion (PDF, DOCX, HTML, PPTX → Markdown) | Document-heavy professionals |
| **Office-Word / PowerPoint / Visio** | Create, read, manipulate MS Office documents | Enterprise workers, Consultants |
| **Inbox Zero** | AI email assistant for reaching inbox zero | Anyone drowning in email |

#### Travel & Lifestyle

| MCP / Skill | What It Does | Professional Who Uses It |
|---|---|---|
| **Airbnb** | Search listings, get details | Travel planners, Remote workers |
| **Tripadvisor** | Location data, reviews, photos | Travel agents, Hospitality |
| **Foursquare** | Place recommendations worldwide | Marketers (location data), Travelers |
| **TomTom** | Geospatial mapping, routing | Logistics teams, Delivery ops |
| **Google Maps** | Location services, directions, place details | Universal |
| **Duffel (Flights)** | Personalized flight recommendations | Travel agents, Corporate travel |
| **Amadeus** | Flight offers search — airlines, times, duration, pricing | Travel industry professionals |
| **Triplyfy** | Itinerary planning with interactive maps | Travel bloggers, Trip planners |

#### Real Estate & Property

| MCP / Skill | What It Does | Professional Who Uses It |
|---|---|---|
| **Zillow / Redfin (via web scraping)** | Property search, home valuations | Real estate agents, Home buyers |
| **FDIC BankFind** | US banking data — structured bank information | Mortgage brokers, Financial advisors |

#### IoT & Smart Home

| MCP / Skill | What It Does | Professional Who Uses It |
|---|---|---|
| **Home Assistant MCP** | Control 2000+ device brands (Hue, Tuya, Sonoff, etc.) via one API — `call_service`, `get_state`, `list_entities`, `fire_event` | Smart home users, Facility managers |
| **LG ThinQ Connect** | Control LG smart home devices & appliances | Smart home enthusiasts, Facility managers |
| **Tuya MCP** | Budget smart plugs, bulbs, sensors (Tuya/Smart Life ecosystem) via Tuya Cloud API | Budget IoT users |
| **MQTT MCP** | Generic MQTT client — any MQTT device (ESP32, Zigbee bridges, custom sensors) | DIY IoT builders, Industrial IoT |
| **Philips Hue MCP** | Hue lights, motion sensors, switches via Bridge API | Smart lighting users |
| **ESPHome MCP** | Custom ESP32/ESP8266 devices via native API — synergizes with our ESP32 glasses hardware | Makers, IoT hobbyists |
| **Apple Script** | Full Mac automation via LLM | Power users, IT admins |
| **Siri Shortcuts** | Interact with all Siri Shortcuts on macOS | Mac power users |
| **iMCP (iMessage, Reminders)** | Apple services integration | Anyone in Apple ecosystem |

> **ESP32 Glasses × IoT Synergy**: Glasses camera detects dark room → agent proactively offers to turn on lights via Home Assistant MCP → voice confirms → lights on. This showcases **vision + voice + IoT** in one loop — a strong "beyond text" demo moment.

#### Media & Creative

| MCP / Skill | What It Does | Professional Who Uses It |
|---|---|---|
| **Blender** | AI-assisted 3D modeling, scene creation | 3D artists, Game designers |
| **Unity / Godot** | Game engine integration | Game developers, XR creators |
| **Ableton Live** | Music creation with prompt-assisted production | Musicians, Producers |
| **Fish Audio** | Text-to-Speech with multiple voices, real-time playback | Podcasters, Voiceover artists |
| **Video Jungle** | Add, edit, search video content | Video editors, Content creators |
| **YouTube (yutu)** | Full YouTube automation — upload, manage | YouTubers, Social media managers |
| **ZapCap** | Video caption and B-roll generation | Video editors, Accessibility |
| **Figma** | AI-driven design operations, asset management | UI/UX designers |

### Why This Matters

1. **Wider Real-World Impact** — An agent hub that serves doctors, lawyers, marketers, and students — not just developers — demonstrates **massive applicability**
2. **Plugin Store Showcase** — The MCP plugin store becomes 10x more impressive with professional verticals: "Browse by: Healthcare | Finance | Marketing | Education | Productivity"
3. **Demo Storytelling** — Instead of just "here's a coding assistant," show: *"A financial analyst asks the glasses to check today's market data and FRED economic indicators while walking to a meeting..."*
4. **Persona × MCP Synergy** — Each agent persona (Doctor, Lawyer, Analyst, Educator) comes pre-configured with relevant MCPs. This is a novel UX pattern
5. **Non-developer use cases** — Showing professional use cases beyond dev tools = **unique angle**

### Recommended Demo Verticals (Pick 2-3 for Live Demo)

| Vertical | Persona | MCPs Used | Demo Script |
|---|---|---|---|
| **Finance Analyst** | "Nova" (analytical voice) | Financial Datasets + FRED + E2B (charts) | "Nova, show me Apple's latest quarterly revenue compared to last year. Plot it." |
| **Healthcare Researcher** | "Dr. Atlas" (calm, authoritative) | BioMCP + PubMed + DGIdb | "Dr. Atlas, what are the latest clinical trials for GLP-1 receptor agonists?" |
| **Marketing Manager** | "Spark" (energetic voice) | Metricool + SEO MCP + LinkedIn | "Spark, how's our Instagram engagement this week? Draft a LinkedIn post about it." |
| **Student / Researcher** | "Sage" (patient, educational) | Scholarly + Wolfram + Rember | "Sage, explain Fourier transforms and create flashcards for my exam." |
| **Executive Assistant** | "Claire" (professional, warm) | Google Calendar + M365 + Slack + Notion | "Claire, what's on my schedule today? Summarize the Notion page from Monday's strategy meeting and post a recap to #team-updates." |

---

## 8. Desktop Client — Computer Use Agent

> **Decision**: If built, the desktop client will be a **lightweight Python tray app** (not Electron) — minimal UI footprint, maximum automation power. It connects to the same Agent Hub backend as web/mobile/glasses.

### How Claude Desktop / Computer Use Works

Claude's "computer use" capability is the current state-of-the-art for desktop AI agents. Understanding how it works informs our own implementation.

#### The Agent Loop
```
User Request (e.g., "Open Excel and create a budget spreadsheet")
       ↓
┌─────────────────────┐
│  1. Take Screenshot  │ ← Capture current display (Xvfb / native screen)
└─────────┬───────────┘
          ↓
┌─────────────────────┐
│  2. Send to Vision   │ ← Screenshot → multimodal LLM for analysis
│     Model (Gemini)   │    "What do you see? What UI elements are present?"
└─────────┬───────────┘
          ↓
┌─────────────────────┐
│  3. Decide Action    │ ← LLM reasons: "I need to click the Start menu"
│     (LLM Reasoning)  │    Returns structured action: {click: [x, y]}
└─────────┬───────────┘
          ↓
┌─────────────────────┐
│  4. Execute Action   │ ← pyautogui.click(x, y) / typewrite(text) / hotkey()
└─────────┬───────────┘
          ↓
┌─────────────────────┐
│  5. Wait + Re-check  │ ← Brief pause for UI to update, then loop to step 1
└─────────────────────┘
```

This is identical to Claude's `computer_20251124` tool — a closed loop: **Look → Reason → Act → Look (repeat)**.

#### Claude's Available Actions
| Action | Description |
|---|---|
| `screenshot` | Capture current display |
| `left_click` / `right_click` / `middle_click` | Click at coordinates [x, y] |
| `double_click` / `triple_click` | Multi-click at coordinates |
| `type` | Type text string |
| `key` | Press key combo (e.g., "ctrl+s") |
| `mouse_move` | Move cursor to coordinates |
| `scroll` | Scroll in any direction with amount control |
| `left_click_drag` | Click and drag between coordinates |
| `hold_key` | Hold a key for N seconds |
| `wait` | Pause between actions |
| `zoom` | View specific screen region at full resolution (Opus 4.6+) |

Claude augments this with a **bash tool** (run terminal commands) and **text editor tool** (read/write files) for more comprehensive automation.

#### Key Limitations (Applies to Any Desktop Agent)
| Limitation | Impact | Our Mitigation |
|---|---|---|
| **Latency** | Each look→reason→act cycle takes 1-3s | Pre-plan multi-step actions, batch when possible |
| **Vision accuracy** | LLM may misidentify UI elements or coordinates | Use pywin32 UIA APIs for precise element targeting when available |
| **Scrolling reliability** | Scroll amounts can be imprecise | Use keyboard shortcuts (Page Down, arrow keys) as fallback |
| **Multi-monitor** | Hard to reason across multiple displays | Limit to primary display initially |
| **Security** | Agent could be tricked by on-screen prompt injections | Sandboxed actions, user confirmation for destructive operations |

### Implementation for Agent Hub — Python Tray App

#### Architecture
```
┌──────────────────────────────────────────────────┐
│              User's Windows Desktop               │
│                                                   │
│  ┌─────────────────────────────────────────────┐  │
│  │  Agent Hub Desktop Client (Python)          │  │
│  │  • System tray icon (pystray)               │  │
│  │  • WebSocket connection to Agent Hub backend │  │
│  │  • Screen capture (pyautogui)               │  │
│  │  • Action execution (pyautogui + pywin32)   │  │
│  │  • File operations (pathlib + shutil)       │  │
│  │  • Process management (psutil + subprocess) │  │
│  │  • Clipboard (pyperclip)                    │  │
│  └──────────────┬──────────────────────────────┘  │
│                 │ WebSocket (wss://)               │
└─────────────────┼─────────────────────────────────┘
                  ↕
┌──────────────────────────────────────────────────┐
│        Agent Hub Backend (Cloud Run)              │
│  ADK Agent with desktop automation tools          │
│  • ScreenCaptureTool → receives screenshot        │
│  • ClickTool(x,y) → sends click command           │
│  • TypeTool(text) → sends keystrokes              │
│  • WindowManagementTool → activate/minimize/close │
│  • FileOperationsTool → list/read/write/delete    │
│  • ProcessManagementTool → launch/kill apps       │
│  • ClipboardTool → copy/paste operations          │
│  • CrossClientActionTool → send commands to other  │
│    clients (glasses, web, mobile)                  │
└──────────────────────────────────────────────────┘
```

#### Core Technologies
| Layer | Package | Purpose |
|---|---|---|
| **System Tray** | `pystray` + `Pillow` | Lightweight tray icon, menu, start/stop |
| **Screen Capture** | `pyautogui` | `screenshot()` → PIL Image → base64 → WebSocket |
| **Vision Analysis** | Gemini 2.5 Flash (server-side) | Screenshot sent to backend → Gemini vision analyzes |
| **Mouse/Keyboard** | `pyautogui` + `pywin32` | Click, type, hotkeys, drag |
| **Window Mgmt** | `pygetwindow` + `pywin32` | Activate, minimize, maximize, list windows |
| **File Operations** | `pathlib` + `shutil` | List, read, write, copy, move, delete files |
| **App Launching** | `subprocess` + `psutil` | Launch apps, list/kill processes |
| **Clipboard** | `pyperclip` | Read/write clipboard for cross-app data transfer |
| **System Info** | `psutil` + `screeninfo` | CPU/RAM/disk usage, screen resolution |
| **WebSocket** | `websockets` | Persistent connection to Agent Hub backend |

#### Execution Flow Example
```python
# Desktop client receives command from backend:
# {"action": "screenshot"}
screenshot = pyautogui.screenshot()
img_bytes = io.BytesIO()
screenshot.save(img_bytes, format='JPEG', quality=85)
await ws.send(base64.b64encode(img_bytes.getvalue()))  # Send to backend

# Backend sends screenshot to Gemini Vision → gets action:
# {"action": "click", "x": 500, "y": 300}
pyautogui.click(500, 300)

# Backend sends type command:
# {"action": "type", "text": "Hello World"}
pyautogui.typewrite('Hello World', interval=0.02)

# Backend sends hotkey:
# {"action": "hotkey", "keys": ["ctrl", "s"]}
pyautogui.hotkey('ctrl', 's')
```

#### ADK Tool Definitions (Server-Side)
```python
async def capture_screen(session_id: str) -> str:
    """Request a screenshot from the desktop client. Returns image analysis."""
    screenshot_data = await desktop_clients[session_id].request_screenshot()
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=["Describe what you see on this desktop screenshot.", screenshot_data]
    )
    return response.text

async def click_at(x: int, y: int, session_id: str) -> str:
    """Click at pixel coordinates on the desktop."""
    await desktop_clients[session_id].send_action({"action": "click", "x": x, "y": y})
    return f"Clicked at ({x}, {y})"

async def type_text(text: str, session_id: str) -> str:
    """Type text on the desktop."""
    await desktop_clients[session_id].send_action({"action": "type", "text": text})
    return f"Typed: {text}"

async def open_application(app_name: str, session_id: str) -> str:
    """Launch an application on the desktop."""
    await desktop_clients[session_id].send_action({"action": "launch", "app": app_name})
    return f"Launched {app_name}"

async def manage_files(operation: str, path: str, dest: str = None, session_id: str = "") -> str:
    """File operations: list, read, write, copy, move, delete."""
    await desktop_clients[session_id].send_action(
        {"action": "file_op", "operation": operation, "path": path, "dest": dest}
    )
    return f"File operation '{operation}' on {path} completed"
```

### Desktop Client Use Cases

| Category | Voice Command Example | What Happens |
|---|---|---|
| **File Management** | "Organize my Downloads folder — move images to Pictures, PDFs to Documents" | Agent screenshots desktop → identifies files → executes move operations via file tools |
| **Multi-App Workflow** | "Copy the Q3 revenue from the Excel file and paste it into the email draft" | Opens Excel → locates cell → copies → switches to email → pastes |
| **Browser Automation** | "Fill out the job application form on this website with my resume info" | Screenshots browser → identifies fields → types info → submits |
| **Code Editing** | "Open VS Code, create a new Python file called utils.py, and add a logging helper" | Launches VS Code → creates file → types code |
| **Document Processing** | "Merge all PDFs in my Reports folder into one file" | Uses subprocess to call a PDF tool or Python library |
| **System Admin** | "Check my disk space and delete temp files if less than 10GB free" | Checks `psutil.disk_usage()` → cleans temp if needed |
| **Calendar/Email** | "Open Outlook and schedule a meeting with the product team for Friday 2pm" | Launches Outlook → navigates to calendar → creates event |
| **Presentation** | "Open PowerPoint, create a 5-slide deck about our Q3 results" | Launches PowerPoint → creates slides with content |
| **Data Entry** | "Enter these 20 customer records from the spreadsheet into the CRM web form" | Reads spreadsheet data → opens CRM → fills forms repeatedly |
| **Cross-Device** ★ | "Hey glasses, take a note" → note appears on desktop Notion app | Voice from glasses → backend → desktop client opens Notion → types note |

#### The Killer Feature: Cross-Client Desktop Actions

The desktop client's biggest value in the Agent Hub ecosystem is **cross-client synergy**:

```
🕶️ Glasses (voice): "Save a note about today's meeting decisions"
    ↓ (audio → backend)
🖥️ Desktop: Agent opens Notion → types meeting notes
    ↓ (confirmation → backend)
📱 Mobile: Push notification: "Meeting notes saved to Notion"
    ↓ (sync)
🌐 Dashboard: Note appears in conversation history + session artifacts
```

Key differentiator:
- Voice on wearable → action on desktop → confirmation on phone → visible on web dashboard
- This is the **"unified AI assistant across all your devices"** story

### Reference: UFO³ by Microsoft

**Status**: Production-ready, LTS | **GitHub**: microsoft/UFO (8.1K ⭐, 994 forks) | **Language**: Python

Microsoft's UFO³ Galaxy is the closest open-source equivalent to our desktop client concept:

| Feature | UFO³ Galaxy | Our Agent Hub Desktop Client |
|---|---|---|
| **Multi-device** | ✅ Windows, Linux, Android | ✅ Windows + glasses + mobile + web |
| **Task decomposition** | DAG-based ConstellationAgent | TaskArchitect dynamic pipeline |
| **Communication** | WebSocket AIP protocol | WebSocket to Agent Hub backend |
| **MCP integration** | ✅ Tool augmentation | ✅ Full MCP plugin store |
| **Voice-first** | ❌ Text/UI only | ✅ Gemini Live Audio native |
| **Agent personas** | ❌ Single agent style | ✅ Multiple voices & personalities |
| **Concurrent execution** | ✅ Async parallel | ✅ ParallelAgent via ADK |

**Our competitive advantage over UFO**: Voice-first interaction via Gemini Live Audio, agent personas with distinct voices, multi-client spanning hardware (glasses), user-installable MCP plugin store, and E2B sandbox for safe code execution.

---

## 9. Architecture Design

### System Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                    Google Cloud (Cloud Run)                   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐     │
│  │              FastAPI Backend (Python)                │     │
│  │                                                     │     │
│  │   ┌─────────────┐    ┌──────────────────┐          │     │
│  │   │ ADK Runner   │    │ MCPManager       │          │     │
│  │   │ run_live()   │    │ Dynamic McpToolset│          │     │
│  │   │ per session  │    │ per user config   │          │     │
│  │   └──────┬──────┘    └────────┬─────────┘          │     │
│  │          │                     │                     │     │
│  │   ┌──────┴──────┐    ┌────────┴─────────┐          │     │
│  │   │ Root Agent   │    │ E2B Sandbox      │          │     │
│  │   │ (Router)     │    │ Service          │          │     │
│  │   │  ├ Assistant │    │ Code execution   │          │     │
│  │   │  ├ Coder     │    │ MCP gateway      │          │     │
│  │   │  ├ Researcher│    └──────────────────┘          │     │
│  │   │  └ Creative  │                                  │     │
│  │   └──────┬──────┘    ┌──────────────────┐          │     │
│  │          │            │ Client Registry   │          │     │
│  │          │            │ Track devices     │          │     │
│  │          │            │ Cross-client cmds │          │     │
│  │          │            └──────────────────┘          │     │
│  │          │                                          │     │
│  │   ┌──────┴──────┐    ┌──────────────────┐          │     │
│  │   │ Persona     │    │ Firestore        │          │     │
│  │   │ Manager     │    │ Sessions, Config │          │     │
│  │   └─────────────┘    │ Personas, MCPs   │          │     │
│  │                      └──────────────────┘          │     │
│  └─────────────────────────────────────────────────────┘     │
│                    ↕ WebSocket (wss://)                       │
└─────────────────────────────────────────────────────────────┘
          ↕                    ↕                    ↕
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Web Dashboard │    │ Mobile PWA   │    │ ESP32 Glasses│
│ React + TS    │    │ React + TS   │    │ Mic + Speaker│
│ Full dashboard│    │ Voice-first  │    │ + Camera     │
│ MCP store     │    │ Camera       │    │ WiFi→WS      │
│ Persona mgmt  │    │ Responsive   │    │ PCM audio    │
└──────────────┘    └──────────────┘    └──────────────┘
```

### Data Flow
```
1. Client connects: WebSocket → /ws/{user_id}/{session_id}/{client_type}
2. Backend registers client in ClientRegistry
3. Backend loads user's MCP config from Firestore → builds McpToolset[]
4. Backend creates LiveRequestQueue + starts run_live() event loop
5. Client sends audio (binary PCM) → upstream task → LiveRequestQueue.send_realtime()
6. Client sends text (JSON) → upstream task → LiveRequestQueue.send_content()
7. Client sends image (JSON base64) → upstream task → LiveRequestQueue.send_realtime()
8. Agent processes → yields Event[] → downstream task → WebSocket.send_text()
9. Agent calls MCP tool → McpToolset routes → MCP server → result → agent continues
10. Agent calls cross_client_action → ClientRegistry → WebSocket message to target client
11. Client disconnects → LiveRequestQueue.close() → session saved
```

### ADK Multi-Agent Architecture — Leveraging All Agent Types

ADK provides 4 orchestration agent types beyond the basic `LlmAgent`. Using them effectively demonstrates **deep architectural sophistication**.

#### Agent Type Reference

| Agent Type | Class | Behavior | When to Use |
|---|---|---|---|
| **LlmAgent** | `Agent` / `LlmAgent` | LLM decides what to do — can call tools, delegate to sub_agents | Dynamic routing, conversation, any task needing reasoning |
| **SequentialAgent** | `SequentialAgent` | Runs sub-agents **in strict order**, output of step N flows to step N+1 | Multi-step workflows where each step depends on the previous |
| **ParallelAgent** | `ParallelAgent` | Runs sub-agents **concurrently**, all results collected when done | Independent data gathering from multiple sources — 4x faster |
| **LoopAgent** | `LoopAgent` | Repeats sub-agents **until exit condition met** or max iterations | Iterative refinement — draft→critique→improve cycles |

#### Where Each Agent Type Fits in Agent Hub

##### LlmAgent — Root Router + All Specialist Personas
The root agent uses Gemini's natural language understanding to dynamically route to the right specialist. This is **not hardcoded if/else** — the LLM decides based on intent.

```python
root_agent = Agent(
    name="hub_router",
    model="gemini-2.5-flash-native-audio-preview-12-2025",
    instruction="You are the Agent Hub router. Analyze user intent and delegate to the best specialist.",
    sub_agents=[assistant, coder, researcher, analyst, creative]
)
```

Each sub-agent persona is also an `LlmAgent` with its own voice, instruction, and MCP tools:
```python
coder = Agent(name="coder", instruction="You are a coding expert...", 
              tools=[e2b_tools, github_tools], generate_content_config=RunConfig(
                  speech_config=SpeechConfig(voice_config=VoiceConfig(prebuilt_voice_id="Kore"))))
```

##### SequentialAgent — Multi-Step Workflows

| User Request | Sequential Pipeline | Why Sequential |
|---|---|---|
| "Research quantum computing and write a report" | `SearchAgent` → `SynthesizeAgent` → `FormatAgent` | Step 2 needs step 1's results, step 3 formats step 2's output |
| "Check calendar, find free slots, draft a meeting invite" | `CalendarReaderAgent` → `SlotFinderAgent` → `EmailDraftAgent` | Each step feeds into the next |
| "Get stock data, analyze trends, create a chart" | `DataFetchAgent` → `AnalysisAgent` → `ChartAgent (E2B)` | Analysis needs data first, chart needs analysis |
| "Analyze this code, run tests, fix bugs" | `CodeAnalyzerAgent` → `TestRunnerAgent` → `BugFixerAgent` | Must analyze → test → then fix |

```python
research_pipeline = SequentialAgent(
    name="deep_research",
    sub_agents=[search_agent, synthesize_agent, format_agent]
)
```

##### ParallelAgent — Concurrent Data Gathering

| User Request | Parallel Agents | Speed Benefit |
|---|---|---|
| "Brief me for my day" | `CalendarAgent` ∥ `NotionAgent` ∥ `SlackAgent` ∥ `EmailAgent` | 4 sources simultaneously — **4x faster** than sequential |
| "Compare 3 competitor websites" | `WebScraperA` ∥ `WebScraperB` ∥ `WebScraperC` | All 3 scraped at once |
| "What's new today?" (Morning Briefing) | `NewsAgent` ∥ `CalendarAgent` ∥ `StockAgent` ∥ `WeatherAgent` | All fetched in parallel |
| "Health dashboard" | `FitBitAgent` ∥ `OuraAgent` ∥ `CalendarAgent` | Sleep + ring + schedule simultaneously |

```python
morning_briefing = ParallelAgent(
    name="morning_briefing",
    sub_agents=[news_agent, calendar_agent, stock_agent, weather_agent]
)
```

##### LoopAgent — Iterative Refinement Until Quality Bar Met

| User Request | Loop Pipeline | Exit Condition |
|---|---|---|
| "Write and polish a blog post" | `DraftAgent` → `CriticAgent` → `RewriteAgent` (loop) | Critic scores ≥ 8/10 |
| "Debug this code until tests pass" | `CodeFixAgent` → `TestRunnerAgent` (loop) | All tests green |
| "Refine my presentation" | `SlideGenAgent` → `ReviewAgent` → `ImproveAgent` (loop) | Review approves all slides |
| "SEO optimize this content" | `ContentAgent` → `SEOCheckAgent` → `OptimizeAgent` (loop) | SEO score ≥ 90 |

```python
content_refiner = LoopAgent(
    name="content_refiner",
    sub_agents=[draft_agent, critic_agent],
    max_iterations=5
)
```

#### Full Agent Tree — 3-Layer Capability-Based Architecture

This is the **complete agent hierarchy** using the implemented 3-layer routing design:

```
Root Agent "omni_root" (LlmAgent — Router)
│  tools: [plan_task]                            ← Layer 2 entry-point
│
│  ┌─── LAYER 1: Persona Pool (capability-matched T1 + T2 tools) ───┐
│  │                                                                  │
│  ├── "assistant" (LlmAgent)                    ← General Q&A, daily tasks
│  │   capabilities: [search, web, knowledge, communication, media]
│  │   T1 tools: [google_search, rag_query, notification_sender]
│  │   T2 (MCP): capability-matched plugins
│  │                                                                  │
│  ├── "coder" (LlmAgent)                        ← Code execution & debugging
│  │   capabilities: [code_execution, sandbox, search, web]
│  │   T1 tools: [google_search, code_execution, e2b_sandbox]
│  │   T2 (MCP): capability-matched plugins
│  │                                                                  │
│  ├── "researcher" (LlmAgent)                   ← Deep research tasks
│  │   capabilities: [search, web, knowledge]
│  │   T1 tools: [google_search]
│  │   T2 (MCP): capability-matched plugins
│  │                                                                  │
│  ├── "analyst" (LlmAgent)                      ← Finance & data analysis
│  │   capabilities: [code_execution, sandbox, search, data, web]
│  │   T1 tools: [google_search, code_execution, e2b_sandbox]
│  │   T2 (MCP): capability-matched plugins
│  │                                                                  │
│  └── "creative" (LlmAgent)                     ← Content creation
│      capabilities: [creative, media]
│      T1 tools: [imagen, creative_tools]
│      T2 (MCP): capability-matched plugins
│  └────────────────────────────────────────────────────────────────┘
│
│  ┌─── LAYER 2: TaskArchitect (plan_task FunctionTool) ────────────┐
│  │  Decomposes complex multi-step requests into stage blueprints   │
│  │  Each stage specifies: persona, action, dependencies            │
│  └────────────────────────────────────────────────────────────────┘
│
└── "device_agent" (LlmAgent)                    ← LAYER 3: Cross-client
    T3 tools: [send_to_device, list_devices, broadcast_message,
               get_device_status, sync_clipboard]
```

**Capability → Tool Matching (ToolCapability enum):**
| Capability | T1 Tools Provided |
|---|---|
| `search` | `google_search` |
| `code_execution` | `code_execution` |
| `sandbox` | `e2b_sandbox` |
| `knowledge` | `rag_query` |
| `communication` | `notification_sender` |
| `creative` | `imagen` |
| `media` | `creative_tools` |
| `web`, `data`, `calendar`, `financial` | *(reserved for T2/MCP plugins)* |

#### Architecture Diagram Strategy (for Submission)

Use **color-coded boxes** in the architecture diagram:
- 🔵 **Blue** = `LlmAgent` (decision makers, personas, root)
- 🟢 **Green** = `FunctionTool` (plan_task — TaskArchitect entry)
- 🟠 **Orange** = Capability tags (search, code_execution, sandbox, …)
- 🟣 **Purple** = `device_agent` (cross-client orchestration)

This single diagram communicates the **3-layer capability-based routing** that differentiates Omni Hub from flat single-agent entries.

#### Impact of Multi-Agent Architecture

| Architecture Pattern | What It Demonstrates | Impact |
|---|---|---|
| **LlmAgent routing** | Dynamic intent understanding — not hardcoded if/else | High — shows LLM-native design |
| **SequentialAgent pipelines** | Sophisticated multi-step reasoning chains | High — shows workflow orchestration |
| **ParallelAgent gathering** | Performance optimization — fast response times | Medium-High — shows engineering quality |
| **LoopAgent refinement** | Self-improving output quality — "agent iterates until good" | High — shows autonomous quality control |
| **Nested composition** | `ParallelAgent` inside `SequentialAgent` inside `LlmAgent` | **Very High** — deep technical architecture |
| **Per-agent voice configs** | Each persona sounds different when speaking | High — live audio differentiation |
| **Capability-based tool matching** | Personas get only relevant tools via `ToolCapability` tags | High — shows modular, scalable design |

#### Key Demo Moments to Showcase Multi-Agent Architecture

1. **"Brief me for my day"** → `ParallelAgent` fires 4 sub-agents simultaneously → results stream back fast → visually impressive speed
2. **"Research quantum computing and write a report"** → `SequentialAgent` executes steps in order → show progress on dashboard (Step 1/3, 2/3, 3/3)
3. **"Write me a LinkedIn post, make it great"** → `LoopAgent` drafts, self-critiques, rewrites → show iteration count on dashboard (Draft 1 → Score: 6/10, Draft 2 → Score: 8/10 ✓)
4. **"Switch to Coder mode"** → Root `LlmAgent` delegates to Coder sub-agent with different voice → voice audibly changes → demonstrates multi-agent delegation live
5. **"Get Apple's revenue data and create a chart"** → `SequentialAgent` with nested `ParallelAgent` for data fetch → shows 2-level nesting in one request

---

### TaskArchitect — Dynamic Meta-Orchestrator

Beyond predefined multi-agent trees, **TaskArchitect** is a meta-orchestrator that **dynamically analyzes any complex task, decomposes it into sub-tasks, and builds a custom multi-agent pipeline on the fly** — choosing Sequential, Parallel, Loop, or Hybrid patterns per sub-task. The resulting agent team executes autonomously while the user watches live progress on the dashboard.

**Key distinction from Personas:**
- **Personas** (Jarvis, Friday, Sage) = user-created; they define personality, voice, preferred tools
- **TaskArchitect pipelines** = system-created; they are dynamic agent TEAMS assembled per-task, visible on dashboard as a live execution graph

#### How It Works

```
User Request (complex task)
       ↓
┌─────────────────────────┐
│   TaskArchitect Agent   │  ← Analyzes task complexity, dependencies, parallelizability
│   (Meta-Orchestrator)   │
└─────────────────────────┘
       ↓
┌─────────────────────────┐
│   Task Decomposition    │  ← Breaks into sub-tasks, identifies dependencies
│   + Pipeline Selection  │  ← Chooses Sequential / Parallel / Loop / Hybrid
└─────────────────────────┘
       ↓
┌─────────────────────────┐
│  Dynamic Agent Pipeline │  ← Creates & runs the agent team
│  (visible on Dashboard) │  ← Live DAG visualization, status, progress
└─────────────────────────┘
       ↓
    Aggregated Result
```

#### Real-World Examples

##### Example 1: "Plan my 2-week trip to Japan on a $5K budget"

TaskArchitect analyzes → multi-source research + constraint optimization + sequential dependencies

```
ParallelAgent("Research") [
    FlightSearchAgent      → finds flights, prices, dates
    HotelSearchAgent       → finds accommodations by region
    AttractionAgent        → top attractions per city
    WeatherAgent           → 2-week forecast
    LocalFoodAgent         → restaurant recommendations
    TransitAgent           → JR Pass, local transport
]
    ↓
SequentialAgent("Plan") [
    ItineraryBuilderAgent  → combines parallel results into day-by-day plan
    BudgetOptimizerAgent   → fits within $5K, suggests trade-offs
    BookingPrepAgent       → generates booking links & checklist
]
    ↓
LoopAgent("Refine") [
    UserPreferenceCheckAgent → "too many temples? more food experiences?"
    AdjustmentAgent          → modifies itinerary
    → loops until user approves
]
```

**Dashboard view:** 6 parallel agents running simultaneously (research phase) with progress indicators, then sequential planning pipeline, then refinement loop with iteration counter.

##### Example 2: "Analyze Tesla's financials and write an investment report"

TaskArchitect → data gathering (parallelizable) + analysis (sequential) + quality loop

```
ParallelAgent("DataGather") [
    SECFilingsAgent        → 10-K, 10-Q, earnings transcripts
    MarketDataAgent        → stock price, P/E, market cap trends
    NewsAgent              → recent news, analyst ratings
    CompetitorAgent        → comparison with Rivian, BYD, Ford EV
    MacroEconomicAgent     → EV market trends, policy changes
]
    ↓
SequentialAgent("Analysis") [
    FinancialAnalysisAgent → revenue growth, margins, cash flow, debt
    RiskAssessmentAgent    → identifies key risks & catalysts
    ValuationAgent         → DCF model, comparable analysis
]
    ↓
LoopAgent("Report") [
    ReportWriterAgent      → drafts full investment report
    QualityCheckerAgent    → checks accuracy, completeness, clarity
    → loops until quality_score > 0.9
]
    ↓
FormattingAgent            → PDF with charts, tables, executive summary
```

**Dashboard view:** 5 data gatherers in parallel with progress bars, then analysis pipeline flowing through, then quality loop showing score improving (0.6 → 0.75 → 0.92 ✓).

##### Example 3: "Debug why our production API is returning 500 errors"

TaskArchitect → diagnostic (parallel probing) + correlation + iterative hypothesis testing

```
ParallelAgent("Diagnose") [
    LogAnalyzerAgent       → scans error logs, stack traces
    MetricsAgent           → CPU, memory, disk, request latency
    DatabaseAgent          → slow queries, connection pool status
    NetworkAgent           → DNS, SSL, upstream service health
    DeploymentAgent        → recent deploys, config changes
]
    ↓
CorrelationAgent           → cross-references all findings, identifies patterns
    ↓
LoopAgent("RootCause") [
    HypothesisAgent        → proposes likely root cause
    TestAgent              → runs diagnostic commands/queries to verify
    ValidateAgent          → confirms or rejects hypothesis
    → loops until root cause confirmed
]
    ↓
SequentialAgent("Resolve") [
    FixRecommendationAgent → generates fix with code/config changes
    ImpactAnalysisAgent    → assesses risk of the fix
    IncidentReportAgent    → creates post-mortem document
]
```

**Dashboard view:** 5 diagnostic probes running simultaneously, then correlation analysis, then hypothesis-test loop (Hypothesis 1: DB pool exhausted → Test → Reject → Hypothesis 2: memory leak after v2.3.1 deploy → Test → **Confirmed** ✓).

##### Example 4: "Create a complete marketing campaign for our SaaS product launch"

TaskArchitect → research → strategy (sequential) → content creation (parallel) → quality loop

```
ParallelAgent("Research") [
    CompetitorAnalysisAgent  → competitor messaging, pricing, channels
    AudienceResearchAgent    → ICP, pain points, buying triggers
    TrendAnalysisAgent       → market trends, seasonal timing
    ChannelAnalysisAgent     → best-performing channels for SaaS
]
    ↓
StrategyAgent              → creates campaign strategy, positioning, messaging framework
    ↓
ParallelAgent("Create") [
    AdCopyAgent             → Google Ads, LinkedIn Ads, Facebook Ads copy
    EmailSequenceAgent      → 5-email nurture sequence
    LandingPageAgent        → landing page copy + structure
    SocialContentAgent      → 30-day social calendar with posts
    BlogPostAgent           → 3 launch-related blog posts
    PRAgent                 → press release draft
]
    ↓
LoopAgent("BrandCheck") [
    BrandConsistencyAgent   → checks tone, voice, messaging alignment
    RevisionAgent           → fixes inconsistencies
    → loops until brand_score > 0.95
]
    ↓
BudgetAllocationAgent      → allocates spend across channels with ROI projections
```

**Dashboard view:** Research (4 parallel), strategy (single), then 6 content agents working simultaneously — the "wow" moment where the user sees 6 agents all producing content at once.

##### Example 5: "Prepare me for my Google SWE interview next week"

TaskArchitect → research (parallel) + gap analysis (sequential) + prep (parallel) + mock loop

```
ParallelAgent("Intel") [
    CompanyResearchAgent    → Google culture, recent products, team info
    RoleAnalysisAgent       → SWE L4 requirements, tech stack
    InterviewPatternAgent   → Google's interview format, common patterns
    GlassdoorAgent          → recent interview experiences, questions asked
]
    ↓
GapAnalysisAgent           → compares user's resume/skills vs requirements
    ↓
ParallelAgent("Prep") [
    CodingPrepAgent         → curated LeetCode problems by Google frequency
    SystemDesignAgent       → practice questions (Design YouTube, Gmail)
    BehavioralAgent         → STAR stories framework, culture-fit answers
    QuestionBankAgent       → 50 likely questions with model answers
]
    ↓
LoopAgent("MockInterview") [
    MockInterviewerAgent    → asks questions, evaluates answers
    FeedbackAgent           → scores, identifies weak areas
    FocusedPracticeAgent    → drills weak areas
    → loops for N rounds or until confidence > 0.8
]
    ↓
FinalPrepAgent             → cheat sheet, day-of checklist, confidence boosters
```

#### Dashboard Visualization for TaskArchitect Pipelines

| Element | Display |
|---|---|
| **Live Agent DAG** | Visual graph — nodes are agents, edges show data flow. Animated when running |
| **Agent Status** | 🟢 Running (pulse), 🟡 Waiting, ✅ Complete, 🔴 Error |
| **Progress** | Overall % bar + per-agent progress |
| **Live Logs** | Stream of each agent's findings/output in real-time |
| **Timeline** | Gantt-like view showing when each agent ran and duration |
| **Loop Counter** | For LoopAgents: "Iteration 3/max 5 — Quality: 0.82" |
| **Resource Meter** | Tokens used, API calls, E2B sandbox time |
| **Pipeline Blueprint** | The architecture the TaskArchitect chose (shown before execution begins) |

#### ADK Implementation — Actual Architecture

> **Implementation status**: `task_architect.py` and `task_planner_tool.py` are **fully implemented**.
> Dashboard DAG visualization and loop quality scoring are stretch goals.

```python
# ── backend/app/agents/task_architect.py ──────────────────────────────────

class StageType(StrEnum):
    SEQUENTIAL = "sequential"
    PARALLEL   = "parallel"
    LOOP       = "loop"
    SINGLE     = "single"

@dataclass
class SubTask:
    id: str
    description: str
    persona_id: str = "assistant"   # assistant | coder | researcher | analyst | creative
    instruction: str = ""

@dataclass
class TaskStage:
    name: str
    stage_type: StageType
    tasks: list[SubTask] = field(default_factory=list)
    max_iterations: int = 3

@dataclass
class PipelineBlueprint:
    task_description: str
    stages: list[TaskStage] = field(default_factory=list)
    pipeline_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    @classmethod
    def from_analysis(cls, analysis: dict, task_description: str) -> PipelineBlueprint:
        """Construct blueprint from the structured LLM JSON response."""
        ...

    def to_dict(self) -> dict: ...


COMPLEXITY_THRESHOLD = 2  # fewer sub-tasks → bypass architect, go direct to persona


class TaskArchitect:
    """Meta-orchestrator — plain Python class. Creates ADK agents dynamically.
    Is NOT itself an ADK agent; it constructs them at runtime from a blueprint.
    """
    def __init__(self, user_id: str, tools_by_persona: dict[str, list] | None = None):
        self.user_id = user_id
        self._tools_by_persona = tools_by_persona or {}
        self._event_bus = get_event_bus()

    async def analyse_task(self, task: str) -> PipelineBlueprint:
        """Call gemini-2.5-flash with a structured JSON decomposition prompt."""
        from google.genai import Client
        client = Client(vertexai=True)
        response = client.models.generate_content(model=TEXT_MODEL, contents=[DECOMPOSE_PROMPT])
        # Falls back to a single-stage sequential plan on JSON parse error
        analysis = json.loads(response.text)
        return PipelineBlueprint.from_analysis(analysis, task)

    def build_pipeline(self, blueprint: PipelineBlueprint) -> Agent:
        """Map each TaskStage → correct ADK agent type, wrap in SequentialAgent."""
        stage_agents = []
        for stage in blueprint.stages:
            sub_agents = [self._create_sub_agent(t) for t in stage.tasks]
            name = _sanitize_name(stage.name)   # valid ADK identifier
            if stage.stage_type == StageType.PARALLEL and len(sub_agents) > 1:
                stage_agents.append(ParallelAgent(name=name, sub_agents=sub_agents))
            elif stage.stage_type == StageType.LOOP:
                stage_agents.append(LoopAgent(
                    name=name, sub_agents=sub_agents,
                    max_iterations=stage.max_iterations,
                ))
            elif stage.stage_type == StageType.SEQUENTIAL and len(sub_agents) > 1:
                stage_agents.append(SequentialAgent(name=name, sub_agents=sub_agents))
            else:
                stage_agents.append(sub_agents[0])  # single — no wrapper needed
        # Top-level pipeline is always a SequentialAgent tying stages together
        return SequentialAgent(name=f"pipeline_{blueprint.pipeline_id}", sub_agents=stage_agents)

    async def execute_pipeline(self, blueprint: PipelineBlueprint, pipeline: Agent) -> str:
        """Run pipeline via ADK Runner; publish live stage progress to EventBus."""
        runner = Runner(
            app_name="omni-pipeline", agent=pipeline,
            session_service=InMemorySessionService(),
        )
        for stage in blueprint.stages:          # publish all stages as "pending" up-front
            await self.publish_stage_update(blueprint.pipeline_id, stage.name, "pending")
        async for event in runner.run_async(...):
            # Detect stage transitions → publish "running" / "completed" events
            ...
        return aggregated_text_summary

    async def publish_blueprint(self, blueprint: PipelineBlueprint) -> None:
        """Event sent to dashboard when plan is ready — before execution starts."""
        await self._event_bus.publish(self.user_id, json.dumps({
            "type": "pipeline_created",
            "pipeline": blueprint.to_dict(),    # stages, tasks, pipeline_id
            "timestamp": time.time(),
        }))

    async def publish_stage_update(
        self, pipeline_id: str, stage_name: str,
        status: str, progress: float = 0.0,
    ) -> None:
        """Event: pipeline_progress — fired on every stage status transition."""
        await self._event_bus.publish(self.user_id, json.dumps({
            "type": "pipeline_progress",
            "pipeline_id": pipeline_id,
            "stage": stage_name,
            "status": status,           # pending | running | completed | failed
            "progress": round(progress, 2),
            "timestamp": time.time(),
        }))

    def _create_sub_agent(self, task: SubTask) -> Agent:
        """Resolve T1 + T2 tools by persona capabilities; build focused LlmAgent."""
        caps = _PERSONA_CAPS[task.persona_id]           # ToolCapability tag list
        tools = get_tools_for_capabilities(caps)         # T1 tools
        tools += self._tools_by_persona.get(task.persona_id, [])  # T2 plugins
        return Agent(name=task.id, model=TEXT_MODEL,
                     instruction=task.instruction, tools=tools)


# ── backend/app/agents/task_planner_tool.py  (FunctionTool bridge) ─────────

async def plan_task(task: str, tool_context: ToolContext | None = None) -> str:
    """Root agent calls this to decompose + execute a complex multi-step task.

    Full pipeline:
      analyse_task() → publish_blueprint() → build_pipeline() → execute_pipeline()
    Returns a formatted plan + execution summary that the root can relay.
    """
    user_id = (tool_context.user_id if tool_context else None) or "unknown"
    tools_by_persona = await _build_tools_for_architect(user_id)
    architect = TaskArchitect(user_id=user_id, tools_by_persona=tools_by_persona)
    blueprint  = await architect.analyse_task(task)
    await architect.publish_blueprint(blueprint)           # → dashboard sees blueprint
    pipeline   = architect.build_pipeline(blueprint)
    summary    = await architect.execute_pipeline(blueprint, pipeline)
    return _format_plan_result(blueprint, summary[:4000])  # ≤4 000 chars for context

def get_task_planner_tool() -> FunctionTool:
    return FunctionTool(plan_task)
```

**Decomposition prompt — JSON schema Gemini must return:**
```json
{
  "stages": [
    {
      "name": "Research",
      "type": "parallel | sequential | loop | single",
      "max_iterations": 3,
      "tasks": [
        {
          "id": "t1",
          "description": "what this agent does",
          "persona_id": "researcher",
          "instruction": "detailed instruction for the LlmAgent"
        }
      ]
    }
  ]
}
```
Prompt constraints: ≤5 stages, ≤12 total sub-tasks, loop stages have exactly one sub-task, `max_iterations` 2–5.

#### Implementation Status & Complexity

| Component | Complexity | Status | Notes |
|---|---|---|---|
| **Task analysis prompt engineering** | Medium | ✅ Done | `_DECOMPOSE_PROMPT` in `task_architect.py`; JSON parse fallback to single-stage plan |
| **PipelineBlueprint data model** | Low | ✅ Done | `PipelineBlueprint`, `TaskStage`, `SubTask`, `StageType` dataclasses |
| **Dynamic agent construction** | Medium-High | ✅ Done | `build_pipeline()` maps stages → `SequentialAgent`/`ParallelAgent`/`LoopAgent` |
| **Pipeline execution + EventBus progress** | Medium | ✅ Done | `execute_pipeline()` via `Runner`; `publish_stage_update()` per stage transition |
| **FunctionTool bridge for root agent** | Low | ✅ Done | `task_planner_tool.py` — `plan_task()` + `get_task_planner_tool()` |
| **Error handling & fallbacks** | Medium | ✅ Done | JSON fallback pipeline; per-stage `failed` status on exception |
| **Loop exit quality scoring** | Medium | ⬜ Stretch | LLM-based `quality_score` 0–1 per iteration; `should_continue` in progress event |
| **Dashboard DAG visualization** | High | ⬜ Stretch | React Flow DAG or step-list rendering `pipeline_created`/`pipeline_progress` events |
| **Pipeline history in Firestore** | Low | ⬜ Stretch | Store `blueprint.to_dict()` per session; show replay in dashboard history view |

#### Risk & Mitigation

| Risk | Impact | Mitigation |
|---|---|---|
| Gemini produces bad blueprint JSON | Pipeline won't build | Strict JSON schema validation + retry with corrective prompt |
| Too many sub-agents for simple tasks | Wastes tokens, slow | Complexity threshold — tasks below it skip TaskArchitect, go to regular agent |
| Dashboard viz takes too long to build | Delays project | MVP: simple ordered step list with status icons. Fancy DAG is stretch goal |
| Sub-agent failures cascade | Whole pipeline fails | Wrap each agent in try/catch, allow partial results, report failures in dashboard |

#### Why TaskArchitect Matters

| Aspect | Value |
|---|---|
| **Agent Architecture** | Not just multi-agent — an agent that **dynamically creates** multi-agent architectures. Meta-level sophistication. |
| **Innovation** | An agent that analyzes tasks and auto-composes pipelines. No hard-coded agent graphs. |
| **Visual Impact** | The dashboard shows a complex task spawning a custom agent team — parallel agents light up simultaneously, sequential ones flow through, loops iterate with improving quality scores. |
| **Practical Value** | Users don't need to know about agent architectures — the system figures it out. True AI autonomy. |

### GenUI — Generative UI on Dashboard

Instead of rendering agent responses as plain text in a chat window, the dashboard can **dynamically generate React UI components** based on tool results — charts, tables, forms, cards, image galleries, interactive widgets.

#### What Is GenUI?

Generative UI (GenUI) is a pattern where the AI agent's response determines not just *what* content to show but *how* to display it. The agent returns structured data + a component hint, and the dashboard renders the appropriate React component.

#### How It Works in Agent Hub

```
User: "Show me Tesla's stock performance this year"
       ↓
Agent calls financial_data_tool() → returns structured JSON:
{
  "type": "chart",
  "chartType": "line",
  "title": "Tesla (TSLA) YTD Performance",
  "data": [{"date": "2026-01", "price": 392}, ...],
  "summary": "Tesla is up 15% YTD with a February dip..."
}
       ↓
Dashboard receives via WebSocket → matches "type": "chart" → renders <LineChart />
Agent speaks summary via Live API audio simultaneously
```

#### Component Mapping

| Agent Response Type | React Component | Example Use Case |
|---|---|---|
| `chart` (line/bar/pie) | `<DynamicChart />` | Stock data, analytics, metrics |
| `table` | `<DataTable />` | Search results, comparisons, logs |
| `card` | `<InfoCard />` | Meeting briefs, person profiles, summaries |
| `code` | `<CodeBlock />` | Code execution results, file contents |
| `image_gallery` | `<ImageGallery />` | Generated images (Nano Banana), screenshots |
| `form` | `<DynamicForm />` | User input collection, settings |
| `timeline` | `<Timeline />` | TaskArchitect pipeline progress, event history |
| `map` | `<MapView />` | Travel planning, location-based results |
| `kanban` | `<KanbanBoard />` | Task management, project status |
| `markdown` | `<MarkdownRenderer />` | Long-form content, reports, documentation |
| `diff` | `<DiffViewer />` | Code changes, document comparisons |
| `weather` | `<WeatherWidget />` | Weather forecasts |

#### Implementation Approach

```jsx
// Dashboard component mapper
function AgentResponse({ message }) {
  const data = JSON.parse(message.structuredData);
  
  switch (data.type) {
    case 'chart':    return <DynamicChart {...data} />;
    case 'table':    return <DataTable {...data} />;
    case 'card':     return <InfoCard {...data} />;
    case 'code':     return <CodeBlock {...data} />;
    case 'image_gallery': return <ImageGallery {...data} />;
    case 'form':     return <DynamicForm {...data} onSubmit={handleFormSubmit} />;
    case 'timeline': return <Timeline {...data} />;
    default:         return <MarkdownRenderer content={message.text} />;
  }
}
```

The agent's tool functions return structured JSON with a `type` field. The backend forwards this via WebSocket. The dashboard maps `type` → React component. This is inspired by Vercel AI SDK's `streamUI` concept but adapted for our WebSocket-first architecture.

#### Why GenUI Matters
- **Beyond chat** — transforms the dashboard from a chat window into a **dynamic workspace**
- **Visual richness** — charts, cards, and tables are far more impressive than plain text
- **Real utility** — financial analysts want charts, not paragraphs describing numbers
- **Reusable** — same components work for any persona (Analyst shows charts, Coder shows code blocks, Researcher shows tables)
- **Concurrent audio + visual** — agent speaks the summary while the dashboard renders the visual. Dual-channel experience.

---

## 10. Implementation Plan

### Phase 1: Backend Core (Days 1-3) — CRITICAL PATH

#### Step 1.1: Project Scaffolding
```
backend/
  main.py                    # FastAPI app, WebSocket endpoints
  agents/
    __init__.py
    personas.py              # Agent persona definitions
    router_agent.py          # Root agent with sub_agents
  services/
    client_registry.py       # Track connected clients
    mcp_manager.py           # Dynamic MCP toolset loading
    e2b_service.py           # E2B sandbox management
    persona_service.py       # Firestore CRUD for personas
  config.py                  # Env vars, model config
  requirements.txt
  .env
```

**Dependencies**: `google-adk`, `google-genai`, `google-cloud-firestore`, `e2b-code-interpreter`, `fastapi`, `uvicorn`, `python-dotenv`

**Environment**:
```env
# Development (Gemini Live API)
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=your_key

# Production (Vertex AI Live API)
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=your_project
GOOGLE_CLOUD_LOCATION=us-central1

E2B_API_KEY=your_e2b_key
```

#### Step 1.2: ADK Agent + Live Streaming
- WebSocket endpoint with `client_type` parameter
- Upstream/downstream `asyncio.gather()` pattern
- `RunConfig` with proactive audio + affective dialog
- Model: `gemini-2.5-flash-native-audio-preview-12-2025`

#### Step 1.3: Client Registry + Cross-Client Tools
- ADK custom tools: `cross_client_action()`, `list_connected_clients()`
- ClientRegistry tracks `{user_id → {client_id → status}}`

#### Step 1.4: Agent Personas
- 4 default personas with unique `Gemini(speech_config=...)` voices
- Root agent delegates to persona sub-agents
- Persona CRUD in Firestore

### Phase 2: MCP Plugin System (Days 3-5)

#### Step 2.1: MCPManager
- Dynamic `McpToolset` instantiation from Firestore config
- Support for Stdio, SSE, StreamableHTTP connections
- Pre-configured catalog of 10+ MCPs

#### Step 2.2: E2B Integration
- `execute_code()` and `run_terminal_command()` as ADK custom tools
- E2B MCP gateway bridge to ADK via `StreamableHTTPConnectionParams`

#### Step 2.3: Google Search Grounding
- ADK built-in `google_search` tool for grounding

### Phase 3: Web Dashboard (Days 4-6)

#### Step 3.1: React + TypeScript + Vite + Tailwind
- Chat View, Persona Manager, MCP Store, Client Status, Sandbox Console

#### Step 3.2: Browser Audio/Video
- AudioWorklet capture (16kHz) + playback (24kHz)
- Camera capture (JPEG 768×768 at 1fps)
- Real-time transcription display

### Phase 4: Mobile PWA (Days 5-6)
- Responsive React, PWA manifest
- Voice-first UX, rear camera integration

### Phase 5: ESP32 Glasses (Day 6-7)
- ESP32 I2S mic/speaker over WiFi WebSocket
- Or: Python simulation script for demo

### Phase 6: Deployment & Demo (Day 7-8)

#### Cloud Deployment
- **Cloud Run**: Dockerfile, uvicorn, min_instances=1
- **Firestore**: sessions, personas, MCP configs
- **Terraform/gcloud scripts** for automated deployment

---

## 11. Tech Stack

> **Philosophy**: Fewest config files, fastest feedback loops, minimal boilerplate. Ship a working prototype, then iterate.

### Complete Stack

| Layer | Technology | Why This Choice |
|---|---|---|
| **Backend Runtime** | **Python 3.12+** | ADK is Python-first; best docs, samples, community support |
| **Package Manager** | **uv** | 10-100x faster than pip; replaces pip + venv + pip-tools in one binary; lockfile support; instant installs |
| **Web Framework** | **FastAPI** | Async native, WebSocket support, auto-generated OpenAPI docs, perfect for ADK `run_live()` |
| **ASGI Server** | **uvicorn** | Production-grade async server for FastAPI |
| **AI Framework** | **Google ADK** (`google-adk`) | `run_live()`, `McpToolset`, multi-agent, callbacks |
| **AI Model** | **Gemini 2.5 Flash Native Audio** | Live streaming, voice personas, affective dialog, proactive audio |
| **Frontend Framework** | **React 19 (JavaScript — no TypeScript)** | Fastest prototyping; skip type definitions overhead; user preference |
| **Frontend Build** | **Vite** | Sub-second HMR, minimal config, fastest dev server available |
| **Frontend Styling** | **Tailwind CSS** | Utility-first = rapid UI building without writing CSS files |
| **Component Library** | **shadcn/ui** (copy-paste, not npm dependency) | Beautiful pre-built components, fully customizable, no lock-in |
| **State Management** | **Zustand** | Minimal boilerplate (3 lines to create a store), no providers/context wrappers |
| **Database** | **Firestore** | Serverless, real-time listeners, GCP native, generous free tier, zero config |
| **File/Image Storage** | **Cloud Storage (GCS)** | Generated images, session media, user uploads |
| **Auth** | **Firebase Auth** | Google/email sign-in in minutes, GCP native, free tier |
| **Deployment** | **Cloud Run** | WebSocket support, auto-scaling, Docker-based, pay-per-use |
| **Container** | **Docker** | Cloud Run requirement; reproducible builds |
| **Sandbox** | **E2B** | Secure code execution, 100+ MCP gateway, <200ms cold start |
| **Realtime Comms** | **WebSocket (native)** | Bidi streaming for PCM audio + JSON events; no library needed |
| **Audio Processing** | **Web Audio API + AudioWorklet** | Browser-native audio capture (16kHz) + playback (24kHz) |
| **Desktop Client** | **Python + pystray + pyautogui** | Lightweight system tray app, computer use agent |
| **Chrome Extension** | **Manifest V3 + vanilla JS** | Voice-activated browser control, minimal dependencies |
| **Mobile** | **React (responsive PWA)** | Same codebase as web dashboard, add to home screen |
| **Charts** | **Recharts** or **Chart.js** | GenUI dynamic chart rendering, React-friendly |
| **Icons** | **Lucide React** | Consistent icon set, tree-shakeable |
| **HTTP Client (frontend)** | **fetch (native)** | No need for axios; native is sufficient |
| **CI/CD** | **Cloud Build** or **GitHub Actions** | Auto-deploy on git push |
| **IaC** | **Terraform** | Automated GCP infra provisioning |
| **Secrets** | **Google Secret Manager** | API keys, MCP credentials — never in env files for prod |
| **Monitoring** | **Cloud Logging + Cloud Trace** | GCP native, zero-config observability |
| **Linting** | **Ruff** (Python) + **ESLint** (JS) | Ruff is 10-100x faster than flake8/pylint; ESLint standard |
| **Formatting** | **Ruff format** (Python) + **Prettier** (JS) | Consistent code style, zero debates |

### Quick Start Commands

```bash
# === Backend Setup ===
pip install uv                              # Install uv (one-time)
uv init backend && cd backend               # Create project
uv add google-adk google-genai              # Core AI
uv add fastapi uvicorn python-dotenv        # Web server
uv add google-cloud-firestore               # Database
uv add e2b-code-interpreter                 # Sandbox
uv add websockets                           # WebSocket client utils
uv add ruff                                 # Linting + formatting

# === Frontend Setup ===
pnpm create vite@latest dashboard -- --template react   # React JS (not TS!)
cd dashboard
pnpm install
pnpm install -D tailwindcss @tailwindcss/vite           # Styling
pnpm install zustand recharts lucide-react               # State, charts, icons
pnpm install firebase                                   # Auth + Firestore client

# === Desktop Client Setup ===
cd .. && uv init desktop-client && cd desktop-client
uv add pystray Pillow pyautogui pyperclip pygetwindow psutil websockets

# === Chrome Extension ===
mkdir -p chrome-extension  # Manifest V3 + vanilla JS — no build step needed

# === Deployment ===
gcloud run deploy agent-hub \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --min-instances 1 \
  --session-affinity
```

### Why These Specific Choices

| Decision | Alternatives Considered | Why We Chose This |
|---|---|---|
| **uv** over pip/poetry | pip, poetry, pdm, conda | uv is 10-100x faster, handles venvs + lockfiles + installs in one tool |
| **JS** over TS | TypeScript | Faster prototyping — skip type definitions, compilation, tsconfig. Prototype first, refactor later |
| **Vite** over CRA/Next.js | Create React App, Next.js, Remix | Vite: zero-opinion, fastest HMR, no SSR complexity. We don't need Next.js routing/SSR |
| **Firestore** over PostgreSQL | Cloud SQL, Supabase, MongoDB Atlas | Firestore: serverless (no connection pools), real-time listeners for dashboard updates, generous free tier, GCP native |
| **Zustand** over Redux/Context | Redux Toolkit, React Context, Jotai | Zustand: 3-line store creation, no provider wrappers, works outside React components |
| **shadcn/ui** over MUI/Chakra | Material UI, Chakra UI, Ant Design | shadcn: copy-paste (not npm dependency), fully customizable, beautiful defaults, Tailwind-native |
| **Firebase Auth** over Auth0/Clerk | Auth0, Clerk, Supabase Auth | Firebase Auth: GCP native, Google sign-in in 10 lines, free tier |
| **Ruff** over flake8/pylint | flake8, pylint, black, isort | Ruff: replaces flake8+pylint+black+isort in one tool, 100x faster |
| **pystray** over Electron | Electron, Tauri, PyQt | pystray: 50 lines for a tray app vs 5000+ for Electron; we need a lightweight agent, not a GUI app |
| **Manifest V3 + vanilla JS** | Plasmo, CRXJS | No build step, no framework overhead; extension is thin — just WebSocket + chrome APIs |
| **Raw WebSocket** over Socket.IO | Socket.IO (`python-socketio` + `socket.io-client`) | Raw WS: zero overhead on binary audio, all ADK/Gemini samples use it, FastAPI native `@app.websocket()`, works on ESP32/Chrome ext/Python without extra libs. Socket.IO rooms/reconnection are nice but we build a thin `ConnectionManager` (~100 lines) + exponential backoff hook (~60 lines) on Day 1 and never touch again. |

### Project Structure

```
agent-hub/
├── backend/                    # Python + FastAPI + ADK
│   ├── pyproject.toml          # uv project config
│   ├── uv.lock                 # Lockfile
│   ├── main.py                 # FastAPI app, WebSocket endpoints
│   ├── agents/                 # ADK agent definitions
│   │   ├── personas.py         # Agent persona configs
│   │   └── router_agent.py     # Root agent with sub_agents
│   ├── services/               # Business logic
│   │   ├── client_registry.py  # Track connected clients
│   │   ├── mcp_manager.py      # Dynamic MCP loading
│   │   └── e2b_service.py      # E2B sandbox management
│   ├── tools/                  # ADK custom tool functions
│   │   ├── desktop_tools.py    # Computer use tools
│   │   ├── image_gen.py        # Nano Banana interleaved output
│   │   └── cross_client.py     # Cross-client action tools
│   ├── Dockerfile              # Cloud Run container
│   └── .env                    # Local dev secrets
├── dashboard/                  # React (JS) + Vite
│   ├── package.json
│   ├── vite.config.js
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/         # UI components
│   │   │   ├── Chat.jsx        # Voice chat + transcription
│   │   │   ├── GenUI.jsx       # Dynamic component renderer
│   │   │   ├── PersonaManager.jsx
│   │   │   ├── MCPStore.jsx
│   │   │   └── ClientStatus.jsx
│   │   ├── stores/             # Zustand stores
│   │   │   └── appStore.js
│   │   ├── hooks/              # Custom hooks
│   │   │   ├── useWebSocket.js
│   │   │   └── useAudio.js
│   │   └── lib/                # Utilities
│   │       └── firebase.js
│   └── public/
├── desktop-client/             # Python tray app
│   ├── pyproject.toml
│   ├── main.py                 # Tray app + WebSocket + automation
│   └── tools.py                # pyautogui actions
├── chrome-extension/           # Manifest V3
│   ├── manifest.json
│   ├── background.js           # Service worker + WebSocket
│   ├── content.js              # Page interaction
│   ├── popup.html + popup.js   # Extension popup UI
│   └── icons/
├── deploy/                     # IaC
│   ├── main.tf                 # Terraform config
│   └── deploy.sh               # gcloud deploy script
├── docs/                       # Documentation
│   └── architecture.png
└── README.md
```

---

## 12. Scope & Decisions

### MVP Definition — What Must Ship

| # | Feature | Priority |
|---|---|---|
| 1 | FastAPI backend with ADK `run_live()` bidi streaming | Must Have |
| 2 | Web dashboard (React JS + Vite + Tailwind + shadcn/ui) — voice chat + GenUI + persona panel + MCP store | Must Have |
| 3 | Mobile PWA — responsive dashboard + camera vision | Should Have |
| 4 | Agent personas with distinct voices (5 default: Nova, Atlas, Sage, Spark, Claire) | Should Have |
| 5 | MCP plugin store — visual UI, enable/disable plugins mid-session, 10+ MCPs | Should Have |
| 6 | E2B sandboxed code execution — write code → execute → return output | Should Have |
| 7 | Cross-client actions — action on one device triggers result on another | Key differentiator |
| 8 | GenUI — agent renders charts, tables, code blocks, cards inline in chat | Key differentiator |
| 9 | Google Search grounding + anti-hallucination instructions | Should Have |
| 10 | Firebase Auth (Google sign-in) | Must Have |
| 11 | Firestore persistence — sessions, personas, MCP configs, chat history | Must Have |
| 12 | Cloud Run deployment — accessible via public URL | Must Have |
| 13 | ADK Callbacks — error handling, input sanitization, tool failure recovery | Should Have |
| 14 | Context Compression — unlimited session length | Should Have |
| 15 | Architecture diagram — professional quality, all components labeled | Must Have |
| 16 | README with setup instructions — clone → configure → deploy | Must Have |

### Stretch Goals

| Priority | Feature | Effort |
|---|---|---|
| S1 | Voice-created personas ("Create a Chef persona with a warm voice") | 3 hours |
| S2 | Chrome extension — voice-activated browser tasks | 8 hours |
| S3 | Desktop tray app — computer use agent (screenshot → action) | 8 hours |
| S4 | TaskArchitect DAG visualization — visual task breakdown GenUI component | 6 hours |
| S5 | Ambient/passive listening mode — proactive audio triggers | 4 hours |
| S6 | Interleaved image generation via Nano Banana tool | 4 hours |
| S7 | ESP32 glasses with real hardware | 12+ hours |
| S8 | ADK Evaluation framework — automated response quality testing | 4 hours |

### Out of Scope

| Feature | Why Not |
|---|---|
| A2A protocol integration | No other agent to talk to in current scope |
| Custom voice training / TTS | Gemini native voices are sufficient; custom training requires separate infra |
| Multi-language UI | English-only for now; i18n is trivial but time-consuming |
| Payment/billing for MCP services | Enterprise feature; not needed for MVP |
| Cron jobs / scheduled tasks | Background automation is useful but not "live" interaction |
| Multi-user collaboration | Single-user hub for MVP; multi-user is an architecture extension |
| Rate-limited public API | Not needed; only our clients connect to backend |

### Key Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| **Backend** | Python 3.12+ / FastAPI | ADK is Python-first. FastAPI supports WebSockets natively. |
| **Package Manager** | uv | Fast, reliable, deterministic. `uv run` in README is cleaner than pip instructions. |
| **Frontend** | React 19 (JavaScript) + Vite | JS over TS for faster prototyping. Vite for fast iteration. |
| **Styling** | Tailwind CSS + shadcn/ui | Professional-looking UI with minimal design effort. Dark mode built-in. |
| **State** | Zustand | Minimal boilerplate. No context provider nesting. |
| **Database** | Firestore | Serverless + real-time + GCP native. Generous free tier. |
| **Auth** | Firebase Auth | Google sign-in in 10 lines. GCP native. |
| **Audio Transport** | Binary WebSocket frames | 33% smaller than base64-in-JSON. Lower latency. |
| **Realtime Transport** | Raw WebSocket (not Socket.IO) | Native binary/text frame distinction, all ADK samples use raw WS, FastAPI `@app.websocket()` built-in, works across all 5 client types without extra libs. |
| **Session (dev)** | InMemorySessionService | Zero setup for local development |
| **Session (prod)** | Firestore-backed custom service | Survives Cloud Run restarts. |
| **Audio Model** | `gemini-2.5-flash-native-audio-preview` | Proactive audio + affective dialog. Most advanced voice model. |
| **Code Execution** | E2B Sandbox | Secure isolation + 100+ built-in MCPs. |
| **MCP Connection** | Stdio + StreamableHTTP | Cover both local and remote MCP servers. |
| **Audio Pipeline** | AudioWorklet (not ScriptProcessorNode) | Runs on separate thread, zero main-thread jank. |
| **GenUI** | Agent returns structured JSON → React renders components | Novel pattern for AI-driven UI rendering. |
