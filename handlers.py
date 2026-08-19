import logging
from typing import Dict, Any, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from config import settings
import railway_api as api
import utils

logger = logging.getLogger(__name__)

# Conversation states
TRAIN, DATE, DESTINATION, CHECKING = range(4)

# Keyboards
START_KEYBOARD = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("🔍 Check Availability", callback_data="check")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")],
    ]
)

RESULT_KEYBOARD = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("🔄 Check Again", callback_data="check")],
        [InlineKeyboardButton("🏠 Home", callback_data="home")],
    ]
)

CANCEL_KEYBOARD = InlineKeyboardMarkup(
    [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "🚆 <b>Train Seat Availability Checker</b>\n"
        "Choose an option:",
        parse_mode="HTML",
        reply_markup=START_KEYBOARD,
    )
    return ConversationHandler.END

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (
        "<b>How to use:</b>\n"
        "1️⃣ Press <b>Check Availability</b>.\n"
        "2️⃣ Enter <b>train number</b> (e.g. 12565).\n"
        "3️⃣ Enter <b>journey date</b> DD-MM-YYYY (e.g. 25-08-2026).\n"
        "4️⃣ Enter <b>destination</b> (station code NDLS or name New Delhi).\n"
        "5️⃣ Bot will fetch the train route, find every station before the destination,\n"
        "   and check seat availability for each boarding station → destination.\n"
        "6️⃣ Results are grouped by boarding station with the best option highlighted.\n\n"
        "Use /cancel anytime to abort."
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=START_KEYBOARD)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=START_KEYBOARD)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.edit_message_text("🚫 Operation cancelled.", reply_markup=START_KEYBOARD)
    else:
        await update.message.reply_text("🚫 Operation cancelled.", reply_markup=START_KEYBOARD)
    context.user_data.clear()
    return ConversationHandler.END

# ----- Conversation steps -----
async def check_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔢 Please enter the <b>train number</b> (e.g. 12565):",
        parse_mode="HTML",
        reply_markup=CANCEL_KEYBOARD,
    )
    return TRAIN

async def train_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    train_no = update.message.text.strip()
    if not train_no.isdigit():
        await update.message.reply_text("❌ Train number must be numeric. Try again:")
        return TRAIN
    context.user_data["train"] = train_no
    logger.info("User %s requested train %s", update.effective_user.id, train_no)
    await update.message.reply_text(
        "📅 Enter <b>journey date</b> in DD-MM-YYYY format (e.g. 25-08-2026):",
        parse_mode="HTML",
        reply_markup=CANCEL_KEYBOARD,
    )
    return DATE

async def date_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    date_str = update.message.text.strip()
    # simple validation
    parts = date_str.split("-")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        await update.message.reply_text("❌ Invalid date format. Use DD-MM-YYYY.")
        return DATE
    context.user_data["date"] = date_str
    await update.message.reply_text(
        "🎯 Enter <b>destination station</b> (code like NDLS or name like New Delhi):",
        parse_mode="HTML",
        reply_markup=CANCEL_KEYBOARD,
    )
    return DESTINATION

async def destination_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    dest_query = update.message.text.strip()
    context.user_data["dest_query"] = dest_query
    await update.message.reply_text(
        "🔍 <b>Fetching train route and checking availability…</b>",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    # Start checking in background, but we can do sequentially here
    return await perform_check(update, context)

async def perform_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    train_no = context.user_data["train"]
    journey_date = context.user_data["date"]
    dest_query = context.user_data["dest_query"]
    chat_id = update.effective_chat.id

    # Progress message
    progress_msg = await context.bot.send_message(
        chat_id,
        "🔍 Checking seat availability...\n"
        f"Train: {train_no}\nDate: {journey_date}\nDestination: {dest_query}\nStations checked: 0/0",
        parse_mode="HTML",
    )

    try:
        # 1. Get train route
        route = await api.fetch_train_route(train_no)
        # 2. Resolve destination
        dest_info = await api.resolve_station(dest_query)
        dest_code = dest_info["code"]
        dest_name = dest_info["name"]

        # Find destination index in route
        dest_index = next((i for i, s in enumerate(route) if s["station"]["code"] == dest_code), None)
        if dest_index is None:
            await progress_msg.edit_text(
                f"❌ Destination <b>{dest_name} ({dest_code})</b> not found on this train's route.",
                parse_mode="HTML",
                reply_markup=RESULT_KEYBOARD,
            )
            return ConversationHandler.END

        boarding_stations = route[:dest_index]  # all before destination
        total = len(boarding_stations)
        results = []

        # Supported classes - we will query only those present in train (simplify: query all)
        classes_to_check = utils.CLASS_ORDER

        for idx, station in enumerate(boarding_stations, 1):
            src_code = station["station"]["code"]
            src_name = station["station"]["name"]
            await progress_msg.edit_text(
                f"🔍 Checking seat availability...\n"
                f"Train: {train_no}\nDate: {journey_date}\nDestination: {dest_name} ({dest_code})\n"
                f"Stations checked: {idx}/{total}",
                parse_mode="HTML",
            )
            class_results = {}
            for cls in classes_to_check:
                try:
                    raw = await api.check_availability(
                        train_no, src_code, dest_code, journey_date, cls, settings.DEFAULT_QUOTA
                    )
                    parsed = utils.parse_availability(raw)
                    if parsed["status"] != "REGRET":
                        class_results[cls] = parsed
                except api.RailwayAPIError as e:
                    logger.warning("Availability error %s->%s %s: %s", src_code, dest_code, cls, e)
                    continue
            if class_results:
                results.append(
                    {
                        "boarding_code": src_code,
                        "boarding_name": src_name,
                        "dest_code": dest_code,
                        "dest_name": dest_name,
                        "classes": class_results,
                    }
                )

        # Sort results: best boarding station first based on best class rank
        results.sort(key=lambda r: min(utils.rank_availability(av) for av in r["classes"].values()))

        best = utils.find_best_option(results)

        # Build final message
        lines = [
            f"🚆 <b>Train:</b> {train_no}",
            f"📅 <b>Journey:</b> {journey_date}",
            f"🎯 <b>Destination:</b> {dest_name} ({dest_code})",
            "",
            "🔍 <b>Availability:</b>",
        ]

        for r in results:
            status_icon = "🟢" if any(av["status"] == "AVAILABLE" for av in r["classes"].values()) else "❌"
            lines.append(f"{status_icon} <b>{r['boarding_name']} ({r['boarding_code']}) → {dest_name} ({dest_code})</b>")
            for cls in utils.CLASS_ORDER:
                if cls in r["classes"]:
                    lines.append(f"   {utils.format_class_result(cls, r['classes'][cls])}")
            lines.append("")

        if best:
            lines.append("⭐ <b>BEST AVAILABLE OPTION</b>")
            lines.append(f"Boarding: {best['boarding_name']} ({best['boarding_code']})")
            lines.append(f"Destination: {best['dest_name']} ({best['dest_code']})")
            for cls in utils.CLASS_ORDER:
                if cls in best["classes"]:
                    lines.append(f"   {utils.format_class_result(cls, best['classes'][cls])}")
        else:
            lines.append("❌ No confirmed availability found from any boarding station to this destination.")
            lines.append("You may check another date or class.")

        final_text = "\n".join(lines)
        await progress_msg.edit_text(final_text, parse_mode="HTML", reply_markup=RESULT_KEYBOARD)

    except api.TrainNotFoundError:
        await progress_msg.edit_text("❌ Train not found. Please check the train number and try again.", reply_markup=RESULT_KEYBOARD)
    except api.StationNotFoundError:
        await progress_msg.edit_text("❌ Destination station not found. Please verify the code/name.", reply_markup=RESULT_KEYBOARD)
    except api.RailwayAPIError as e:
        logger.exception("Railway API error")
        await progress_msg.edit_text("⚠️ Railway availability service is temporarily unavailable. Please try again later.", reply_markup=RESULT_KEYBOARD)
    except Exception:
        logger.exception("Unexpected error during availability check")
        await progress_msg.edit_text("⚠️ An unexpected error occurred. Please try again.", reply_markup=RESULT_KEYBOARD)

    return ConversationHandler.END

# ----- Handlers registration -----
def build_application() -> Application:
    application = Application.builder().token(settings.BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(check_start, pattern="^check$"),
            CommandHandler("start", start),
        ],
        states={
            TRAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, train_received)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, date_received)],
            DESTINATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, destination_received)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern="^cancel$"),
            CallbackQueryHandler(start, pattern="^home$"),
            CallbackQueryHandler(help_cmd, pattern="^help$"),
        ],
        allow_reentry=True,
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CallbackQueryHandler(help_cmd, pattern="^help$"))
    application.add_handler(CallbackQueryHandler(start, pattern="^home$"))

    return application