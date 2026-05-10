#!/usr/bin/env python
"""LLM Proxy Sniffer - Single-file proxy server with logging and web UI."""

import asyncio
import base64
import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
import aiosqlite
from aiohttp import web

import config

# --- Database Setup ---


async def init_db():
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    os.makedirs(os.path.join(config.MEDIA_DIR, "images"), exist_ok=True)
    os.makedirs(os.path.join(config.MEDIA_DIR, "audio"), exist_ok=True)
    db = await aiosqlite.connect(config.DB_PATH)
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            name TEXT,
            created_at TEXT,
            last_active TEXT
        );
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            timestamp TEXT,
            client_type TEXT,
            model TEXT,
            request_body TEXT,
            response_body TEXT,
            status_code INTEGER,
            duration_ms INTEGER,
            stream INTEGER DEFAULT 0,
            error TEXT
        );
        CREATE TABLE IF NOT EXISTS media_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER,
            role TEXT,
            media_type TEXT,
            mime_type TEXT,
            file_path TEXT,
            message_index INTEGER,
            created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_requests_session ON requests(session_id, timestamp);
        CREATE INDEX IF NOT EXISTS idx_media_request ON media_files(request_id);
    """)
    await db.commit()
    return db


# --- Session Management ---


async def resolve_session(db, request, body):
    session_id = request.headers.get("X-Session-ID")
    if session_id:
        await ensure_session(db, session_id, body)
        return session_id

    # Infer session from client IP + model + time window
    client_ip = request.remote or "unknown"
    model = body.get("model", "unknown")
    key = hashlib.md5(f"{client_ip}:{model}".encode()).hexdigest()[:16]

    now = datetime.now(timezone.utc)
    cutoff = now.timestamp() - config.SESSION_TIMEOUT

    async with db.execute(
        "SELECT id, last_active FROM sessions WHERE id LIKE ? ORDER BY last_active DESC LIMIT 1",
        (f"{key}%",),
    ) as cursor:
        row = await cursor.fetchone()
        if row:
            last_active = datetime.fromisoformat(row[1]).timestamp()
            if last_active > cutoff:
                session_id = row[0]
                await db.execute(
                    "UPDATE sessions SET last_active = ? WHERE id = ?",
                    (now.isoformat(), session_id),
                )
                await db.commit()
                return session_id

    session_id = f"{key}-{uuid.uuid4().hex[:8]}"
    await ensure_session(db, session_id, body)
    return session_id


async def ensure_session(db, session_id, body):
    now = datetime.now(timezone.utc).isoformat()
    async with db.execute(
        "SELECT id FROM sessions WHERE id = ?", (session_id,)
    ) as cursor:
        if await cursor.fetchone():
            await db.execute(
                "UPDATE sessions SET last_active = ? WHERE id = ?", (now, session_id)
            )
        else:
            name = extract_session_name(body)
            await db.execute(
                "INSERT INTO sessions (id, name, created_at, last_active) VALUES (?, ?, ?, ?)",
                (session_id, name, now, now),
            )
    await db.commit()


def extract_session_name(body):
    messages = body.get("messages", [])
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        return block["text"][:50]
            elif isinstance(content, str):
                return content[:50]
    return f"Session {datetime.now(timezone.utc).strftime('%m-%d %H:%M')}"


# --- Media Extraction ---


def extract_and_save_media(body, request_id, role):
    """Extract base64 media from messages and save to disk. Returns modified body."""
    media_records = []
    messages = body.get("messages", []) if isinstance(body, dict) else []
    if (
        isinstance(body, dict)
        and "content" in body
        and isinstance(body["content"], list)
    ):
        # Response with content blocks
        messages = [body]

    for msg_idx, msg in enumerate(messages):
        content = msg.get("content", "")
        if not isinstance(content, list):
            continue
        for block_idx, block in enumerate(content):
            if not isinstance(block, dict):
                continue
            saved = _try_save_media_block(block, request_id, msg_idx, block_idx, role)
            if saved:
                media_records.append(saved)
    return media_records


def _try_save_media_block(block, request_id, msg_idx, block_idx, role):
    # OpenAI image_url with data URI
    if block.get("type") == "image_url":
        url = block.get("image_url", {}).get("url", "")
        if url.startswith("data:"):
            return _save_data_uri(url, request_id, msg_idx, block_idx, role, "image")

    # Anthropic image with base64
    if block.get("type") == "image":
        source = block.get("source", {})
        if source.get("type") == "base64":
            mime = source.get("media_type", "image/png")
            data = source.get("data", "")
            return _save_base64(
                data, mime, request_id, msg_idx, block_idx, role, "image"
            )

    # OpenAI audio input
    if block.get("type") == "input_audio":
        audio_data = block.get("input_audio", {})
        fmt = audio_data.get("format", "wav")
        data = audio_data.get("data", "")
        mime = f"audio/{fmt}"
        return _save_base64(data, mime, request_id, msg_idx, block_idx, role, "audio")

    return None


def _save_data_uri(uri, request_id, msg_idx, block_idx, role, media_type):
    # data:image/png;base64,xxxxx
    header, data = uri.split(",", 1)
    mime = header.split(":")[1].split(";")[0]
    return _save_base64(data, mime, request_id, msg_idx, block_idx, role, media_type)


def _save_base64(data, mime, request_id, msg_idx, block_idx, role, media_type):
    ext = mime.split("/")[-1].split(";")[0]
    if ext == "jpeg":
        ext = "jpg"
    filename = f"{request_id}_{msg_idx}_{block_idx}.{ext}"
    subdir = "images" if media_type == "image" else "audio"
    filepath = os.path.join(config.MEDIA_DIR, subdir, filename)
    try:
        raw = base64.b64decode(data)
        with open(filepath, "wb") as f:
            f.write(raw)
        rel_path = f"{subdir}/{filename}"
        return {
            "role": role,
            "media_type": media_type,
            "mime_type": mime,
            "file_path": rel_path,
            "message_index": msg_idx,
        }
    except Exception:
        return None


# --- Anthropic → OpenAI Conversion ---


def convert_anthropic_to_openai(body):
    """Convert Anthropic Messages API request to OpenAI Chat Completions format."""
    openai_body = {}
    openai_body["model"] = body.get("model", "")
    openai_body["stream"] = body.get("stream", False)

    if "max_tokens" in body:
        openai_body["max_tokens"] = body["max_tokens"]
    if "temperature" in body:
        openai_body["temperature"] = body["temperature"]
    if "top_p" in body:
        openai_body["top_p"] = body["top_p"]
    if "stop_sequences" in body:
        openai_body["stop"] = body["stop_sequences"]

    # Convert messages
    messages = []
    if "system" in body:
        sys_content = body["system"]
        if isinstance(sys_content, list):
            sys_text = " ".join(
                b.get("text", "") for b in sys_content if b.get("type") == "text"
            )
        else:
            sys_text = sys_content
        messages.append({"role": "system", "content": sys_text})

    for msg in body.get("messages", []):
        converted = convert_anthropic_message(msg)
        if isinstance(converted, list):
            messages.extend(converted)
        else:
            messages.append(converted)

    openai_body["messages"] = messages

    # Convert tools
    if "tools" in body:
        openai_body["tools"] = [convert_anthropic_tool(t) for t in body["tools"]]

    if "tool_choice" in body:
        tc = body["tool_choice"]
        if isinstance(tc, dict):
            if tc.get("type") == "tool":
                openai_body["tool_choice"] = {
                    "type": "function",
                    "function": {"name": tc["name"]},
                }
            elif tc.get("type") == "any":
                openai_body["tool_choice"] = "required"
            elif tc.get("type") == "auto":
                openai_body["tool_choice"] = "auto"
        elif tc == "none":
            openai_body["tool_choice"] = "none"
        elif tc == "auto":
            openai_body["tool_choice"] = "auto"

    return openai_body


def convert_anthropic_message(msg):
    role = msg.get("role")
    content = msg.get("content", "")

    if isinstance(content, str):
        return {"role": role, "content": content}

    if role == "user":
        # Check for tool_result blocks
        tool_results = [
            b for b in content if isinstance(b, dict) and b.get("type") == "tool_result"
        ]
        if tool_results:
            # Split into tool messages and regular content
            result = []
            other_blocks = [
                b
                for b in content
                if not (isinstance(b, dict) and b.get("type") == "tool_result")
            ]
            if other_blocks:
                result.append(
                    {"role": "user", "content": convert_content_blocks(other_blocks)}
                )
            for tr in tool_results:
                tr_content = tr.get("content", "")
                if isinstance(tr_content, list):
                    tr_content = " ".join(
                        b.get("text", "")
                        for b in tr_content
                        if isinstance(b, dict) and b.get("type") == "text"
                    )
                result.append(
                    {
                        "role": "tool",
                        "tool_call_id": tr.get("tool_use_id", ""),
                        "content": (
                            tr_content
                            if isinstance(tr_content, str)
                            else json.dumps(tr_content)
                        ),
                    }
                )
            return result
        else:
            return {"role": "user", "content": convert_content_blocks(content)}

    if role == "assistant":
        # Check for tool_use blocks
        tool_uses = [
            b for b in content if isinstance(b, dict) and b.get("type") == "tool_use"
        ]
        text_blocks = [
            b for b in content if isinstance(b, dict) and b.get("type") == "text"
        ]

        text_content = (
            " ".join(b.get("text", "") for b in text_blocks) if text_blocks else None
        )

        if tool_uses:
            msg_out = {"role": "assistant"}
            if text_content:
                msg_out["content"] = text_content
            else:
                msg_out["content"] = None
            msg_out["tool_calls"] = []
            for tu in tool_uses:
                msg_out["tool_calls"].append(
                    {
                        "id": tu.get("id", str(uuid.uuid4())),
                        "type": "function",
                        "function": {
                            "name": tu.get("name", ""),
                            "arguments": json.dumps(tu.get("input", {})),
                        },
                    }
                )
            return msg_out
        else:
            if text_content is not None:
                return {"role": "assistant", "content": text_content}
            return {"role": "assistant", "content": convert_content_blocks(content)}

    return {"role": role, "content": str(content)}


def convert_content_blocks(blocks):
    """Convert Anthropic content blocks to OpenAI format."""
    if not blocks:
        return ""
    if len(blocks) == 1 and blocks[0].get("type") == "text":
        return blocks[0].get("text", "")

    result = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            result.append({"type": "text", "text": block.get("text", "")})
        elif btype == "image":
            source = block.get("source", {})
            if source.get("type") == "base64":
                url = f"data:{source.get('media_type', 'image/png')};base64,{source.get('data', '')}"
            else:
                url = source.get("url", "")
            result.append({"type": "image_url", "image_url": {"url": url}})
    return result if result else ""


def convert_anthropic_tool(tool):
    return {
        "type": "function",
        "function": {
            "name": tool.get("name", ""),
            "description": tool.get("description", ""),
            "parameters": tool.get("input_schema", {}),
        },
    }


# --- OpenAI → Anthropic Response Conversion ---


def convert_openai_response_to_anthropic(openai_resp, model):
    """Convert OpenAI response back to Anthropic format for Anthropic clients."""
    choice = openai_resp.get("choices", [{}])[0]
    message = choice.get("message", {})
    finish_reason = choice.get("finish_reason", "stop")

    content = []
    if message.get("content"):
        content.append({"type": "text", "text": message["content"]})

    if message.get("tool_calls"):
        for tc in message["tool_calls"]:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            content.append(
                {
                    "type": "tool_use",
                    "id": tc.get("id", str(uuid.uuid4())),
                    "name": fn.get("name", ""),
                    "input": args,
                }
            )

    stop_reason_map = {
        "stop": "end_turn",
        "tool_calls": "tool_use",
        "length": "max_tokens",
        "content_filter": "end_turn",
    }

    usage = openai_resp.get("usage", {})
    return {
        "id": openai_resp.get("id", f"msg_{uuid.uuid4().hex[:24]}"),
        "type": "message",
        "role": "assistant",
        "content": content,
        "model": model,
        "stop_reason": stop_reason_map.get(finish_reason, "end_turn"),
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }


# --- Streaming Helpers ---


def assemble_streamed_response(chunks):
    """Assemble collected SSE chunks into a complete response object."""
    content = ""
    tool_calls = {}
    finish_reason = "stop"
    model = ""
    resp_id = ""

    for chunk in chunks:
        if not chunk:
            continue
        choices = chunk.get("choices", [])
        if not choices:
            continue
        delta = choices[0].get("delta", {})
        if "content" in delta and delta["content"]:
            content += delta["content"]
        if "tool_calls" in delta:
            for tc in delta["tool_calls"]:
                idx = tc.get("index", 0)
                if idx not in tool_calls:
                    tool_calls[idx] = {
                        "id": tc.get("id", ""),
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    }
                if tc.get("id"):
                    tool_calls[idx]["id"] = tc["id"]
                fn = tc.get("function", {})
                if fn.get("name"):
                    tool_calls[idx]["function"]["name"] = fn["name"]
                if fn.get("arguments"):
                    tool_calls[idx]["function"]["arguments"] += fn["arguments"]
        fr = choices[0].get("finish_reason")
        if fr:
            finish_reason = fr
        if chunk.get("model"):
            model = chunk["model"]
        if chunk.get("id"):
            resp_id = chunk["id"]

    message = {"role": "assistant", "content": content or None}
    if tool_calls:
        message["tool_calls"] = [tool_calls[i] for i in sorted(tool_calls.keys())]

    return {
        "id": resp_id,
        "object": "chat.completion",
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
    }


def convert_openai_stream_chunk_to_anthropic(
    chunk, chunk_index, is_first, is_last, model
):
    """Convert a single OpenAI SSE chunk to Anthropic SSE events."""
    events = []
    if is_first:
        events.append(
            (
                "message_start",
                {
                    "type": "message_start",
                    "message": {
                        "id": chunk.get("id", f"msg_{uuid.uuid4().hex[:24]}"),
                        "type": "message",
                        "role": "assistant",
                        "content": [],
                        "model": model,
                        "stop_reason": None,
                        "usage": {"input_tokens": 0, "output_tokens": 0},
                    },
                },
            )
        )
        events.append(
            (
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "text", "text": ""},
                },
            )
        )

    choices = chunk.get("choices", [])
    if choices:
        delta = choices[0].get("delta", {})
        if delta.get("content"):
            events.append(
                (
                    "content_block_delta",
                    {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {"type": "text_delta", "text": delta["content"]},
                    },
                )
            )
        finish_reason = choices[0].get("finish_reason")
        if finish_reason and is_last:
            stop_reason_map = {
                "stop": "end_turn",
                "tool_calls": "tool_use",
                "length": "max_tokens",
            }
            events.append(
                ("content_block_stop", {"type": "content_block_stop", "index": 0})
            )
            events.append(
                (
                    "message_delta",
                    {
                        "type": "message_delta",
                        "delta": {
                            "stop_reason": stop_reason_map.get(
                                finish_reason, "end_turn"
                            )
                        },
                        "usage": {"output_tokens": 0},
                    },
                )
            )
            events.append(("message_stop", {"type": "message_stop"}))

    return events


# --- Proxy Handlers ---


async def handle_openai_proxy(request):
    """Handle OpenAI format requests - transparent proxy."""
    app = request.app
    db = app["db"]
    body = await request.json()
    session_id = await resolve_session(db, request, body)
    is_stream = body.get("stream", False)
    model = body.get("model", "")
    start_time = time.time()
    timestamp = datetime.now(timezone.utc).isoformat()

    # Forward to backend
    headers = {"Content-Type": "application/json"}
    auth = request.headers.get("Authorization")
    if config.BACKEND_API_KEY:
        headers["Authorization"] = f"Bearer {config.BACKEND_API_KEY}"
    elif auth:
        headers["Authorization"] = auth

    backend_url = f"{config.REMOTE_URL.rstrip('/')}/v1/chat/completions"

    if is_stream:
        return await handle_stream_proxy(
            request,
            db,
            session_id,
            body,
            headers,
            backend_url,
            "openai",
            model,
            timestamp,
            start_time,
            convert_for_client=None,
        )
    else:
        return await handle_non_stream_proxy(
            request,
            db,
            session_id,
            body,
            headers,
            backend_url,
            "openai",
            model,
            timestamp,
            start_time,
            convert_response=None,
        )


async def handle_anthropic_proxy(request):
    """Handle Anthropic format requests - convert and proxy."""
    app = request.app
    db = app["db"]
    body = await request.json()
    session_id = await resolve_session(db, request, body)
    is_stream = body.get("stream", False)
    model = body.get("model", "")
    start_time = time.time()
    timestamp = datetime.now(timezone.utc).isoformat()

    # Convert Anthropic → OpenAI
    openai_body = convert_anthropic_to_openai(body)

    headers = {"Content-Type": "application/json"}
    if config.BACKEND_API_KEY:
        headers["Authorization"] = f"Bearer {config.BACKEND_API_KEY}"

    backend_url = f"{config.REMOTE_URL.rstrip('/')}/v1/chat/completions"

    if is_stream:
        return await handle_stream_proxy(
            request,
            db,
            session_id,
            body,
            headers,
            backend_url,
            "anthropic",
            model,
            timestamp,
            start_time,
            convert_for_client="anthropic",
            forward_body=openai_body,
        )
    else:
        return await handle_non_stream_proxy(
            request,
            db,
            session_id,
            body,
            headers,
            backend_url,
            "anthropic",
            model,
            timestamp,
            start_time,
            convert_response="anthropic",
            forward_body=openai_body,
        )


async def handle_stream_proxy(
    request,
    db,
    session_id,
    original_body,
    headers,
    backend_url,
    client_type,
    model,
    timestamp,
    start_time,
    convert_for_client=None,
    forward_body=None,
):
    """Handle streaming proxy with accumulation."""
    send_body = forward_body or original_body
    chunks = []
    error_msg = None
    status_code = 200

    response = web.StreamResponse()

    if convert_for_client == "anthropic":
        response.content_type = "text/event-stream"
    else:
        response.content_type = "text/event-stream"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                backend_url, json=send_body, headers=headers
            ) as backend_resp:
                status_code = backend_resp.status
                if status_code != 200:
                    error_body = await backend_resp.text()
                    error_msg = error_body
                    response.set_status(status_code)
                    await response.prepare(request)
                    await response.write(error_body.encode())
                    await response.write_eof()
                else:
                    await response.prepare(request)
                    chunk_index = 0
                    async for line in backend_resp.content:
                        line_str = line.decode("utf-8", errors="replace")
                        for single_line in line_str.split("\n"):
                            single_line = single_line.strip()
                            if not single_line:
                                if convert_for_client != "anthropic":
                                    await response.write(b"\n")
                                continue
                            if single_line.startswith("data: "):
                                data_str = single_line[6:]
                                if data_str == "[DONE]":
                                    if convert_for_client == "anthropic":
                                        # Send final events
                                        pass
                                    else:
                                        await response.write(b"data: [DONE]\n\n")
                                    continue
                                try:
                                    chunk_data = json.loads(data_str)
                                    chunks.append(chunk_data)
                                    if convert_for_client == "anthropic":
                                        events = (
                                            convert_openai_stream_chunk_to_anthropic(
                                                chunk_data,
                                                chunk_index,
                                                is_first=(chunk_index == 0),
                                                is_last=bool(
                                                    chunk_data.get("choices", [{}])[
                                                        0
                                                    ].get("finish_reason")
                                                ),
                                                model=model,
                                            )
                                        )
                                        for event_type, event_data in events:
                                            event_line = f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n"
                                            await response.write(event_line.encode())
                                    else:
                                        await response.write(
                                            f"data: {data_str}\n\n".encode()
                                        )
                                    chunk_index += 1
                                except json.JSONDecodeError:
                                    if convert_for_client != "anthropic":
                                        await response.write(
                                            f"{single_line}\n".encode()
                                        )
                            elif convert_for_client != "anthropic":
                                await response.write(f"{single_line}\n".encode())

                    await response.write_eof()
    except Exception as e:
        error_msg = str(e)
    finally:
        # Assemble and log
        duration_ms = int((time.time() - start_time) * 1000)
        assembled = assemble_streamed_response(chunks) if chunks else {}
        request_body_str = json.dumps(original_body, ensure_ascii=False)
        response_body_str = json.dumps(assembled, ensure_ascii=False)

        async with db.execute(
            """INSERT INTO requests (session_id, timestamp, client_type, model, request_body, response_body, status_code, duration_ms, stream, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (
                session_id,
                timestamp,
                client_type,
                model,
                request_body_str,
                response_body_str,
                status_code,
                duration_ms,
                error_msg,
            ),
        ) as cursor:
            request_id = cursor.lastrowid

        await db.commit()

        # Extract media
        media_records = extract_and_save_media(original_body, request_id, "request")
        media_records += extract_and_save_media(assembled, request_id, "response")
        for rec in media_records:
            if rec:
                await db.execute(
                    "INSERT INTO media_files (request_id, role, media_type, mime_type, file_path, message_index, created_at) VALUES (?,?,?,?,?,?,?)",
                    (
                        request_id,
                        rec["role"],
                        rec["media_type"],
                        rec["mime_type"],
                        rec["file_path"],
                        rec["message_index"],
                        timestamp,
                    ),
                )
        await db.commit()

    return response


async def handle_non_stream_proxy(
    request,
    db,
    session_id,
    original_body,
    headers,
    backend_url,
    client_type,
    model,
    timestamp,
    start_time,
    convert_response=None,
    forward_body=None,
):
    """Handle non-streaming proxy."""
    send_body = forward_body or original_body
    error_msg = None

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                backend_url, json=send_body, headers=headers
            ) as backend_resp:
                status_code = backend_resp.status
                resp_text = await backend_resp.text()

                if status_code == 200:
                    resp_data = json.loads(resp_text)
                    if convert_response == "anthropic":
                        client_resp = convert_openai_response_to_anthropic(
                            resp_data, model
                        )
                        final_resp = web.json_response(client_resp)
                    else:
                        final_resp = web.Response(
                            text=resp_text, content_type="application/json"
                        )
                else:
                    error_msg = resp_text
                    final_resp = web.Response(
                        text=resp_text,
                        status=status_code,
                        content_type="application/json",
                    )
                    resp_data = resp_text
    except Exception as e:
        error_msg = str(e)
        resp_data = {"error": error_msg}
        status_code = 502
        final_resp = web.json_response({"error": error_msg}, status=502)

    # Log
    duration_ms = int((time.time() - start_time) * 1000)
    request_body_str = json.dumps(original_body, ensure_ascii=False)
    response_body_str = (
        json.dumps(resp_data, ensure_ascii=False)
        if isinstance(resp_data, dict)
        else resp_data
    )

    async with db.execute(
        """INSERT INTO requests (session_id, timestamp, client_type, model, request_body, response_body, status_code, duration_ms, stream, error)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
        (
            session_id,
            timestamp,
            client_type,
            model,
            request_body_str,
            response_body_str,
            status_code,
            duration_ms,
            error_msg,
        ),
    ) as cursor:
        request_id = cursor.lastrowid
    await db.commit()

    # Extract media
    media_records = extract_and_save_media(original_body, request_id, "request")
    if isinstance(resp_data, dict):
        media_records += extract_and_save_media(resp_data, request_id, "response")
    for rec in media_records:
        if rec:
            await db.execute(
                "INSERT INTO media_files (request_id, role, media_type, mime_type, file_path, message_index, created_at) VALUES (?,?,?,?,?,?,?)",
                (
                    request_id,
                    rec["role"],
                    rec["media_type"],
                    rec["mime_type"],
                    rec["file_path"],
                    rec["message_index"],
                    timestamp,
                ),
            )
    await db.commit()

    return final_resp


# --- Log Viewing API ---


async def api_get_sessions(request):
    db = request.app["db"]
    async with db.execute("""
        SELECT s.id, s.name, s.created_at, s.last_active, COUNT(r.id) as request_count
        FROM sessions s LEFT JOIN requests r ON r.session_id = s.id
        GROUP BY s.id ORDER BY s.last_active DESC
    """) as cursor:
        rows = await cursor.fetchall()
    sessions = [
        {
            "id": r[0],
            "name": r[1],
            "created_at": r[2],
            "last_active": r[3],
            "request_count": r[4],
        }
        for r in rows
    ]
    return web.json_response(sessions)


async def api_get_session_requests(request):
    db = request.app["db"]
    session_id = request.match_info["id"]
    async with db.execute(
        "SELECT id, timestamp, client_type, model, request_body, response_body, status_code, duration_ms, stream, error FROM requests WHERE session_id = ? ORDER BY timestamp",
        (session_id,),
    ) as cursor:
        rows = await cursor.fetchall()
    requests_list = []
    for r in rows:
        requests_list.append(
            {
                "id": r[0],
                "timestamp": r[1],
                "client_type": r[2],
                "model": r[3],
                "request_body": json.loads(r[4]) if r[4] else None,
                "response_body": json.loads(r[5]) if r[5] else None,
                "status_code": r[6],
                "duration_ms": r[7],
                "stream": bool(r[8]),
                "error": r[9],
            }
        )
    return web.json_response(requests_list)


async def api_get_request_detail(request):
    db = request.app["db"]
    req_id = request.match_info["id"]
    async with db.execute(
        "SELECT id, session_id, timestamp, client_type, model, request_body, response_body, status_code, duration_ms, stream, error FROM requests WHERE id = ?",
        (req_id,),
    ) as cursor:
        row = await cursor.fetchone()
    if not row:
        return web.json_response({"error": "not found"}, status=404)

    # Get media
    async with db.execute(
        "SELECT id, role, media_type, mime_type, file_path, message_index FROM media_files WHERE request_id = ?",
        (req_id,),
    ) as cursor:
        media_rows = await cursor.fetchall()

    media = [
        {
            "id": m[0],
            "role": m[1],
            "media_type": m[2],
            "mime_type": m[3],
            "file_path": m[4],
            "message_index": m[5],
        }
        for m in media_rows
    ]

    return web.json_response(
        {
            "id": row[0],
            "session_id": row[1],
            "timestamp": row[2],
            "client_type": row[3],
            "model": row[4],
            "request_body": json.loads(row[5]) if row[5] else None,
            "response_body": json.loads(row[6]) if row[6] else None,
            "status_code": row[7],
            "duration_ms": row[8],
            "stream": bool(row[9]),
            "error": row[10],
            "media": media,
        }
    )


async def api_serve_media(request):
    path = request.match_info["path"]
    filepath = os.path.join(config.MEDIA_DIR, path)
    if not os.path.isfile(filepath):
        return web.Response(status=404, text="Not found")
    return web.FileResponse(filepath)


async def api_delete_session(request):
    db = request.app["db"]
    session_id = request.match_info["id"]
    await db.execute(
        "DELETE FROM media_files WHERE request_id IN (SELECT id FROM requests WHERE session_id = ?)",
        (session_id,),
    )
    await db.execute("DELETE FROM requests WHERE session_id = ?", (session_id,))
    await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    await db.commit()
    return web.json_response({"ok": True})


# --- Static File Serving (SPA) ---


async def handle_static(request):
    """Serve static files with SPA fallback."""
    path = request.match_info.get("path", "")
    if not path:
        path = "index.html"
    filepath = os.path.join(config.STATIC_DIR, path)
    if os.path.isfile(filepath):
        return web.FileResponse(filepath)
    # SPA fallback
    index_path = os.path.join(config.STATIC_DIR, "index.html")
    if os.path.isfile(index_path):
        return web.FileResponse(index_path)
    return web.Response(
        status=404, text="Frontend not built. Run: cd frontend && npm run build"
    )


# --- App Setup ---


async def on_startup(app):
    app["db"] = await init_db()
    print(
        f"LLM Proxy Sniffer running on http://{config.LISTEN_HOST}:{config.LISTEN_PORT}"
    )
    print(f"  Proxy (OpenAI):    POST /v1/chat/completions")
    print(f"  Proxy (Anthropic): POST /v1/messages")
    print(f"  Web UI:            http://localhost:{config.LISTEN_PORT}/")
    print(f"  Backend:           {config.REMOTE_URL}")


async def on_cleanup(app):
    await app["db"].close()


def create_app():
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    # Proxy routes
    app.router.add_post("/v1/chat/completions", handle_openai_proxy)
    app.router.add_post("/v1/messages", handle_anthropic_proxy)

    # Log API routes
    app.router.add_get("/api/sessions", api_get_sessions)
    app.router.add_get("/api/sessions/{id}/requests", api_get_session_requests)
    app.router.add_get("/api/requests/{id}", api_get_request_detail)
    app.router.add_get("/api/media/{path:.*}", api_serve_media)
    app.router.add_delete("/api/sessions/{id}", api_delete_session)

    # Static files (frontend SPA)
    app.router.add_get("/{path:.*}", handle_static)

    return app


if __name__ == "__main__":
    web.run_app(create_app(), host=config.LISTEN_HOST, port=config.LISTEN_PORT)
