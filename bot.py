
"""
OTT Downloader Telegram Bot

Commands:
  /start      - Welcome message
  /help       - Show all commands
  /rip        - Select a title: /rip <platform> <url> [quality]
  /status     - Check active downloads
  /cancel     - Cancel a download
  /platforms  - List supported platforms
"""

import os
import asyncio
import subprocess
import uuid
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

from dotenv import load_dotenv

load_dotenv()

# ── Configuration ──────────────────────────────────────────────────────────

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

ALLOWED_IDS = (
    set(map(int, os.getenv("ALLOWED_USER_IDS", "").split(",")))
    if os.getenv("ALLOWED_USER_IDS")
    else set()
)

# Active downloads
active_downloads: dict[str, dict] = {}

# Pending quality selections
pending_downloads: dict[str, dict] = {}

PLATFORMS = {
    "global": [
        "netflix", "prime", "disney", "hbomax",
        "hulu", "apple", "peacock", "paramount"
    ],

    "indian": [
        "jiocinema", "hotstar", "sonyliv", "zee5",
        "altbalaji", "erosnow", "manoramamax", "hoichoi"
    ],

    "regional": [
        "aha", "mxplayer", "voot", "shemaroo",
        "sun_nxt", "yupp_tv", "stage"
    ],
}

ALL_PLATFORMS = [
    platform
    for group in PLATFORMS.values()
    for platform in group
]

QUALITIES = ["4K", "1080p", "720p", "480p"]


# ── Authentication ─────────────────────────────────────────────────────────

def is_allowed(user_id: int) -> bool:
    return not ALLOWED_IDS or user_id in ALLOWED_IDS


# ── /start ──────────────────────────────────────────────────────────────────

async def start(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE
):

    if not is_allowed(update.effective_user.id):
        await update.message.reply_text(
            "⛔ You are not authorised to use this bot."
        )
        return

    text = (
        "🎬 *OTT Downloader Bot*\n\n"
        "Download from supported platforms using your configured scripts.\n\n"

        "*Quick commands:*\n"
        "`/rip <platform> <url>` — Start a download\n"
        "`/rip <platform> <url> 4K` — Select 4K\n"
        "`/status` — View active downloads\n"
        "`/platforms` — List supported platforms\n"
        "`/help` — Full help\n\n"

        "*Example:*\n"
        "`/rip jiocinema https://jiocinema.com/... 4K`"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# ── /help ───────────────────────────────────────────────────────────────────

async def help_cmd(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE
):

    if not is_allowed(update.effective_user.id):
        return

    text = (
        "📖 *Full Command Reference*\n\n"

        "*Download:*\n"
        "`/rip <platform> <url> [quality] [type]`\n"

        "platform → jiocinema, netflix, aha, etc.\n"
        "quality → 4K, 1080p, 720p, 480p\n"
        "type → movies, shows, anime, documentaries\n\n"

        "*Examples:*\n"
        "`/rip jiocinema https://... 4K movies`\n"
        "`/rip netflix https://... 1080p shows`\n"
        "`/rip aha https://... 720p`\n\n"

        "*Other commands:*\n"
        "`/status` — Active downloads\n"
        "`/cancel <job_id>` — Cancel a download\n"
        "`/platforms` — Supported platforms"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# ── /platforms ──────────────────────────────────────────────────────────────

async def platforms_cmd(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE
):

    if not is_allowed(update.effective_user.id):
        return

    text = (
        "📡 *Supported Platforms*\n\n"

        "🌍 *Global*\n"
        f"`{'` · `'.join(PLATFORMS['global'])}`\n\n"

        "🇮🇳 *Indian*\n"
        f"`{'` · `'.join(PLATFORMS['indian'])}`\n\n"

        "🗺️ *Regional*\n"
        f"`{'` · `'.join(PLATFORMS['regional'])}`"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# ── /rip ────────────────────────────────────────────────────────────────────

async def rip_cmd(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE
):

    if not is_allowed(update.effective_user.id):
        await update.message.reply_text(
            "⛔ Not authorised."
        )
        return

    args = ctx.args

    if len(args) < 2:
        await update.message.reply_text(
            "❌ *Usage:*\n"
            "`/rip <platform> <url> [quality] [type]`\n\n"
            "Example:\n"
            "`/rip jiocinema https://... 4K movies`",
            parse_mode="Markdown"
        )
        return

    platform = args[0].lower()
    url = args[1]

    quality = (
        args[2].upper()
        if len(args) > 2 and args[2].upper() in QUALITIES
        else "1080p"
    )

    ctype = (
        args[3].lower()
        if len(args) > 3
        else "movies"
    )

    if platform not in ALL_PLATFORMS:
        await update.message.reply_text(
            f"❌ Unknown platform `{platform}`.\n"
            "Use /platforms to see supported platforms.",
            parse_mode="Markdown"
        )
        return

    # Quality selection
    if len(args) < 3:

        keyboard = []

        for q in QUALITIES:

            # Generate a short unique token
            token = uuid.uuid4().hex[:16]

            # Store the actual download information
            pending_downloads[token] = {
                "platform": platform,
                "url": url,
                "quality": q,
                "ctype": ctype,
                "user_id": update.effective_user.id
            }

            # Only send the short token to Telegram
            keyboard.append([
                InlineKeyboardButton(
                    q,
                    callback_data=f"quality:{token}"
                )
            ])

        await update.message.reply_text(
            f"🎬 Choose quality for *{platform}*:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

        return

    await start_download(
        update,
        platform,
        url,
        quality,
        ctype
    )


# ── Quality Button Callback ─────────────────────────────────────────────────

async def button_callback(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if not is_allowed(query.from_user.id):
        await query.answer(
            "Not authorised.",
            show_alert=True
        )
        return

    data = query.data or ""

    if not data.startswith("quality:"):
        await query.answer(
            "Invalid button.",
            show_alert=True
        )
        return

    token = data.split(":", 1)[1]

    download = pending_downloads.get(token)

    if not download:
        await query.answer(
            "Selection expired. Please try again.",
            show_alert=True
        )
        return

    if download["user_id"] != query.from_user.id:
        await query.answer(
            "This selection belongs to another user.",
            show_alert=True
        )
        return

    # Remove used selection
    pending_downloads.pop(token, None)

    await query.answer()

    await query.edit_message_text(
        f"⏳ Starting {download['quality']} selection for "
        f"*{download['platform']}*...",
        parse_mode="Markdown"
    )

    await start_download(
        query,
        download["platform"],
        download["url"],
        download["quality"],
        download["ctype"],
        from_callback=True
    )


# ── Core Download Function ──────────────────────────────────────────────────

async def start_download(
    update,
    platform: str,
    url: str,
    quality: str,
    ctype: str,
    from_callback=False
):

    job_id = str(uuid.uuid4())[:8]

    started = datetime.now().strftime("%H:%M:%S")

    active_downloads[job_id] = {
        "platform": platform,
        "url": url,
        "quality": quality,
        "type": ctype,
        "status": "running",
        "started": started,
        "process": None
    }

    msg_fn = (
        update.message.reply_text
        if not from_callback
        else update.edit_message_text
    )

    status_msg = await msg_fn(
        f"⬇️ *Download started!*\n\n"

        f"🆔 Job ID: `{job_id}`\n"
        f"📡 Platform: `{platform}`\n"
        f"🎯 Quality: `{quality}`\n"
        f"📁 Type: `{ctype}`\n"
        f"🕐 Started: `{started}`\n\n"

        f"Use `/status` to check progress.\n"
        f"Use `/cancel {job_id}` to stop.",
        parse_mode="Markdown"
    )

    asyncio.create_task(
        run_download(
            job_id,
            platform,
            url,
            quality,
            ctype,
            status_msg
        )
    )


# ── Platform Folder ─────────────────────────────────────────────────────────

def _platform_folder(platform: str) -> str:

    if platform in PLATFORMS["global"]:
        return "global"

    if platform in PLATFORMS["indian"]:
        return "indian"

    if platform in PLATFORMS["regional"]:
        return "regional"

    return "global"


# ── Background Process ───────────────────────────────────────────────────────

async def run_download(
    job_id,
    platform,
    url,
    quality,
    ctype,
    status_msg
):

    # This invokes your locally configured platform script.
    # Ensure the script is authorized to access and process the content.

    script = (
        f"scripts/{_platform_folder(platform)}/{platform}.py"
    )

    cmd = [
        "python",
        script,
        "--url", url,
        "--quality", quality,
        "--type", ctype
    ]

    try:

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        active_downloads[job_id]["process"] = proc

        stdout, stderr = await proc.communicate()

        if proc.returncode == 0:

            active_downloads[job_id]["status"] = "done"

            await status_msg.reply_text(
                f"✅ *Download complete!*\n"
                f"🆔 Job `{job_id}` finished successfully.",
                parse_mode="Markdown"
            )

        else:

            active_downloads[job_id]["status"] = "failed"

            err = (
                stderr.decode(errors="replace")[-300:]
                if stderr
                else "Unknown error"
            )

            await status_msg.reply_text(
                f"❌ *Download failed!*\n"
                f"🆔 Job `{job_id}`\n\n"
                f"Error:\n`{err}`",
                parse_mode="Markdown"
            )

    except Exception as e:

        active_downloads[job_id]["status"] = "error"

        await status_msg.reply_text(
            f"💥 *Unexpected error* in job `{job_id}`:\n"
            f"`{str(e)[:250]}`",
            parse_mode="Markdown"
        )


# ── /status ─────────────────────────────────────────────────────────────────

async def status_cmd(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE
):

    if not is_allowed(update.effective_user.id):
        return

    if not active_downloads:
        await update.message.reply_text(
            "📭 No downloads yet. Use `/rip` to start one.",
            parse_mode="Markdown"
        )
        return

    lines = ["📊 *Download Status*\n"]

    icons = {
        "running": "⬇️",
        "done": "✅",
        "failed": "❌",
        "error": "💥",
        "cancelled": "🚫"
    }

    for jid, info in list(active_downloads.items())[-10:]:

        icon = icons.get(
            info["status"],
            "❓"
        )

        lines.append(
            f"{icon} `{jid}` — *{info['platform']}* "
            f"{info['quality']}\n"
            f"   Status: `{info['status']}` · "
            f"Started: `{info['started']}`"
        )

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown"
    )


# ── /cancel ─────────────────────────────────────────────────────────────────

async def cancel_cmd(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE
):

    if not is_allowed(update.effective_user.id):
        return

    if not ctx.args:
        await update.message.reply_text(
            "Usage: `/cancel <job_id>`",
            parse_mode="Markdown"
        )
        return

    job_id = ctx.args[0]

    if job_id not in active_downloads:
        await update.message.reply_text(
            f"❌ Job `{job_id}` not found.",
            parse_mode="Markdown"
        )
        return

    info = active_downloads[job_id]

    if info["status"] != "running":
        await update.message.reply_text(
            f"Job `{job_id}` is not running.",
            parse_mode="Markdown"
        )
        return

    proc = info.get("process")

    if proc and proc.returncode is None:
        proc.terminate()

    info["status"] = "cancelled"

    await update.message.reply_text(
        f"🚫 Job `{job_id}` cancelled.",
        parse_mode="Markdown"
    )


# ── Main ─────────────────────────────────────────────────────────────────────

def main():

    if not TOKEN:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN not set in environment!"
        )

    app = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("help", help_cmd)
    )

    app.add_handler(
        CommandHandler("platforms", platforms_cmd)
    )

    app.add_handler(
        CommandHandler("rip", rip_cmd)
    )

    app.add_handler(
        CommandHandler("status", status_cmd)
    )

    app.add_handler(
        CommandHandler("cancel", cancel_cmd)
    )

    app.add_handler(
        CallbackQueryHandler(button_callback)
    )

    print("🤖 OTT Bot is running...")

    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
