import os
import logging
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update, Bot
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ── Logging ──────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Configuration from Environment ───────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
SUPPORT_GROUP_ID = os.getenv("SUPPORT_GROUP_ID", "").strip()
ADMIN_IDS = os.getenv("ADMIN_IDS", "").strip()
SUPPORT_MEMBER_IDS = os.getenv("SUPPORT_MEMBER_IDS", "").strip()
PORT = int(os.getenv("PORT", "10000"))

# Parse IDs
support_group_id = int(SUPPORT_GROUP_ID) if SUPPORT_GROUP_ID else None
admin_ids = set(int(x.strip()) for x in ADMIN_IDS.split(",") if x.strip())
support_member_ids = set(int(x.strip()) for x in SUPPORT_MEMBER_IDS.split(",") if x.strip())

# ── Temporary In-Memory Mapping ──────────────────────────
# Maps: Group Message ID -> Original User Chat ID
group_to_user = {}

# ── Health Check Server (for Render Web Service) ─────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive")

    def log_message(self, format, *args):
        # Silence default HTTP logs
        pass


def start_health_server():
    """Start a simple HTTP server so Render detects an open port."""
    try:
        server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
        logger.info(f"✅ Health server listening on port {PORT}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Health server error: {e}")


# ── Helper Functions ─────────────────────────────────────
def get_user_info(user) -> str:
    name = user.full_name or "Unknown"
    username = f"@{user.username}" if user.username else "Not Available"
    user_id = user.id
    return (
        f"👤 New User Message\n\n"
        f"Name: {name}\n"
        f"Username: {username}\n"
        f"ID: {user_id}\n\n"
    )


async def startup_checks(application: Application):
    """Run startup validation checks."""
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN is not set!")
        sys.exit(1)
    if not support_group_id:
        logger.error("❌ SUPPORT_GROUP_ID is not set!")
        sys.exit(1)
    if not admin_ids:
        logger.warning("⚠️ ADMIN_IDS is empty. No admin commands will work.")
    if not support_member_ids:
        logger.warning("⚠️ SUPPORT_MEMBER_IDS is empty. No replies will be forwarded.")

    try:
        bot: Bot = application.bot
        me = await bot.get_me()
        logger.info(f"✅ Bot connected: @{me.username} (ID: {me.id})")

        # Check if bot is in the group and is admin
        try:
            chat_member = await bot.get_chat_member(support_group_id, me.id)
            if chat_member.status not in ("administrator", "creator"):
                logger.error(f"❌ Bot is not an administrator in group {support_group_id}")
                sys.exit(1)
            logger.info(f"✅ Bot is administrator in support group {support_group_id}")
        except Exception as e:
            logger.error(f"❌ Cannot verify bot membership in group {support_group_id}: {e}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Startup error: {e}")
        sys.exit(1)


# ── Command Handlers ─────────────────────────────────────
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command for users."""
    user = update.effective_user
    if user.id in admin_ids:
        await update.message.reply_text(
            "👋 Welcome, Admin!\n\n"
            "Commands:\n"
            "/start - This message\n"
            "/status - Bot status"
        )
    else:
        welcome_text = (
            "✨ WELCOME TO TEAM TOXIC SUPPORT 🤍🔥\n\n"
            "👋 Welcome to Team TOXIC Support!\n"
            "अगर आपको किसी भी Batch / Lecture / PDF / DPP / Class Notes से जुड़ी कोई समस्या है, "
            "तो बेझिझक हमें बताएं। 📚💬\n\n"
            "📌 अगर किसी Batch में:\n"
            "❌ Lecture Upload नहीं हुआ है\n"
            "❌ PDF / Notes Available नहीं हैं\n"
            "❌ DPP Upload नहीं हुई है\n"
            "❌ Class Notes Missing हैं\n"
            "❌ या कोई भी Technical / Content Problem है\n\n"
            "👉 बस अपनी Problem Clearly बताएं और अगर possible हो तो Batch का नाम + Chapter/Lecture भी mention करें। 📝\n\n"
            "⏳ Team आपकी समस्या को जल्द से जल्द check करके reply करेगी।\n"
            "🙏 थोड़ा patience रखें, Team हर query का जवाब देने की पूरी कोशिश करेगी। ❤️‍🔥\n\n"
            "🚀 TEAM TOXIC SUPPORT — WE’RE HERE TO HELP! 🤍"
        )
        await update.message.reply_text(welcome_text)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command (admin only)."""
    user = update.effective_user
    if user.id not in admin_ids:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    status_text = (
        f"📊 Bot Status\n\n"
        f"Bot: Online\n"
        f"Group: {'Configured' if support_group_id else 'Not Configured'}\n"
        f"Support Members: {len(support_member_ids)}\n"
        f"Database: Not Used\n"
        f"Active Mappings: {len(group_to_user)}"
    )
    await update.message.reply_text(status_text)


# ── User → Group Relay ───────────────────────────────────
async def relay_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Forward user messages to the support group."""
    if not support_group_id:
        logger.error("SUPPORT_GROUP_ID not configured")
        return

    user = update.effective_user
    message = update.effective_message

    # Build user info header
    header = get_user_info(user)

    try:
        sent_message = None

        # Try to copy the message with a caption/header
        if message.text:
            sent_message = await context.bot.send_message(
                chat_id=support_group_id,
                text=header + message.text,
            )
        elif message.photo:
            caption = (message.caption or "") + "\n\n" + header if message.caption else header
            sent_message = await context.bot.send_photo(
                chat_id=support_group_id,
                photo=message.photo[-1].file_id,
                caption=caption,
            )
        elif message.video:
            caption = (message.caption or "") + "\n\n" + header if message.caption else header
            sent_message = await context.bot.send_video(
                chat_id=support_group_id,
                video=message.video.file_id,
                caption=caption,
            )
        elif message.document:
            caption = (message.caption or "") + "\n\n" + header if message.caption else header
            sent_message = await context.bot.send_document(
                chat_id=support_group_id,
                document=message.document.file_id,
                caption=caption,
            )
        elif message.audio:
            caption = (message.caption or "") + "\n\n" + header if message.caption else header
            sent_message = await context.bot.send_audio(
                chat_id=support_group_id,
                audio=message.audio.file_id,
                caption=caption,
            )
        elif message.voice:
            caption = header
            sent_message = await context.bot.send_voice(
                chat_id=support_group_id,
                voice=message.voice.file_id,
                caption=caption,
            )
        elif message.video_note:
            # Video notes don't support captions, send header separately then video note
            header_msg = await context.bot.send_message(
                chat_id=support_group_id,
                text=header,
            )
            sent_message = await context.bot.send_video_note(
                chat_id=support_group_id,
                video_note=message.video_note.file_id,
            )
            # Map the video note message
            if sent_message:
                group_to_user[sent_message.message_id] = user.id
            # Also map header for reply purposes
            group_to_user[header_msg.message_id] = user.id
            return
        elif message.sticker:
            # Send header first, then sticker
            header_msg = await context.bot.send_message(
                chat_id=support_group_id,
                text=header,
            )
            sent_message = await context.bot.send_sticker(
                chat_id=support_group_id,
                sticker=message.sticker.file_id,
            )
            if sent_message:
                group_to_user[sent_message.message_id] = user.id
            group_to_user[header_msg.message_id] = user.id
            return
        elif message.animation:
            caption = (message.caption or "") + "\n\n" + header if message.caption else header
            sent_message = await context.bot.send_animation(
                chat_id=support_group_id,
                animation=message.animation.file_id,
                caption=caption,
            )
        elif message.contact:
            contact_info = (
                f"{header}"
                f"📞 Contact:\n"
                f"Name: {message.contact.first_name} {message.contact.last_name or ''}\n"
                f"Phone: {message.contact.phone_number}"
            )
            sent_message = await context.bot.send_message(
                chat_id=support_group_id,
                text=contact_info,
            )
        elif message.location:
            loc_info = (
                f"{header}"
                f"📍 Location:\n"
                f"Latitude: {message.location.latitude}\n"
                f"Longitude: {message.location.longitude}"
            )
            sent_message = await context.bot.send_message(
                chat_id=support_group_id,
                text=loc_info,
            )
        elif message.poll:
            poll_info = (
                f"{header}"
                f"📊 Poll: {message.poll.question}\n"
                f"Options: {', '.join([opt.text for opt in message.poll.options])}"
            )
            sent_message = await context.bot.send_message(
                chat_id=support_group_id,
                text=poll_info,
            )
        else:
            # Fallback for unsupported types
            fallback = (
                f"{header}"
                f"⚠️ Unsupported message type received from user."
            )
            sent_message = await context.bot.send_message(
                chat_id=support_group_id,
                text=fallback,
            )

        # Store mapping: Group Message ID -> User Chat ID
        if sent_message:
            group_to_user[sent_message.message_id] = user.id
            logger.info(f"Mapped group_msg_id={sent_message.message_id} -> user_chat_id={user.id}")

    except Exception as e:
        logger.error(f"Error relaying user message: {e}")
        try:
            await update.message.reply_text(
                "❌ Sorry, we couldn't forward your message. Please try again later."
            )
        except Exception:
            pass


# ── Group → User Reply Relay ─────────────────────────────
async def relay_support_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Forward support team replies back to the original user."""
    message = update.effective_message
    user = update.effective_user

    # Ignore bot's own messages
    if user and user.id == context.bot.id:
        return

    # Only process replies from configured support members
    if user.id not in support_member_ids:
        return

    # Must be a reply to a message
    if not message.reply_to_message:
        return

    replied_msg_id = message.reply_to_message.message_id

    # Look up the original user
    original_user_id = group_to_user.get(replied_msg_id)
    if not original_user_id:
        logger.warning(f"No mapping found for group message {replied_msg_id}")
        return

    try:
        # Forward the reply back to the user
        if message.text:
            await context.bot.send_message(
                chat_id=original_user_id,
                text=message.text,
            )
        elif message.photo:
            await context.bot.send_photo(
                chat_id=original_user_id,
                photo=message.photo[-1].file_id,
                caption=message.caption,
            )
        elif message.video:
            await context.bot.send_video(
                chat_id=original_user_id,
                video=message.video.file_id,
                caption=message.caption,
            )
        elif message.document:
            await context.bot.send_document(
                chat_id=original_user_id,
                document=message.document.file_id,
                caption=message.caption,
            )
        elif message.audio:
            await context.bot.send_audio(
                chat_id=original_user_id,
                audio=message.audio.file_id,
                caption=message.caption,
            )
        elif message.voice:
            await context.bot.send_voice(
                chat_id=original_user_id,
                voice=message.voice.file_id,
                caption=message.caption,
            )
        elif message.video_note:
            await context.bot.send_video_note(
                chat_id=original_user_id,
                video_note=message.video_note.file_id,
            )
        elif message.sticker:
            await context.bot.send_sticker(
                chat_id=original_user_id,
                sticker=message.sticker.file_id,
            )
        elif message.animation:
            await context.bot.send_animation(
                chat_id=original_user_id,
                animation=message.animation.file_id,
                caption=message.caption,
            )
        elif message.contact:
            await context.bot.send_contact(
                chat_id=original_user_id,
                phone_number=message.contact.phone_number,
                first_name=message.contact.first_name,
                last_name=message.contact.last_name,
            )
        elif message.location:
            await context.bot.send_location(
                chat_id=original_user_id,
                latitude=message.location.latitude,
                longitude=message.location.longitude,
            )
        else:
            await context.bot.send_message(
                chat_id=original_user_id,
                text="⚠️ The support team sent a message type that couldn't be forwarded.",
            )

        logger.info(f"Relayed reply from support member {user.id} to user {original_user_id}")

    except Exception as e:
        logger.error(f"Error relaying support reply to user {original_user_id}: {e}")


# ── Error Handler ────────────────────────────────────────
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors gracefully."""
    logger.error(f"Update {update} caused error: {context.error}")


# ── Main ─────────────────────────────────────────────────
def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable is required!")
        sys.exit(1)

    # Python 3.14+ compatibility: ensure an event loop exists
    try:
        import asyncio
        asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Start health server in background thread (needed for Render Web Service)
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()

    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(startup_checks)
        .build()
    )

    # Commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))

    # User messages → Group (private chats only, exclude bot itself)
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & ~filters.COMMAND & ~filters.UpdateType.EDITED_MESSAGE,
            relay_user_message,
        )
    )

    # Support replies → User (group chats only, replies only)
    application.add_handler(
        MessageHandler(
            filters.Chat(support_group_id)
            & filters.REPLY
            & ~filters.COMMAND
            & ~filters.UpdateType.EDITED_MESSAGE,
            relay_support_reply,
        )
    )

    # Error handler
    application.add_error_handler(error_handler)

    logger.info("🚀 Starting Telegram Support Relay Bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
